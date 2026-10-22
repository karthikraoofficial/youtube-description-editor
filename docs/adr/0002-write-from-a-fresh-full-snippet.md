# Write from a fresh, full snippet

`videos.update(part=snippet)` replaces the whole snippet, so any field we omit (tags, defaultLanguage) is wiped. At the start of every Run we re-fetch each target Video with `videos.list`, store that snippet as the Backup, and build the update from it. We never build the update body from the local cache, which may be out of date.

The update body is the fresh snippet's writable fields, `title`, `categoryId`, `tags`, `defaultLanguage` and `defaultAudioLanguage`, unchanged, plus the new `description`:
- Read-only fields in the fetched snippet (`publishedAt`, `thumbnails`, `localized`, `channelTitle`, …) aren't sent; YouTube ignores or rejects them.
- Optional fields the Video doesn't have are left out, not sent as empty values.

The full fetched snippet, read-only fields included, is what the Backup keeps.
