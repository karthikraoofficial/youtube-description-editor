"""The Run engine: the only code allowed to write descriptions to YouTube (CLAUDE.md hard rule).

For every Run:
1. Fetch every target Video fresh, and save each live snippet as the Backup, in the database and a
   JSON file, before the first write (ADR-0002).
2. Skip Videos whose live description no longer matches what the owner reviewed (Stale, ADR-0003); one
   that already reads exactly like the target isn't written again (ADR-0014).
3. Re-validate each target; never send a blocked description.
4. Send the fresh snippet's writable fields back unchanged, with only the description replaced,
   retrying temporary YouTube errors with backoff (ADR-0014).
5. Record each Video's outcome as it happens; one Video failing never stops the others.
A Run that stops early (quota, sign-in, the app closing) continues only through resume() (ADR-0007).
"""
import json
import logging
import random
from concurrent.futures import Executor
from pathlib import Path
from time import sleep  # module-level so tests can replace it
from typing import Literal

from pydantic import TypeAdapter

from app.connection import Connection, NotConnected
from app.domain.operations import Operation, summarize
from app.domain.validation import check, is_blocked
from app.quota import UPDATE_UNITS, QuotaLedger
from app.store.db import Store, utc_now
from app.youtube.errors import AuthExpired, GatewayError, QuotaExceeded, RetryableError
from app.youtube.gateway import FreshSnippet

_OPERATION = TypeAdapter(Operation)

BATCH = 50
MAX_ATTEMPTS = 5  # per request: the first try plus 4 retries
BASE_BACKOFF_S = 1.0  # 1, 2, 4, 8 s (+ up to 0.5 s jitter)
RESUMABLE = ("paused", "paused_quota", "interrupted")
ACTIVE = ("pending", "running")
# The one rule for "this Video can be restored from this Run": the Run wrote it, and backed it up first.
RESTORABLE_ITEM = "status = 'success' AND backup_snippet_json IS NOT NULL"
Control = Literal["pause", "cancel"]
CONTROLS: dict[str, str] = {"pause": "paused", "cancel": "cancelled"}
PAUSED_MESSAGE = "Paused by you. The remaining videos are still queued."
CANCELLED_MESSAGE = "Cancelled by you. Videos already written stay written."
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


def update_body(fresh_snippet: dict, description: str) -> dict:
    """The fresh snippet's writable fields, unchanged, with only the description replaced (ADR-0002)."""
    body = {k: fresh_snippet[k] for k in WRITABLE_FIELDS if fresh_snippet.get(k) not in (None, [], "")}
    body["description"] = description
    return body


