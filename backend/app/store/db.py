"""The Store: every table the app keeps, on SQLite or Postgres (ADR-0016)."""
from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any
from datetime import UTC, datetime

from app.store.engines import Engine, PostgresEngine, SqliteEngine
from app.youtube.errors import ChannelChanged

if TYPE_CHECKING:
    from app.config import Settings
    from app.shorts import ShortLabel
from app.youtube.gateway import Channel, VideoDetails

LAST_SYNC_AT = "last_sync_at"


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def open_store(settings: Settings) -> Store:
    """Postgres when the settings name a database URL, otherwise SQLite in the data dir."""
    engine = PostgresEngine(settings.database_url) if settings.database_url else SqliteEngine(settings.db_path)
    return Store(engine)


class Store:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        engine.migrate()

    @contextmanager
    def tx(self) -> Iterator[Any]:
        """One unit of work; commits on success, rolls back on error."""
        with self._engine.tx() as conn:
            yield conn

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
            # A temp table, not one placeholder per Video, so a Channel of any size fits. It's dropped in the
            # same transaction, so a pooled Postgres connection never keeps it.
            conn.execute("CREATE TEMP TABLE keep (id TEXT PRIMARY KEY)")
            conn.executemany("INSERT INTO keep VALUES (?) ON CONFLICT DO NOTHING", [(v.id,) for v in videos])
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
            conn.execute("INSERT INTO settings (key, value) VALUES (?, ?) "
                         "ON CONFLICT (key) DO UPDATE SET value = excluded.value", (LAST_SYNC_AT, now))

    def list_videos(self) -> list:
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

    def get_videos_by_ids(self, video_ids: list[str]) -> list:
        """Cached Videos in the order asked for; unknown ids are skipped."""
        if not video_ids:
            return []
        with self.tx() as conn:
            rows = conn.execute(f"SELECT * FROM videos WHERE id IN ({','.join('?' * len(video_ids))})",
                                video_ids).fetchall()
        by_id = {r["id"]: r for r in rows}
        return [by_id[i] for i in dict.fromkeys(video_ids) if i in by_id]

    def get_video(self, video_id: str) -> Any:
        with self.tx() as conn:
            return conn.execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()

    def video_count(self) -> int:
        with self.tx() as conn:
            return conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]

    def get_setting(self, key: str) -> str | None:
        with self.tx() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def set_setting(self, key: str, value: str) -> None:
        with self.tx() as conn:
            conn.execute("INSERT INTO settings (key, value) VALUES (?, ?) "
                         "ON CONFLICT (key) DO UPDATE SET value = excluded.value", (key, value))

    def delete_setting(self, key: str) -> None:
        with self.tx() as conn:
            conn.execute("DELETE FROM settings WHERE key = ?", (key,))

    # --- quota -----------------------------------------------------------------------------

    def add_quota_event(self, pt_date: str, method: str, units: int, run_id: int | None) -> None:
        with self.tx() as conn:
            conn.execute("INSERT INTO quota_events (ts, pt_date, method, units, run_id) VALUES (?, ?, ?, ?, ?)",
                         (utc_now(), pt_date, method, units, run_id))

    def quota_used(self, pt_date: str) -> int:
        with self.tx() as conn:
            return conn.execute("SELECT CAST(COALESCE(SUM(units), 0) AS INTEGER) FROM quota_events WHERE pt_date = ?",
                                (pt_date,)).fetchone()[0]
