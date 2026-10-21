import { useMemo, useState } from "react";
import { type Bucket, type ChangesetItem, useChangeset, useSetIncluded } from "../api/changesets";
import { DiffView } from "../components/DiffView";
import { metaOf } from "../lib/operations";

const TABS: { bucket: Bucket; label: string }[] = [
  { bucket: "to_write", label: "To write" },
  { bucket: "excluded", label: "Excluded" },
  { bucket: "blocked", label: "Blocked" },
  { bucket: "unchanged", label: "Unchanged" },
];

const PAGE = 25;

type Props = { changesetId: number; onBackToEdit: () => void };

export function ReviewScreen({ changesetId, onBackToEdit }: Props) {
  const cs = useChangeset(changesetId);
  const setIncluded = useSetIncluded(changesetId);
  const [tab, setTab] = useState<Bucket>("to_write");
  const [shown, setShown] = useState(PAGE);

  const items = useMemo(() => (cs.data?.items ?? []).filter((i) => i.bucket === tab), [cs.data, tab]);

  if (cs.isPending) return <p className="text-muted">Loading review…</p>;
  if (cs.isError) return <p className="text-danger">Couldn't load this review: {cs.error.message}</p>;
  const { counts, operation, status, estimated_units, missing } = cs.data;

  return (
    <section>
      <button type="button" onClick={onBackToEdit} className="mb-1 text-sm text-accent hover:underline">
        ← Back to edit
      </button>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Review changes</h2>
          <p className="text-sm text-muted">
            {metaOf(operation.type).label} on {counts.selected} selected videos. Nothing has been written to YouTube.
          </p>
        </div>
        <p className="text-sm">
          <span className="text-base font-semibold">{counts.to_write}</span> to write
          <span className="text-muted"> · about {estimated_units.toLocaleString()} quota units</span>
        </p>
      </div>

      {missing > 0 && (
        <p className="mb-4 rounded-md border border-warn/30 bg-warn/10 px-3 py-2 text-sm text-warn" role="status">
          {missing} selected video{missing === 1 ? " is" : "s are"} no longer in your synced list, so{" "}
          {missing === 1 ? "it isn't" : "they aren't"} part of this review.
        </p>
      )}
      {status !== "draft" && (
        <p className="mb-4 rounded-md border border-warn/30 bg-warn/10 px-3 py-2 text-sm text-warn" role="alert">
          This review was replaced by a newer one, so it can't be changed. Go back to edit and review again.
        </p>
      )}

      <div className="mb-4 flex flex-wrap gap-1 border-b border-line" role="tablist">
        {TABS.map((t) => (
          <button
            key={t.bucket}
            type="button"
            role="tab"
            aria-selected={tab === t.bucket}
            onClick={() => {
              setTab(t.bucket);
              setShown(PAGE);
            }}
            className={`-mb-px border-b-2 px-3 py-2 text-sm ${
              tab === t.bucket ? "border-accent font-medium text-fg" : "border-transparent text-muted hover:text-fg"
            }`}
          >
            {t.label} <span className="tabular-nums text-muted">({counts[t.bucket]})</span>
          </button>
        ))}
      </div>

      {setIncluded.isError && (
        <p className="mb-3 rounded-md bg-danger/10 px-3 py-2 text-sm text-danger" role="alert">
          {setIncluded.error.message}
        </p>
      )}

      {items.length === 0 ? (
        <div className="rounded-xl border border-line bg-surface p-10 text-center text-sm text-muted">
          {EMPTY[tab]}
        </div>
      ) : (
        <ul className="space-y-3">
          {items.slice(0, shown).map((item) => (
            <ReviewItem
              key={item.video_id}
              item={item}
              editable={status === "draft"}
              onToggle={(included) => setIncluded.mutate({ videoId: item.video_id, included })}
            />
          ))}
        </ul>
      )}
      {items.length > shown && (
        <button
          type="button"
          onClick={() => setShown((s) => s + PAGE)}
          className="mt-4 w-full rounded-md border border-line bg-surface py-2 text-sm text-accent hover:bg-line/40"
        >
          Show {Math.min(PAGE, items.length - shown)} more of {items.length - shown}
        </button>
      )}
    </section>
  );
}

const EMPTY: Record<Bucket, string> = {
  to_write: "No videos are set to be written.",
  excluded: "You haven't excluded any videos.",
  blocked: "No videos are blocked.",
  unchanged: "Every selected video would change.",
};

function ReviewItem({
  item,
  editable,
  onToggle,
}: {
  item: ChangesetItem;
  editable: boolean;
  onToggle: (included: boolean) => void;
}) {
  const bucket = item.bucket;
  const canToggle = editable && (bucket === "to_write" || bucket === "excluded");
  return (
    <li className={`rounded-xl border bg-surface p-4 ${bucket === "excluded" ? "border-line opacity-70" : "border-line"}`}>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <label className={`flex min-w-0 items-center gap-2.5 ${canToggle ? "cursor-pointer" : ""}`}>
          <input
            type="checkbox"
            checked={item.included}
            disabled={!canToggle}
            onChange={(e) => onToggle(e.target.checked)}
            aria-label={`Include ${item.title}`}
            className="h-4 w-4 accent-[var(--color-accent)]"
          />
          <span className="truncate text-sm font-medium" title={item.title}>
            {item.title}
          </span>
        </label>
        <span className="text-xs text-muted">
          {bucket === "to_write" ? "Will be written" : bucket === "excluded" ? "Excluded by you" : ""}
        </span>
      </div>
      {item.flags.map((f) => (
        <p
          key={f.code}
          className={`mb-2 rounded-md px-2.5 py-1.5 text-xs ${f.blocking ? "bg-danger/10 text-danger" : "bg-warn/10 text-warn"}`}
        >
          {f.blocking ? "Blocked: " : ""}
          {f.message}
        </p>
      ))}
      {item.changed ? (
        <DiffView before={item.before} after={item.after} />
      ) : (
        <p className="text-xs text-muted">The description stays as it is.</p>
      )}
    </li>
  );
}
