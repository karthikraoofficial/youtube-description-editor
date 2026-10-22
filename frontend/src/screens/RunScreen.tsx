import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { type ItemStatus, type RunStatus, isActive, isResumable, useResume, useRun } from "../api/runs";
import { useQuota } from "../api/videos";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { formatDateTime } from "../lib/format";

const RESUME_HINT: Partial<Record<RunStatus, string>> = {
  paused: "Paused because the app wasn't connected, the Google sign-in expired, or YouTube kept failing.",
  paused_quota: "Paused because YouTube's daily quota ran out.",
  interrupted: "Interrupted because the app stopped during the run.",
};

const RUN_LABEL: Record<RunStatus, string> = {
  pending: "Starting…",
  running: "Writing descriptions…",
  paused: "Paused",
  paused_quota: "Paused: daily quota used up",
  interrupted: "Interrupted",
  cancelled: "Cancelled",
  completed: "Finished",
};

const ITEM_LABEL: Record<ItemStatus, { text: string; tone: string }> = {
  pending: { text: "Waiting", tone: "bg-line text-muted" },
  success: { text: "Updated", tone: "bg-ok/15 text-ok" },
  failed: { text: "Failed", tone: "bg-danger/15 text-danger" },
  stale: { text: "Skipped: changed on YouTube", tone: "bg-warn/15 text-warn" },
  blocked: { text: "Blocked", tone: "bg-danger/15 text-danger" },
  noop: { text: "Already up to date", tone: "bg-line text-muted" },
  cancelled: { text: "Cancelled", tone: "bg-line text-muted" },
};

export function RunScreen({ runId, onDone }: { runId: number; onDone: () => void }) {
  const run = useRun(runId);
  const resume = useResume(runId);
  const quota = useQuota();
  const [confirming, setConfirming] = useState(false);
  const qc = useQueryClient();
  const active = run.data ? isActive(run.data.status) : true;

  // Once the Run stops, refresh what other screens show (edited badges, quota, the cache).
  useEffect(() => {
    if (!active) {
      qc.invalidateQueries({ queryKey: ["videos"] });
      qc.invalidateQueries({ queryKey: ["quota"] });
      qc.invalidateQueries({ queryKey: ["runs"] });
    }
  }, [active, qc]);

  if (run.isPending) return <p className="text-muted">Loading run…</p>;
  if (run.isError) return <p className="text-danger">Couldn't load this run: {run.error.message}</p>;
  const r = run.data;
  const done = r.total - r.counts.pending;

  return (
    <section>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">
            Run #{r.id}: {RUN_LABEL[r.status]}
          </h2>
          <p className="text-sm text-muted">
            {r.started_at ? `Started ${formatDateTime(r.started_at)}` : "Not started yet"}
            {r.finished_at && ` · finished ${formatDateTime(r.finished_at)}`}
          </p>
        </div>
        <div className="flex gap-2">
          {isResumable(r.status) && r.counts.pending > 0 && (
            <button
              type="button"
              onClick={() => {
                quota.refetch();
                setConfirming(true);
              }}
              className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
            >
              Resume {r.counts.pending} video{r.counts.pending === 1 ? "" : "s"}…
            </button>
          )}
          {!active && (
            <button type="button" onClick={onDone} className="rounded-md border border-line px-4 py-2 text-sm hover:bg-line/50">
              Back to videos
            </button>
          )}
        </div>
      </div>

      {isResumable(r.status) && (
        <p className="mb-4 rounded-md border border-warn/30 bg-warn/10 px-3 py-2 text-sm text-warn" role="status">
          {RESUME_HINT[r.status]} {r.counts.pending} video
          {r.counts.pending === 1 ? " is" : "s are"} still queued; nothing more is written until you press Resume.
        </p>
      )}

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
        <div className="mb-2 flex justify-between text-sm">
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
            <li key={i.video_id} className="flex items-start justify-between gap-3 px-4 py-2.5 text-sm">
              <div className="min-w-0">
                <div className="truncate font-medium" title={i.title}>
                  {i.title}
                </div>
                {(i.error || i.attempts > 1) && (
                  <div className="mt-0.5 text-xs text-muted">
                    {i.error}
                    {i.attempts > 1 && ` (after ${i.attempts} tries)`}
                  </div>
                )}
              </div>
              <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${ITEM_LABEL[i.status].tone}`}>
                {ITEM_LABEL[i.status].text}
              </span>
            </li>
          ))}
        </ul>
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
    </section>
  );
}
