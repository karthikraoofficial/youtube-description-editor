# YouTube Description Editor

Bulk-editing the descriptions and titles of one creator's own public YouTube videos, safely: every change is previewed, reviewed, backed up and reversible.

## Language

### Channel and videos

**Channel**:
The single YouTube channel the owner has connected; only its public uploads are in scope.

**Owner**:
The one person allowed to use the app: the Google account named by `YDE_OWNER_EMAIL`, which owns (or manages) the Channel. For a Channel on a YouTube Brand Account, that's the Brand Account's Google-issued address (`…@pages.plusgoogle.com`).
_Avoid_: User, admin

**Owner sign-in**:
Signing in with Google through the web flow, which both proves the Owner and makes the Connection. Any other Google account is turned away and leaves nothing behind.
_Avoid_: Login, account

**Session**:
The signed cookie that lets the Owner's browser use the deployed app for 30 days after an Owner sign-in. Separate from the Connection: the Session says who is at the browser, the Connection lets the app reach YouTube.

**Connection**:
The app's authorised link to the Channel through the Owner's Google sign-in: connected, disconnected, or expired (the sign-in can no longer be refreshed and must be redone).
_Avoid_: Login, account

**Video**:
One public upload on the Channel, as cached locally at the last Sync.
_Avoid_: Upload, item

**Short**:
A Video that YouTube serves as a Short, detected by probe, by duration fallback, or set by hand.

**Snippet**:
The YouTube metadata block holding a Video's title, description, category, tags and languages, which YouTube replaces as a whole on every update.

**Sync**:
Making the local cache match the Channel's public Videos: new ones are added, changed ones updated, and ones that are no longer public are dropped.

**Field**:
The one part of a Video's Snippet that a Changeset edits: description, title or tags (ADR-0022). Every layer handles its value as text; tags are written one per line.
_Avoid_: Property, attribute

**Fake mode**:
Running the app against an in-memory stand-in Channel instead of YouTube, so every screen can be tried without touching the real Channel.
_Avoid_: Demo mode, sandbox

**Local mode**:
The app running on the Owner's own machine (`python dev.py`): SQLite and files in `data/`, reachable only from that machine, no Session needed.

**Cloud mode**:
The app deployed on Vercel, recognised by an https `YDE_PUBLIC_URL`: Postgres for the Store, a private Blob store for Backup copies, and only the Owner's Session gets in.
_Avoid_: Production, server mode

**How It Works**:
The walkthrough a visitor sees before signing in: phone screenshots of each step, taken in Fake mode, each with a one-line caption. It's shown on the homepage above sign-in and at `/how-it-works.html`.
_Avoid_: Tour, onboarding

**Edited**:
A Video whose description this app has successfully written at least once.

### Editing

**Selection**:
The set of Videos the owner has ticked for the next Operation. It persists while filters change, and loses Videos that a Sync drops.
_Avoid_: Batch, picks

**Operation**:
A rule that turns the current value of a Video's Field into a new one: find and replace, Append to Description, prepend, template, or section.
_Avoid_: Edit, transform, rule

**Append to Description**:
The Operation that adds the owner's text after a Video's existing description, separated by a blank line, a new line or nothing. Videos that already end with that separator and text are skipped. **Prepend** is the same at the start. On titles it's called **Append to Title**, and joins with " | ", " - ", a space or nothing.

**Template**:
The Operation that rewrites the whole description from text containing Template variables. A Template that doesn't use `{description}` discards the current text.

**Template variable**:
A `{name}` placeholder that a Template fills in per Video (for example `{title}` or `{video_url}`). `{{` and `}}` stand for literal braces.

**Section**:
The part of a description between a start marker and an end marker, which a section Operation replaces or inserts.

**Preview**:
The result of applying an Operation to a sample of the selected Videos, before anything is saved.

**Changeset**:
The full set of Proposed changes for one Operation on one Field over the selected Videos, as reviewed by the owner. Only one Changeset is open for review at a time; starting a new review discards the previous one. A Changeset is open for review, discarded or applied.
_Avoid_: Draft, batch, plan

**To write / Excluded / Unchanged / Blocked**:
The four buckets every Proposed change in a Changeset falls into, exactly one each. To write: will be written. Excluded: would change, but the owner unticked it. Unchanged: nothing to do. Blocked: has a blocking Flag.

**Proposed change**:
One Video's before and after values of the Field under an Operation, with its validation Flags. A Preview shows Proposed changes for a sample; a Changeset holds one per selected Video, each with an include flag.

**Override**:
A value of the Field the owner typed by hand for one Proposed change, replacing the Operation's result. It's validated like any result; resetting it restores the Operation's result and verdict. Text identical to the Operation's result is not an Override.
_Avoid_: Manual edit

**Flag**:
A problem with one Proposed change. A blocking Flag stops that Video from being written. It's raised either because the new description breaks YouTube's rules (over 5,000 bytes, or containing `<` or `>`), or because this Video can't take the Operation at all (for example broken Section markers); in the second case the description is left as it is.

### Writing and undoing

**Run**:
One execution that writes descriptions to YouTube: an apply Run (from a Changeset) or a restore Run (from an earlier Run).
_Avoid_: Job, batch

**Run item**:
One Video's write within a Run, with the number of attempts it took. Its outcome is one of:
- pending: not reached yet.
- success: written, including a write YouTube took just before the Run stopped.
- failed: YouTube refused it, temporary errors outlasted the retries, or the Video is gone or no longer public.
- stale.
- blocked: the target failed validation at write time.
- noop: the live description already read exactly like the target, so nothing was sent.
- cancelled.

**Step**:
One request from the Run screen that writes a Run's next Videos for up to about 40 s. The browser drives a Run by sending Steps until it stops.

**Lease**:
A Run's claim by the one browser tab driving it, renewed by every Step; when it runs out, nothing is driving the Run any more.

**Paused / Interrupted**:
A Run that stopped with Videos still pending: paused (the owner pressed Pause, the app wasn't connected, the sign-in expired, the daily Quota ran out, or YouTube kept failing while fetching) or interrupted (its Lease ran out: the tab closed, the computer slept, or the app stopped). Either continues only by Resume.

**Cancelled**:
A Run the owner stopped for good: Videos not yet written are marked cancelled and can't be resumed; Videos already written stay written (and can be Restored).

**Backup**:
The full Snippet of each Video in a Run, fetched fresh from YouTube and saved before the Run's first write: in the database, and as a JSON copy in the backup archive (files locally, a private Vercel Blob store in the cloud). The first Backup of a Video in a Run is the one kept.

**Stale**:
A Run item whose live value of the Run's Field no longer matches its expected "before" text (for an apply Run, what the owner reviewed; for a restore Run, what the source Run wrote); it is skipped, not overwritten.

**Restore**:
Putting the backed-up value of the Run's Field back onto one Video or every Video of a Run, done as a new restore Run of the same Field.
_Avoid_: Undo, rollback

**Resume**:
Continuing a paused, quota-stopped or interrupted Run from its first pending Run item, only on the owner's click.

**Quota**:
The daily 10,000-unit allowance of the YouTube Data API, reset at midnight Pacific time; each description update costs 50 units, and each read costs 1.

**Quota ledger**:
The app's own record of units spent per Pacific-time day. YouTube does not report remaining Quota, so the ledger is an estimate.
