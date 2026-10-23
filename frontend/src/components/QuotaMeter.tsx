import { useQuota } from "../api/videos";
import { formatDateTime } from "../lib/format";

/** Today's estimated YouTube quota (the app's own ledger; YouTube doesn't report what's left). */
export function QuotaMeter({ compact = false }: { compact?: boolean }) {
  const quota = useQuota();
  if (!quota.data) return null;
  const { used, limit, remaining, resets_at, update_units } = quota.data;
  const share = Math.min(1, used / limit);
  const updatesLeft = Math.floor(remaining / update_units);
  // Warn when only a few runs' worth of description updates are left today.
  const tone = updatesLeft < 10 ? "bg-danger" : updatesLeft < 50 ? "bg-warn" : "bg-ok";
  const label = `Quota (estimated): ${used.toLocaleString()} of ${limit.toLocaleString()} units used today; ${remaining.toLocaleString()} left. Resets ${formatDateTime(resets_at)}.`;

  if (compact)
    return (
      <div className="flex items-center gap-2 text-xs text-muted" title={label}>
        <span className="hidden sm:inline">Quota</span>
        <span className="block h-1.5 w-12 overflow-hidden rounded-full bg-line sm:w-20" aria-hidden>
          <span className={`block h-full ${tone}`} style={{ width: `${share * 100}%` }} />
        </span>
        <span className="tabular-nums">
          {remaining.toLocaleString()} left<span className="hidden sm:inline"> (est.)</span>
        </span>
        <span className="sr-only">{label}</span>
      </div>
    );

  return (
    <div className="rounded-xl border border-line bg-surface p-4" role="group" aria-label="Quota">
      <div className="mb-1 flex justify-between text-sm">
        <span className="font-medium">
          Quota today <span className="font-normal text-muted">(estimated)</span>
        </span>
        <span className="tabular-nums text-muted">
          {used.toLocaleString()} / {limit.toLocaleString()}
        </span>
      </div>
      <div
        className="h-2 overflow-hidden rounded-full bg-line"
        role="meter"
        aria-valuemin={0}
        aria-valuemax={limit}
        aria-valuenow={used}
        aria-label="Quota units used today"
        aria-valuetext={`${used.toLocaleString()} of ${limit.toLocaleString()} units used`}
      >
        <div className={`h-full ${tone} transition-all`} style={{ width: `${share * 100}%` }} />
      </div>
      <p className="mt-1.5 text-xs text-muted">
        {remaining.toLocaleString()} units left · about {updatesLeft.toLocaleString()} more video
        updates · resets {formatDateTime(resets_at)} (midnight Pacific time)
      </p>
    </div>
  );
}
