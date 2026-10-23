import type { Field, Operation, OperationType, Separator, SizeUnit } from "../api/preview";
import { OPERATIONS, metaOf } from "./operations";

/** A Field as GET /api/fields describes it. The backend's registry is the only source of what a Field
 * allows (ADR-0001, ADR-0022); these helpers only arrange it for the Edit screen. */
export type FieldInfo = {
  field: Field;
  label: string;
  /** Lower case, for sentences: "each video's title". */
  singular: string;
  plural: string;
  /** A value is a single line, so it's edited in a one-line box. */
  one_line: boolean;
  operations: OperationType[];
  /** How Append and Prepend may join text; the first is the default. */
  separators: Separator[];
  max_size: number;
  size_unit: SizeUnit;
};

export const SEPARATOR_LABELS: Record<Separator, string> = {
  blank_line: "Blank line",
  newline: "New line",
  none: "Nothing",
  pipe: "“ | ”",
  dash: "“ - ”",
  space: "A space",
};

/** The Operations this Field takes, in the order the backend lists them. */
export const operationsFor = (info: FieldInfo) => info.operations.map(metaOf).filter((o) => OPERATIONS.includes(o));

/** "Append to Description" is that Operation's name; on other Fields it names the Field it appends to. */
export function labelFor(type: OperationType, info: FieldInfo): string {
  return type === "append" ? `Append to ${info.label}` : metaOf(type).label;
}

export const hintFor = (type: OperationType, info: FieldInfo) => metaOf(type).hint(info.singular);

/** "title" or "titles", for counts in sentences. */
export const countOf = (n: number, info: FieldInfo) => (n === 1 ? info.singular : info.plural);

/** The draft, changed only as much as it must be to suit the Field: same Operation and text where allowed. */
export function fitDraft(op: Operation, info: FieldInfo): Operation {
  if (!info.operations.includes(op.type)) return operationsFor(info)[0].empty;
  if ((op.type === "append" || op.type === "prepend") && !info.separators.includes(op.separator))
    return { ...op, separator: info.separators[0] };
  return op;
}
