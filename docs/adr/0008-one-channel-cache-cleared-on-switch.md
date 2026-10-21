# One Channel's cache, cleared when a different Channel connects

The local store holds exactly one Channel's Videos. Connecting a different Channel deletes the cached Videos, including local-only data: Short overrides and edited markers. Keeping several Channels' caches side by side would mean scoping every table and query by Channel, for a single-owner tool that edits one channel. Run history and Backups are not affected: they record their own Video ids and snapshots. A Sync that finishes after a Channel switch is discarded rather than written under the new Channel.
