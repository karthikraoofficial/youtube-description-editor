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
import { formatDateTime } from "../lib/format";
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

  return (
    <section>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">
            Run #{r.id}: {RUN_STATUS[r.status].long}
          </h2>
          <p className="text-sm text-muted">
            {r.started_at ? `Started ${formatDateTime(r.started_at)}` : "Not started yet"}
            {r.finished_at && ` · finished ${formatDateTime(r.finished_at)}`}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {active && (
            <>
              <button
                type="button"
                onClick={() => control.mutate("pause", { onSuccess: () => setPauseRequested(true) })}
                disabled={control.isPending || pauseRequested}
                className="rounded-md border border-line px-4 py-2 text-sm hover:bg-line/50 disabled:opacity-50"
              >
                {pauseRequested ? "Pause requested…" : "Pause"}
              </button>
              <button
                type="button"
                onClick={() => setConfirmingCancel(true)}
                disabled={control.isPending}
                className="rounded-md border border-danger/40 px-4 py-2 text-sm text-danger hover:bg-danger/10 disabled:opacity-50"
              >
                Cancel…
              </button>
            </>
          )}
          {isResumable(r.status) && r.counts.pending > 0 && (
            <button
              type="button"
              onClick={() => setConfirmingCancel(true)}
              className="rounded-md border border-danger/40 px-4 py-2 text-sm text-danger hover:bg-danger/10"
            >
              Cancel the rest…
            </button>
          )}
          {isResumable(r.status) && r.counts.pending > 0 && (
            <button
              type="button"
              onClick={() => {
                quota.refetch();
                setConfirming(true);
              }}
              className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-on-accent hover:opacity-90"
            >
              Resume {r.counts.pending} video{r.counts.pending === 1 ? "" : "s"}…
            </button>
          )}
          {!active && (
            <button type="button" onClick={onDone} className="rounded-md border border-line px-4 py-2 text-sm hover:bg-line/50">
              {doneLabel}
            </button>
          )}
          {!active && r.restorable > 0 && (
            <button
              type="button"
              onClick={() => setRestoring({ count: r.restorable, label: `all ${r.restorable} written videos` })}
              className="rounded-md border border-accent/40 px-4 py-2 text-sm text-accent hover:bg-accent/10"
            >
              Restore {r.restorable === 1 ? "the written video" : `all ${r.restorable}`}…
            </button>
          )}
        </div>
      </div>

      <ConfirmDialog
        open={restoring !== null}
        title={`Restore ${restoring?.label ?? ""}?`}
        confirmLabel={`Restore ${restoring?.count ?? 0} description${restoring?.count === 1 ? "" : "s"}`}
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
          The description{restoring?.count === 1 ? "" : "s"} this run replaced will be put back, as a new run that's
          backed up first and can itself be restored.
        </p>
        <p>
          Only the description changes: today's title and tags stay as they are. A video changed on YouTube since this run
          is skipped, not overwritten.
        </p>
        {restore.isError && (
          <p className="text-danger" role="alert">
            {restore.error.message}
          </p>
        )}
      </ConfirmDialog>

      {isResumable(r.status) && (
        <p className="mb-4 rounded-md border border-warn/30 bg-warn/10 px-3 py-2 text-sm text-warn" role="status">
          {RESUME_HINT[r.status]} {r.counts.pending} video
          {r.counts.pending === 1 ? " is" : "s are"} still queued; nothing more is written until you press Resume.
        </p>
      )}

      {control.isError && (
        <p className="mb-4 rounded-md bg-danger/10 px-3 py-2 text-sm text-danger" role="alert">
          {control.error.message}
        </p>
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
        title={`Resume writing ${r.counts.pending} description${r.counts.pending === 1 ? "" : "s"}?`}
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
          <p className="rounded-md bg-warn/15 px-2.5 py-1.5 text-warn" role="alert">
            Today's quota still looks used up. It resets {formatDateTime(quota.data.resets_at)} (midnight Pacific
            time); resuming before then will pause again straight away.
          </p>
        )}
        {resume.isError && (
          <p className="text-danger" role="alert">
            {resume.error.message}
          </p>
        )}
      </ConfirmDialog>

      <div className="mb-4 rounded-xl border border-line bg-surface p-4">
        <div className="mb-2 flex flex-wrap justify-between gap-x-4 text-sm">
          <span>
            {done} of {r.total} done
          </span>
          <span className="text-muted">
            {r.counts.success} updated · {r.counts.failed} failed · {r.counts.stale} skipped · {r.counts.blocked} blocked
          </span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-line" role="progressbar" aria-valuemin={0} aria-valuemax={r.total} aria-valuenow={done}>
          <div className="h-full bg-accent transition-all" style={{ width: `${r.total ? (done / r.total) * 100 : 0}%` }} />
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
        <ul className="divide-y divide-line overflow-hidden rounded-xl border border-line bg-surface">
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
        <div className="space-y-4">
        <QuotaMeter />
        <div className="rounded-xl border border-line bg-surface p-4">
          <h3 className="mb-2 text-sm font-semibold">Log</h3>
          <ol className="max-h-96 space-y-1 overflow-auto font-mono text-xs" aria-live="polite">
            {r.log.map((l, n) => (
              <li key={n} className={l.level === "error" ? "text-danger" : l.level === "warning" ? "text-warn" : "text-muted"}>
                {new Date(l.ts).toLocaleTimeString()} {l.message}
              </li>
            ))}
          </ol>
        </div>
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
    <li className="px-4 py-2.5 text-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <button
            type="button"
            onClick={() => setOpen((o) => !o)}
            aria-expanded={open}
            className="block max-w-full truncate text-left font-medium hover:underline"
            title={item.title}
          >
            <span aria-hidden className="mr-1 inline-block w-3 text-muted">
              {open ? "▾" : "▸"}
            </span>
            {item.title}
          </button>
          {(item.error || item.attempts > 1) && (
            <div className="mt-0.5 pl-4 text-xs text-muted">
              {item.error}
              {item.attempts > 1 && ` (after ${item.attempts} tries)`}
            </div>
          )}
        </div>
        <span className="flex shrink-0 items-center gap-2">
          {canRestore && (
            <button type="button" onClick={onRestore} className="text-xs text-accent hover:underline">
              Restore
            </button>
          )}
          <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${ITEM_STATUS[item.status].tone}`}>
            {ITEM_STATUS[item.status].text}
          </span>
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
