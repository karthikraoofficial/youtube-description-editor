import type { ItemStatus, RunStatus } from "../api/runs";
import type { Tone } from "../components/ui/tone";

/** How a Run's status reads, everywhere it's shown. */
export const RUN_STATUS: Record<RunStatus, { short: string; long: string; tone: Tone }> = {
  pending: { short: "Starting", long: "Starting…", tone: "neutral" },
  running: { short: "Running", long: "Writing to YouTube…", tone: "accent" },
  paused: { short: "Paused", long: "Paused", tone: "warn" },
  paused_quota: { short: "Paused: quota", long: "Paused: daily quota used up", tone: "warn" },
  interrupted: { short: "Interrupted", long: "Interrupted", tone: "warn" },
  cancelled: { short: "Cancelled", long: "Cancelled", tone: "neutral" },
  completed: { short: "Finished", long: "Finished", tone: "ok" },
};

/** How one Video's outcome in a Run reads. */
export const ITEM_STATUS: Record<ItemStatus, { text: string; tone: Tone }> = {
  pending: { text: "Waiting", tone: "neutral" },
  success: { text: "Updated", tone: "ok" },
  failed: { text: "Failed", tone: "danger" },
  stale: { text: "Skipped: changed on YouTube", tone: "warn" },
  blocked: { text: "Blocked", tone: "danger" },
  noop: { text: "Already up to date", tone: "neutral" },
  cancelled: { text: "Cancelled", tone: "neutral" },
};
