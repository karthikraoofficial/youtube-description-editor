# Nothing that matters lives only in one instance's memory

On a serverless host each request may reach a different, freshly started instance of the app, and an instance can be frozen or stopped between requests. So everything the app relies on lives in the Store, and process memory is only a cache:
- **The Connection.** Every use reads the stored credentials, and whether Google has stopped accepting them, from the Store, in one query. An instance keeps the gateway it built for the credentials it last read and rebuilds it when they change. A sign-in, a Disconnect or an expiry met by one instance is seen by all of them on their next request. There is no startup step. Two races are closed:
  - An expiry is recorded by the gateway that met it, as a fingerprint of *its* credentials (`google_expired`). A request still running on an older sign-in can't expire a newer one.
  - A refreshed token is saved only if the stored credentials are still the ones refreshed (compare-and-set). A refresh can't bring back credentials after a Disconnect or overwrite a newer sign-in.
- **One Sync at a time.** A lease in the Store's `leases` table (name, holder, until) replaces the in-process lock. It's claimed in one atomic upsert that succeeds only when the earlier claim has run out (300 s). A Sync releases only its own claim, so one that outlived its lease can't free its successor's. A Sync that died mid-way frees it when the lease runs out.
- **Runs** already keep their lease in the Store (ADR-0017), and **Sessions** need only the session epoch (ADR-0019).
- **Sign-in** holds no lock at all. The web flow ends in a single quick callback, not a consent flow the server waits on.

**Settings.** A deployment is recognised by an https `YDE_PUBLIC_URL`, which is cloud mode (`Settings.cloud`). There is no separate mode variable. In cloud mode:
- the only valid Host is the public URL's host, which replaces the loopback check of local mode (ADR-0006);
- the CORS origin is the public URL itself;
- `DATABASE_URL` (Postgres) and a Vercel Blob store are required, since the disk doesn't last;
- nothing is written to `data/`.

Local mode is unchanged: SQLite and files in `data/`, the 127.0.0.1/localhost Host check, and the Vite origin.

Some per-instance caches stay, because they only cost a repeat request if lost: the gateway itself, the regex timeout cache, and the Shorts prober's rate limiter.
