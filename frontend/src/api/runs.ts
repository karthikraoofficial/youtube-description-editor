import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { nextMove, type StepOutcome, tabDriverId } from "../lib/runDriver";
import { type RunEvent, mergeRunEvent } from "../lib/runEvents";
import { ApiError, api } from "./client";
import type { Field, Operation } from "./preview";

export type RunStatus = "pending" | "running" | "paused" | "paused_quota" | "interrupted" | "cancelled" | "completed";
export type ItemStatus = "pending" | "success" | "failed" | "stale" | "blocked" | "noop" | "cancelled";

export type RunSummary = {
  id: number;
  kind: "apply" | "restore";
  /** The Field this Run writes; a restore Run writes the same Field as its source. */
  field: Field;
  status: RunStatus;
  changeset_id: number | null;
  source_run_id: number | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  total: number;
  counts: Record<ItemStatus, number>;
  /** Quota units to finish the queued videos. */
  estimated_units: number;
  /** The Operation an apply Run carried out (null for a restore). */
  operation: Operation | null;
  /** A one-line description of that Operation, from the backend. */
  operation_summary: string | null;
  /** How many of its videos can be restored (written by it, with a backup). */
  restorable: number;
};

export type RunItem = {
  video_id: string;
  title: string;
  status: ItemStatus;
  error: string | null;
  before: string;
  after: string;
  has_backup: boolean;
  attempts: number;
  /** Written by this Run with a backup, so it can be restored (decided by the backend). */
  restorable: boolean;
};

export type Run = RunSummary & {
  items: RunItem[];
  log: { id: number; ts: string; level: "info" | "warning" | "error"; message: string }[];
};

export const isActive = (s: RunStatus) => s === "pending" || s === "running";
/** Stopped with videos still queued; continues only when the owner presses Resume (ADR-0007). */
export const isResumable = (s: RunStatus) => s === "paused" || s === "paused_quota" || s === "interrupted";

export const useRuns = () => useQuery({ queryKey: ["runs", "all"], queryFn: () => api<RunSummary[]>("/runs") });

/** Restore a Run's videos (all of them, or `videoIds`) as a new restore Run (ADR-0004). */
export function useRestore(runId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ confirmCount, videoIds }: { confirmCount: number; videoIds?: string[] }) =>
      api<{ id: number }>(`/runs/${runId}/restore`, {
        method: "POST",
        body: JSON.stringify({ confirm_count: confirmCount, ...(videoIds ? { video_ids: videoIds } : {}) }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["runs"] }),
  });
}

export const useUnfinishedRuns = () =>
  useQuery({ queryKey: ["runs", "unfinished"], queryFn: () => api<RunSummary[]>("/runs?unfinished=true") });

export function useResume(runId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (confirmCount: number) =>
      api<{ id: number }>(`/runs/${runId}/resume`, {
        method: "POST",
        body: JSON.stringify({ confirm_count: confirmCount }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["run", runId] });
      qc.invalidateQueries({ queryKey: ["runs"] });
    },
  });
}

/** The full Run. While it's writing, the Steps (or, when watching, progress polls) keep it current. */
export const useRun = (id: number) => useQuery({ queryKey: ["run", id], queryFn: () => api<Run>(`/runs/${id}`) });

export type DriveMode = "driving" | "watching";

/** While the Run is writing, drive it in Steps from this tab (ADR-0017). If another tab holds its lease, watch
 * that tab's progress instead. Returns which of the two this tab is doing. */
export function useRunDriver(id: number, enabled: boolean): DriveMode {
  const qc = useQueryClient();
  const [mode, setMode] = useState<DriveMode>("driving");
  useEffect(() => {
    if (!enabled) return;
    let stopped = false;
    setMode("driving");
    const driver = tabDriverId();
    // Ask only for log lines after the newest one we have, so nothing is sent twice.
    const after = () => qc.getQueryData<Run>(["run", id])?.log.at(-1)?.id ?? 0;
    const show = (event: RunEvent) => {
      qc.setQueryData<Run>(["run", id], (current) => mergeRunEvent(current, event));
      if (event.quota) qc.setQueryData(["quota"], event.quota);
    };
    const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

    (async () => {
      while (!stopped) {
        let outcome: StepOutcome;
        try {
          const event = await api<RunEvent>(`/runs/${id}/step?after_log_id=${after()}`, {
            method: "POST",
            body: JSON.stringify({ driver }),
          });
          if (stopped) return;
          show(event);
          setMode("driving");
          outcome = { kind: "ok", status: event.run.status };
        } catch (e) {
          outcome = !(e instanceof ApiError) || e.status >= 500
            ? { kind: "error" }
            : e.status === 409
              ? { kind: "conflict" }
              : { kind: "refused" };
        }
        const move = nextMove(outcome);
        if (move.action === "stop") {
          // Refused outright (gone, signed out): reload the Run so the screen shows where it really is.
          if (outcome.kind === "refused") qc.invalidateQueries({ queryKey: ["run", id] });
          return;
        }
        if (move.action === "watch") {
          setMode("watching");
          try {
            const event = await api<RunEvent>(`/runs/${id}/progress?after_log_id=${after()}`);
            if (stopped) return;
            show(event);
            if (!isActive(event.run.status)) return;
          } catch {
            // try again next round
          }
        }
        await wait(move.delayMs);
      }
    })();
    return () => {
      stopped = true;
    };
  }, [id, enabled, qc]);
  return mode;
}

export function useRunControl(runId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (action: "pause" | "cancel") => api<{ id: number }>(`/runs/${runId}/${action}`, { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["run", runId] });
      qc.invalidateQueries({ queryKey: ["runs"] });
    },
  });
}

export function useApply(changesetId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (confirmCount: number) =>
      api<{ id: number }>(`/changesets/${changesetId}/apply`, {
        method: "POST",
        body: JSON.stringify({ confirm_count: confirmCount }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["changeset"] });
      qc.invalidateQueries({ queryKey: ["videos"] });
      qc.invalidateQueries({ queryKey: ["quota"] });
    },
  });
}
