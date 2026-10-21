import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api } from "./client";

export type FindReplaceOp = {
  type: "find_replace";
  find: string;
  replace: string;
  regex: boolean;
  case_sensitive: boolean;
};

/** Mirrors the backend's Operation union; the backend is the only place descriptions are computed. */
export type Operation = FindReplaceOp;

export type Flag = { code: string; message: string; blocking: boolean };

export type ProposedChange = {
  video_id: string;
  title: string;
  before: string;
  after: string;
  changed: boolean;
  after_bytes: number;
  flags: Flag[];
};

export type PreviewResult = { items: ProposedChange[]; max_bytes: number; sample_max: number };

export function usePreview(operation: Operation | null, videoIds: string[]) {
  return useQuery({
    queryKey: ["preview", operation, videoIds],
    queryFn: () =>
      api<PreviewResult>("/preview", {
        method: "POST",
        body: JSON.stringify({ operation, video_ids: videoIds }),
      }),
    enabled: operation !== null && videoIds.length > 0,
    placeholderData: keepPreviousData, // keep the last preview on screen while typing
    retry: false,
  });
}
