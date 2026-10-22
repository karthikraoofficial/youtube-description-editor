# Skip stale videos instead of overwriting

If a Video's live description (from the fresh fetch) differs from the "before" text in the reviewed Changeset, the Run item is marked Stale and skipped. We considered two alternatives and rejected both:
- Re-applying the Operation to the new text would write something the owner never saw in review.
- Overwriting would lose edits made in YouTube Studio.

The owner can rebuild the Changeset to pick up the change.

For a restore Run (ADR-0004), the expected "before" is the text the source Run wrote. A Video edited again since then is skipped as Stale instead of being restored over the newer edit.
