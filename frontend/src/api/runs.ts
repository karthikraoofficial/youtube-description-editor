import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";

export type RunStatus = "pending" | "running" | "paused" | "paused_quota" | "interrupted" | "cancelled" | "completed";
export type ItemStatus = "pending" | "success" | "failed" | "stale" | "blocked" | "noop" | "cancelled";

export type RunSummary = {
  id: number;
  kind: "apply" | "restore";
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
};

export type Run = RunSummary & {
  items: RunItem[];
  log: { ts: string; level: "info" | "warning" | "error"; message: string }[];
};

export const isActive = (s: RunStatus) => s === "pending" || s === "running";
/** Stopped with videos still queued; continues only when the owner presses Resume (ADR-0007). */
export const isResumable = (s: RunStatus) => s === "paused" || s === "paused_quota" || s === "interrupted";

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

export function useRun(id: number) {
  return useQuery({
    queryKey: ["run", id],
    queryFn: () => api<Run>(`/runs/${id}`),
    // Poll while the Run is working; stop once it has finished or paused.
    refetchInterval: (q) => (q.state.data && !isActive(q.state.data.status) ? false : 1000),
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
