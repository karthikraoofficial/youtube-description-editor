import type { Operation, OperationType } from "../api/preview";

type Meta = {
  type: OperationType;
  label: string;
  /** What it does, given the Field's word ("description", "title"). */
  hint: (what: string) => string;
  empty: Operation;
  /** For Operations that add text: where it goes, and an example. */
  adds?: { at: "start" | "end"; placeholder: string; oneLinePlaceholder: string };
};

/** The Operations the Edit builder offers, in display order. */
export const OPERATIONS: Meta[] = [
  {
    type: "find_replace",
    label: "Find and replace",
    hint: () => "Swap text (or a regex match) everywhere it appears.",
    empty: { type: "find_replace", find: "", replace: "", regex: false, case_sensitive: true },
  },
  {
    type: "append",
    label: "Append to Description",
    hint: (what) => `Add your text after each video's existing ${what}. The rest is left untouched.`,
    empty: { type: "append", text: "", separator: "blank_line", skip_if_present: true },
    adds: { at: "end", placeholder: "e.g. Guitar lessons: https://…", oneLinePlaceholder: "e.g. Guitar Lesson" },
  },
  {
    type: "prepend",
    label: "Prepend",
    hint: (what) => `Add your text before each video's existing ${what}.`,
    empty: { type: "prepend", text: "", separator: "blank_line", skip_if_present: true },
    adds: { at: "start", placeholder: "e.g. New album out now!", oneLinePlaceholder: "e.g. Late Night Sessions" },
  },
  {
    type: "template",
    label: "Template",
    hint: () => "Rewrite each description from a template with per-video variables.",
    empty: { type: "template", template: "" },
  },
  {
    type: "section",
    label: "Section between markers",
    hint: () => "Keep a block (like your links) up to date between two marker lines you choose.",
    empty: { type: "section", start_marker: "", end_marker: "", content: "", if_missing: "append" },
  },
];

export function metaOf(type: OperationType): Meta {
  const meta = OPERATIONS.find((o) => o.type === type);
  if (!meta) throw new Error(`Unknown operation ${type}`);
  return meta;
}

/** Ready to preview once the required fields are filled in (the backend still validates). */
export function isReady(op: Operation): boolean {
  switch (op.type) {
    case "find_replace":
      return op.find.length > 0;
    case "append":
    case "prepend":
      return op.text.trim().length > 0;
    case "template":
      return op.template.trim().length > 0;
    case "section":
      return op.start_marker.trim().length > 0 && op.end_marker.trim().length > 0;
  }
}
