# Retry temporary errors; recognise videos already written

**Retries.** Server errors (5xx), 429 and the rate-limit 403s (`rateLimitExceeded`, `userRateLimitExceeded`) are retried up to 5 times per request, with 1, 2, 4 and 8 s backoff plus up to 0.5 s jitter. Every try is logged and charged to the Quota ledger. Retrying `videos.update` is safe for the description, because each try sends the identical full snippet. The cost of that safety:
- A 5xx that actually landed can cost an extra 50 units.
- A Studio edit made during the few seconds of backoff could be overwritten. That's the same exposure window as any write.

**Network errors.** The gateway keeps one HTTPS connection to Google open between requests, and it goes stale when the PC sleeps or changes network. Any network error (dropped connection, timeout, SSL or DNS failure, or a token refresh that couldn't reach Google) makes the gateway close its connections and send the request once more at once. If that also fails, the error becomes a temporary error, so a Run retries it as above and a Sync reports "Couldn't reach YouTube" instead of crashing. The quick resend isn't charged to the Quota ledger again: a dropped connection usually means the request never reached YouTube.

When retries run out on an update, that Video fails and the Run continues. When they run out on the fresh fetch, the whole Run pauses with nothing written, because nothing can be checked against a live description without it.

**Already written.** Some Videos already read exactly like the target when a Run reaches them. They are never written again:
- If the Video was backed up by an earlier execution of this Run, YouTube took our write before the app stopped and recorded it. It is recorded as success.
- Otherwise the text got there some other way, for example the owner typed it in Studio. It is a noop: not credited to the app and not marked Edited.

This is the one exception to the Stale rule (ADR-0003): a description that changed, but changed to exactly the target, is not skipped as Stale, because no write is needed either way.
