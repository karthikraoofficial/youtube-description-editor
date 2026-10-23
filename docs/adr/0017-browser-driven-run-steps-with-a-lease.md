# The browser drives a Run in Steps, holding a lease

On a serverless host nothing runs between requests, and a function lives at most a few minutes. So a Run can't be a background thread that writes every Video. Instead, the Run screen drives it: after Apply, Restore or Resume, it calls `POST /api/runs/{id}/step` again and again. Local mode uses the same path, so there is one engine.

**A Step:**
- claims the Run for one browser tab (a random driver id kept in that tab's sessionStorage);
- fetches every pending Video fresh and saves first-time Backups, all before its first write;
- writes Videos one at a time, obeying Pause and Cancel between them (ADR-0015);
- starts no new Video once about 40 s have passed, but always does at least one;
- returns the progress, new log lines and today's Quota.

**Lease.** Every Step, and every Video within it, renews the Run's lease for two minutes. A Run whose lease runs out is no longer being driven: the tab was closed, the computer slept, or the app stopped. Before anything reads or changes Runs, such a Run stops:
- cancelled, if the owner asked for Cancel;
- paused, if they asked for Pause;
- otherwise interrupted.

It continues only through Resume (ADR-0007). Nothing writes without a tab open on it.

**One writer.** A Step is refused (409) while another tab holds a fresh lease, or while another Step on the same Run is still writing. That second case covers a duplicated tab, which copies sessionStorage, and React mounting an effect twice.
- Each Step claims the Run with its own random token. Renewing the lease, stopping, pausing and completing all happen in one UPDATE that requires that token. So a Step that outlived its lease never changes the Run after it was stopped, cancelled or resumed.
- If a Step dies part-way (its function is killed), its token stays until the lease runs out. The Run then shows Interrupted and needs Resume. Letting the token expire sooner could let two Steps write at once.
- A refused tab watches instead: it polls `GET /api/runs/{id}/progress` and tries to Step again every couple of seconds.

**Fetching every Step.** Each Step fetches the pending Videos again, so every write still sends a snippet read seconds before it (ADR-0002). That costs 1 Quota unit per 50 pending Videos per Step, which is small next to 50 units per write. The first Backup of a Video in a Run is still the one kept.

**Rejected alternatives.**
- A cron job continuing Runs needs Vercel Pro for a per-minute schedule. It would also write with no window open, which this app has never done.
- A queue service adds a second platform for one user's occasional Runs.
