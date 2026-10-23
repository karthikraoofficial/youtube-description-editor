"""The Run engine: the only code allowed to write to YouTube (CLAUDE.md hard rule).

For every Run:
1. Fetch every target Video fresh, and save each live snippet as the Backup, in the database and a
   JSON file, before the first write (ADR-0002).
2. Skip Videos whose live Field no longer matches what the owner reviewed (Stale, ADR-0003); one
   that already reads exactly like the target isn't written again (ADR-0014).
3. Re-validate each target; never send a blocked value.
4. Send the fresh snippet's writable fields back unchanged, with only the Run's Field replaced (ADR-0022),
   retrying temporary YouTube errors with backoff (ADR-0014).
5. Record each Video's outcome as it happens; one Video failing never stops the others.
The browser drives a Run in Steps, each holding the Run's lease (ADR-0017). A Run that stops early (quota,
sign-in, nobody driving it any more) continues only through resume() (ADR-0007).
"""
import json
import logging
import random
import time
import uuid
from collections.abc import Callable
from time import sleep  # module-level so tests can replace it
from typing import Literal

from pydantic import TypeAdapter

from app.backups import BackupArchive, BackupArchiveError
from app.connection import Connection, NotConnected
from app.domain import fields
from app.domain.fields import FieldName
from app.domain.operations import Operation, summarize
from app.domain.validation import is_blocked
from app.quota import UPDATE_UNITS, QuotaLedger
from app.store.db import Store, utc_now
from app.youtube.errors import AuthExpired, GatewayError, QuotaExceeded, RetryableError
from app.youtube.gateway import FreshSnippet

_OPERATION = TypeAdapter(Operation)

BATCH = 50
MAX_ATTEMPTS = 5  # per request: the first try plus 4 retries
BASE_BACKOFF_S = 1.0  # 1, 2, 4, 8 s (+ up to 0.5 s jitter)
STEP_BUDGET_S = 40.0  # a Step starts no new Video after this, well inside a serverless function's time limit
LEASE_S = 120  # a Run no Step has renewed for this long is no longer being driven (ADR-0017)
RESUMABLE = ("paused", "paused_quota", "interrupted")
ACTIVE = ("pending", "running")
# The one rule for "this Video can be restored from this Run": the Run wrote it, and backed it up first.
RESTORABLE_ITEM = "status = 'success' AND backup_snippet_json IS NOT NULL"
Control = Literal["pause", "cancel"]
CONTROLS: dict[str, str] = {"pause": "paused", "cancel": "cancelled"}
PAUSED_MESSAGE = "Paused by you. The remaining videos are still queued."
CANCELLED_MESSAGE = "Cancelled by you. Videos already written stay written."
ABANDONED_MESSAGE = ("Stopped: no window was running this run any more (it was closed, or the computer slept). "
                     "The remaining videos are still queued.")
DRIVEN_ELSEWHERE = ("Another tab or window is running this run. Watch it there, or close it and wait two minutes "
                    "before resuming here.")
# The snippet fields videos.update accepts; everything else in a fetched snippet is read-only.
WRITABLE_FIELDS = ("title", "description", "categoryId", "tags", "defaultLanguage", "defaultAudioLanguage")

log = logging.getLogger(__name__)


class RunConflict(Exception):
    """The request can't be honoured in the current state. The message is user-facing."""


class RunNotFound(Exception):
    pass


class RunInvalid(Exception):
    """The request names something that can't be done (e.g. restoring a Video the Run never wrote)."""


class _GaveUp(Exception):
    """Retries ran out for a temporary failure."""

    def __init__(self, error: RetryableError, attempts: int) -> None:
        super().__init__(str(error))
        self.error = error
        self.attempts = attempts


def update_body(fresh_snippet: dict, value: str, field: FieldName = "description") -> dict:
    """The fresh snippet's writable fields, unchanged, with only the Field replaced (ADR-0002, ADR-0022)."""
    body = {k: fresh_snippet[k] for k in WRITABLE_FIELDS if fresh_snippet.get(k) not in (None, [], "")}
    spec = fields.spec(field)
    snippet_value = spec.to_snippet(value)
    if snippet_value is None:
        body.pop(spec.snippet_key, None)
    else:
        body[spec.snippet_key] = snippet_value
    return body


