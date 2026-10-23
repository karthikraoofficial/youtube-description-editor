# Pause and Cancel act between Videos, and a Cancel always wins

The owner's Pause or Cancel on a writing Run is stored as a request (`runs.control`). The engine acts on it before starting the next Video, never during a write, so no Video is ever left half-handled. Pause leaves the rest pending, to Resume later (ADR-0007). Cancel marks the rest cancelled for good. A Run that's already stopped (paused, out of quota, interrupted) can be cancelled straight away.

If the Run stops for another reason while a Cancel is waiting, such as the quota running out or the sign-in expiring, the Cancel wins and the Run ends cancelled, not paused. Otherwise the owner's explicit decision would be silently lost and the Run would look resumable. A request that arrives during the last Video has nothing left to act on, and the log says so.

A Pause or Cancel asked for while no tab is driving the Run takes effect when its lease runs out (ADR-0017). Each Step, and each progress poll, returns the summary, each item's outcome and only the log lines after the newest one the tab already has, by id. A retried Step never duplicates the log.
