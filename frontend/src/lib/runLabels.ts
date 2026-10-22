import type { ItemStatus, RunStatus } from "../api/runs";

/** How a Run's status reads, everywhere it's shown. */
export const RUN_STATUS: Record<RunStatus, { short: string; long: string; tone: string }> = {
  pending: { short: "Starting", long: "Starting…", tone: "bg-line text-muted" },
  running: { short: "Running", long: "Writing descriptions…", tone: "bg-accent/15 text-accent" },
  paused: { short: "Paused", long: "Paused", tone: "bg-warn/15 text-warn" },
  paused_quota: { short: "Paused: quota", long: "Paused: daily quota used up", tone: "bg-warn/15 text-warn" },
  interrupted: { short: "Interrupted", long: "Interrupted", tone: "bg-warn/15 text-warn" },
  cancelled: { short: "Cancelled", long: "Cancelled", tone: "bg-line text-muted" },
  completed: { short: "Finished", long: "Finished", tone: "bg-ok/15 text-ok" },
};

/** How one Video's outcome in a Run reads. */
export const ITEM_STATUS: Record<ItemStatus, { text: string; tone: string }> = {
  pending: { text: "Waiting", tone: "bg-line text-muted" },
  success: { text: "Updated", tone: "bg-ok/15 text-ok" },
  failed: { text: "Failed", tone: "bg-danger/15 text-danger" },
  stale: { text: "Skipped: changed on YouTube", tone: "bg-warn/15 text-warn" },
  blocked: { text: "Blocked", tone: "bg-danger/15 text-danger" },
  noop: { text: "Already up to date", tone: "bg-line text-muted" },
  cancelled: { text: "Cancelled", tone: "bg-line text-muted" },
};
