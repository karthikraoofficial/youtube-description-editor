# Runs continue only on the owner's click

A Run can stop because of quota, a pause, or the app closing. It is then left as `paused_quota`, `paused` or `interrupted`, and only continues when the owner presses Resume. Resuming automatically on startup or after the quota reset would be more convenient. But it would break the rule that nothing is written to YouTube without an explicit click.
