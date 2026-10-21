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

_Arrives with the Connect screen ticket._

## Development

```sh
git config core.hooksPath .githooks   # enable the secret guard (this repo is public)
cd backend && .venv/Scripts/python -m pytest   # backend tests
cd frontend && npm test && npm run typecheck   # frontend tests + types
```

Workflow, rules and commands: [CLAUDE.md](CLAUDE.md). Domain language: [CONTEXT.md](CONTEXT.md). Decisions: [docs/adr/](docs/adr/).
