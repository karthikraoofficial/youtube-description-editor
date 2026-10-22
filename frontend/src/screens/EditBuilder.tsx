import { useMemo, useRef, useState } from "react";
import { ApiError } from "../api/client";
import {
  type Operation,
  type OperationType,
  type PreviewSummary,
  type ProposedChange,
  usePreview,
  usePreviewSummary,
} from "../api/preview";
import { useCreateChangeset } from "../api/changesets";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { OperationForm } from "../components/OperationForms";
import { OPERATIONS, isReady, metaOf } from "../lib/operations";
import { sampleIds } from "../lib/sample";
import { useDebounced } from "../lib/useDebounced";

const SAMPLE_SIZE = 5; // how many examples to show at once (the backend caps a Preview at sample_max)

export const INITIAL_OPERATION: Operation = OPERATIONS[0].empty;

type Props = {
  selectedIds: string[];
  draft: Operation;
  onDraftChange: (op: Operation) => void;
  onBack: () => void;
  onReview: (changesetId: number) => void;
  /** Choices in the open review that a new review would discard. */
  atRisk: { overrides: number; excluded: number } | null;
};

export function EditBuilder({ selectedIds, draft, onDraftChange, onBack, onReview, atRisk }: Props) {
  const createChangeset = useCreateChangeset();
  const [confirming, setConfirming] = useState(false);
  const startReview = () =>
    createChangeset.mutate({ operation: draft, video_ids: selectedIds }, { onSuccess: (cs) => onReview(cs.id) });
  const wouldLose = atRisk && (atRisk.overrides > 0 || atRisk.excluded > 0) ? atRisk : null;
  const [page, setPage] = useState(0);
  // Each Operation keeps its own fields while you switch between them.
  const drafts = useRef(new Map<OperationType, Operation>([[draft.type, draft]]));
  const choose = (type: OperationType) => {
    drafts.current.set(draft.type, draft);
    onDraftChange(drafts.current.get(type) ?? metaOf(type).empty);
  };

  const sample = useMemo(() => sampleIds(selectedIds, page, SAMPLE_SIZE), [selectedIds, page]);
  const debounced = useDebounced(isReady(draft) ? draft : null, 300);
  const preview = usePreview(debounced, sample);
  // The whole-Selection summary is heavier, so it waits for a longer pause in typing.
  const summaryOp = useDebounced(isReady(draft) ? draft : null, 700);
  const summary = usePreviewSummary(summaryOp, selectedIds);
  const items = preview.data?.items ?? [];

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
        <div className="text-right">
          <button
            type="button"
            disabled={!isReady(draft) || createChangeset.isPending || selectedIds.length === 0}
            onClick={() => (wouldLose ? setConfirming(true) : startReview())}
            className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-40"
          >
            {createChangeset.isPending ? "Preparing review…" : `Review all ${selectedIds.length} →`}
          </button>
          <ConfirmDialog
            open={confirming}
            title="Start a new review?"
            confirmLabel="Start a new review"
            tone="danger"
            onCancel={() => setConfirming(false)}
            onConfirm={() => {
              setConfirming(false);
              startReview();
            }}
          >
            <p>Your current review has choices that a new review will discard:</p>
            <ul className="list-disc pl-5">
              {wouldLose && wouldLose.overrides > 0 && (
                <li>
                  {wouldLose.overrides} hand edit{wouldLose.overrides === 1 ? "" : "s"}
                </li>
              )}
              {wouldLose && wouldLose.excluded > 0 && (
                <li>
                  {wouldLose.excluded} excluded video{wouldLose.excluded === 1 ? "" : "s"}
                </li>
              )}
            </ul>
          </ConfirmDialog>
          {createChangeset.isError && (
            <p className="mt-1 text-sm text-danger" role="alert">
              {createChangeset.error.message}
            </p>
          )}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(320px,420px)_1fr]">
        <div className="rounded-xl border border-line bg-surface p-5">
          <fieldset>
            <legend className="mb-2 text-sm font-semibold">Operation</legend>
            <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Operation">
              {OPERATIONS.map((o) => (
                <OperationChoice key={o.type} label={o.label} checked={draft.type === o.type} onSelect={() => choose(o.type)} />
              ))}
            </div>
            <p className="mt-2 text-xs text-muted">{metaOf(draft.type).hint}</p>
          </fieldset>
          <div className="mt-5">
            <OperationForm op={draft} onChange={onDraftChange} />
          </div>
        </div>

        <div>
          {summaryOp && summary.isError && !preview.isError && (
            <div className="mb-4 rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger" role="alert">
              Couldn't check all selected videos: {summary.error.message}
            </div>
          )}
          {summaryOp && summary.data && !summary.isError && <SummaryBar summary={summary.data} />}
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-semibold">
              Live preview <span className="font-normal text-muted">· {sample.length} examples</span>
            </h3>
            {selectedIds.length > SAMPLE_SIZE && (
              <button type="button" onClick={() => setPage((p) => p + 1)} className="text-sm text-accent hover:underline">
                Show other examples
              </button>
            )}
          </div>
          {debounced && !preview.isError && preview.data?.keeps_description === false && (
            <p className="mb-3 rounded-md bg-warn/15 px-3 py-2 text-sm text-warn" role="alert">
              This template doesn't use <code>{"{description}"}</code>, so each video's current description will be
              replaced entirely.
            </p>
          )}
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

