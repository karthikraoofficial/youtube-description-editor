import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type { Flag, Operation } from "./preview";

export type Bucket = "to_write" | "excluded" | "unchanged" | "blocked";

export type ChangesetItem = {
  video_id: string;
  title: string;
  before: string;
  after: string;
  /** The Operation's own result (what a reset returns to). */
  computed: string;
  overridden: boolean;
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
  /** How many items carry a hand edit. */
  overrides: number;
};

/** Include/exclude and/or a hand edit; `override: null` resets it to the Operation's result. */
export type ItemUpdate = { included?: boolean; override?: string | null };

const key = (id: number) => ["changeset", id];

export function useCreateChangeset() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { operation: Operation; video_ids: string[] }) =>
      api<Changeset>("/changesets", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: (cs) => qc.setQueryData(key(cs.id), cs),
  });
}

/** The review still open (at most one, ADR-0012), so it survives a page reload. */
export const useOpenChangesetId = () =>
  useQuery({
    queryKey: ["changeset", "open"],
    queryFn: async () => (await api<{ id: number } | null>("/changesets/open"))?.id ?? null,
  });

export const useChangeset = (id: number | null) =>
  useQuery({
    queryKey: id === null ? ["changeset", "none"] : key(id),
    queryFn: () => api<Changeset>(`/changesets/${id}`),
    enabled: id !== null,
  });

export function useUpdateItem(id: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ videoId, update }: { videoId: string; update: ItemUpdate }) =>
      api<{ item: ChangesetItem; counts: ChangesetCounts; estimated_units: number; overrides: number }>(
        `/changesets/${id}/items/${encodeURIComponent(videoId)}`,
        { method: "PATCH", body: JSON.stringify(update) },
      ),
    onSuccess: ({ item, counts, estimated_units, overrides }) =>
      qc.setQueryData<Changeset>(
        key(id),
        (cs) =>
          cs && {
            ...cs,
            counts,
            estimated_units,
            overrides,
            items: cs.items.map((i) => (i.video_id === item.video_id ? item : i)),
          },
      ),
  });
}
