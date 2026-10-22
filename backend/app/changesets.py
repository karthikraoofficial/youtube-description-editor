"""Changesets: the reviewed set of Proposed changes for one Operation over the selected Videos.

Only one Changeset is a live draft at a time (ADR-0012): creating one discards the earlier draft.
"""
import json
from dataclasses import asdict
from typing import Literal

from pydantic import TypeAdapter

from app.domain.operations import Operation
from app.domain.validation import Flag, check, is_blocked
from app.proposals import propose
from app.quota import UPDATE_UNITS
from app.store.db import Store, utc_now

_OPERATION = TypeAdapter(Operation)

Bucket = Literal["to_write", "excluded", "unchanged", "blocked"]
BUCKETS: tuple[Bucket, ...] = ("to_write", "excluded", "unchanged", "blocked")


class _Unset:
    """Marks "override not given" (None means "reset the override")."""


UNSET = _Unset()


class ChangesetNotFound(Exception):
    pass


class ChangesetConflict(Exception):
    """The request can't be honoured in the Changeset's current state. The message is user-facing."""


def bucket_of(changed: bool, flags, included: bool) -> Bucket:
    """The single home of the bucket rules (ADR-0011); every other layer reads the result."""
    if is_blocked(flags):
        return "blocked"
    if not changed:
        return "unchanged"
    return "to_write" if included else "excluded"


def counts(buckets: list[Bucket]) -> dict:
    """Buckets never overlap: to_write + excluded + unchanged + blocked = selected."""
    return {"selected": len(buckets), **{b: buckets.count(b) for b in BUCKETS}}


