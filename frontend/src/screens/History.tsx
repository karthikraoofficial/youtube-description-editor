import { useFields } from "../api/fields";
import { type RunSummary, useRuns } from "../api/runs";
import type { FieldInfo } from "../lib/fields";
import { formatDateTime } from "../lib/format";
import { RUN_STATUS } from "../lib/runLabels";
import { Badge } from "../components/ui/Badge";

function describe(run: RunSummary, fields: FieldInfo[] | undefined): string {
  // Restores of other Fields than the description say which Field they put back.
  if (run.kind === "restore") {
    const plural = fields?.find((f) => f.field === run.field)?.plural ?? run.field;
    return `Restore of run #${run.source_run_id}${run.field === "description" ? "" : ` (${plural})`}`;
  }
  return run.operation_summary ?? "Apply";
}

export function HistoryScreen({ onOpenRun }: { onOpenRun: (id: number) => void }) {
  const runs = useRuns();
  const fields = useFields();

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
                className="flex w-full flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 text-left text-sm hover:bg-line/40 focus-visible:bg-accent/10"
              >
                <span className="font-mono text-muted sm:w-12">#{run.id}</span>
                <span className="min-w-0 flex-1 truncate font-medium" title={describe(run, fields.data)}>
                  {describe(run, fields.data)}
                </span>
                <span className="text-muted">{formatDateTime(run.created_at)}</span>
                <span className="w-full text-muted sm:w-56 sm:text-right">
                  {run.counts.success} updated
                  {run.counts.failed > 0 && ` · ${run.counts.failed} failed`}
                  {run.counts.stale > 0 && ` · ${run.counts.stale} skipped`}
                  {run.counts.blocked > 0 && ` · ${run.counts.blocked} blocked`}
                  {run.counts.noop > 0 && ` · ${run.counts.noop} already up to date`}
                  {run.counts.cancelled > 0 && ` · ${run.counts.cancelled} cancelled`}
                  {run.counts.pending > 0 && ` · ${run.counts.pending} queued`}
                </span>
                <Badge tone={RUN_STATUS[run.status].tone}>{RUN_STATUS[run.status].short}</Badge>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
