import { useMemo, useState } from "react";
import { type DiffRow, type StackedLine, sideBySide, stacked, withContext } from "../lib/diff";
import { NARROW, useMediaQuery } from "../lib/useMediaQuery";

const CONTEXT_LINES = 2;

const LEFT_TONE: Partial<Record<DiffRow["kind"], string>> = { removed: "bg-danger/15", changed: "bg-danger/10" };
const RIGHT_TONE: Partial<Record<DiffRow["kind"], string>> = { added: "bg-ok/15", changed: "bg-ok/10" };

/** Old vs new, line by line, with changed lines highlighted and long unchanged stretches folded. */
export function DiffView({ before, after }: { before: string; after: string }) {
  const [expanded, setExpanded] = useState(false);
  const all = useMemo(() => sideBySide(before, after), [before, after]);
  const rows = useMemo(() => (expanded ? all : withContext(all, CONTEXT_LINES)), [all, expanded]);
  const folded = rows.some((r) => r.kind === "gap");
  // Two columns of text don't fit a phone: show the changes in one column instead.
  const narrow = useMediaQuery(NARROW);

  return (
    <div className="overflow-hidden rounded-md border border-line">
      {narrow ? (
        <div className="border-b border-line bg-bg px-2 py-1 text-xs font-semibold uppercase tracking-wide text-muted">
          Changes <span className="font-normal normal-case">(− before, + after)</span>
        </div>
      ) : (
        <div className="grid grid-cols-2 border-b border-line bg-bg text-xs font-semibold uppercase tracking-wide text-muted">
          <div className="px-2 py-1">Before</div>
          <div className="border-l border-line px-2 py-1">After</div>
        </div>
      )}
      <div className="max-h-96 overflow-auto font-mono text-xs leading-relaxed">
        {narrow
          ? stacked(rows).map((l, i) => <StackedRow key={i} line={l} onExpand={() => setExpanded(true)} />)
          : rows.map((r, i) => <Row key={i} row={r} onExpand={() => setExpanded(true)} />)}
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

function Gap({ hidden, onExpand }: { hidden: number; onExpand: () => void }) {
  return (
    <button type="button" onClick={onExpand} className="block w-full bg-line/30 py-0.5 text-center text-muted hover:text-fg">
      ··· {hidden} unchanged line{hidden === 1 ? "" : "s"} ···
    </button>
  );
}

const STACKED_TONE = { same: "", removed: "bg-danger/15", added: "bg-ok/15" } as const;
const STACKED_SIGN = { same: "", removed: "−", added: "+" } as const;

function StackedRow({ line, onExpand }: { line: StackedLine; onExpand: () => void }) {
  if (line.kind === "gap") return <Gap hidden={line.hidden} onExpand={onExpand} />;
  return <Cell side={line} tone={STACKED_TONE[line.kind]} sign={STACKED_SIGN[line.kind]} />;
}

function Row({ row, onExpand }: { row: DiffRow; onExpand: () => void }) {
  if (row.kind === "gap") return <Gap hidden={row.hidden} onExpand={onExpand} />;
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
