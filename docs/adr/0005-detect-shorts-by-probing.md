# Detect Shorts by probing youtube.com/shorts

The Data API has no "is Short" field. During Sync we send a HEAD request (without following redirects) to `https://www.youtube.com/shorts/{id}`. A 200 means it is a Short; a redirect to `/watch` means it is not. Anything else, such as a consent page, a 429 or a network error, means "couldn't tell". A duration-only rule was rejected because it mislabels short regular videos: on the owner's channel it would have mislabelled 62 of 313.

The probe is unofficial and may break, so:
- It is throttled to about 10 request starts per second across 4 workers, with a 5 s timeout and a 120 s budget per Sync. A 429 isn't retried, only treated as "couldn't tell".
- A probe result is final: it is cached on the Video and never re-probed.
- When the probe can't tell, the label falls back to "duration ≤ 180 s", records that source, and is re-probed on the next Sync until a probe succeeds. A Video with an unknown (0 s) duration stays unclassified instead of being guessed.
- The owner can override the label by hand. A manual label is final: Sync never changes it, and there is deliberately no "back to automatic" option.
