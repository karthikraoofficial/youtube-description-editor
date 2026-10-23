import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, api } from "./client";

export type Video = {
  id: string;
  title: string;
  description: string;
  tags: string[];
  published_at: string;
  duration_s: number;
  thumbnail_url: string | null;
  is_short: boolean | null;
  short_source: "probe" | "duration" | "manual" | null;
  edited: boolean;
};

export type SyncStatus = { last_sync_at: string | null; video_count: number };
export type Quota = {
  date_pt: string;
  used: number;
  limit: number;
  remaining: number;
  resets_at: string;
  /** Units one description update costs. */
  update_units: number;
};

export const useVideos = () => useQuery({ queryKey: ["videos"], queryFn: () => api<Video[]>("/videos") });
export const useSyncStatus = () =>
  useQuery({ queryKey: ["sync", "status"], queryFn: () => api<SyncStatus>("/sync/status") });
export const useQuota = () => useQuery({ queryKey: ["quota"], queryFn: () => api<Quota>("/quota") });

export function useOverrideShort() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, isShort }: { id: string; isShort: boolean }) =>
      api<Video>(`/videos/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify({ is_short: isShort }) }),
    onSuccess: (video) =>
      qc.setQueryData<Video[]>(["videos"], (old) => old?.map((v) => (v.id === video.id ? video : v))),
  });
}

export function useSync() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<SyncStatus>("/sync", { method: "POST" }),
    onSuccess: (status) => qc.setQueryData(["sync", "status"], status),
    onError: (err) => {
      // 401 means the sign-in expired: refresh auth so the Connect screen takes over.
      if (err instanceof ApiError && err.status === 401) qc.invalidateQueries({ queryKey: ["auth"] });
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ["videos"] });
      qc.invalidateQueries({ queryKey: ["quota"] });
    },
  });
}
