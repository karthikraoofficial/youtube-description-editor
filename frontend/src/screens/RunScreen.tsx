import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  type RunStatus,
  isActive,
  isResumable,
  type RunItem,
  useRestore,
  useResume,
  useRun,
  useRunControl,
  useRunDriver,
} from "../api/runs";
import { useQuota } from "../api/videos";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { DiffView } from "../components/DiffView";
import { QuotaMeter } from "../components/QuotaMeter";
import { useFields } from "../api/fields";
import { countOf } from "../lib/fields";
import { formatDateTime } from "../lib/format";
import { ChevronDown, ChevronRight, Pause, Play, RotateCcw } from "lucide-react";
import { Alert } from "../components/ui/Alert";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { ITEM_STATUS, RUN_STATUS } from "../lib/runLabels";

const RESUME_HINT: Partial<Record<RunStatus, string>> = {
  paused: "Paused because the app wasn't connected, the Google sign-in expired, or YouTube kept failing.",
  paused_quota: "Paused because YouTube's daily quota ran out.",
  interrupted: "Interrupted because no window was running it any more (it was closed, or the computer slept).",
};

type RestoreChoice = { count: number; label: string; videoIds?: string[] };

export function RunScreen({
  runId,
  onDone,
  doneLabel,
  onOpenRun,
}: {
  runId: number;
  onDone: () => void;
  /** Where "back" goes, e.g. "Back to videos" or "Back to history". */
  doneLabel: string;
  onOpenRun: (id: number) => void;
}) {
  const restore = useRestore(runId);
  const [restoring, setRestoring] = useState<RestoreChoice | null>(null);
  const run = useRun(runId);
  const fields = useFields();
  const active = run.data ? isActive(run.data.status) : false;
  // This tab writes the Run in Steps while it's active, or watches the tab that does (ADR-0017).
  const mode = useRunDriver(runId, active);
  const resume = useResume(runId);
  const control = useRunControl(runId);
  const [confirmingCancel, setConfirmingCancel] = useState(false);
  const quota = useQuota();
  const [confirming, setConfirming] = useState(false);
  const qc = useQueryClient();
  // A Pause is acted on after the current video; show it as requested until the Run actually stops.
  const [pauseRequested, setPauseRequested] = useState(false);
  useEffect(() => {
    if (!active) setPauseRequested(false);
  }, [active]);

  // Once the Run stops, refresh what other screens show (edited badges, quota, the cache).
  useEffect(() => {
    if (!active) {
      qc.invalidateQueries({ queryKey: ["videos"] });
      qc.invalidateQueries({ queryKey: ["quota"] });
      qc.invalidateQueries({ queryKey: ["runs"] });
      // Steps carry progress only; reload the full Run so restorable counts are current.
      qc.invalidateQueries({ queryKey: ["run", runId] });
    }
  }, [active, qc, runId]);

  if (run.isPending) return <p className="text-muted">Loading run…</p>;
  if (run.isError) return <p className="text-danger">Couldn't load this run: {run.error.message}</p>;
  const r = run.data;
  const done = r.total - r.counts.pending;
  const meta = fields.data?.find((f) => f.field === r.field);
  if (!meta) return <p className="text-muted">Loading run…</p>;
  const values = (n: number) => countOf(n, meta);

  return (
    <section>
      <PageHeader
        title={
          <span className="inline-flex flex-wrap items-center gap-x-3 gap-y-1">
            Run #{r.id}
            <Badge tone={RUN_STATUS[r.status].tone} size="md">
              {r.status === "running" ? `Writing ${meta.plural}…` : RUN_STATUS[r.status].long}
            </Badge>
          </span>
        }
        subtitle={
          <>
            {r.started_at ? `Started ${formatDateTime(r.started_at)}` : "Not started yet"}
            {r.finished_at && ` · finished ${formatDateTime(r.finished_at)}`}
          </>
        }
        actions={
          <>
            {active && (
              <>
                <Button
                  icon={<Pause aria-hidden className="size-4" />}
                  onClick={() => control.mutate("pause", { onSuccess: () => setPauseRequested(true) })}
                  disabled={control.isPending || pauseRequested}
                >
                  {pauseRequested ? "Pause requested…" : "Pause"}
                </Button>
                <Button variant="danger-outline" onClick={() => setConfirmingCancel(true)} disabled={control.isPending}>
                  Cancel…
                </Button>
              </>
            )}
            {isResumable(r.status) && r.counts.pending > 0 && (
              <>
              <Button variant="danger-outline" onClick={() => setConfirmingCancel(true)}>
                Cancel the rest…
              </Button>
              <Button
                variant="primary"
                icon={<Play aria-hidden className="size-4" />}
                onClick={() => {
                  quota.refetch();
                  setConfirming(true);
                }}
              >
                Resume {r.counts.pending} video{r.counts.pending === 1 ? "" : "s"}…
              </Button>
              </>
            )}
            {!active && <Button onClick={onDone}>{doneLabel}</Button>}
            {!active && r.restorable > 0 && (
              <Button
                variant="accent-outline"
                icon={<RotateCcw aria-hidden className="size-4" />}
                onClick={() => setRestoring({ count: r.restorable, label: `all ${r.restorable} written videos` })}
              >
                Restore {r.restorable === 1 ? "the written video" : `all ${r.restorable}`}…
              </Button>
            )}
          </>
        }
      />

      <ConfirmDialog
        open={restoring !== null}
        title={`Restore ${restoring?.label ?? ""}?`}
        confirmLabel={`Restore ${restoring?.count ?? 0} ${values(restoring?.count ?? 0)}`}
        busy={restore.isPending}
        onCancel={() => {
          setRestoring(null);
          restore.reset();
        }}
        onConfirm={() =>
          restoring &&
          restore.mutate(
            { confirmCount: restoring.count, videoIds: restoring.videoIds },
            {
              onSuccess: ({ id }) => {
                setRestoring(null);
                onOpenRun(id);
              },
            },
          )
        }
      >
        <p>
          The {values(restoring?.count ?? 0)} this run replaced will be put back, as a new run that's
          backed up first and can itself be restored.
        </p>
        <p>
          Only the {meta.singular} changes: everything else stays as it is today. A video changed on YouTube since this run
          is skipped, not overwritten.
        </p>
        {restore.isError && (
          <p className="text-danger" role="alert">
            {restore.error.message}
          </p>
        )}
      </ConfirmDialog>

      {isResumable(r.status) && (
        <Alert tone="warn" role="status" className="mb-4">
          {RESUME_HINT[r.status]} {r.counts.pending} video
          {r.counts.pending === 1 ? " is" : "s are"} still queued; nothing more is written until you press Resume.
        </Alert>
      )}

      {control.isError && (
        <Alert tone="danger" role="alert" className="mb-4">
          {control.error.message}
        </Alert>
      )}
      {active && (
        <p className="mb-4 text-xs text-muted">
          {mode === "driving"
            ? "This tab is writing the run: keep it open until it finishes. If it closes, the run stops and waits for Resume."
            : "Another tab or window is writing this run; this one shows its progress."}{" "}
          Pause and Cancel take effect after the video being written now.
        </p>
      )}

      <ConfirmDialog
        open={confirmingCancel}
        title="Stop this run for good?"
        confirmLabel="Cancel the videos not written yet"
        cancelLabel={active ? "Keep running" : "Keep it paused"}
        tone="danger"
        busy={control.isPending}
        onCancel={() => setConfirmingCancel(false)}
        onConfirm={() => control.mutate("cancel", { onSuccess: () => setConfirmingCancel(false) })}
      >
        <p>
          Videos not written yet{active ? " (after the one being written now)" : ""} are marked cancelled and can't be
          resumed. Videos already written stay written.
        </p>
      </ConfirmDialog>

      <ConfirmDialog
        open={confirming}
        title={`Resume writing ${r.counts.pending} ${values(r.counts.pending)}?`}
        confirmLabel={`Resume ${r.counts.pending}`}
        busy={resume.isPending}
        onCancel={() => setConfirming(false)}
        onConfirm={() => resume.mutate(r.counts.pending, { onSuccess: () => setConfirming(false) })}
      >
        <p>
          The queued videos are fetched fresh again. Any you've changed on YouTube since the review are skipped, and the
          backups taken when the run started are kept.
        </p>
        <p>
          Quota cost: about <strong className="text-fg">{r.estimated_units.toLocaleString()}</strong> units
          {quota.data && ` (${quota.data.remaining.toLocaleString()} estimated left today)`}.
        </p>
        {quota.data && r.status === "paused_quota" && quota.data.remaining < r.estimated_units / r.counts.pending && (
          <Alert tone="warn" role="alert">
            Today's quota still looks used up. It resets {formatDateTime(quota.data.resets_at)} (midnight Pacific
            time); resuming before then will pause again straight away.
          </Alert>
        )}
        {resume.isError && (
          <p className="text-danger" role="alert">
            {resume.error.message}
          </p>
        )}
      </ConfirmDialog>

      <Card className="mb-4 p-4">
        <div className="mb-2 flex flex-wrap justify-between gap-x-4 text-sm">
          <span className="font-medium">
            {done} of {r.total} done
          </span>
          <span className="text-muted">
            {r.counts.success} updated · {r.counts.failed} failed · {r.counts.stale} skipped · {r.counts.blocked} blocked
          </span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-line" role="progressbar" aria-valuemin={0} aria-valuemax={r.total} aria-valuenow={done}>
          <div className="h-full bg-accent transition-all" style={{ width: `${r.total ? (done / r.total) * 100 : 0}%` }} />
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
        <Card className="self-start overflow-hidden">
        <ul className="divide-y divide-line">
          {r.items.map((i) => (
            <RunItemRow
              key={i.video_id}
              item={i}
              kind={r.kind}
              canRestore={!active && i.restorable}
              onRestore={() => setRestoring({ videoIds: [i.video_id], count: 1, label: i.title })}
            />
          ))}
        </ul>
        </Card>
        <div className="space-y-4">
        <QuotaMeter />
        <Card className="p-4">
          <h3 className="mb-2 text-sm font-semibold">Log</h3>
          <ol className="max-h-96 space-y-1 overflow-auto font-mono text-xs" aria-live="polite">
            {r.log.map((l, n) => (
              <li key={n} className={l.level === "error" ? "text-danger" : l.level === "warning" ? "text-warn" : "text-muted"}>
                {new Date(l.ts).toLocaleTimeString()} {l.message}
              </li>
            ))}
          </ol>
        </Card>
        </div>
      </div>
    </section>
  );
}

