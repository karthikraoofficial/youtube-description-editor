# One open review (Changeset) at a time

Creating a Changeset discards any earlier one that's still open for review, and a discarded Changeset can no longer be edited (409). Several open reviews could each be applied, and two Runs could then race to write different descriptions to the same Videos from different "before" texts. Keeping a single open review makes "what am I about to apply?" unambiguous. The cost: going back to edit and reviewing again throws away the per-Video choices, meaning excluded Videos and hand edits (Overrides). So:
- The Edit builder asks for confirmation before starting a new review when the open one holds such choices. The warning fires when the new review is created, because that's when the discard happens, not when the Operation changes.
- The open review can be found with `GET /api/changesets/open`, so it, and the warning, survive a page reload.
