import type { ItemStatus, Run, RunSummary } from "../api/runs";
import type { Quota } from "../api/videos";

/** One message from GET /api/runs/{id}/events. */
export type RunEvent = {
  run: RunSummary;
  items: { video_id: string; status: ItemStatus; error: string | null; attempts: number }[];
  log: Run["log"];
  quota?: Quota;
};

/** Fold a live event into the full Run: statuses and counts change, item details stay, the log grows. */
export function mergeRunEvent(current: Run | undefined, event: RunEvent): Run | undefined {
  if (!current) return current;
  const updates = new Map(event.items.map((i) => [i.video_id, i]));
  return {
    ...current,
    ...event.run,
    items: current.items.map((i) => {
      const u = updates.get(i.video_id);
      return u ? { ...i, status: u.status, error: u.error, attempts: u.attempts } : i;
    }),
    // Log lines carry ids; a reconnect may resend some, so keep each once.
    log: [...current.log, ...event.log.filter((l) => !current.log.some((c) => c.id === l.id))],
  };
}
