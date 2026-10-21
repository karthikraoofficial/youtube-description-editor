"""Local SQLite store. Numbered SQL files in migrations/ are applied once, in order."""
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from app.youtube.gateway import Channel

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


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
        """The store holds one Channel: the one currently connected."""
        with self.tx() as conn:
            conn.execute("DELETE FROM channel")
            conn.execute(
                "INSERT INTO channel (id, title, avatar_url, uploads_playlist_id, connected_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (channel.id, channel.title, channel.avatar_url, channel.uploads_playlist_id, utc_now()))