class Runs:
    def __init__(self, store: Store, connection: Connection, ledger: QuotaLedger, archive: BackupArchive,
                 clock: Callable[[], float] = time.time) -> None:
        """`clock` gives epoch seconds for leases and Step budgets; tests pass one they move by hand."""
        self._store = store
        self._connection = connection
        self._ledger = ledger
        self._archive = archive
        self._clock = clock

    def _lease_from_now(self) -> int:
        return int(self._clock()) + LEASE_S

    def _expire_leases(self) -> None:
        """A Run whose lease ran out stops (ADR-0017): cancelled or paused if the owner asked for that, otherwise
        interrupted. Done lazily, before anything reads or changes Runs, since nothing runs between requests.
        One UPDATE claims them all, so two requests can't both stop the same Run."""
        now = utc_now()
        with self._store.tx() as conn:
            stopped = conn.execute(
                f"""UPDATE runs SET
                       status = CASE control WHEN 'cancel' THEN 'cancelled' WHEN 'pause' THEN 'paused'
                                ELSE 'interrupted' END,
                       finished_at = CASE control WHEN 'cancel' THEN ? ELSE finished_at END,
                       control = NULL, driver = NULL, step_token = NULL
                   WHERE status IN ({_marks(ACTIVE)}) AND (lease_until IS NULL OR lease_until < ?)
                   RETURNING id, status""", (now, *ACTIVE, int(self._clock()))).fetchall()
            for r in stopped:
                if r["status"] == "cancelled":
                    conn.execute("UPDATE run_items SET status = 'cancelled', updated_at = ? "
                                 "WHERE run_id = ? AND status = 'pending'", (now, r["id"]))
        messages = {"cancelled": CANCELLED_MESSAGE, "paused": PAUSED_MESSAGE, "interrupted": ABANDONED_MESSAGE}
        for r in stopped:
            self._log(r["id"], "warning" if r["status"] == "interrupted" else "info", messages[r["status"]])

    # --- creating -----------------------------------------------------------------------------

    def apply_changeset(self, cs_id: int, confirm_count: int) -> int:
        """Turn the open review into a Run and start it. Nothing is written unless confirm_count matches."""
        with self._store.tx() as conn:
            cs = conn.execute("SELECT status, field FROM changesets WHERE id = ?", (cs_id,)).fetchone()
            if cs is None:
                raise RunNotFound()
            # Claim the review atomically, so two Apply clicks can never make two Runs.
            claimed = conn.execute("UPDATE changesets SET status = 'applied' WHERE id = ? AND status = 'draft'",
                                   (cs_id,)).rowcount
            if not claimed:
                raise RunConflict("This review was already applied or replaced. Review again to make more changes.")
            items = conn.execute(
                """SELECT video_id, title, before_description,
                          COALESCE(override_description, computed_description) AS target
                   FROM changeset_items WHERE changeset_id = ? AND included = 1 ORDER BY seq""",
                (cs_id,)).fetchall()
            if confirm_count != len(items):
                raise RunConflict(f"You confirmed {confirm_count} videos but the review has {len(items)} to write. "
                                  "Nothing was written.")
            if not items:
                raise RunConflict("There's nothing to write in this review.")
            now = utc_now()
            run_id = conn.execute("INSERT INTO runs (kind, changeset_id, field, status, created_at, lease_until) "
                                  "VALUES ('apply', ?, ?, 'pending', ?, ?) RETURNING id",
                                  (cs_id, cs["field"], now, self._lease_from_now())).fetchone()[0]
            conn.executemany(
                """INSERT INTO run_items (run_id, video_id, seq, title, expected_before, target_description,
                       status, updated_at) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)""",
                [(run_id, r["video_id"], seq, r["title"], r["before_description"], r["target"], now)
                 for seq, r in enumerate(items)])
        self._log(run_id, "info", f"Run created: {len(items)} videos to write.")
        return run_id

    def restore(self, source_run_id: int, confirm_count: int, video_ids: list[str] | None = None) -> int:
        """Put back the values a Run replaced, as a new restore Run of the same Field (ADR-0004). Only Videos the
        source Run actually wrote can be restored; each gets its backed-up value on today's snippet."""
        if video_ids is not None and not video_ids:
            raise RunInvalid("Choose at least one video to restore.")
        self._expire_leases()
        with self._store.tx() as conn:
            source = conn.execute("SELECT status, field FROM runs WHERE id = ?", (source_run_id,)).fetchone()
            if source is None:
                raise RunNotFound()
            if source["status"] in ACTIVE:
                raise RunConflict("This run is still writing. Pause it or wait for it to finish, then restore.")
            busy = conn.execute(f"SELECT id FROM runs WHERE source_run_id = ? AND status IN "
                                f"({_marks(ACTIVE)})", (source_run_id, *ACTIVE)).fetchone()
            if busy is not None:  # a double click, or a restore already under way
                raise RunConflict(f"Run #{busy['id']} is already restoring this run.")
            written = conn.execute(
                f"""SELECT video_id, title, target_description, backup_snippet_json FROM run_items
                    WHERE run_id = ? AND {RESTORABLE_ITEM} ORDER BY seq""",
                (source_run_id,)).fetchall()
            if video_ids is not None:
                wanted = set(video_ids)
                unknown = wanted - {r["video_id"] for r in written}
                if unknown:
                    raise RunInvalid("Only videos this run actually wrote can be restored: "
                                     f"{', '.join(sorted(unknown))} weren't.")
                written = [r for r in written if r["video_id"] in wanted]
            if not written:
                raise RunConflict("This run didn't write any videos, so there's nothing to restore.")
            if confirm_count != len(written):
                raise RunConflict(f"You confirmed {confirm_count} videos but {len(written)} would be restored. "
                                  "Nothing was written.")
            now = utc_now()
            run_id = conn.execute("INSERT INTO runs (kind, source_run_id, field, status, created_at, lease_until) "
                                  "VALUES ('restore', ?, ?, 'pending', ?, ?) RETURNING id",
                                  (source_run_id, source["field"], now, self._lease_from_now())).fetchone()[0]
            # The live value must still be what the source Run wrote; otherwise it's Stale and left alone.
            # A Backup snippet without the Field's key means the value was empty.
            conn.executemany(
                """INSERT INTO run_items (run_id, video_id, seq, title, expected_before, target_description,
                       status, updated_at) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)""",
                [(run_id, r["video_id"], seq, r["title"], r["target_description"],
                  fields.value_in_snippet(source["field"], json.loads(r["backup_snippet_json"])), now)
                 for seq, r in enumerate(written)])
        self._log(run_id, "info", f"Restore of run #{source_run_id} created: {len(written)} videos.")
        return run_id

    def resume(self, run_id: int, confirm_count: int) -> None:
        """Continue a paused, quota-stopped or interrupted Run, only on the owner's click (ADR-0007).
        confirm_count must equal the number of Videos still pending."""
        self._expire_leases()
        with self._store.tx() as conn:
            run = conn.execute("SELECT status FROM runs WHERE id = ?", (run_id,)).fetchone()
            if run is None:
                raise RunNotFound()
            pending = conn.execute("SELECT COUNT(*) FROM run_items WHERE run_id = ? AND status = 'pending'",
                                   (run_id,)).fetchone()[0]
            if run["status"] not in RESUMABLE:
                raise RunConflict("This run isn't paused, so there's nothing to resume.")
            if confirm_count != pending:
                raise RunConflict(f"You confirmed {confirm_count} videos but {pending} are still queued. "
                                  "Nothing was written.")
            # Claimed atomically, so two Resume clicks can't start the Run twice.
            claimed = conn.execute(
                f"UPDATE runs SET status = 'pending', control = NULL, driver = NULL, step_token = NULL, "
                f"lease_until = ? WHERE id = ? AND status IN ({_marks(RESUMABLE)})",
                (self._lease_from_now(), run_id, *RESUMABLE)).rowcount
            if not claimed:
                raise RunConflict("This run was resumed already.")
        self._log(run_id, "info", f"Resumed by you: {pending} videos still to do.")

    def request(self, run_id: int, action: Control) -> None:
        """The owner's Pause or Cancel (ADR-0015). A writing Run acts on it after the current Video; a stopped
        Run can be cancelled straight away. Raises RunConflict when there's nothing to pause or cancel."""
        if action not in CONTROLS:
            raise ValueError(f"Unknown control {action!r}")
        self._expire_leases()
        with self._store.tx() as conn:
            run = conn.execute("SELECT status FROM runs WHERE id = ?", (run_id,)).fetchone()
            if run is None:
                raise RunNotFound()
            if run["status"] in ACTIVE:
                conn.execute("UPDATE runs SET control = ? WHERE id = ?", (action, run_id))
                return
            if action == "cancel" and run["status"] in RESUMABLE:
                self._cancel_pending(conn, run_id)
            else:
                raise RunConflict(f"This run is {run['status'].replace('_', ' ')}, so it can't be "
                                  f"{CONTROLS[action]}.")
        self._log(run_id, "info", CANCELLED_MESSAGE)

    def _obey_control(self, run_id: int, token: str) -> bool:
        """Act on a pending Pause/Cancel between Videos. Returns True if the Run must stop now."""
        stopped = self._halt(run_id, token, "paused", only_if_asked=True)
        if stopped:
            self._log(run_id, "info", CANCELLED_MESSAGE if stopped == "cancelled" else PAUSED_MESSAGE)
        return stopped is not None

    def _stop(self, run_id: int, token: str, status: str) -> None:
        """Every early stop of a Step goes through here, so a Cancel the owner asked for is never lost to another
        reason for stopping (quota, sign-in, a crash): the Cancel wins."""
        if self._halt(run_id, token, status) == "cancelled":
            self._log(run_id, "info", CANCELLED_MESSAGE)

    def _halt(self, run_id: int, token: str, status: str, only_if_asked: bool = False) -> str | None:
        """Stop the Run as `status`, or as cancelled if a Cancel is waiting, in one UPDATE that only the Step
        holding `token` can make: a Step that outlived its lease never changes a Run it no longer owns.
        Returns the status set, or None if nothing changed."""
        now = utc_now()
        with self._store.tx() as conn:
            row = conn.execute(
                f"""UPDATE runs SET
                       status = CASE WHEN control = 'cancel' THEN 'cancelled' ELSE ? END,
                       finished_at = CASE WHEN control = 'cancel' THEN ? ELSE finished_at END,
                       control = NULL
                   WHERE id = ? AND step_token = ?{" AND control IS NOT NULL" if only_if_asked else ""}
                   RETURNING status""", (status, now, run_id, token)).fetchone()
            if row is not None and row["status"] == "cancelled":
                conn.execute("UPDATE run_items SET status = 'cancelled', updated_at = ? "
                             "WHERE run_id = ? AND status = 'pending'", (now, run_id))
        return row["status"] if row is not None else None

    @staticmethod
    def _cancel_pending(conn, run_id: int) -> None:
        now = utc_now()
        conn.execute("UPDATE run_items SET status = 'cancelled', updated_at = ? WHERE run_id = ? AND status = 'pending'",
                     (now, run_id))
        conn.execute("UPDATE runs SET status = 'cancelled', control = NULL, finished_at = ? WHERE id = ?",
                     (now, run_id))

    # --- executing ----------------------------------------------------------------------------

    def step(self, run_id: int, driver: str) -> None:
        """Write the next Videos of a pending or running Run for up to STEP_BUDGET_S, holding its lease for
        `driver` (one browser tab). Raises RunConflict if another driver holds the lease, another Step is
        writing it right now, or the Run isn't writing; a stopped Run continues only through resume()."""
        self._expire_leases()
        with self._store.tx() as conn:
            run = conn.execute("SELECT status FROM runs WHERE id = ?", (run_id,)).fetchone()
            if run is None:
                raise RunNotFound()
            token = uuid.uuid4().hex  # this Step's own claim, released only by this Step
            claimed = conn.execute(
                f"""UPDATE runs SET status = 'running', driver = ?, lease_until = ?, step_token = ?,
                       started_at = COALESCE(started_at, ?)
                   WHERE id = ? AND status IN ({_marks(ACTIVE)}) AND (driver IS NULL OR driver = ?)
                       AND step_token IS NULL""",
                (driver, self._lease_from_now(), token, utc_now(), run_id, *ACTIVE, driver)).rowcount
        if not claimed:
            if run["status"] in ACTIVE:
                raise RunConflict(DRIVEN_ELSEWHERE)
            raise RunConflict(f"This run is {run['status'].replace('_', ' ')}, so there's nothing to write.")
        try:
            self._execute(run_id, token)
        finally:
            with self._store.tx() as conn:
                conn.execute("UPDATE runs SET step_token = NULL WHERE id = ? AND step_token = ?", (run_id, token))

    def _holds_lease(self, run_id: int, token: str) -> bool:
        """Renew the lease between Videos. False if this Step no longer owns the Run (its lease ran out during a
        long retry, say, and the Run was stopped or resumed): then it must not write another Video."""
        with self._store.tx() as conn:
            return conn.execute("UPDATE runs SET lease_until = ? WHERE id = ? AND status = 'running' "
                                "AND step_token = ?", (self._lease_from_now(), run_id, token)).rowcount == 1

    def _execute(self, run_id: int, token: str) -> None:
        try:
            self._run(run_id, token)
        except Exception:  # never leave a Run looking busy
            log.exception("Run %s crashed", run_id)
            try:
                self._stop(run_id, token, "interrupted")
                self._log(run_id, "error", "The run stopped unexpectedly. Already-written videos are recorded.")
            except Exception:
                log.exception("Couldn't record that run %s stopped; it will be interrupted when its lease runs out",
                              run_id)

    def _run(self, run_id: int, token: str) -> None:
        deadline = self._clock() + STEP_BUDGET_S
        try:
            gateway = self._connection.gateway()
        except NotConnected:
            self._log(run_id, "error", "Not connected to YouTube. The videos are still queued.")
            self._stop(run_id, token, "paused")
            return
        pending = self._pending(run_id)
        with self._store.tx() as conn:
            source = conn.execute("SELECT kind, source_run_id, field FROM runs WHERE id = ?", (run_id,)).fetchone()
        field = source["field"]
        stale_reason = (f"Changed on YouTube since run #{source['source_run_id']} wrote it; left as it is."
                        if source["kind"] == "restore" else "Changed on YouTube since you reviewed it; left as it is.")

        # 1. Fresh fetch + Backups of every pending Video, before this Step's first write. Every Step fetches
        #    again, so each write still uses a snippet fetched seconds before it (ADR-0002).
        try:
            fresh = self._fetch_fresh(run_id, gateway, [r["video_id"] for r in pending])
        except AuthExpired:
            self._log(run_id, "error", "Google sign-in expired before anything was written. The videos are still queued.")
            self._stop(run_id, token, "paused")
            return
        except QuotaExceeded:
            self._quota_stop(run_id, token)
            return
        except RetryableError as e:
            self._log(run_id, "error", f"YouTube kept failing while fetching the videos ({e}). Nothing was written; "
                                       "the videos are still queued.")
            self._stop(run_id, token, "paused")
            return
        try:
            added = self._save_backups(run_id, pending, fresh)
        except BackupArchiveError as e:
            self._log(run_id, "error", f"Couldn't save the backup copy ({e}). Nothing was written; the videos are "
                                       "still queued.")
            self._stop(run_id, token, "paused")
            return
        if added:
            self._log(run_id, "info", f"Backed up {added} videos. Writing {fields.spec(field).plural}…")

        # 2-5. One Video at a time; each outcome is committed before the next write.
        for n, item in enumerate(pending):
            if n and self._clock() >= deadline:  # at least one Video per Step, so a Run always moves on
                return  # the lease is held; the next Step carries on
            if self._obey_control(run_id, token):  # Pause/Cancel take effect between Videos, never mid-write
                return
            if not self._holds_lease(run_id, token):
                return
            vid = item["video_id"]
            snap = fresh.get(vid)
            if snap is None or snap.privacy_status != "public":
                self._finish_item(run_id, vid, "failed", "The video is no longer public or no longer exists.")
                continue
            live = fields.value_in_snippet(field, snap.snippet)
            target = item["target_description"]
            if live == target:
                if item["backup_snippet_json"] is not None and live != item["expected_before"]:
                    # Backed up by an earlier execution of this Run, so YouTube took our write before the app
                    # stopped and recorded it: done, not stale (ADR-0014).
                    self._record_success(run_id, vid, field, target, attempts=0)
                    self._log(run_id, "info", f"{item['title']}: already updated before the run stopped.")
                else:
                    self._finish_item(run_id, vid, "noop", None)  # already says exactly this; nothing to send
                continue
            if live != item["expected_before"]:
                self._finish_item(run_id, vid, "stale", stale_reason)
                continue
            flags = fields.spec(field).check(target)
            if is_blocked(flags):
                self._finish_item(run_id, vid, "blocked", "; ".join(f.message for f in flags))
                continue
            try:
                _, attempts = self._with_retries(
                    run_id, item["title"], lambda: gateway.update_snippet(vid, update_body(snap.snippet, target, field)))
            except QuotaExceeded:
                self._quota_stop(run_id, token)  # this Video and the rest stay pending
                return
            except AuthExpired:
                self._log(run_id, "error", "Google sign-in expired. The remaining videos are still queued.")
                self._stop(run_id, token, "paused")
                return
            except _GaveUp as e:
                self._finish_item(run_id, vid, "failed", str(e.error), attempts=e.attempts)
                self._log(run_id, "warning", f"{item['title']}: gave up after {e.attempts} tries ({e.error})")
                continue
            except GatewayError as e:
                self._finish_item(run_id, vid, "failed", str(e), attempts=getattr(e, "attempts", 1))
                self._log(run_id, "warning", f"{item['title']}: {e}")
                continue
            self._record_success(run_id, vid, field, target, attempts=attempts)
            self._log(run_id, "info", f"Updated: {item['title']}")
            if not snap.snippet.get("defaultAudioLanguage"):
                self._log(run_id, "info", f"{item['title']}: had no audio language; YouTube usually fills it in "
                                          "(en-US) on any update.")

        with self._store.tx() as conn:
            late = conn.execute("SELECT control FROM runs WHERE id = ?", (run_id,)).fetchone()["control"]
        if not self._complete(run_id, token):
            return  # stopped meanwhile (its lease ran out): leave it as it is
        if late:
            self._log(run_id, "info", f"Your {late} arrived after the last video, so there was nothing left to "
                                      f"{late}.")
        self._log(run_id, "info", "Run finished.")

    def _with_retries(self, run_id: int, what: str, call) -> tuple[object, int]:
        """Run `call`, retrying temporary failures with exponential backoff (1, 2, 4, 8 s) plus jitter.
        Returns (result, attempts). Raises _GaveUp when retries run out; any other GatewayError passes through
        with `.attempts` set, so the Run item records every try (ADR-0014)."""
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                return call(), attempt
            except RetryableError as e:
                if attempt == MAX_ATTEMPTS:
                    raise _GaveUp(e, attempt) from e
                delay = BASE_BACKOFF_S * 2 ** (attempt - 1) + random.uniform(0, BASE_BACKOFF_S / 2)
                self._log(run_id, "warning", f"{what}: {e}; retrying in {delay:.1f} s (try {attempt + 1} of "
                                             f"{MAX_ATTEMPTS})")
                sleep(delay)
            except GatewayError as e:
                e.attempts = attempt  # type: ignore[attr-defined]
                raise
        raise AssertionError("unreachable")  # pragma: no cover

    def _fetch_fresh(self, run_id: int, gateway, ids: list[str]) -> dict[str, FreshSnippet]:
        """Raises RetryableError if YouTube keeps failing: the Run then pauses with nothing written (ADR-0014)."""
        fresh: dict[str, FreshSnippet] = {}
        for i in range(0, len(ids), BATCH):
            chunk = ids[i:i + BATCH]
            try:
                batch, _ = self._with_retries(run_id, "Fetching videos", lambda: gateway.get_snippets(chunk))
            except _GaveUp as e:
                raise e.error from e
            for snap in batch:
                fresh[snap.id] = snap
        return fresh

    def _save_backups(self, run_id: int, pending, fresh: dict[str, FreshSnippet]) -> int:
        """Save the Backups in the database, in one transaction, then the JSON copy of all the Run's Backups to
        the archive (ADR-0018). The first Backup of a Video in a Run is the one kept: a later Step or Resume never
        replaces it, in either copy. Returns how many Videos were backed up for the first time; raises
        BackupArchiveError if the copy couldn't be saved."""
        added = sum(1 for r in pending if r["video_id"] in fresh and r["backup_snippet_json"] is None)
        with self._store.tx() as conn:
            conn.executemany(
                "UPDATE run_items SET backup_snippet_json = COALESCE(backup_snippet_json, ?) "
                "WHERE run_id = ? AND video_id = ?",
                [(json.dumps(fresh[r["video_id"]].snippet, ensure_ascii=False), run_id, r["video_id"])
                 for r in pending if r["video_id"] in fresh])
            backed_up = conn.execute("SELECT video_id, backup_snippet_json FROM run_items WHERE run_id = ? "
                                     "AND backup_snippet_json IS NOT NULL ORDER BY seq", (run_id,)).fetchall()
        # Rebuilt from the database every Step, so a copy that failed to save once is complete the next time.
        self._archive.save(run_id, {"run_id": run_id, "saved_at": utc_now(), "videos": [
            {"video_id": r["video_id"], "snippet": json.loads(r["backup_snippet_json"])} for r in backed_up]})
        return added

    def _record_success(self, run_id: int, video_id: str, field: FieldName, value: str, attempts: int) -> None:
        """The cache and the Run item change together, so a crash can't leave a written Video pending."""
        now = utc_now()
        spec = fields.spec(field)
        with self._store.tx() as conn:
            # The column name comes from the fixed Field registry, never from a request.
            conn.execute(f"UPDATE videos SET {spec.cache_column} = ?, last_edited_run_id = ? WHERE id = ?",
                         (spec.to_cache(value), run_id, video_id))
            conn.execute("UPDATE run_items SET status = 'success', error = NULL, attempts = attempts + ?, "
                         "updated_at = ? WHERE run_id = ? AND video_id = ?", (attempts, now, run_id, video_id))

    def _quota_stop(self, run_id: int, token: str) -> None:
        self._ledger.mark_exhausted()
        self._log(run_id, "warning", "YouTube's daily quota is used up. The remaining videos are still queued; "
                                     "the quota resets at midnight Pacific time.")
        self._stop(run_id, token, "paused_quota")

    # --- reading ------------------------------------------------------------------------------

    def get(self, run_id: int) -> dict:
        self._expire_leases()
        with self._store.tx() as conn:
            run = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
            if run is None:
                raise RunNotFound()
            items = conn.execute("SELECT * FROM run_items WHERE run_id = ? ORDER BY seq", (run_id,)).fetchall()
            logs = conn.execute("SELECT id, ts, level, message FROM run_log WHERE run_id = ? ORDER BY id",
                                (run_id,)).fetchall()
            operations = _operations(conn)
        statuses = [i["status"] for i in items]
        restorable = [_is_restorable(i["status"], i["backup_snippet_json"] is not None) for i in items]
        return {**_run_summary(run, statuses), **_history(run, operations, sum(restorable)),
                "items": [{"video_id": i["video_id"], "title": i["title"], "status": i["status"],
                           "error": i["error"], "before": i["expected_before"], "after": i["target_description"],
                           "has_backup": i["backup_snippet_json"] is not None, "attempts": i["attempts"],
                           "restorable": can} for i, can in zip(items, restorable, strict=True)],
                "log": [dict(entry) for entry in logs]}

    def progress(self, run_id: int, after_log_id: int) -> dict:
        """What the live view needs, cheaply: the summary, each item's outcome (no descriptions) and only
        the log lines after `after_log_id`."""
        self._expire_leases()
        with self._store.tx() as conn:
            run = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
            if run is None:
                raise RunNotFound()
            items = conn.execute("SELECT video_id, status, error, attempts FROM run_items WHERE run_id = ? "
                                 "ORDER BY seq", (run_id,)).fetchall()
            logs = conn.execute("SELECT id, ts, level, message FROM run_log WHERE run_id = ? AND id > ? ORDER BY id",
                                (run_id, after_log_id)).fetchall()
        return {"run": _run_summary(run, [i["status"] for i in items]), "items": [dict(i) for i in items],
                "log": [dict(entry) for entry in logs]}

    def list(self, unfinished: bool = False) -> list[dict]:
        """Newest first; `unfinished` keeps only Runs waiting for Resume."""
        where = f"WHERE status IN ({_marks(RESUMABLE)})" if unfinished else ""
        self._expire_leases()
        with self._store.tx() as conn:
            runs = conn.execute(f"SELECT * FROM runs {where} ORDER BY id DESC",
                                RESUMABLE if unfinished else ()).fetchall()
            rows = conn.execute("SELECT run_id, status, backup_snippet_json IS NOT NULL AS backed_up "
                                "FROM run_items").fetchall()
            operations = _operations(conn)
        statuses: dict[int, list[str]] = {}
        restorable: dict[int, int] = {}
        for r in rows:
            statuses.setdefault(r["run_id"], []).append(r["status"])
            restorable[r["run_id"]] = restorable.get(r["run_id"], 0) + _is_restorable(r["status"], bool(r["backed_up"]))
        return [{**_run_summary(run, statuses.get(run["id"], [])),
                 **_history(run, operations, restorable.get(run["id"], 0))} for run in runs]

    # --- bookkeeping --------------------------------------------------------------------------

    def _pending(self, run_id: int):
        with self._store.tx() as conn:
            return conn.execute("SELECT * FROM run_items WHERE run_id = ? AND status = 'pending' ORDER BY seq",
                                (run_id,)).fetchall()

    def _finish_item(self, run_id: int, video_id: str, status: str, error: str | None, attempts: int = 0) -> None:
        with self._store.tx() as conn:
            conn.execute("UPDATE run_items SET status = ?, error = ?, attempts = attempts + ?, updated_at = ? "
                         "WHERE run_id = ? AND video_id = ?",
                         (status, error, attempts, utc_now(), run_id, video_id))

    def _complete(self, run_id: int, token: str) -> bool:
        """Finish the Run, if this Step still owns it. A Pause/Cancel that arrived after the last Video has
        nothing left to act on once the Run finishes."""
        with self._store.tx() as conn:
            return conn.execute("UPDATE runs SET status = 'completed', finished_at = ?, control = NULL, driver = NULL "
                                "WHERE id = ? AND status = 'running' AND step_token = ?",
                                (utc_now(), run_id, token)).rowcount == 1

    def _log(self, run_id: int, level: str, message: str) -> None:
        with self._store.tx() as conn:
            conn.execute("INSERT INTO run_log (run_id, ts, level, message) VALUES (?, ?, ?, ?)",
                         (run_id, utc_now(), level, message))


