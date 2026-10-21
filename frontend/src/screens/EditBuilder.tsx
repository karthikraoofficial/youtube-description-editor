import { useMemo, useState } from "react";
import { ApiError } from "../api/client";
import { type FindReplaceOp, type Operation, type ProposedChange, usePreview } from "../api/preview";
import { sampleIds } from "../lib/sample";
import { useDebounced } from "../lib/useDebounced";

const SAMPLE_SIZE = 5; // how many examples to show at once (the backend caps a Preview at sample_max)

export const EMPTY_FIND_REPLACE: FindReplaceOp = {
  type: "find_replace",
  find: "",
  replace: "",
  regex: false,
  case_sensitive: true,
};

type Props = {
  selectedIds: string[];
  draft: Operation;
  onDraftChange: (op: Operation) => void;
  onBack: () => void;
};

/** An Operation is ready to preview once its required fields are filled in. */
function ready(op: Operation): Operation | null {
  return op.find ? op : null;
}

export function EditBuilder({ selectedIds, draft, onDraftChange, onBack }: Props) {
  const [page, setPage] = useState(0);
  const sample = useMemo(() => sampleIds(selectedIds, page, SAMPLE_SIZE), [selectedIds, page]);
  const debounced = useDebounced(ready(draft), 300);
  const preview = usePreview(debounced, sample);
  const items = preview.data?.items ?? [];
  const changedCount = items.filter((i) => i.changed).length;
  const blockedCount = items.filter((i) => i.flags.some((f) => f.blocking)).length;

  return (
    <section>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <button type="button" onClick={onBack} className="mb-1 text-sm text-accent hover:underline">
            ← Back to videos
          </button>
          <h2 className="text-lg font-semibold">Edit descriptions</h2>
          <p className="text-sm text-muted">
            {selectedIds.length} video{selectedIds.length === 1 ? "" : "s"} selected. Nothing is written to YouTube from
            this screen.
          </p>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(320px,420px)_1fr]">
        <div className="rounded-xl border border-line bg-surface p-5">
          <fieldset>
            <legend className="mb-2 text-sm font-semibold">Operation</legend>
            <div className="flex flex-wrap gap-2" role="radiogroup">
              <OperationChoice label="Find and replace" checked onSelect={() => onDraftChange(draft)} />
            </div>
          </fieldset>
          <div className="mt-5">
            <FindReplaceForm op={draft} onChange={onDraftChange} />
          </div>
        </div>

        <div>
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-semibold">
              Live preview{" "}
              <span className="font-normal text-muted">
                · {sample.length} of {selectedIds.length} selected
                {items.length > 0 && ` · ${changedCount} would change`}
                {blockedCount > 0 && ` · ${blockedCount} blocked`}
              </span>
            </h3>
            {selectedIds.length > SAMPLE_SIZE && (
              <button type="button" onClick={() => setPage((p) => p + 1)} className="text-sm text-accent hover:underline">
                Show other examples
              </button>
            )}
          </div>
          <PreviewBody
            hasOperation={debounced !== null}
            error={preview.error}
            isLoading={preview.isPending && preview.fetchStatus !== "idle"}
            items={items}
            maxBytes={preview.data?.max_bytes}
          />
        </div>
      </div>
    </section>
  );
}

function OperationChoice({ label, checked, onSelect }: { label: string; checked: boolean; onSelect: () => void }) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={checked}
      onClick={onSelect}
      className={`rounded-md border px-3 py-1.5 text-sm ${
        checked ? "border-accent bg-accent/10 font-medium text-accent" : "border-line hover:bg-line/50"
      }`}
    >
      {label}
    </button>
  );
}

const input =
  "w-full rounded-md border border-line bg-bg px-3 py-2 font-mono text-sm focus-visible:outline-2 focus-visible:outline-accent";

