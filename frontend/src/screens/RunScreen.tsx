import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { type ItemStatus, type RunStatus, isActive, useRun } from "../api/runs";
import { formatDateTime } from "../lib/format";

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
  const qc = useQueryClient();
  const active = run.data ? isActive(run.data.status) : true;

  // Once the Run stops, refresh what other screens show (edited badges, quota, the cache).
  useEffect(() => {
    if (!active) {
      qc.invalidateQueries({ queryKey: ["videos"] });
      qc.invalidateQueries({ queryKey: ["quota"] });
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
        {!active && (
          <button type="button" onClick={onDone} className="rounded-md border border-line px-4 py-2 text-sm hover:bg-line/50">
            Back to videos
          </button>
        )}
      </div>

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
                {i.error && <div className="mt-0.5 text-xs text-muted">{i.error}</div>}
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
