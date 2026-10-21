import { useMemo, useState } from "react";
import { type DiffRow, sideBySide, withContext } from "../lib/diff";

const CONTEXT_LINES = 2;

const LEFT_TONE: Partial<Record<DiffRow["kind"], string>> = { removed: "bg-danger/15", changed: "bg-danger/10" };
const RIGHT_TONE: Partial<Record<DiffRow["kind"], string>> = { added: "bg-ok/15", changed: "bg-ok/10" };

/** Old vs new, line by line, with changed lines highlighted and long unchanged stretches folded. */
export function DiffView({ before, after }: { before: string; after: string }) {
  const [expanded, setExpanded] = useState(false);
  const all = useMemo(() => sideBySide(before, after), [before, after]);
  const rows = useMemo(() => (expanded ? all : withContext(all, CONTEXT_LINES)), [all, expanded]);
  const folded = rows.some((r) => r.kind === "gap");

  return (
    <div className="overflow-hidden rounded-md border border-line">
      <div className="grid grid-cols-2 border-b border-line bg-bg text-xs font-semibold uppercase tracking-wide text-muted">
        <div className="px-2 py-1">Before</div>
        <div className="border-l border-line px-2 py-1">After</div>
      </div>
      <div className="max-h-96 overflow-auto font-mono text-xs leading-relaxed">
        {rows.map((r, i) => (
          <Row key={i} row={r} onExpand={() => setExpanded(true)} />
        ))}
      </div>
      {(folded || expanded) && (
        <button
          type="button"
          onClick={() => setExpanded((e) => !e)}
          className="w-full border-t border-line bg-bg py-1 text-xs text-accent hover:underline"
        >
          {expanded ? "Show changes only" : "Show the whole description"}
        </button>
      )}
    </div>
  );
}

function Row({ row, onExpand }: { row: DiffRow; onExpand: () => void }) {
  if (row.kind === "gap")
    return (
      <button
        type="button"
        onClick={onExpand}
        className="block w-full bg-line/30 py-0.5 text-center text-muted hover:text-fg"
      >
        ··· {row.hidden} unchanged line{row.hidden === 1 ? "" : "s"} ···
      </button>
    );
  return (
    <div className="grid grid-cols-2">
      <Cell side={row.left} tone={LEFT_TONE[row.kind]} sign={row.kind === "same" ? "" : "−"} />
      <Cell side={row.right} tone={RIGHT_TONE[row.kind]} sign={row.kind === "same" ? "" : "+"} border />
    </div>
  );
}

function Cell({
  side,
  tone,
  sign,
  border,
}: {
  side?: { n: number; text: string };
  tone?: string;
  sign: string;
  border?: boolean;
}) {
  return (
    <div className={`flex min-w-0 ${border ? "border-l border-line" : ""} ${side ? (tone ?? "") : "bg-line/20"}`}>
      <span className="w-9 shrink-0 select-none pr-1 text-right text-muted/70">{side?.n ?? ""}</span>
      <span className="w-3 shrink-0 select-none text-muted" aria-hidden>
        {side ? sign : ""}
      </span>
      <span className="min-w-0 whitespace-pre-wrap break-words pr-2">{side ? side.text || " " : ""}</span>
    </div>
  );
}
