# Block the Video, not the Operation

There are two kinds of failure:
- **The Operation itself is invalid**, such as a bad regex or an unknown Template variable. That's an `OperationError`: the whole Preview, summary or Changeset fails with a message, because no Video could be processed.
- **One Video can't take a valid Operation**, such as Section markers that are missing an end, out of order or duplicated. That's a `VideoProblem`: that Video gets a blocking Flag and is left unchanged, and every other Video proceeds.

We rejected guessing (for example, appending a fresh section when a start marker has no end), because a guess can quietly duplicate or destroy text. We also rejected failing everything, because one odd old description shouldn't stop a bulk edit.

The whole-Selection summary reports buckets that don't overlap: changed (would be written), unchanged (nothing to do, costs no quota) and blocked (any blocking Flag). They always add up to the number of selected Videos. A Changeset splits "changed" further into To write and Excluded (unticked by the owner). The backend is the single place these rules live (`changesets.bucket_of`); the UI only shows the bucket it's given.
