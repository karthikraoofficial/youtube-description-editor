import { ArrowRight, Shuffle } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { ApiError } from "../api/client";
import {
  type Field,
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
import { useFields } from "../api/fields";
import { type FieldInfo, fitDraft, hintFor, labelFor, operationsFor } from "../lib/fields";
import { OPERATIONS, isReady, metaOf } from "../lib/operations";
import { sampleIds } from "../lib/sample";
import { useDebounced } from "../lib/useDebounced";
import { Alert } from "../components/ui/Alert";
import { BackLink } from "../components/ui/BackLink";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { Segmented } from "../components/ui/Segmented";

const SAMPLE_SIZE = 5; // how many examples to show at once (the backend caps a Preview at sample_max)

export const INITIAL_OPERATION: Operation = OPERATIONS[0].empty;

type Props = {
  selectedIds: string[];
  field: Field;
  onFieldChange: (field: Field) => void;
  draft: Operation;
  onDraftChange: (op: Operation) => void;
  onBack: () => void;
  onReview: (changesetId: number) => void;
  /** Choices in the open review that a new review would discard. */
  atRisk: { overrides: number; excluded: number } | null;
};

export function EditBuilder({ selectedIds, field, onFieldChange, draft, onDraftChange, onBack, onReview, atRisk }: Props) {
  const createChangeset = useCreateChangeset();
  const [confirming, setConfirming] = useState(false);
  const fields = useFields();
  const meta = fields.data?.find((f) => f.field === field);
  const startReview = () =>
    createChangeset.mutate({ field, operation: draft, video_ids: selectedIds }, { onSuccess: (cs) => onReview(cs.id) });
  const wouldLose = atRisk && (atRisk.overrides > 0 || atRisk.excluded > 0) ? atRisk : null;
  const [page, setPage] = useState(0);
  // Each Operation keeps its own fields while you switch between them.
  const drafts = useRef(new Map<OperationType, Operation>([[draft.type, draft]]));
  const choose = (type: OperationType) => {
    drafts.current.set(draft.type, draft);
    const next = drafts.current.get(type) ?? metaOf(type).empty;
    onDraftChange(meta ? fitDraft(next, meta) : next);
  };
  // Switching Field keeps the Operation and its text where the new Field allows them.
  const chooseField = (next: FieldInfo) => {
    onFieldChange(next.field);
    onDraftChange(fitDraft(draft, next));
  };

  const sample = useMemo(() => sampleIds(selectedIds, page, SAMPLE_SIZE), [selectedIds, page]);
  const debounced = useDebounced(isReady(draft) ? draft : null, 300);
  const preview = usePreview(field, debounced, sample);
  // The whole-Selection summary is heavier, so it waits for a longer pause in typing.
  const summaryOp = useDebounced(isReady(draft) ? draft : null, 700);
  const summary = usePreviewSummary(field, summaryOp, selectedIds);
  const items = preview.data?.items ?? [];

  if (fields.isError) return <p className="text-danger">Couldn't load the edit options: {fields.error.message}</p>;
  if (!meta) return <p className="text-muted">Loading…</p>;

  return (
    <section>
      <PageHeader
        back={<BackLink onClick={onBack}>Back to videos</BackLink>}
        title={`Edit ${meta.plural}`}
        subtitle={`${selectedIds.length} video${selectedIds.length === 1 ? "" : "s"} selected. Nothing is written to YouTube from this screen.`}
        actions={
          <Button
            variant="primary"
            disabled={!isReady(draft) || createChangeset.isPending || selectedIds.length === 0}
            onClick={() => (wouldLose ? setConfirming(true) : startReview())}
          >
            {createChangeset.isPending ? "Preparing review…" : `Review all ${selectedIds.length}`}
            {!createChangeset.isPending && <ArrowRight aria-hidden className="size-4" />}
          </Button>
        }
      />
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
        <Alert tone="danger" role="alert" className="mb-4">
          {createChangeset.error.message}
        </Alert>
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(320px,420px)_1fr]">
        <Card className="self-start p-4 sm:p-5">
          <fieldset className="mb-5">
            <legend className="mb-2 text-sm font-semibold">What to edit</legend>
            <Segmented
              label="What to edit"
              options={(fields.data ?? []).map((f) => ({ id: f.field, label: f.label }))}
              value={field}
              onChange={(id) => {
                const next = fields.data?.find((f) => f.field === id);
                if (next) chooseField(next);
              }}
            />
          </fieldset>
          <fieldset>
            <legend className="mb-2 text-sm font-semibold">Operation</legend>
            <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Operation">
              {operationsFor(meta).map((o) => (
                <OperationChoice
                  key={o.type}
                  label={labelFor(o.type, meta)}
                  checked={draft.type === o.type}
                  onSelect={() => choose(o.type)}
                />
              ))}
            </div>
            <p className="mt-2 text-xs text-muted">{hintFor(draft.type, meta)}</p>
          </fieldset>
          <div className="mt-5">
            <OperationForm op={draft} field={meta} onChange={onDraftChange} />
          </div>
        </Card>

        <div>
          {summaryOp && summary.isError && !preview.isError && (
            <Alert tone="danger" role="alert" className="mb-4">
              Couldn't check all selected videos: {summary.error.message}
            </Alert>
          )}
          {summaryOp && summary.data && !summary.isError && <SummaryBar summary={summary.data} />}
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-semibold">
              Live preview <span className="font-normal text-muted">· {sample.length} examples</span>
            </h3>
            {selectedIds.length > SAMPLE_SIZE && (
              <Button variant="ghost" size="sm" icon={<Shuffle aria-hidden className="size-3.5" />} onClick={() => setPage((p) => p + 1)}>
                Show other examples
              </Button>
            )}
          </div>
          {debounced && !preview.isError && preview.data?.keeps_description === false && (
            <Alert tone="warn" role="alert" className="mb-3">
              This template doesn't use <code>{"{description}"}</code>, so each video's current description will be
              replaced entirely.
            </Alert>
          )}
          <PreviewBody
            hasOperation={debounced !== null}
            error={preview.error}
            isLoading={preview.isPending && preview.fetchStatus !== "idle"}
            items={items}
            limit={preview.data && { max: preview.data.max_size, unit: preview.data.size_unit }}
            field={meta}
          />
        </div>
      </div>
    </section>
  );
}

