# YouTube Description Editor

Bulk-edit the descriptions of your own public YouTube videos from a clean local web app: pick videos, define an edit, review exact before/after diffs, apply with a backup, and restore any change in one click. It runs only on `localhost`.

> Work in progress. The PRD and tickets are in GitHub Issues.

## Safety model

- Nothing is written until you click **Apply** after the review screen and confirm the video count and quota cost.
- Every Run backs up the full snippet of each video before the first write.
- Only the description changes. The title, tags, category and languages are sent back unchanged.
- Videos edited in YouTube Studio since you reviewed them are skipped, not overwritten.
- Any Run, or a single video, can be restored.

## Prerequisites

- Python 3.11+ and Node.js 20+

## Install

```sh
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"     # macOS/Linux: .venv/bin/python
cd ../frontend
npm install
```

## Run

```sh
python dev.py          # starts backend (127.0.0.1:8000) + frontend (localhost:5173) and opens the browser
python dev.py --fake   # same, with an in-memory fake channel: no Google calls
```

Press Ctrl+C to stop both.

## Google Cloud setup

The app uses your own OAuth client, so your channel is never shared with anyone else's server.

1. Open the [Google Cloud console](https://console.cloud.google.com/) and **create a project** (any name).
2. **APIs & Services → Library**: search for **YouTube Data API v3** and click **Enable**.
3. **APIs & Services → OAuth consent screen** (Google Auth Platform):
   - User type **External**; fill in the app name and your email.
   - Leave publishing status as **Testing**.
   - Under **Audience → Test users**, add the Google account that owns your channel.
4. **APIs & Services → Credentials → Create credentials → OAuth client ID**:
   - Application type **Desktop app**.
   - Download the JSON and save it as `data/client_secret.json` in this repo. The `data/` folder is gitignored, and the pre-commit hook refuses to commit it.
5. Run `python dev.py`, click **Sign in with Google**, and approve access in the tab that opens. Google will warn that the app isn't verified: choose **Continue**, since it's your own app. The token is cached in `data/token.json`.

**Scope:** `youtube.force-ssl`, the scope required to update video metadata.

**Sign-in expires every 7 days.** Google expires refresh tokens for apps in Testing mode after 7 days. The app then shows *"Your Google sign-in expired"*; click **Sign in again**. Your history and backups are kept.

**Disconnect** (top right) revokes the token with Google and deletes `data/token.json`.

## Development

```sh
git config core.hooksPath .githooks   # enable the secret guard (this repo is public)
cd backend && .venv/Scripts/python -m pytest   # backend tests
cd frontend && npm test && npm run typecheck   # frontend tests + types
```

Workflow, rules and commands: [CLAUDE.md](CLAUDE.md). Domain language: [CONTEXT.md](CONTEXT.md). Decisions: [docs/adr/](docs/adr/).
