import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { type RunEvent, mergeRunEvent } from "../lib/runEvents";
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
  log: { id: number; ts: string; level: "info" | "warning" | "error"; message: string }[];
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

/** The full Run. While it's working, live events keep it current; polling is only the fallback. */
export function useRun(id: number, live: boolean) {
  return useQuery({
    queryKey: ["run", id],
    queryFn: () => api<Run>(`/runs/${id}`),
    refetchInterval: (q) => (live || (q.state.data && !isActive(q.state.data.status)) ? false : 2000),
  });
}

/** Subscribe to the Run's Server-Sent Events while it's working. Returns whether the stream is connected. */
export function useRunEvents(id: number, enabled: boolean): boolean {
  const qc = useQueryClient();
  const [connected, setConnected] = useState(false);
  useEffect(() => {
    if (!enabled) return;
    // Start after the newest log line we already have, so nothing is sent twice.
    const known = qc.getQueryData<Run>(["run", id])?.log;
    const after = known?.length ? known[known.length - 1].id : 0;
    const source = new EventSource(`/api/runs/${id}/events?after_log_id=${after}`);
    source.onopen = () => setConnected(true);
    source.onmessage = (msg) => {
      const event = JSON.parse(msg.data) as RunEvent;
      qc.setQueryData<Run>(["run", id], (current) => mergeRunEvent(current, event));
      if (event.quota) qc.setQueryData(["quota"], event.quota);
      if (!isActive(event.run.status)) source.close();
    };
    source.onerror = () => {
      setConnected(false); // the browser retries on its own; polling covers the gap
    };
    return () => {
      source.close();
      setConnected(false);
    };
  }, [id, enabled, qc]);
  return connected;
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
