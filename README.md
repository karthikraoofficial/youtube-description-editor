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
python dev.py --reload # development: restart the backend when its code changes
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

### Troubleshooting sign-in

- **"Access blocked: … has not completed the Google verification process" (Error 403: access_denied).** The Google account you signed in with isn't on the test-user list. Go to **Google Auth Platform → Audience → Test users → Add users** and add the Gmail address you sign in with.
  - If your channel is a **Brand Account**, add the personal Gmail that owns or manages it.
  - When signing in, pick that Gmail. Google then asks which channel to use: pick your channel there.
  - Changes can take a few minutes to apply.
  - The app waits up to 3 minutes for Google, then shows a timeout message; click **Sign in with Google** again after that.
- **"YouTube Data API v3 has not been used in project … or it is disabled."** Enable the API in **APIs & Services → Library**.

## Using the app

1. **Connect:** sign in with Google. The header shows your channel; **Disconnect** is top right.
2. **Sync:** on the Videos screen, click **Sync** to cache your **public** videos locally. Unlisted, private and scheduled videos are never fetched or edited. A sync costs about 2 quota units per 50 videos. Your library is read from the local cache afterwards, so browsing costs nothing.

3. **Find and select videos** in the table:
   - Sort by any column.
   - Search titles and descriptions (press `/`).
   - Filter by Short, publish date range, or edited status.
   - Tick videos, or use **Select all N matching** to select everything the current filters show.
   - Your selection is kept while you change filters. The count tells you if some selected videos are hidden by the current filters.
   - Keyboard: ↑/↓ move between rows, Space selects, Home/End and PageUp/PageDown jump.
4. **Shorts** are detected during Sync by asking YouTube whether each video opens as a Short. Each video is checked once, so the first sync takes about a minute for a few hundred videos; later syncs only check new ones.
   - If YouTube doesn't answer, the label is guessed from length (3 minutes or less), marked **≈**, and checked again next Sync.
   - To correct a label, click it or press **S** on the row. Your correction is marked **✎** and kept from then on.

5. **Edit:** click **Edit N selected →** and pick an Operation:
   - **Append to Description** adds your text after each video's existing description. Choose what separates it (blank line, new line, or nothing).
     - **Skip videos that already end with this text** is on by default, so running it twice never adds it twice, and skipped videos cost no quota.
     - Trailing spaces and blank lines are tidied up first. Nothing else in the description changes.
   - **Prepend** does the same at the start of the description.
   - **Section between markers** keeps a block, such as your links, up to date between two marker lines you choose (e.g. `[LINKS]` and `[/LINKS]`):
     - The markers stay; only the text between them is replaced.
     - Videos without the markers get the section added at the end or the start, or are left alone (your choice).
     - Videos with broken markers (a start without an end, the end first, or the section twice) are blocked rather than guessed at.
     - Markers must be one line, can't contain `<` or `>`, and can't appear inside the content.
   - **Template** rewrites the whole description from a template filled in per video:
     - Variables: `{description}` (the current text: include it to keep it), `{title}`, `{video_url}`, `{short_url}`, `{video_id}`, `{publish_date}` (YYYY-MM-DD, in UTC) and `{duration}` (e.g. `3:05` or `1:02:03`).
     - Click a variable to insert it at the cursor. Write `{{` or `}}` for a literal brace.
     - A misspelt variable or a single stray brace is reported before anything can be reviewed.
     - If the template doesn't use `{description}`, you're warned that each description will be replaced entirely.
   - **Find and replace**:
   - Plain text, or a regular expression. In a regex, `^` and `$` match at each line, and `\1` or `\g<name>` insert captured groups.
   - "Match case" is on by default.
   - A live preview shows Before and After for 5 of your selected videos. **Show other examples** moves to the next 5.
   - A summary line covers **every** selected video, not just the examples: how many would change, how many are blocked, and the longest result in bytes.
   - Each result shows its size in bytes. A video is marked **Blocked** and will never be written if:
     - its result is over 5,000 bytes,
     - its result contains `<` or `>`, or
     - it can't take the Operation, for example broken section markers.
   - Nothing is written to YouTube from this screen.