function FindReplaceForm({ op, onChange }: { op: FindReplaceOp; onChange: (op: FindReplaceOp) => void }) {
  const set = <K extends keyof FindReplaceOp>(k: K, v: FindReplaceOp[K]) => onChange({ ...op, [k]: v });
  return (
    <div className="space-y-4">
      <label className="block">
        <span className="mb-1 block text-sm font-medium">Find</span>
        <textarea rows={3} value={op.find} onChange={(e) => set("find", e.target.value)} className={input} />
      </label>
      <label className="block">
        <span className="mb-1 block text-sm font-medium">Replace with</span>
        <textarea
          rows={3}
          value={op.replace}
          onChange={(e) => set("replace", e.target.value)}
          placeholder="Leave empty to delete the matches"
          className={input}
        />
      </label>
      <div className="flex flex-wrap gap-x-5 gap-y-2 text-sm">
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={op.case_sensitive} onChange={(e) => set("case_sensitive", e.target.checked)} />
          Match case
        </label>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={op.regex} onChange={(e) => set("regex", e.target.checked)} />
          Regular expression
        </label>
      </div>
      {op.regex && (
        <p className="text-xs text-muted">
          Python-style regex. <code>^</code> and <code>$</code> match at each line; use <code>\1</code> or{" "}
          <code>\g&lt;name&gt;</code> in the replacement for captured groups.
        </p>
      )}
    </div>
  );
}

function PreviewBody({
  hasOperation,
  error,
  isLoading,
  items,
  maxBytes,
}: {
  hasOperation: boolean;
  error: Error | null;
  isLoading: boolean;
  items: ProposedChange[];
  maxBytes: number | undefined;
}) {
  if (!hasOperation) return <Panel>Fill in the operation to see how your descriptions would change.</Panel>;
  if (error)
    return (
      <Panel tone="danger">
        {error instanceof ApiError && error.status === 422 ? error.message : `Preview failed: ${error.message}`}
      </Panel>
    );
  if (isLoading && items.length === 0) return <Panel>Computing preview…</Panel>;
  return (
    <ul className="space-y-3">
      {items.map((item) => (
        <PreviewCard key={item.video_id} item={item} maxBytes={maxBytes} />
      ))}
    </ul>
  );
}

function PreviewCard({ item, maxBytes }: { item: ProposedChange; maxBytes: number | undefined }) {
  // "Too long" is decided by the backend's Flag, not recomputed here (ADR-0001).
  const over = item.flags.some((f) => f.code === "too_long");
  return (
    <li className="rounded-xl border border-line bg-surface p-4">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <span className="truncate text-sm font-medium" title={item.title}>
          {item.title}
        </span>
        <span className="flex items-center gap-2 text-xs">
          {!item.changed && <span className="rounded-full bg-line px-2 py-0.5 text-muted">No change</span>}
          <span className={`tabular-nums ${over ? "font-semibold text-danger" : "text-muted"}`}>
            {item.after_bytes.toLocaleString()}
            {maxBytes ? ` / ${maxBytes.toLocaleString()}` : ""} bytes
          </span>
        </span>
      </div>
      {item.flags.map((f) => (
        <p key={f.code} className="mb-2 rounded-md bg-danger/10 px-2.5 py-1.5 text-xs text-danger" role="alert">
          {f.blocking ? "Blocked: " : ""}
          {f.message}
        </p>
      ))}
      {item.changed && (
        <div className="grid gap-3 md:grid-cols-2">
          <TextBlock label="Before" text={item.before} />
          <TextBlock label="After" text={item.after} />
        </div>
      )}
    </li>
  );
}

function TextBlock({ label, text }: { label: string; text: string }) {
  return (
    <div className="min-w-0">
      <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">{label}</div>
      <pre className="max-h-56 overflow-auto whitespace-pre-wrap break-words rounded-md bg-bg p-2.5 font-sans text-xs leading-relaxed">
        {text || <em className="text-muted">Empty</em>}
      </pre>
    </div>
  );
}

function Panel({ children, tone }: { children: React.ReactNode; tone?: "danger" }) {
  return (
    <div
      className={`rounded-xl border p-8 text-center text-sm ${
        tone === "danger" ? "border-danger/30 bg-danger/10 text-danger" : "border-line bg-surface text-muted"
      }`}
      role={tone === "danger" ? "alert" : undefined}
    >
      {children}
    </div>
  );
}
