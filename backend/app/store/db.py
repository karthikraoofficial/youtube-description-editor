"""Local SQLite store. Numbered SQL files in migrations/ are applied once, in order."""
from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING
from datetime import UTC, datetime
from pathlib import Path

from app.youtube.errors import ChannelChanged

if TYPE_CHECKING:
    from app.shorts import ShortLabel
from app.youtube.gateway import Channel, VideoDetails

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
LAST_SYNC_AT = "last_sync_at"


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class Store:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._migrate()

    def _open(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        """One connection per unit of work; commits on success, rolls back on error."""
        conn = self._open()
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _migrate(self) -> None:
        conn = self._open()
        conn.isolation_level = None  # explicit BEGIN/COMMIT below
        try:
            conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY)")
            done = {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}
            for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
                if path.stem in done:
                    continue
                # executescript commits anything pending first, so the migration and its
                # bookkeeping row go in one explicit transaction inside the script.
                version = path.stem.replace("'", "")
                try:
                    conn.executescript(f"BEGIN;\n{path.read_text(encoding='utf-8')}\n"
                                       f"INSERT INTO schema_migrations VALUES ('{version}');\nCOMMIT;")
                except sqlite3.Error:
                    if conn.in_transaction:
                        conn.execute("ROLLBACK")
                    raise
        finally:
            conn.close()

    # --- channel ---------------------------------------------------------------------------

    def get_channel(self) -> Channel | None:
        with self.tx() as conn:
            row = conn.execute("SELECT id, title, avatar_url, uploads_playlist_id FROM channel").fetchone()
        return Channel(**dict(row)) if row else None

    def save_channel(self, channel: Channel) -> None:
        """The store holds one Channel: the one currently connected. Switching Channel drops the
        previous Channel's cached Videos."""
        with self.tx() as conn:
            old = conn.execute("SELECT id FROM channel").fetchone()
            if old and old["id"] != channel.id:
                conn.execute("DELETE FROM videos")
                conn.execute("DELETE FROM settings WHERE key = ?", (LAST_SYNC_AT,))
            conn.execute("DELETE FROM channel")
            conn.execute(
                "INSERT INTO channel (id, title, avatar_url, uploads_playlist_id, connected_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (channel.id, channel.title, channel.avatar_url, channel.uploads_playlist_id, utc_now()))

    # --- videos ----------------------------------------------------------------------------

    def replace_videos(self, channel_id: str, videos: list[VideoDetails]) -> None:
        """Make the cache exactly `videos`, keeping local-only fields (Short label, edited marker).
        Raises ChannelChanged if `channel_id` is no longer the connected Channel."""
        now = utc_now()
        with self.tx() as conn:
            current = conn.execute("SELECT id FROM channel").fetchone()
            if not current or current["id"] != channel_id:
                raise ChannelChanged("A different channel was connected during the sync. Sync again.")
            conn.execute("CREATE TEMP TABLE keep (id TEXT PRIMARY KEY)")
            conn.executemany("INSERT OR IGNORE INTO keep VALUES (?)", [(v.id,) for v in videos])
            conn.execute("DELETE FROM videos WHERE id NOT IN (SELECT id FROM keep)")
            conn.execute("DROP TABLE keep")
            conn.executemany(
                """INSERT INTO videos (id, title, description, category_id, tags_json, default_language,
                       default_audio_language, published_at, duration_s, privacy_status, thumbnail_url,
                       synced_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT (id) DO UPDATE SET
                       title = excluded.title, description = excluded.description,
                       category_id = excluded.category_id, tags_json = excluded.tags_json,
                       default_language = excluded.default_language,
                       default_audio_language = excluded.default_audio_language,
                       published_at = excluded.published_at, duration_s = excluded.duration_s,
                       privacy_status = excluded.privacy_status, thumbnail_url = excluded.thumbnail_url,
                       synced_at = excluded.synced_at""",
                [(v.id, v.title, v.description, v.category_id, json.dumps(list(v.tags)), v.default_language,
                  v.default_audio_language, v.published_at, v.duration_s, v.privacy_status,
                  v.thumbnail_url, now) for v in videos])
            conn.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", (LAST_SYNC_AT, now))

    def list_videos(self) -> list[sqlite3.Row]:
        with self.tx() as conn:
            return conn.execute("SELECT * FROM videos ORDER BY published_at DESC, id").fetchall()

    def videos_needing_short_check(self) -> list[tuple[str, int]]:
        """Unclassified Videos and duration-fallback guesses; probe and manual labels are final."""
        with self.tx() as conn:
            rows = conn.execute("SELECT id, duration_s FROM videos WHERE short_source IS NULL "
                                "OR short_source = 'duration'").fetchall()
        return [(r["id"], r["duration_s"]) for r in rows]

    def set_short_labels(self, labels: dict[str, "ShortLabel"]) -> None:
        with self.tx() as conn:
            conn.executemany(
                "UPDATE videos SET is_short = ?, short_source = ? WHERE id = ? "
                "AND (short_source IS NULL OR short_source != 'manual')",
                [(None if label.is_short is None else int(label.is_short), label.source, vid)
                 for vid, label in labels.items()])

    def set_short_manually(self, video_id: str, is_short: bool) -> bool:
        with self.tx() as conn:
            cur = conn.execute("UPDATE videos SET is_short = ?, short_source = 'manual' WHERE id = ?",
                               (int(is_short), video_id))
        return cur.rowcount == 1

    def get_video(self, video_id: str) -> sqlite3.Row | None:
        with self.tx() as conn:
            return conn.execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()

    def video_count(self) -> int:
        with self.tx() as conn:
            return conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]

    def get_setting(self, key: str) -> str | None:
        with self.tx() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    # --- quota -----------------------------------------------------------------------------

    def add_quota_event(self, pt_date: str, method: str, units: int, run_id: int | None) -> None:
        with self.tx() as conn:
            conn.execute("INSERT INTO quota_events (ts, pt_date, method, units, run_id) VALUES (?, ?, ?, ?, ?)",
                         (utc_now(), pt_date, method, units, run_id))

    def quota_used(self, pt_date: str) -> int:
        with self.tx() as conn:
            return conn.execute("SELECT COALESCE(SUM(units), 0) FROM quota_events WHERE pt_date = ?",
                                (pt_date,)).fetchone()[0]
