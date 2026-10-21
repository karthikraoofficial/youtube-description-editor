# YouTube Description Editor

Bulk-editing the descriptions of one creator's own public YouTube videos, safely: every change is previewed, reviewed, backed up and reversible.

## Language

### Channel and videos

**Channel**:
The single YouTube channel the owner has connected; only its public uploads are in scope.

**Connection**:
The app's authorised link to the Channel through the owner's Google sign-in: connected, disconnected, or expired (the sign-in can no longer be refreshed and must be redone).
_Avoid_: Session, login, account

**Video**:
One public upload on the Channel, as cached locally at the last Sync.
_Avoid_: Upload, item

**Short**:
A Video that YouTube serves as a Short, detected by probe, by duration fallback, or set by hand.

**Snippet**:
The YouTube metadata block holding a Video's title, description, category, tags and languages, which YouTube replaces as a whole on every update.

**Sync**:
Making the local cache match the Channel's public Videos: new ones are added, changed ones updated, and ones that are no longer public are dropped.

**Fake mode**:
Running the app against an in-memory stand-in Channel instead of YouTube, so every screen can be tried without touching the real Channel.
_Avoid_: Demo mode, sandbox

**Edited**:
A Video whose description this app has successfully written at least once.

### Editing

**Selection**:
The set of Videos the owner has ticked for the next Operation. It persists while filters change, and loses Videos that a Sync drops.
_Avoid_: Batch, picks

**Operation**:
A rule that turns a Video's current description into a new one: find and replace, Append to Description, prepend, template, or section.
_Avoid_: Edit, transform, rule

**Append to Description**:
The Operation that adds the owner's text after a Video's existing description, separated by a blank line, a new line or nothing. Videos that already end with that separator and text are skipped. **Prepend** is the same at the start.

**Template**:
The Operation that rewrites the whole description from text containing Template variables. A Template that doesn't use `{description}` discards the current text.

**Template variable**:
A `{name}` placeholder that a Template fills in per Video (for example `{title}` or `{video_url}`). `{{` and `}}` stand for literal braces.

**Section**:
The part of a description between a start marker and an end marker, which a section Operation replaces or inserts.

**Preview**:
The result of applying an Operation to a sample of the selected Videos, before anything is saved.

**Changeset**:
The full set of Proposed changes for one Operation over the selected Videos, as reviewed by the owner.
_Avoid_: Draft, batch, plan

**Proposed change**:
One Video's before and after descriptions under an Operation, with its validation Flags. A Preview shows Proposed changes for a sample; a Changeset holds one per selected Video, each with an include flag.

**Override**:
A description the owner typed by hand for one Proposed change, replacing the Operation's result.
_Avoid_: Manual edit

**Flag**:
A problem with one Proposed change. A blocking Flag stops that Video from being written. It's raised either because the new description breaks YouTube's rules (over 5,000 bytes, or containing `<` or `>`), or because this Video can't take the Operation at all (for example broken Section markers); in the second case the description is left as it is.

### Writing and undoing

**Run**:
One execution that writes descriptions to YouTube: an apply Run (from a Changeset) or a restore Run (from an earlier Run).
_Avoid_: Job, batch

**Run item**:
One Video's write within a Run, with its own status.

**Backup**:
The full Snippet of each Video in a Run, fetched fresh from YouTube and saved before the Run's first write.

**Stale**:
A Run item whose live description no longer matches the "before" text the owner reviewed; it is skipped, not overwritten.

**Restore**:
Putting the backed-up description back onto one Video or every Video of a Run, done as a new restore Run.
_Avoid_: Undo, rollback

**Resume**:
Continuing a paused, quota-stopped or interrupted Run from its first pending Run item, only on the owner's click.

**Quota**:
The daily 10,000-unit allowance of the YouTube Data API, reset at midnight Pacific time; each description update costs 50 units, and each read costs 1.

**Quota ledger**:
The app's own record of units spent per Pacific-time day. YouTube does not report remaining Quota, so the ledger is an estimate.