class Runs:
    def __init__(self, store: Store, connection: Connection, ledger: QuotaLedger, executor: Executor,
                 backups_dir: Path) -> None:
        self._store = store
        self._connection = connection
        self._ledger = ledger
        self._executor = executor
        self._backups_dir = backups_dir

    def recover(self) -> None:
        """At startup: a Run that was pending or running when the app stopped is interrupted (ADR-0007)."""
        with self._store.tx() as conn:
            ids = [r["id"] for r in conn.execute("SELECT id FROM runs WHERE status IN ('pending', 'running')")]
            conn.execute("UPDATE runs SET status = 'interrupted', control = NULL WHERE status IN ('pending', 'running')")
        for run_id in ids:
            self._log(run_id, "warning", "The app stopped during this run. Videos not yet written are still queued.")

    # --- creating -----------------------------------------------------------------------------

    def apply_changeset(self, cs_id: int, confirm_count: int) -> int:
        """Turn the open review into a Run and start it. Nothing is written unless confirm_count matches."""
        with self._store.tx() as conn:
            cs = conn.execute("SELECT status FROM changesets WHERE id = ?", (cs_id,)).fetchone()
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
            run_id = conn.execute("INSERT INTO runs (kind, changeset_id, status, created_at) "
                                  "VALUES ('apply', ?, 'pending', ?) RETURNING id", (cs_id, now)).fetchone()[0]
            conn.executemany(
                """INSERT INTO run_items (run_id, video_id, seq, title, expected_before, target_description,
                       status, updated_at) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)""",
                [(run_id, r["video_id"], seq, r["title"], r["before_description"], r["target"], now)
                 for seq, r in enumerate(items)])
        self._log(run_id, "info", f"Run created: {len(items)} videos to write.")
        self._executor.submit(self._execute, run_id)
        return run_id

    def restore(self, source_run_id: int, confirm_count: int, video_ids: list[str] | None = None) -> int:
        """Put back the descriptions a Run replaced, as a new restore Run (ADR-0004). Only Videos the source Run
        actually wrote can be restored; each gets its backed-up description on today's snippet."""
        if video_ids is not None and not video_ids:
            raise RunInvalid("Choose at least one video to restore.")
        with self._store.tx() as conn:
            source = conn.execute("SELECT status FROM runs WHERE id = ?", (source_run_id,)).fetchone()
            if source is None:
                raise RunNotFound()
            if source["status"] in ACTIVE:
                raise RunConflict("This run is still writing. Pause it or wait for it to finish, then restore.")
            busy = conn.execute(f"SELECT id FROM runs WHERE source_run_id = ? AND status IN "
                                f"({', '.join('?' * len(ACTIVE))})", (source_run_id, *ACTIVE)).fetchone()
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
            run_id = conn.execute("INSERT INTO runs (kind, source_run_id, status, created_at) "
                                  "VALUES ('restore', ?, 'pending', ?) RETURNING id", (source_run_id, now)).fetchone()[0]
            # The live text must still be what the source Run wrote; otherwise it's Stale and left alone.
            # A Backup snippet with no "description" key means the Video's description was empty.
            conn.executemany(
                """INSERT INTO run_items (run_id, video_id, seq, title, expected_before, target_description,
                       status, updated_at) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)""",
                [(run_id, r["video_id"], seq, r["title"], r["target_description"],
                  json.loads(r["backup_snippet_json"]).get("description", ""), now) for seq, r in enumerate(written)])
        self._log(run_id, "info", f"Restore of run #{source_run_id} created: {len(written)} videos.")
        self._executor.submit(self._execute, run_id)
        return run_id

    def resume(self, run_id: int, confirm_count: int) -> None:
        """Continue a paused, quota-stopped or interrupted Run, only on the owner's click (ADR-0007).
        confirm_count must equal the number of Videos still pending."""
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
                f"UPDATE runs SET status = 'pending', control = NULL WHERE id = ? "
                f"AND status IN ({', '.join('?' * len(RESUMABLE))})",
                (run_id, *RESUMABLE)).rowcount
            if not claimed:
                raise RunConflict("This run was resumed already.")
        self._log(run_id, "info", f"Resumed by you: {pending} videos still to do.")
        self._executor.submit(self._execute, run_id)

    def request(self, run_id: int, action: Control) -> None:
        """The owner's Pause or Cancel (ADR-0015). A writing Run acts on it after the current Video; a stopped
        Run can be cancelled straight away. Raises RunConflict when there's nothing to pause or cancel."""
        if action not in CONTROLS:
            raise ValueError(f"Unknown control {action!r}")
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

    def _obey_control(self, run_id: int) -> bool:
        """Act on a pending Pause/Cancel between Videos. Returns True if the Run must stop now."""
        with self._store.tx() as conn:
            control = conn.execute("SELECT control FROM runs WHERE id = ?", (run_id,)).fetchone()["control"]
            if control is None:
                return False
            if control == "cancel":
                self._cancel_pending(conn, run_id)
            else:
                conn.execute("UPDATE runs SET status = 'paused', control = NULL WHERE id = ?", (run_id,))
        self._log(run_id, "info", CANCELLED_MESSAGE if control == "cancel" else PAUSED_MESSAGE)
        return True

    def _stop(self, run_id: int, status: str) -> None:
        """Every early stop goes through here, so a Cancel the owner asked for is never lost to another
        reason for stopping (quota, sign-in, a crash): the Cancel wins."""
        with self._store.tx() as conn:
            control = conn.execute("SELECT control FROM runs WHERE id = ?", (run_id,)).fetchone()["control"]
            if control == "cancel":
                self._cancel_pending(conn, run_id)
            else:
                conn.execute("UPDATE runs SET status = ?, control = NULL WHERE id = ?", (status, run_id))
        if control == "cancel":
            self._log(run_id, "info", CANCELLED_MESSAGE)

    @staticmethod
    def _cancel_pending(conn, run_id: int) -> None:
        now = utc_now()
        conn.execute("UPDATE run_items SET status = 'cancelled', updated_at = ? WHERE run_id = ? AND status = 'pending'",
                     (now, run_id))
        conn.execute("UPDATE runs SET status = 'cancelled', control = NULL, finished_at = ? WHERE id = ?",
                     (now, run_id))

    # --- executing ----------------------------------------------------------------------------

    def _execute(self, run_id: int) -> None:
        try:
            self._run(run_id)
        except Exception:  # never leave a Run looking busy
            log.exception("Run %s crashed", run_id)
            try:
                self._stop(run_id, "interrupted")
                self._log(run_id, "error", "The run stopped unexpectedly. Already-written videos are recorded.")
            except Exception:
                log.exception("Couldn't record that run %s stopped; it will be interrupted at next start", run_id)

    def _run(self, run_id: int) -> None:
        self._set_status(run_id, "running", started=True)
        try:
            gateway = self._connection.gateway()
        except NotConnected:
            self._log(run_id, "error", "Not connected to YouTube. The videos are still queued.")
            self._stop(run_id, "paused")
            return
        pending = self._pending(run_id)
        with self._store.tx() as conn:
            source = conn.execute("SELECT kind, source_run_id FROM runs WHERE id = ?", (run_id,)).fetchone()
        stale_reason = (f"Changed on YouTube since run #{source['source_run_id']} wrote it; left as it is."
                        if source["kind"] == "restore" else "Changed on YouTube since you reviewed it; left as it is.")

        # 1. Fresh fetch + Backups, all before the first write.
        try:
            fresh = self._fetch_fresh(run_id, gateway, [r["video_id"] for r in pending])
        except AuthExpired:
            self._connection.mark_expired()
            self._log(run_id, "error", "Google sign-in expired before anything was written. The videos are still queued.")
            self._stop(run_id, "paused")
            return
        except QuotaExceeded:
            self._quota_stop(run_id)
            return
        except RetryableError as e:
            self._log(run_id, "error", f"YouTube kept failing while fetching the videos ({e}). Nothing was written; "
                                       "the videos are still queued.")
            self._stop(run_id, "paused")
            return
        self._save_backups(run_id, pending, fresh)
        self._log(run_id, "info", f"Backed up {len(fresh)} videos. Writing descriptions…")

        # 2-5. One Video at a time; each outcome is committed before the next write.
        for item in pending:
            if self._obey_control(run_id):  # Pause/Cancel take effect between Videos, never mid-write
                return
            vid = item["video_id"]
            snap = fresh.get(vid)
            if snap is None or snap.privacy_status != "public":
                self._finish_item(run_id, vid, "failed", "The video is no longer public or no longer exists.")
                continue
            live = snap.snippet.get("description", "")
            target = item["target_description"]
            if live == target:
                if item["backup_snippet_json"] is not None and live != item["expected_before"]:
                    # Backed up by an earlier execution of this Run, so YouTube took our write before the app
                    # stopped and recorded it: done, not stale (ADR-0014).
                    self._record_success(run_id, vid, target, attempts=0)
                    self._log(run_id, "info", f"{item['title']}: already updated before the run stopped.")
                else:
                    self._finish_item(run_id, vid, "noop", None)  # already says exactly this; nothing to send
                continue
            if live != item["expected_before"]:
                self._finish_item(run_id, vid, "stale", stale_reason)
                continue
            flags = check(target)
            if is_blocked(flags):
                self._finish_item(run_id, vid, "blocked", "; ".join(f.message for f in flags))
                continue
            try:
                _, attempts = self._with_retries(
                    run_id, item["title"], lambda: gateway.update_snippet(vid, update_body(snap.snippet, target)))
            except QuotaExceeded:
                self._quota_stop(run_id)  # this Video and the rest stay pending
                return
            except AuthExpired:
                self._connection.mark_expired()
                self._log(run_id, "error", "Google sign-in expired. The remaining videos are still queued.")
                self._stop(run_id, "paused")
                return
            except _GaveUp as e:
                self._finish_item(run_id, vid, "failed", str(e.error), attempts=e.attempts)
                self._log(run_id, "warning", f"{item['title']}: gave up after {e.attempts} tries ({e.error})")
                continue
            except GatewayError as e:
                self._finish_item(run_id, vid, "failed", str(e), attempts=getattr(e, "attempts", 1))
                self._log(run_id, "warning", f"{item['title']}: {e}")
                continue
            self._record_success(run_id, vid, target, attempts=attempts)
            self._log(run_id, "info", f"Updated: {item['title']}")
            if not snap.snippet.get("defaultAudioLanguage"):
                self._log(run_id, "info", f"{item['title']}: had no audio language; YouTube usually fills it in "
                                          "(en-US) on any update.")

        with self._store.tx() as conn:
            late = conn.execute("SELECT control FROM runs WHERE id = ?", (run_id,)).fetchone()["control"]
        self._set_status(run_id, "completed", finished=True)
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

    def _save_backups(self, run_id: int, pending, fresh: dict[str, FreshSnippet]) -> None:
        """The first Backup of a Video in a Run is the one kept: continuing a Run later never replaces it."""
        self._backups_dir.mkdir(parents=True, exist_ok=True)
        path = self._backups_dir / f"run-{run_id}.json"
        saved = json.loads(path.read_text(encoding="utf-8"))["videos"] if path.exists() else []
        known = {v["video_id"] for v in saved}
        saved += [{"video_id": vid, "snippet": snap.snippet} for vid, snap in fresh.items() if vid not in known]
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps({"run_id": run_id, "saved_at": utc_now(), "videos": saved}, ensure_ascii=False,
                                  indent=1), encoding="utf-8")
        tmp.replace(path)  # the file appears whole or not at all
        with self._store.tx() as conn:
            conn.executemany(
                "UPDATE run_items SET backup_snippet_json = COALESCE(backup_snippet_json, ?) "
                "WHERE run_id = ? AND video_id = ?",
                [(json.dumps(fresh[r["video_id"]].snippet, ensure_ascii=False), run_id, r["video_id"])
                 for r in pending if r["video_id"] in fresh])

    def _record_success(self, run_id: int, video_id: str, description: str, attempts: int) -> None:
        """The cache and the Run item change together, so a crash can't leave a written Video pending."""
        now = utc_now()
        with self._store.tx() as conn:
            conn.execute("UPDATE videos SET description = ?, last_edited_run_id = ? WHERE id = ?",
                         (description, run_id, video_id))
            conn.execute("UPDATE run_items SET status = 'success', error = NULL, attempts = attempts + ?, "
                         "updated_at = ? WHERE run_id = ? AND video_id = ?", (attempts, now, run_id, video_id))

    def _quota_stop(self, run_id: int) -> None:
        self._ledger.mark_exhausted()
        self._log(run_id, "warning", "YouTube's daily quota is used up. The remaining videos are still queued; "
                                     "the quota resets at midnight Pacific time.")
        self._stop(run_id, "paused_quota")

    # --- reading ------------------------------------------------------------------------------

    def get(self, run_id: int) -> dict:
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
        where = f"WHERE status IN ({', '.join('?' * len(RESUMABLE))})" if unfinished else ""
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

    def _set_status(self, run_id: int, status: str, *, started: bool = False, finished: bool = False) -> None:
        # A Pause/Cancel that arrived after the last Video has nothing left to act on once the Run finishes.
        sets = ["status = ?"] + (["started_at = COALESCE(started_at, ?)"] if started else []) + \
               (["finished_at = ?", "control = NULL"] if finished else [])
        args = [status] + ([utc_now()] if started else []) + ([utc_now()] if finished else [])
        with self._store.tx() as conn:
            conn.execute(f"UPDATE runs SET {', '.join(sets)} WHERE id = ?", (*args, run_id))

    def _log(self, run_id: int, level: str, message: str) -> None:
        with self._store.tx() as conn:
            conn.execute("INSERT INTO run_log (run_id, ts, level, message) VALUES (?, ?, ?, ?)",
                         (run_id, utc_now(), level, message))


