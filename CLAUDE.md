# YouTube Description Editor

A local-only web app (FastAPI + React) that bulk-edits the descriptions of the owner's public YouTube videos through the YouTube Data API v3, with preview, diff review, backup and restore.

## Hard rules

- **This repo is public.** Never commit or log anything in `data/` (`client_secret.json`, `token.json`, `app.db`, `backups/`; fake mode uses its own `data/fake/` so fake videos never mix with the real Channel's). The `.githooks/pre-commit` guard enforces this; never bypass it with `--no-verify`.
- **Never log secrets.** Tokens, client secrets and auth codes go through the redacting log filter. Do not print credentials objects.
- **Writes to YouTube happen only inside the run engine**, in Steps the Run screen sends after an explicit Apply / Restore / Resume request with a matching `confirm_count` (ADR-0017). A Run nobody drives stops; it never continues on its own. No other code path may call `videos.update`: `update_snippet` is called only from `backend/app/runs.py`.
- **Always round-trip the full fresh snippet.** `videos.update(part=snippet)` replaces the whole snippet. Send back the freshly fetched title, categoryId, tags, defaultLanguage and defaultAudioLanguage unchanged; change only the description (ADR-0002).
- **Back up before the first write** of every Run, in one transaction, plus a JSON copy in `data/backups/`.
- **Tests never touch the real API.** Use `FakeGateway` through the gateway dependency override.
- The backend binds to `127.0.0.1` only.

## Commands

See the README for first-time install.

- `python dev.py`: start backend and frontend and open the browser
- `python dev.py --fake`: same, with the in-memory fake YouTube (no Google calls)
- `python dev.py --reload`: auto-restart the backend on code changes (off by default; uvicorn's reload can hang on Windows, so restart dev.py if the API stops answering)
- `cd backend && .venv/Scripts/python -m pytest`: backend tests (the venv lives at `backend/.venv`)
- `cd backend && YDE_TEST_DATABASE_URL=postgresql://postgres:yde@127.0.0.1:55432/yde_test .venv/Scripts/python -m pytest`: the same suite on Postgres (the README shows the Docker container). It empties every table, so never point it at production. A schema change needs a migration in both `store/migrations/sqlite/` and `store/migrations/postgres/` (ADR-0016).
- `cd frontend && npm test`: frontend unit tests; `npm run typecheck`
- `git config core.hooksPath .githooks`: enable the secret guard (once per clone)
- `python scripts/board.py <issue> <backlog|ready|in-progress|in-review|done>`: move a ticket on the board
- `backend/.venv/Scripts/python scripts/screenshots.py out/`: screenshot every screen, light and dark, at 1024 and 1280 px. It needs `pip install -e "backend[screenshots]"`, `playwright install chromium`, and `python dev.py --fake` running on a fresh `data/fake/`. Exits 1 on overflow or console errors.

## Workflow

Matt Pocock's framework: PRD issue, then tickets with native blocking links, then the Projects board, then `/implement` with `/tdd` at the seams agreed in the PRD, then `/code-review`, commit, close the ticket with the commit SHA, and move the board item. Keep CONTEXT.md, `docs/adr/`, the README and this file in sync in the same commit as the code.

## Agent skills

### Issue tracker

GitHub Issues on `karthikraoofficial/youtube-description-editor` via `gh`, plus the Projects kanban board. See `docs/agents/issue-tracker.md`.

### Triage labels

Default five-role vocabulary (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: root `CONTEXT.md` + `docs/adr/`. See `docs/agents/domain.md`.
