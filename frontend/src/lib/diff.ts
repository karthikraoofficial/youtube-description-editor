/**
 * Side-by-side line diff for the Review screen. Display only: the backend computes descriptions (ADR-0001).
 */
export type Side = { n: number; text: string };
export type DiffRow =
  | { kind: "same" | "changed"; left: Side; right: Side }
  | { kind: "removed"; left: Side; right?: undefined }
  | { kind: "added"; left?: undefined; right: Side }
  | { kind: "gap"; hidden: number; left?: undefined; right?: undefined };

type Op = { op: "same" | "del" | "ins"; text: string };

/** Longest-common-subsequence edit script over lines. */
function editScript(a: string[], b: string[]): Op[] {
  const n = a.length;
  const m = b.length;
  const lcs: Uint32Array[] = Array.from({ length: n + 1 }, () => new Uint32Array(m + 1));
  for (let i = n - 1; i >= 0; i--)
    for (let j = m - 1; j >= 0; j--)
      lcs[i][j] = a[i] === b[j] ? lcs[i + 1][j + 1] + 1 : Math.max(lcs[i + 1][j], lcs[i][j + 1]);
  const ops: Op[] = [];
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) {
      ops.push({ op: "same", text: a[i] });
      i++;
      j++;
    } else if (lcs[i + 1][j] >= lcs[i][j + 1]) ops.push({ op: "del", text: a[i++] });
    else ops.push({ op: "ins", text: b[j++] });
  }
  while (i < n) ops.push({ op: "del", text: a[i++] });
  while (j < m) ops.push({ op: "ins", text: b[j++] });
  return ops;
}

/** An empty description has no lines (not one empty line). */
const linesOf = (text: string) => (text === "" ? [] : text.split("\n"));

/** Identical leading/trailing lines are matched directly, so appends and prepends stay linear. */
function trimmedScript(a: string[], b: string[]): Op[] {
  let head = 0;
  while (head < a.length && head < b.length && a[head] === b[head]) head++;
  let tail = 0;
  while (tail < a.length - head && tail < b.length - head && a[a.length - 1 - tail] === b[b.length - 1 - tail]) tail++;
  const same = (text: string): Op => ({ op: "same", text });
  return [
    ...a.slice(0, head).map(same),
    ...editScript(a.slice(head, a.length - tail), b.slice(head, b.length - tail)),
    ...a.slice(a.length - tail).map(same),
  ];
}

export function sideBySide(before: string, after: string): DiffRow[] {
  const ops = trimmedScript(linesOf(before), linesOf(after));
  const rows: DiffRow[] = [];
  let ln = 0;
  let rn = 0;
  let dels: string[] = [];
  let ins: string[] = [];

  // Within a block of edits, pair removed and added lines in order; leftovers stay removed/added.
  const flush = () => {
    const paired = Math.min(dels.length, ins.length);
    for (let k = 0; k < paired; k++)
      rows.push({ kind: "changed", left: { n: ++ln, text: dels[k] }, right: { n: ++rn, text: ins[k] } });
    for (const text of dels.slice(paired)) rows.push({ kind: "removed", left: { n: ++ln, text } });
    for (const text of ins.slice(paired)) rows.push({ kind: "added", right: { n: ++rn, text } });
    dels = [];
    ins = [];
  };

  for (const o of ops) {
    if (o.op === "same") {
      flush();
      rows.push({ kind: "same", left: { n: ++ln, text: o.text }, right: { n: ++rn, text: o.text } });
    } else if (o.op === "del") dels.push(o.text);
    else ins.push(o.text);
  }
  flush();
  return rows;
}

/** Keep changed rows plus `context` unchanged lines around them; fold longer unchanged runs into gaps. */
export function withContext(rows: DiffRow[], context: number): DiffRow[] {
  const keep = rows.map(() => false);
  rows.forEach((r, i) => {
    if (r.kind === "same") return;
    for (let k = Math.max(0, i - context); k <= Math.min(rows.length - 1, i + context); k++) keep[k] = true;
  });
  const out: DiffRow[] = [];
  let run: DiffRow[] = [];
  const flushRun = () => {
    if (run.length >= 2) out.push({ kind: "gap", hidden: run.length });
    else out.push(...run); // folding a single line saves nothing
    run = [];
  };
  rows.forEach((r, i) => {
    if (keep[i]) {
      flushRun();
      out.push(r);
    } else run.push(r);
  });
  flushRun();
  return out;
}

export type StackedLine =
  | { kind: "same" | "removed" | "added"; n: number; text: string }
  | { kind: "gap"; hidden: number };

/** The same diff in one column for narrow screens: an edited line shows as removed, then added. */
export function stacked(rows: DiffRow[]): StackedLine[] {
  return rows.flatMap((r): StackedLine[] => {
    switch (r.kind) {
      case "gap":
        return [r];
      case "same":
        return [{ kind: "same", n: r.right.n, text: r.right.text }];
      case "removed":
        return [{ kind: "removed", ...r.left }];
      case "added":
        return [{ kind: "added", ...r.right }];
      case "changed":
        return [
          { kind: "removed", ...r.left },
          { kind: "added", ...r.right },
        ];
    }
  });
}
