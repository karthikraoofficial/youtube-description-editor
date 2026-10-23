# Runs continue only on the owner's click

A Run can stop with Videos still pending:
- when YouTube reports the daily quota is used up: `paused_quota`, and today's Quota ledger is marked full;
- when the owner presses Pause (ADR-0015), the Google sign-in expires, the app isn't connected, or YouTube keeps failing during the fresh fetch: `paused`;
- when nothing drives it any more (the tab closed, the computer slept, the app stopped): `interrupted`, once its lease runs out (ADR-0017).

It then only continues when the owner presses Resume. That's `POST /api/runs/{id}/resume`, with `confirm_count` equal to the number of Videos still pending. The Run is claimed atomically, so a double click can't start it twice. A resumed Run fetches its pending Videos fresh again and keeps the Backups from its first execution. Resuming automatically on startup or after the quota reset would be more convenient. But it would break the rule that nothing is written to YouTube without an explicit click.