def _marks(values) -> str:
    """One `?` placeholder per value, for an IN (...) list."""
    return ", ".join("?" * len(values))


def _is_restorable(status: str, backed_up: bool) -> bool:
    """Python twin of RESTORABLE_ITEM, for rows already in hand."""
    return status == "success" and backed_up


def _operations(conn) -> dict[int, dict]:
    """Changeset id -> the Operation it applied."""
    return {r["id"]: json.loads(r["operation_json"]) for r in conn.execute("SELECT id, operation_json FROM changesets")}


def _history(run, operations: dict[int, dict], restorable: int) -> dict:
    """What History shows beyond the summary: what an apply Run did, and how many Videos can be restored."""
    op = operations.get(run["changeset_id"]) if run["changeset_id"] else None
    spec = fields.spec(run["field"])
    return {"operation": op,
            "operation_summary": summarize(_OPERATION.validate_python(op), spec) if op else None,
            "restorable": restorable}


def _run_summary(run, statuses: list[str]) -> dict:
    counts = {s: statuses.count(s) for s in ("pending", "success", "failed", "stale", "blocked", "noop", "cancelled")}
    return {"id": run["id"], "kind": run["kind"], "field": run["field"], "status": run["status"],
            "changeset_id": run["changeset_id"],
            "estimated_units": counts["pending"] * UPDATE_UNITS,  # what finishing the queued Videos costs
            "source_run_id": run["source_run_id"], "created_at": run["created_at"],
            "started_at": run["started_at"], "finished_at": run["finished_at"],
            "total": len(statuses), "counts": counts}

