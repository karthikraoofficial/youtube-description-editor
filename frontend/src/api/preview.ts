import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api } from "./client";

export type FindReplaceOp = {
  type: "find_replace";
  find: string;
  replace: string;
  regex: boolean;
  case_sensitive: boolean;
};

export type Separator = "blank_line" | "newline" | "none";
type AddText = { text: string; separator: Separator; skip_if_present: boolean };
export type AppendOp = { type: "append" } & AddText;
export type PrependOp = { type: "prepend" } & AddText;

export type TemplateOp = { type: "template"; template: string };
export type SectionOp = {
  type: "section";
  start_marker: string;
  end_marker: string;
  content: string;
  if_missing: "append" | "prepend" | "skip";
};

/** Mirrors the backend's Operation union; the backend is the only place descriptions are computed. */
export type Operation = FindReplaceOp | AppendOp | PrependOp | TemplateOp | SectionOp;
export type OperationType = Operation["type"];

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

export type PreviewResult = {
  items: ProposedChange[];
  max_bytes: number;
  sample_max: number;
  /** Templates only: whether {description} is used, so the current text is kept. */
  keeps_description: boolean | null;
};

export type TemplateVariable = { name: string; help: string };

export const useTemplateVariables = () =>
  useQuery({
    queryKey: ["template-variables"],
    queryFn: () => api<TemplateVariable[]>("/template-variables"),
    staleTime: Infinity,
  });

export type PreviewSummary = {
  selected: number;
  changed: number;
  unchanged: number;
  blocked: number;
  largest_after_bytes: number;
  max_bytes: number;
};

/** Counts over every selected Video (the Preview itself only shows a sample). */
export function usePreviewSummary(operation: Operation | null, videoIds: string[]) {
  return useQuery({
    queryKey: ["preview-summary", operation, videoIds],
    queryFn: () =>
      api<PreviewSummary>("/preview/summary", {
        method: "POST",
        body: JSON.stringify({ operation, video_ids: videoIds }),
      }),
    enabled: operation !== null && videoIds.length > 0,
    placeholderData: keepPreviousData,
    retry: false,
  });
}

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