/** Totals across every selected Video, including the ones outside the sample. */
function SummaryBar({ summary }: { summary: PreviewSummary }) {
  return (
    <Card tone={summary.blocked ? "danger" : "plain"} className="mb-4 px-4 py-3 text-sm" aria-live="polite">
      {/* The backend's buckets don't overlap: changed + unchanged + blocked = selected. */}
      <span className="font-medium">All {summary.selected} selected:</span>{" "}
      {summary.changed} would change, {summary.unchanged} unchanged (no quota)
      {summary.blocked > 0 && <span className="font-medium text-danger">, {summary.blocked} blocked</span>}.
      {summary.largest_after_size > 0 && (
        <>
          {" "}
          Longest result:{" "}
          <span className={summary.largest_after_size > summary.max_size ? "font-medium text-danger" : ""}>
            {summary.largest_after_size.toLocaleString()} / {summary.max_size.toLocaleString()} {summary.size_unit}
          </span>
          .
        </>
      )}
    </Card>
  );
}

function OperationChoice({
  label,
  checked,
  disabled,
  onSelect,
}: {
  label: string;
  checked: boolean;
  disabled?: boolean;
  onSelect: () => void;
}) {
  const look = checked ? "border-accent bg-accent/10 font-medium text-accent" : "border-line bg-surface hover:bg-subtle";
  return (
    <button
      type="button"
      role="radio"
      aria-checked={checked}
      disabled={disabled}
      title={disabled ? "Coming soon" : undefined}
      onClick={onSelect}
      className={`rounded-md border px-3 py-1.5 text-sm disabled:cursor-not-allowed disabled:opacity-40 ${look}`}
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
  limit,
  field,
}: {
  hasOperation: boolean;
  error: Error | null;
  isLoading: boolean;
  items: ProposedChange[];
  limit: Limit | undefined;
  field: FieldInfo;
}) {
  if (!hasOperation) return <Panel>Fill in the operation to see how your {field.plural} would change.</Panel>;
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
        <PreviewCard key={item.video_id} item={item} limit={limit} field={field} />
      ))}
    </ul>
  );
}

type Limit = { max: number; unit: string };

function PreviewCard({ item, limit, field }: { item: ProposedChange; limit: Limit | undefined; field: FieldInfo }) {
  // "Too long" is decided by the backend's Flag, not recomputed here (ADR-0001).
  const over = item.flags.some((f) => f.code === "too_long");
  const blocked = item.flags.some((f) => f.blocking);
  return (
    <li>
      <Card className="p-4">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <span className="truncate text-sm font-medium" title={item.title}>
          {item.title}
        </span>
        <span className="flex items-center gap-2 text-xs">
          {blocked ? <Badge tone="danger">Blocked</Badge> : !item.changed && <Badge>No change</Badge>}
          <span className={`tabular-nums ${over ? "font-semibold text-danger" : "text-muted"}`}>
            {item.after_size.toLocaleString()}
            {limit ? ` / ${limit.max.toLocaleString()} ${limit.unit}` : ""}
          </span>
        </span>
      </div>
      {item.flags.map((f) => (
        <Alert key={f.code} tone="danger" size="sm" role="alert" className="mb-2">
          {f.message}
        </Alert>
      ))}
      {item.changed ? (
        <div className="grid gap-3 md:grid-cols-2">
          <TextBlock label="Before" text={item.before} />
          <TextBlock label="After" text={item.after} />
        </div>
      ) : (
        blocked && <TextBlock label={`Current ${field.singular} (left as it is)`} text={item.before} />
      )}
      </Card>
    </li>
  );
}

function TextBlock({ label, text }: { label: string; text: string }) {
  return (
    <div className="min-w-0">
      <div className="mb-1 text-xs font-medium text-muted">{label}</div>
      <pre className="max-h-56 overflow-auto whitespace-pre-wrap break-words rounded-lg border border-line bg-subtle p-2.5 font-sans text-xs leading-relaxed">
        {text || <em className="text-muted">Empty</em>}
      </pre>
    </div>
  );
}

function Panel({ children, tone }: { children: React.ReactNode; tone?: "danger" }) {
  if (tone === "danger")
    return (
      <Alert tone="danger" size="lg" role="alert">
        {children}
      </Alert>
    );
  return <Card className="p-8 text-center text-sm text-muted">{children}</Card>;
}