/** Totals across every selected Video, including the ones outside the sample. */
function SummaryBar({ summary }: { summary: PreviewSummary }) {
  return (
    <div
      className={`mb-4 rounded-xl border px-4 py-3 text-sm ${
        summary.blocked ? "border-danger/30 bg-danger/10" : "border-line bg-surface"
      }`}
      aria-live="polite"
    >
      {/* The backend's buckets don't overlap: changed + unchanged + blocked = selected. */}
      <span className="font-medium">All {summary.selected} selected:</span>{" "}
      {summary.changed} would change, {summary.unchanged} unchanged (no quota)
      {summary.blocked > 0 && <span className="font-medium text-danger">, {summary.blocked} blocked</span>}.
      {summary.largest_after_bytes > 0 && (
        <>
          {" "}
          Longest result:{" "}
          <span className={summary.largest_after_bytes > summary.max_bytes ? "font-medium text-danger" : ""}>
            {summary.largest_after_bytes.toLocaleString()} / {summary.max_bytes.toLocaleString()} bytes
          </span>
          .
        </>
      )}
    </div>
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
  const blocked = item.flags.some((f) => f.blocking);
  return (
    <li className="rounded-xl border border-line bg-surface p-4">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <span className="truncate text-sm font-medium" title={item.title}>
          {item.title}
        </span>
        <span className="flex items-center gap-2 text-xs">
          {blocked ? (
            <span className="rounded-full bg-danger/15 px-2 py-0.5 font-medium text-danger">Blocked</span>
          ) : (
            !item.changed && <span className="rounded-full bg-line px-2 py-0.5 text-muted">No change</span>
          )}
          <span className={`tabular-nums ${over ? "font-semibold text-danger" : "text-muted"}`}>
            {item.after_bytes.toLocaleString()}
            {maxBytes ? ` / ${maxBytes.toLocaleString()}` : ""} bytes
          </span>
        </span>
      </div>
      {item.flags.map((f) => (
        <p key={f.code} className="mb-2 rounded-md bg-danger/10 px-2.5 py-1.5 text-xs text-danger" role="alert">
          {f.message}
        </p>
      ))}
      {item.changed ? (
        <div className="grid gap-3 md:grid-cols-2">
          <TextBlock label="Before" text={item.before} />
          <TextBlock label="After" text={item.after} />
        </div>
      ) : (
        blocked && <TextBlock label="Current description (left as it is)" text={item.before} />
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