6. **Review:** click **Review all N →** to check every selected video before anything is written.
   - Tabs: **To write**, **Excluded**, **Blocked** and **Unchanged**, with counts and the estimated quota cost (50 units per video written).
   - Each video shows a side-by-side **Before / After** diff:
     - Removed lines are tinted red and added lines green.
     - Long unchanged stretches are folded; click them, or **Show the whole description**.
   - Untick a video to exclude it. Blocked and unchanged videos can't be included.
   - **Edit by hand:** rewrite one video's result yourself.
     - It's checked against YouTube's limits when you save, and can even fix a blocked video.
     - It's marked **Edited by hand**. **Reset to the operation's result** undoes it.
     - Any video you excluded stays excluded.
   - Reviews are saved locally and survive a restart and a page reload. The Videos screen shows **Continue the review →** while one is open.
   - Only one review is open at a time. If the open one has hand edits or excluded videos, **Review all** asks before starting a new review that would discard them.
   - If a Sync removed some selected videos in the meantime, the review says how many are missing.

7. **Apply:** on the Review screen, click **Apply N changes to YouTube…**.
   - A confirmation shows how many descriptions will be written and the quota cost. It warns if that's more than today's estimated remaining quota.
   - Nothing is written unless you confirm, and only the exact number you confirmed.
   - For each run, the app:
     1. Fetches every video fresh from YouTube.
     2. Saves its current snippet as a backup, in the database and as `data/backups/run-<id>.json`, before the first write.
     3. Skips videos you've changed in YouTube Studio since the review.
     4. Re-checks every new description against YouTube's limits.
     5. Sends back the title, category, tags and languages exactly as they are, replacing only the description.
   - The Run screen updates live as each video is written. It shows each video's outcome (**Updated**, **Failed**, **Skipped: changed on YouTube**, **Blocked**), a log, and today's quota. One video failing never stops the rest.
   - **Pause** stops after the video being written now; Resume continues later.
   - **Cancel…** stops for good: videos not written yet are cancelled, and videos already written stay written.
   - The header always shows today's estimated quota left. The Run screen shows the full meter with how many more description updates fit today and when it resets (midnight Pacific time).
   - Temporary YouTube errors (server errors, rate limits) are retried automatically, up to 5 tries with growing waits. Each retry appears in the log.
   - If the daily quota runs out, the sign-in expires, or the app closes mid-run, the run stops with the remaining videos still queued. The Videos screen shows a banner for it.
   - **Resume N videos…** continues it after a confirmation. Nothing resumes on its own.
   - A resumed run re-fetches the queued videos and keeps the original backups. It never writes a video twice, and a video YouTube had already accepted before a crash counts as done.
   - Updated videos show the **Edited** badge in the table.
   - **Known YouTube behaviour:** if a video has no audio language set, YouTube fills it in, usually as `en-US`, whenever the video is updated. The app doesn't send that field. The Apply dialog says how many videos this affects, and the run log notes each one (ADR-0013).

8. **History and Restore:** the **History** tab lists every run you applied or restored, newest first, with:
   - what it did (e.g. *Append to Description: "Guitar lessons…"*)
   - when it ran, its counts, and its status

   Open a run to expand any video and see its before and after.
   - **Restore all N…** puts back every description the run replaced. A written video's own **Restore** does it for just that video.
   - A restore only touches videos that run actually wrote. It writes back the description only, so today's title and tags stay as they are.
   - Videos changed on YouTube since that run are skipped, not overwritten.
   - A restore is a run like any other: confirmed, backed up first, resumable, and restorable itself.
   - A run that's still writing can't be restored until it's paused or finished.

### Quota

YouTube allows 10,000 units a day per Google Cloud project, reset at midnight Pacific time. Reads cost 1 unit, and each description update costs 50, so about 199 updates a day. The app keeps its own estimate (`GET /api/quota`). YouTube doesn't report what's left, so other apps on the same project aren't counted.

## Development

```sh
git config core.hooksPath .githooks   # enable the secret guard (this repo is public)
cd backend && .venv/Scripts/python -m pytest   # backend tests
cd frontend && npm test && npm run typecheck   # frontend tests + types
```

Workflow, rules and commands: [CLAUDE.md](CLAUDE.md). Domain language: [CONTEXT.md](CONTEXT.md). Decisions: [docs/adr/](docs/adr/).
