import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type { Flag, Operation } from "./preview";

export type Bucket = "to_write" | "excluded" | "unchanged" | "blocked";

export type ChangesetItem = {
  video_id: string;
  title: string;
  before: string;
  after: string;
  changed: boolean;
  included: boolean;
  flags: Flag[];
  /** Decided by the backend (the single home of the bucket rules). */
  bucket: Bucket;
};

/** Buckets that never overlap: to_write + excluded + unchanged + blocked = selected. */
export type ChangesetCounts = { selected: number; to_write: number; excluded: number; unchanged: number; blocked: number };

export type Changeset = {
  id: number;
  created_at: string;
  status: "draft" | "discarded" | "applied";
  operation: Operation;
  items: ChangesetItem[];
  counts: ChangesetCounts;
  estimated_units: number;
  /** Selected ids that are no longer in the cache (e.g. dropped by a Sync). */
  missing: number;
};

const key = (id: number) => ["changeset", id];

export function useCreateChangeset() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { operation: Operation; video_ids: string[] }) =>
      api<Changeset>("/changesets", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: (cs) => qc.setQueryData(key(cs.id), cs),
  });
}

export const useChangeset = (id: number) =>
  useQuery({ queryKey: key(id), queryFn: () => api<Changeset>(`/changesets/${id}`) });

export function useSetIncluded(id: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ videoId, included }: { videoId: string; included: boolean }) =>
      api<{ item: ChangesetItem; counts: ChangesetCounts; estimated_units: number }>(
        `/changesets/${id}/items/${encodeURIComponent(videoId)}`,
        { method: "PATCH", body: JSON.stringify({ included }) },
      ),
    onSuccess: ({ item, counts, estimated_units }) =>
      qc.setQueryData<Changeset>(
        key(id),
        (cs) =>
          cs && {
            ...cs,
            counts,
            estimated_units,
            items: cs.items.map((i) => (i.video_id === item.video_id ? item : i)),
          },
      ),
  });
}