def _is_restorable(status: str, backed_up: bool) -> bool:
    """Python twin of RESTORABLE_ITEM, for rows already in hand."""
    return status == "success" and backed_up


def _operations(conn) -> dict[int, dict]:
    """Changeset id -> the Operation it applied."""
    return {r["id"]: json.loads(r["operation_json"]) for r in conn.execute("SELECT id, operation_json FROM changesets")}


def _history(run, operations: dict[int, dict], restorable: int) -> dict:
    """What History shows beyond the summary: what an apply Run did, and how many Videos can be restored."""
    op = operations.get(run["changeset_id"]) if run["changeset_id"] else None
    return {"operation": op, "operation_summary": summarize(_OPERATION.validate_python(op)) if op else None,
            "restorable": restorable}


def _run_summary(run, statuses: list[str]) -> dict:
    counts = {s: statuses.count(s) for s in ("pending", "success", "failed", "stale", "blocked", "noop", "cancelled")}
    return {"id": run["id"], "kind": run["kind"], "status": run["status"], "changeset_id": run["changeset_id"],
            "estimated_units": counts["pending"] * UPDATE_UNITS,  # what finishing the queued Videos costs
            "source_run_id": run["source_run_id"], "created_at": run["created_at"],
            "started_at": run["started_at"], "finished_at": run["finished_at"],
            "total": len(statuses), "counts": counts}

