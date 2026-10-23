import { describe, expect, it } from "vitest";
import type { Run } from "../api/runs";
import { mergeRunEvent } from "./runEvents";

const run: Run = {
  id: 1,
  kind: "apply",
  field: "description",
  status: "running",
  changeset_id: 3,
  source_run_id: null,
  created_at: "t0",
  started_at: "t1",
  finished_at: null,
  total: 2,
  estimated_units: 100,
  operation: null,
  operation_summary: null,
  restorable: 0,
  counts: { pending: 2, success: 0, failed: 0, stale: 0, blocked: 0, noop: 0, cancelled: 0 },
  items: [
    { video_id: "a", title: "A", status: "pending", error: null, before: "x", after: "y", has_backup: true, attempts: 0, restorable: false },
    { video_id: "b", title: "B", status: "pending", error: null, before: "x", after: "y", has_backup: true, attempts: 0, restorable: false },
  ],
  log: [{ id: 1, ts: "t1", level: "info", message: "Run created" }],
};

describe("mergeRunEvent", () => {
  it("updates statuses and counts, keeps item details, and appends new log lines", () => {
    const merged = mergeRunEvent(run, {
      run: { ...run, status: "running", counts: { ...run.counts, pending: 1, success: 1 } },
      items: [
        { video_id: "a", status: "success", error: null, attempts: 1 },
        { video_id: "b", status: "pending", error: null, attempts: 0 },
      ],
      log: [
        { id: 1, ts: "t1", level: "info", message: "Run created" }, // resent after a reconnect
        { id: 2, ts: "t2", level: "info", message: "Updated: A" },
      ],
    })!;
    expect(merged.items.map((i) => [i.video_id, i.status, i.title, i.after])).toEqual([
      ["a", "success", "A", "y"],
      ["b", "pending", "B", "y"],
    ]);
    expect(merged.counts.success).toBe(1);
    expect(merged.log.map((l) => l.message)).toEqual(["Run created", "Updated: A"]);
  });

  it("does nothing until the full run has loaded", () => {
    expect(mergeRunEvent(undefined, { run, items: [], log: [] })).toBeUndefined();
  });
});
