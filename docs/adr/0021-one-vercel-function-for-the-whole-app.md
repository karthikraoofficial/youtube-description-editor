# One Vercel function serves the whole app

Cloud mode deploys to Vercel (Hobby) as **one Python function** that serves both the API and the built React app:
- `index.py` at the repo root is Vercel's entrypoint. It builds the app from the environment, with the frontend build at `frontend/dist`.
- A root `pyproject.toml` lists the backend package, with `[tool.uv.sources]` pointing at `./backend`, plus `fastapi` by name so Vercel recognises the framework. Vercel locks and installs it with uv. A `requirements.txt` line `./backend` didn't work: Vercel turned it into a package named after the folder, `backend`, which uv refused because the package is `yde-backend`.
- `.python-version` pins Python 3.13, the version the tests run on.
- `vercel.json`:
  - runs the frontend build (`npm ci && npm run build`) before deploying;
  - lets the function run for 300 s, enough for a Sync or a Step;
  - excludes `node_modules`, sources, tests, docs and `data/` from the bundle.
- FastAPI's `app.frontend()` serves the build, and API routes always win over its files.
- Because the app has top-level middleware, Vercel keeps those files in the function rather than its CDN. One user doesn't need a CDN.
- `.vercelignore` keeps `data/`, `.env*`, virtualenvs and `node_modules` from ever being uploaded.

**Two things the tests can't see.** The backend is installed from a wheel, so its SQL migrations must be declared as package data. A container rehearsal of `index.py` against Postgres caught them missing. Without them, the app started on an empty database and every request failed. Two guards now stop that from coming back:
- the migration runner refuses to start without migrations;
- a test checks the package declares them.

**Environment.** Every setting is a Production-only Vercel environment variable:
- `YDE_PUBLIC_URL`, `YDE_OWNER_EMAIL`, `YDE_SESSION_SECRET` and `YDE_TOKEN_KEY`;
- `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`;
- `DATABASE_URL` and `BLOB_READ_WRITE_TOKEN`, added by the Neon and Blob integrations.

**Production only.** Vercel connects Marketplace stores to every environment by default, so a Preview deployment could get the production `DATABASE_URL` and run unreviewed code against it. Two guards stop that:
- The wizard connects Neon and Blob to Production only.
- The app refuses to start on Vercel (`VERCEL` is set) without an https `YDE_PUBLIC_URL`, which only Production has. Preview builds and deployments therefore fail, which is intended: this app has one environment.

The production deployment's own per-deployment URLs fail the Host check, so only the public address works.

The frontend is served by the function rather than as separate static files with a `/api/*` rewrite. This keeps one routing table, and `maxDuration` applies to the whole function. A deployment without its frontend build refuses to start.

**Setup** is a set of steps only the Owner can take: Google Cloud, Neon, Blob, Vercel. `scripts/deploy-wizard.sh` walks through them.

**Rejected alternatives.**
- Vercel Services (a separate frontend and backend) adds a second build and cross-service routing for no gain at one user.
- A backend on another host was ruled out in the PRD.
