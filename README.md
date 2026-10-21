# YouTube Description Editor

Bulk-edit the descriptions of your own public YouTube videos from a clean local web app: pick videos, define an edit, review exact before/after diffs, apply with a backup, and restore any change in one click. It runs only on `localhost`.

> Work in progress. The PRD and tickets are in GitHub Issues.

## Safety model

- Nothing is written until you click **Apply** after the review screen and confirm the video count and quota cost.
- Every Run backs up the full snippet of each video before the first write.
- Only the description changes. The title, tags, category and languages are sent back unchanged.
- Videos edited in YouTube Studio since you reviewed them are skipped, not overwritten.
- Any Run, or a single video, can be restored.

## Setup

_Google Cloud setup, install and run instructions arrive with the first tickets._

## Development

```sh
git config core.hooksPath .githooks   # enable the secret guard (this repo is public)
```

Workflow, rules and commands: [CLAUDE.md](CLAUDE.md). Domain language: [CONTEXT.md](CONTEXT.md). Decisions: [docs/adr/](docs/adr/).
