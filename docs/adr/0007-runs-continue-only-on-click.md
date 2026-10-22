# Runs continue only on the owner's click

A Run can stop with Videos still pending:
- when YouTube reports the daily quota is used up: `paused_quota`, and today's Quota ledger is marked full;
- when the Google sign-in expires, or the app isn't connected: `paused`;
- when the app closes mid-Run: `interrupted`, set at the next startup for any Run left pending or running.

It then only continues when the owner presses Resume. Resuming automatically on startup or after the quota reset would be more convenient. But it would break the rule that nothing is written to YouTube without an explicit click.