function RunItemRow({
  item,
  kind,
  canRestore,
  onRestore,
}: {
  item: RunItem;
  kind: "apply" | "restore";
  canRestore: boolean;
  onRestore: () => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <li className="px-4 py-3 text-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <button
            type="button"
            onClick={() => setOpen((o) => !o)}
            aria-expanded={open}
            className="flex max-w-full items-center gap-1 text-left font-medium hover:underline"
            title={item.title}
          >
            {open ? (
              <ChevronDown aria-hidden className="size-4 shrink-0 text-muted" />
            ) : (
              <ChevronRight aria-hidden className="size-4 shrink-0 text-muted" />
            )}
            <span className="truncate">{item.title}</span>
          </button>
          {(item.error || item.attempts > 1) && (
            <div className="mt-0.5 pl-5 text-xs text-muted">
              {item.error}
              {item.attempts > 1 && ` (after ${item.attempts} tries)`}
            </div>
          )}
        </div>
        <span className="flex shrink-0 items-center gap-2">
          {canRestore && (
            <Button variant="link" size="xs" onClick={onRestore}>
              Restore
            </Button>
          )}
          <Badge tone={ITEM_STATUS[item.status].tone}>{ITEM_STATUS[item.status].text}</Badge>
        </span>
      </div>
      {open && (
        <div className="mt-2">
          <p className="mb-1 text-xs text-muted">
            {kind === "restore" ? "What this restore set out to put back:" : "What this run set out to write:"}
          </p>
          <DiffView before={item.before} after={item.after} />
        </div>
      )}
    </li>
  );
}
