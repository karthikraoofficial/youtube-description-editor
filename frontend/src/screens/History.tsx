import { useFields } from "../api/fields";
import { type RunSummary, useRuns } from "../api/runs";
import type { FieldInfo } from "../lib/fields";
import { formatDateTime } from "../lib/format";
import { RUN_STATUS, runOutcome } from "../lib/runLabels";
import { Alert } from "../components/ui/Alert";
import { Badge } from "../components/ui/Badge";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";

function describe(run: RunSummary, fields: FieldInfo[] | undefined): string {
  // Restores of other Fields than the description say which Field they put back.
  if (run.kind === "restore") {
    const plural = fields?.find((f) => f.field === run.field)?.plural ?? run.field;
    return `Restore of run #${run.source_run_id}${run.field === "description" ? "" : ` (${plural})`}`;
  }
  return run.operation_summary ?? "Apply";
}

const COLUMNS = "md:grid-cols-[3.5rem_minmax(0,1fr)_9.5rem_7.5rem]";

export function HistoryScreen({ onOpenRun }: { onOpenRun: (id: number) => void }) {
  const runs = useRuns();
  const fields = useFields();

  return (
    <section>
      <PageHeader
        title="History"
        subtitle="Every run you applied or restored, newest first. Open one to see each video's before and after, or to restore it."
      />
      {runs.isPending && <p className="text-muted">Loading history…</p>}
      {runs.isError && (
        <Alert tone="danger" role="alert">
          Couldn't load the history: {runs.error.message}
        </Alert>
      )}
      {runs.data?.length === 0 && (
        <Card className="p-10 text-center text-sm text-muted">No runs yet. Apply a review and it will appear here.</Card>
      )}
      {!!runs.data?.length && (
        <Card className="overflow-hidden">
          {/* Column headings, like the Videos table; below 768 px each run stacks instead. */}
          <div aria-hidden className={`hidden gap-x-4 border-b border-line bg-subtle px-4 py-2.5 text-xs font-medium text-muted md:grid ${COLUMNS}`}>
            <span>Run</span>
            <span>Change</span>
            <span>When</span>
            <span className="text-right">Status</span>
          </div>
          <ul className="divide-y divide-line">
            {runs.data.map((run) => (
              <li key={run.id}>
                <button
                  type="button"
                  onClick={() => onOpenRun(run.id)}
                  className={`flex w-full flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 text-left text-sm hover:bg-subtle focus-visible:bg-accent/10 md:grid ${COLUMNS}`}
                >
                  <span className="font-mono text-muted">#{run.id}</span>
                  <span className="min-w-0 flex-1 basis-48 md:basis-auto">
                    <span className="block truncate font-medium" title={describe(run, fields.data)}>
                      {describe(run, fields.data)}
                    </span>
                    <span className="block text-xs text-muted">{runOutcome(run.counts)}</span>
                  </span>
                  <span className="text-muted">{formatDateTime(run.created_at)}</span>
                  <span className="md:text-right">
                    <Badge tone={RUN_STATUS[run.status].tone}>{RUN_STATUS[run.status].short}</Badge>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </section>
  );
}
