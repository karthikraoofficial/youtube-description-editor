import { type RunSummary, useRuns } from "../api/runs";
import { formatDateTime } from "../lib/format";
import { RUN_STATUS } from "../lib/runLabels";

function describe(run: RunSummary): string {
  if (run.kind === "restore") return `Restore of run #${run.source_run_id}`;
  return run.operation_summary ?? "Apply";
}

export function HistoryScreen({ onOpenRun }: { onOpenRun: (id: number) => void }) {
  const runs = useRuns();

  return (
    <section>
      <div className="mb-4">
        <h2 className="text-lg font-semibold">History</h2>
        <p className="text-sm text-muted">
          Every run you applied or restored, newest first. Open one to see each video's before and after, or to restore it.
        </p>
      </div>
      {runs.isPending && <p className="text-muted">Loading history…</p>}
      {runs.isError && <p className="text-danger">Couldn't load the history: {runs.error.message}</p>}
      {runs.data?.length === 0 && (
        <div className="rounded-xl border border-line bg-surface p-10 text-center text-sm text-muted">
          No runs yet. Apply a review and it will appear here.
        </div>
      )}
      {!!runs.data?.length && (
        <ul className="divide-y divide-line overflow-hidden rounded-xl border border-line bg-surface">
          {runs.data.map((run) => (
            <li key={run.id}>
              <button
                type="button"
                onClick={() => onOpenRun(run.id)}
                className="flex w-full flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 text-left text-sm hover:bg-line/40 focus-visible:bg-accent/10 focus-visible:outline-none"
              >
                <span className="w-12 font-mono text-muted">#{run.id}</span>
                <span className="min-w-0 flex-1 truncate font-medium" title={describe(run)}>
                  {describe(run)}
                </span>
                <span className="text-muted">{formatDateTime(run.created_at)}</span>
                <span className="w-56 text-right text-muted">
                  {run.counts.success} updated
                  {run.counts.failed > 0 && ` · ${run.counts.failed} failed`}
                  {run.counts.stale > 0 && ` · ${run.counts.stale} skipped`}
                  {run.counts.blocked > 0 && ` · ${run.counts.blocked} blocked`}
                  {run.counts.noop > 0 && ` · ${run.counts.noop} already up to date`}
                  {run.counts.cancelled > 0 && ` · ${run.counts.cancelled} cancelled`}
                  {run.counts.pending > 0 && ` · ${run.counts.pending} queued`}
                </span>
                <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${RUN_STATUS[run.status].tone}`}>
                  {RUN_STATUS[run.status].short}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
