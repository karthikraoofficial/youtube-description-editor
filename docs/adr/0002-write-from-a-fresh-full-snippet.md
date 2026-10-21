# Write from a fresh, full snippet

`videos.update(part=snippet)` replaces the whole snippet, so any field we omit (tags, defaultLanguage) is wiped. At the start of every Run we re-fetch each target Video with `videos.list`, store that snippet as the Backup, and send it back with only `description` changed. We never build the update body from the local cache, which may be out of date.
