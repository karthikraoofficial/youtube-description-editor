# One Store, two databases

The Store runs on SQLite in local mode and on Postgres when `DATABASE_URL` is set (the planned Vercel deployment will use Neon). It stays raw SQL, with no ORM, and the SQL is written once:
- `?` placeholders, translated to psycopg's `%s` for Postgres;
- `ON CONFLICT` instead of `INSERT OR IGNORE/REPLACE`, and `RETURNING id` instead of `lastrowid`;
- no SQLite-only statements, and sums cast to `INTEGER` so both engines return a plain int.

Each engine has its own migrations folder (`store/migrations/sqlite/`, `store/migrations/postgres/`). Postgres starts from one baseline equal to SQLite migrations 001–006, so every new schema change needs a file in both. The Postgres migration runner takes an advisory lock, so two serverless instances cold-starting at once can't both apply it.

Postgres connections come from one pool per process, shared by every app built in it, so a unit of work reuses a connection instead of opening one. Two settings matter:
- Prepared statements are off, because Neon's pooled endpoint (PgBouncer) can't keep them.
- Each connection is checked before use, because one left idle while a serverless instance was frozen may be dead.

The connection isn't pinned to a request: the pool already avoids the cost of a new connection.

The default test run stays on SQLite: fast, with no setup. Setting `YDE_TEST_DATABASE_URL` runs the same suite on Postgres, and every test starts from emptied tables. Run it before deploying.

SQLAlchemy would hide the dialect differences, but it means rewriting every query for a gain this small. A Postgres-only setup would make local dev and tests depend on Docker or the network.
