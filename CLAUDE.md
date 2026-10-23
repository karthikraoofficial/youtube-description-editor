# YouTube Description Editor

A web app (FastAPI + React) that bulk-edits the descriptions of the Owner's public YouTube videos through the YouTube Data API v3, with preview, diff review, backup and restore. It runs in **local mode** on the Owner's machine, or in **cloud mode** on Vercel for the Owner alone (ADR-0019, ADR-0020).

## Hard rules

- **This repo is public.** Never commit `.vercel/` or `.env*`, and never commit or log anything in `data/` (including `data/deploy.env`, `client_secret.json`, `app.db`, which holds the Google sign-in, `backups/`; fake mode uses its own `data/fake/` so fake videos never mix with the real Channel's). The `.githooks/pre-commit` guard enforces this; never bypass it with `--no-verify`.
- **Never log secrets.** Google tokens, client secrets, auth codes, Blob tokens, Bearer headers and database passwords go through the redacting log filter. Never log the session secret or the token key at all. Do not print credentials objects or `Settings` fields marked `repr=False`.
- **Only the Owner gets in** (ADR-0019). With `YDE_SESSION_SECRET` set, every `/api` route but health, login and callback needs the Owner's session; the app refuses to start without `YDE_OWNER_EMAIL`. Never add an API route that skips this.
- **Writes to YouTube happen only inside the run engine**, in Steps the Run screen sends after an explicit Apply / Restore / Resume request with a matching `confirm_count` (ADR-0017). A Run nobody drives stops; it never continues on its own. No other code path may call `videos.update`: `update_snippet` is called only from `backend/app/runs.py`.
- **Always round-trip the full fresh snippet.** `videos.update(part=snippet)` replaces the whole snippet. Send back the freshly fetched title, categoryId, tags, defaultLanguage and defaultAudioLanguage unchanged; change only the description (ADR-0002).
- **Back up before the first write** of every Run, in one transaction, plus a JSON copy in the backup archive: `data/backups/` locally, a private Vercel Blob store in the cloud (ADR-0018). No copy, no write.
- **Tests never touch the real API.** Use `FakeGateway` through the gateway dependency override.
- In local mode the backend binds to `127.0.0.1` only (ADR-0006). In cloud mode only the public URL's Host is accepted, and only the Owner's session gets past sign-in (ADR-0019).
- **Nothing that matters lives only in process memory** (ADR-0020). Any request may reach a fresh serverless instance: keep state in the Store, and use a Store lease, not a thread lock, for one-at-a-time work.

## Commands

See the README for first-time install.

- `python dev.py`: start backend and frontend and open the browser
- `python dev.py --fake`: same, with the in-memory fake YouTube (no Google calls)
- `python dev.py --reload`: auto-restart the backend on code changes (off by default; uvicorn's reload can hang on Windows, so restart dev.py if the API stops answering)
- `cd backend && .venv/Scripts/python -m pytest`: backend tests (the venv lives at `backend/.venv`)
- `cd backend && YDE_TEST_DATABASE_URL=postgresql://postgres:yde@127.0.0.1:55432/yde_test .venv/Scripts/python -m pytest`: the same suite on Postgres (the README shows the Docker container). It empties every table, so never point it at production. A schema change needs a migration in both `store/migrations/sqlite/` and `store/migrations/postgres/` (ADR-0016).
- `cd frontend && npm test`: frontend unit tests; `npm run typecheck`
- `bash scripts/deploy-wizard.sh`: the Owner's guided Vercel setup and deploy (Google Cloud, Neon, Blob, env vars). Never run it for them: it needs their accounts. Redeploy with `npx vercel@latest deploy --prod`.
- Cloud mode env vars (names only; values live in Vercel and `data/deploy.env`): `YDE_PUBLIC_URL`, `YDE_OWNER_EMAIL`, `YDE_SESSION_SECRET`, `YDE_TOKEN_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `DATABASE_URL`, `BLOB_READ_WRITE_TOKEN` (ADR-0021).
- `git config core.hooksPath .githooks`: enable the secret guard (once per clone)
- `python scripts/board.py <issue> <backlog|ready|in-progress|in-review|done>`: move a ticket on the board
- `backend/.venv/Scripts/python scripts/screenshots.py out/`: screenshot every screen, light and dark, at 390, 1024 and 1280 px (every screen must fit 390 px). It needs `pip install -e "backend[screenshots]"`, `playwright install chromium`, and `python dev.py --fake` running on a fresh `data/fake/`. It refuses to run unless the app is in fake mode. Exits 1 on overflow or console errors.

## Workflow

Matt Pocock's framework: PRD issue, then tickets with native blocking links, then the Projects board, then `/implement` with `/tdd` at the seams agreed in the PRD, then `/code-review`, commit, close the ticket with the commit SHA, and move the board item. Keep CONTEXT.md, `docs/adr/`, the README and this file in sync in the same commit as the code.

## Agent skills

### Issue tracker

GitHub Issues on `karthikraoofficial/youtube-description-editor` via `gh`, plus the Projects kanban board. See `docs/agents/issue-tracker.md`.

### Triage labels

Default five-role vocabulary (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: root `CONTEXT.md` + `docs/adr/`. See `docs/agents/domain.md`.
