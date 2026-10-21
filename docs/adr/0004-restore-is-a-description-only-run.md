# Restore is a new, description-only Run

A Restore creates a new restore Run that writes the backed-up description onto the Video's *current* snippet, keeping today's title and tags. Restoring the whole Backup snippet would silently undo any title or tag changes made since then. Because it is an ordinary Run, a Restore gets its own Backup, confirm dialog, Stale guard and Resume, and can itself be restored.
