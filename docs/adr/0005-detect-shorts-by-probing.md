# Detect Shorts by probing youtube.com/shorts

The Data API has no "is Short" field. At Sync we send a HEAD request (without following redirects) to `https://www.youtube.com/shorts/{id}`: a 200 means it is a Short, a redirect means it is not. The probe is unofficial and may break, so:
- It is throttled and cached per Video.
- It falls back to "duration ≤ 180 s", and records which method decided.
- It can be overridden by hand.

A duration-only rule was rejected because it mislabels short regular videos.