class Changesets:
    def __init__(self, store: Store) -> None:
        self._store = store

    def create(self, op: Operation, video_ids: list[str]) -> int:
        """Raises OperationError if the Operation can't be applied. Earlier drafts are discarded."""
        rows = self._store.get_videos_by_ids(video_ids)
        proposals = [propose(op, row) for row in rows]  # all computed before anything is saved
        with self._store.tx() as conn:
            conn.execute("UPDATE changesets SET status = 'discarded' WHERE status = 'draft'")
            cs_id = conn.execute(
                "INSERT INTO changesets (created_at, operation_json, requested, status) VALUES (?, ?, ?, 'draft')",
                (utc_now(), json.dumps(op.model_dump()), len(dict.fromkeys(video_ids)))).lastrowid
            conn.executemany(
                """INSERT INTO changeset_items (changeset_id, video_id, seq, title, before_description,
                       computed_description, changed, included, flags_json, computed_flags_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                # Everything that would be written starts included; the owner can exclude from there.
                [(cs_id, p.video_id, seq, p.title, p.before, p.after, int(p.changed),
                  int(bucket_of(p.changed, p.flags, True) == "to_write"),
                  _flags_json(p.flags), _flags_json(p.flags)) for seq, p in enumerate(proposals)])
        return cs_id

    def open_id(self) -> int | None:
        with self._store.tx() as conn:
            row = conn.execute("SELECT id FROM changesets WHERE status = 'draft' ORDER BY id DESC LIMIT 1").fetchone()
        return row["id"] if row else None

    def get(self, cs_id: int) -> dict:
        with self._store.tx() as conn:
            cs = self._header(conn, cs_id)
            rows = conn.execute("SELECT * FROM changeset_items WHERE changeset_id = ? ORDER BY seq",
                                (cs_id,)).fetchall()
        items = [self._item(r) for r in rows]
        return {"id": cs["id"], "created_at": cs["created_at"], "status": cs["status"],
                "operation": _OPERATION.validate_json(cs["operation_json"]).model_dump(),
                "missing": cs["requested"] - len(items),  # selected ids no longer in the cache
                "items": items, **self._totals([i["bucket"] for i in items]),
                "overrides": sum(1 for i in items if i["overridden"])}

    def update_item(self, cs_id: int, video_id: str, *, included: bool | None = None,
                    override: str | None | _Unset = UNSET) -> dict:
        """Hand-edit (or reset, with override=None) and/or include/exclude one item.
        Returns the updated item and the new totals (without re-reading every description)."""
        with self._store.tx() as conn:
            cs = self._header(conn, cs_id)
            row = self._row(conn, cs_id, video_id)
            if cs["status"] != "draft":
                raise ChangesetConflict("This review was replaced by a newer one. Start the review again.")
            if not isinstance(override, _Unset):
                self._set_override(conn, row, override)
                row = self._row(conn, cs_id, video_id)
            if included is not None:
                self._set_included(conn, row, included)
                row = self._row(conn, cs_id, video_id)
            light = conn.execute("SELECT changed, included, flags_json, override_description IS NOT NULL AS overridden "
                                 "FROM changeset_items WHERE changeset_id = ?", (cs_id,)).fetchall()
        buckets = [bucket_of(bool(r["changed"]), json.loads(r["flags_json"]), bool(r["included"])) for r in light]
        return {"item": self._item(row), **self._totals(buckets),
                "overrides": sum(r["overridden"] for r in light)}

    @staticmethod
    def _row(conn, cs_id: int, video_id: str):
        row = conn.execute("SELECT * FROM changeset_items WHERE changeset_id = ? AND video_id = ?",
                           (cs_id, video_id)).fetchone()
        if row is None:
            raise ChangesetNotFound()
        return row

    def _set_override(self, conn, row, override: str | None) -> None:
        """A hand edit is validated like any result; resetting restores the Operation's own verdict.
        An exclusion the owner made survives both."""
        before = row["before_description"]
        if override == row["computed_description"]:
            override = None  # the same as the Operation's result: not a hand edit
        if override is None:
            after, flags = row["computed_description"], json.loads(row["computed_flags_json"])
        else:
            after = override
            flags = [asdict(f) for f in check(override)] if override != before else []
        changed = after != before
        owner_excluded = self._item(row)["bucket"] == "excluded"
        writable = bucket_of(changed, flags, True) == "to_write"
        conn.execute(
            "UPDATE changeset_items SET override_description = ?, changed = ?, flags_json = ?, included = ? "
            "WHERE changeset_id = ? AND video_id = ?",
            (override, int(changed), json.dumps(flags), int(writable and not owner_excluded),
             row["changeset_id"], row["video_id"]))

    def _set_included(self, conn, row, included: bool) -> None:
        if included:
            bucket = self._item(row)["bucket"]
            if bucket == "blocked":
                raise ChangesetConflict("This video is blocked, so it can't be included.")
            if bucket == "unchanged":
                raise ChangesetConflict("This video wouldn't change, so there's nothing to include.")
        conn.execute("UPDATE changeset_items SET included = ? WHERE changeset_id = ? AND video_id = ?",
                     (int(included), row["changeset_id"], row["video_id"]))

    @staticmethod
    def _header(conn, cs_id: int):
        cs = conn.execute("SELECT * FROM changesets WHERE id = ?", (cs_id,)).fetchone()
        if cs is None:
            raise ChangesetNotFound()
        return cs

    @staticmethod
    def _totals(buckets: list[Bucket]) -> dict:
        c = counts(buckets)
        return {"counts": c, "estimated_units": c["to_write"] * UPDATE_UNITS}

    @staticmethod
    def _item(r) -> dict:
        after = r["override_description"] if r["override_description"] is not None else r["computed_description"]
        flags = [asdict(Flag(**f)) for f in json.loads(r["flags_json"])]
        changed, included = bool(r["changed"]), bool(r["included"])
        return {"video_id": r["video_id"], "title": r["title"], "before": r["before_description"], "after": after,
                "computed": r["computed_description"], "overridden": r["override_description"] is not None,
                "changed": changed, "included": included, "flags": flags,
                "bucket": bucket_of(changed, flags, included)}


def _flags_json(flags: list[Flag]) -> str:
    return json.dumps([asdict(f) for f in flags])
