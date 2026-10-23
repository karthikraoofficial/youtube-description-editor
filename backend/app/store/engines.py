"""The two databases the Store can run on (ADR-0016): SQLite in local mode, Postgres when DATABASE_URL is set.

Both hand the Store a connection with sqlite3's small API (execute / executemany returning a cursor with
fetchone, fetchall, rowcount and iteration; rows readable by column name or index), so the Store's SQL is
written once. That SQL must run on both engines: `?` placeholders, ON CONFLICT, RETURNING, no SQLite-only
statements. Each engine has its own migrations folder, applied once each, in order.
"""
from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator, Sequence
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path
from typing import Any, Protocol

MIGRATIONS_ROOT = Path(__file__).parent / "migrations"
MIGRATION_LOCK_KEY = 0x59444500  # any constant bigint, the same in every instance


def _migrations(dialect: str) -> list[Path]:
    """The engine's migrations, in order. None at all means the package was installed without them; starting on
    an empty database would only fail later, less clearly."""
    files = sorted((MIGRATIONS_ROOT / dialect).glob("*.sql"))
    if not files:
        raise RuntimeError(f"No {dialect} migrations found in {MIGRATIONS_ROOT}: the backend package was installed "
                           "without its SQL files.")
    return files


class Engine(Protocol):
    def tx(self) -> AbstractContextManager[Any]:
        """One unit of work: commits on success, rolls back on error."""

    def migrate(self) -> None: ...


# --- SQLite ---------------------------------------------------------------------------------------


class SqliteEngine:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

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

    def migrate(self) -> None:
        conn = self._open()
        conn.isolation_level = None  # explicit BEGIN/COMMIT below
        try:
            conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY)")
            done = {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}
            for path in _migrations("sqlite"):
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


# --- Postgres -------------------------------------------------------------------------------------


class Row:
    """A result row readable like sqlite3.Row: by column name, by index, and through dict(row)."""

    __slots__ = ("_values", "_index")

    def __init__(self, values: Sequence[Any], index: dict[str, int]) -> None:
        self._values = values
        self._index = index

    def __getitem__(self, key: str | int) -> Any:
        return self._values[self._index[key] if isinstance(key, str) else key]

    def keys(self) -> list[str]:
        return list(self._index)

    def __iter__(self):
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)


def _row_factory(cursor):
    index = {col.name: i for i, col in enumerate(cursor.description or [])}
    return lambda values: Row(values, index)


def to_pyformat(sql: str) -> str:
    """`?` placeholders to psycopg's `%s`, leaving quoted text and `--` comments alone; every literal `%`
    becomes `%%`, which psycopg reads back as `%`."""
    out: list[str] = []
    quote: str | None = None  # the quote we're inside, or "--" inside a comment
    for i, ch in enumerate(sql):
        if quote == "--":
            if ch == "\n":
                quote = None
        elif quote:
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
        elif ch == "-" and sql.startswith("--", i):
            quote = "--"
        elif ch == "?":
            out.append("%s")
            continue
        out.append("%%" if ch == "%" else ch)
    return "".join(out)


class _PgConnection:
    """The sqlite3-shaped face of a psycopg connection."""

    def __init__(self, conn) -> None:
        self._conn = conn

    def execute(self, sql: str, params: Sequence[Any] = ()):
        cur = self._conn.cursor(row_factory=_row_factory)
        if params:
            cur.execute(to_pyformat(sql), tuple(params))
        else:
            cur.execute(sql)  # no parameters: psycopg leaves `%` alone
        return cur

    def executemany(self, sql: str, seq: Sequence[Sequence[Any]]):
        cur = self._conn.cursor(row_factory=_row_factory)
        cur.executemany(to_pyformat(sql), [tuple(p) for p in seq])
        return cur


# One pool per database URL per process: every app built in this process (tests, a warm serverless
# instance) shares it, so connections are reused instead of opened per unit of work.
_pools: dict[str, Any] = {}
_pools_lock = threading.Lock()


def _pool(url: str):
    from psycopg_pool import ConnectionPool  # imported only when Postgres is used

    with _pools_lock:
        pool = _pools.get(url)
        if pool is None:
            # prepare_threshold=None: Neon's pooled endpoint (PgBouncer) can't keep prepared statements.
            # check: a connection left idle while a serverless instance was frozen may be dead; replace it.
            pool = ConnectionPool(url, min_size=1, max_size=8, timeout=20, open=True,
                                  kwargs={"prepare_threshold": None}, check=ConnectionPool.check_connection,
                                  name="yde")
            _pools[url] = pool
        return pool


class PostgresEngine:
    def __init__(self, url: str) -> None:
        self._url = url

    @contextmanager
    def tx(self) -> Iterator[_PgConnection]:
        """A pooled connection for one unit of work; the pool commits on success and rolls back on error."""
        with _pool(self._url).connection() as conn:
            yield _PgConnection(conn)

    def migrate(self) -> None:
        with _pool(self._url).connection() as conn:
            # Two instances cold-starting at once must not both apply a migration.
            conn.execute("SELECT pg_advisory_xact_lock(%s)", (MIGRATION_LOCK_KEY,))
            conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY)")
            done = {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}
            for path in _migrations("postgres"):
                if path.stem not in done:
                    conn.execute(path.read_text(encoding="utf-8"))
                    conn.execute("INSERT INTO schema_migrations VALUES (%s)", (path.stem,))
