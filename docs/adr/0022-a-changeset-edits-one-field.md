# A Changeset edits one Field

The app started out editing only descriptions. To bulk-edit titles and tags as well, a Changeset now edits exactly one **Field** of the Snippet: description, title or tags. It never edits several at once. The Field is stored on the changeset, and again on every Run. A restore Run copies the Field of the Run it restores, so a Restore of a Restore never has to follow a chain of Runs to find it.

Everything downstream handles the Field's value as plain text: Preview, the Review diff, an Override, the Stale check, the write and Restore. Tags use one tag per line as their text, which is turned back into a list only when it's sent to YouTube. Diffs, hand edits and Stale comparisons therefore work the same for every Field, with no per-Field code outside one registry (`app/domain/fields.py`). That registry holds each Field's snippet key, cache column, conversions and validation. The `*_description` columns in `changeset_items` and `run_items` keep their names but hold the Field's value; renaming them would touch every query for no gain.

This extends ADR-0002 and ADR-0004 rather than replacing them. The update body is still the fresh snippet's writable fields, sent back unchanged, but now with only the Run's Field replaced. A Restore puts back only that Field from the Backup and keeps the rest of today's snippet. One Field per Changeset keeps the review, the confirm count and the Quota cost (still one `videos.update` per Video) easy to reason about. Editing two Fields means two Changesets and two Runs.

Template and Section stay description-only, because they're about multi-line text. The API refuses them for any other Field.

The Edit screen reads each Field's Operations, separators, limit and wording from `GET /api/fields`, which serves the registry, so the frontend never keeps its own copy of these rules (ADR-0001).
