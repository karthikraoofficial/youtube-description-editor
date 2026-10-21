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

### Editing

**Operation**:
A rule that turns a Video's current description into a new one: find and replace, Append to Description, prepend, template, or section.
_Avoid_: Edit, transform, rule

**Append to Description**:
The Operation that adds the owner's text after a Video's existing description, separated by a blank line, a new line or nothing.

**Section**:
The part of a description between a start marker and an end marker, which a section Operation replaces or inserts.

**Preview**:
The result of applying an Operation to a sample of the selected Videos, before anything is saved.

**Changeset**:
The full set of Proposed changes for one Operation over the selected Videos, as reviewed by the owner.
_Avoid_: Draft, batch, plan

**Proposed change**:
One Video's before and after descriptions within a Changeset, with its include flag and validation Flags.

**Override**:
A description the owner typed by hand for one Proposed change, replacing the Operation's result.
_Avoid_: Manual edit

**Flag**:
A validation problem on a proposed description. A blocking Flag (over 5,000 bytes, or containing `<` or `>`) stops that Video from being written.

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
