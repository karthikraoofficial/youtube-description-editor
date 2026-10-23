import { useMemo, useState } from "react";
import { type Bucket, type ChangesetItem, type ItemUpdate, useChangeset, useUpdateItem } from "../api/changesets";
import { useApply } from "../api/runs";
import { useQuota } from "../api/videos";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { DiffView } from "../components/DiffView";
import { useFields } from "../api/fields";
import { type FieldInfo, countOf, labelFor } from "../lib/fields";
import { Alert } from "../components/ui/Alert";
import { BackLink } from "../components/ui/BackLink";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { inputClass, textareaClass } from "../components/ui/inputs";
import { PageHeader } from "../components/ui/PageHeader";
import { Tabs, panelId, tabId } from "../components/ui/Tabs";

const TABS: { bucket: Bucket; label: string }[] = [
  { bucket: "to_write", label: "To write" },
  { bucket: "excluded", label: "Excluded" },
  { bucket: "blocked", label: "Blocked" },
  { bucket: "unchanged", label: "Unchanged" },
];

const PAGE = 25;

type Props = { changesetId: number; onBackToEdit: () => void; onApplied: (runId: number) => void };

export function ReviewScreen({ changesetId, onBackToEdit, onApplied }: Props) {
  const cs = useChangeset(changesetId);
  const fields = useFields();
  const updateItem = useUpdateItem(changesetId);
  const apply = useApply(changesetId);
  const quota = useQuota();
  const [confirmingApply, setConfirmingApply] = useState(false);
  const [tab, setTab] = useState<Bucket>("to_write");
  const [shown, setShown] = useState(PAGE);

  const items = useMemo(() => (cs.data?.items ?? []).filter((i) => i.bucket === tab), [cs.data, tab]);

  if (cs.isPending) return <p className="text-muted">Loading review…</p>;
  if (cs.isError) return <p className="text-danger">Couldn't load this review: {cs.error.message}</p>;
  const { counts, field, operation, status, estimated_units, missing, no_audio_language } = cs.data;
  const meta = fields.data?.find((f) => f.field === field);
  if (!meta) return <p className="text-muted">Loading review…</p>;
  const values = (n: number) => countOf(n, meta);

  return (
    <section>
      <PageHeader
        back={<BackLink onClick={onBackToEdit}>Back to edit</BackLink>}
        title="Review changes"
        subtitle={`${labelFor(operation.type, meta)} on ${counts.selected} selected videos. Nothing has been written to YouTube.`}
        actions={
          <>
            <p className="text-sm">
              <span className="text-base font-semibold">{counts.to_write}</span> to write
              <span className="text-muted"> · about {estimated_units.toLocaleString()} quota units</span>
            </p>
            <Button
              variant="primary"
              disabled={status !== "draft" || counts.to_write === 0 || apply.isPending}
              onClick={() => {
                quota.refetch();
                setConfirmingApply(true);
              }}
            >
              Apply {counts.to_write} change{counts.to_write === 1 ? "" : "s"} to YouTube…
            </Button>
          </>
        }
      />

      <ConfirmDialog
        open={confirmingApply}
        title={`Write ${counts.to_write} ${values(counts.to_write)} to YouTube?`}
        confirmLabel={`Apply ${counts.to_write} change${counts.to_write === 1 ? "" : "s"}`}
        busy={apply.isPending}
        onCancel={() => setConfirmingApply(false)}
        onConfirm={() =>
          apply.mutate(counts.to_write, {
            onSuccess: ({ id }) => {
              setConfirmingApply(false);
              onApplied(id);
            },
          })
        }
      >
        <p>
          <strong className="text-fg">{counts.to_write}</strong> video {values(counts.to_write)} will be updated on
          your channel. Quota cost: about <strong className="text-fg">{estimated_units.toLocaleString()}</strong>{" "}
          units
          {quota.data && ` (${quota.data.remaining.toLocaleString()} of ${quota.data.limit.toLocaleString()} estimated left today)`}.
        </p>
        {quota.data && estimated_units > quota.data.remaining && (
          <Alert tone="warn" role="alert">
            That's more than today's estimated remaining quota. The run will pause when YouTube says the quota is used
            up; the videos not yet written stay queued. The quota resets at midnight Pacific time.
          </Alert>
        )}
        {no_audio_language > 0 && (
          <p>
            {no_audio_language} of these video{no_audio_language === 1 ? " has" : "s have"} no audio language set. YouTube
            usually fills it in as <strong className="text-fg">en-US</strong> when a video is updated.
          </p>
        )}
        <p>
          Each video is fetched fresh and its current snippet is backed up before anything is written. Videos changed on
          YouTube since you reviewed them are skipped. Only the {meta.singular} changes; everything else is sent back as
          it is.
        </p>
        {apply.isError && (
          <p className="text-danger" role="alert">
            {apply.error.message}
          </p>
        )}
      </ConfirmDialog>

      {missing > 0 && (
        <Alert tone="warn" role="status" className="mb-4">
          {missing} selected video{missing === 1 ? " is" : "s are"} no longer in your synced list, so{" "}
          {missing === 1 ? "it isn't" : "they aren't"} part of this review.
        </Alert>
      )}
      {status !== "draft" && (
        <Alert tone="warn" role="alert" className="mb-4">
          This review was replaced by a newer one, so it can't be changed. Go back to edit and review again.
        </Alert>
      )}

      <Tabs
        label="Review buckets"
        idPrefix="review"
        className="mb-4"
        tabs={TABS.map((t) => ({ id: t.bucket, label: t.label, count: counts[t.bucket] }))}
        value={tab}
        onChange={(b) => {
          setTab(b);
          setShown(PAGE);
        }}
      />
      <div role="tabpanel" id={panelId("review")} aria-labelledby={tabId("review", tab)}>

      {updateItem.isError && (
        <Alert tone="danger" role="alert" className="mb-3">
          {updateItem.error.message}
        </Alert>
      )}

      {items.length === 0 ? (
        <Card className="p-10 text-center text-sm text-muted">{EMPTY[tab]}</Card>
      ) : (
        <ul className="space-y-3">
          {items.slice(0, shown).map((item) => (
            <ReviewItem
              key={item.video_id}
              item={item}
              editable={status === "draft"}
              field={meta}
              onUpdate={(update, onSaved) =>
                updateItem.mutate({ videoId: item.video_id, update }, { onSuccess: () => onSaved?.() })
              }
              saving={updateItem.isPending && updateItem.variables?.videoId === item.video_id}
            />
          ))}
        </ul>
      )}
      {items.length > shown && (
        <Button variant="accent-outline" onClick={() => setShown((s) => s + PAGE)} className="mt-4 w-full">
          Show {Math.min(PAGE, items.length - shown)} more of {items.length - shown}
        </Button>
      )}
      </div>
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
  field,
  onUpdate,
  saving,
}: {
  item: ChangesetItem;
  editable: boolean;
  field: FieldInfo;
  onUpdate: (update: ItemUpdate, onSaved?: () => void) => void;
  saving: boolean;
}) {
  const bucket = item.bucket;
  const canToggle = editable && (bucket === "to_write" || bucket === "excluded");
  const [editing, setEditing] = useState<string | null>(null);

  return (
    <li>
      <Card className={`p-4 ${bucket === "excluded" ? "opacity-70" : ""}`}>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <label className={`flex min-w-0 items-center gap-2.5 ${canToggle ? "cursor-pointer" : ""}`}>
          <input
            type="checkbox"
            checked={item.included}
            disabled={!canToggle}
            onChange={(e) => onUpdate({ included: e.target.checked })}
            aria-label={`Include ${item.title}`}
            className="h-4 w-4"
          />
          <span className="truncate text-sm font-medium" title={item.title}>
            {item.title}
          </span>
        </label>
        <span className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
          {item.overridden && <Badge tone="accent">Edited by hand</Badge>}
          <span className="text-muted">
            {bucket === "to_write" ? "Will be written" : bucket === "excluded" ? "Excluded by you" : ""}
          </span>
          {editable && editing === null && (
            <Button variant="link" size="xs" onClick={() => setEditing(item.after)}>
              Edit by hand
            </Button>
          )}
          {editable && item.overridden && editing === null && (
            <Button variant="ghost" size="xs" onClick={() => onUpdate({ override: null })} disabled={saving}>
              Reset to the operation's result
            </Button>
          )}
        </span>
      </div>
      {item.flags.map((f) => (
        <Alert key={f.code} tone={f.blocking ? "danger" : "warn"} size="sm" className="mb-2">
          {f.blocking ? "Blocked: " : ""}
          {f.message}
        </Alert>
      ))}
      {editing !== null ? (
        <div>
          <label className="mb-1 block text-xs font-medium text-muted" htmlFor={`edit-${item.video_id}`}>
            New {field.singular} for this video
          </label>
          {field.one_line ? (
            <input
              id={`edit-${item.video_id}`}
              value={editing}
              onChange={(e) => setEditing(e.target.value)}
              className={`w-full font-mono ${inputClass}`}
            />
          ) : (
            <textarea
              id={`edit-${item.video_id}`}
              rows={Math.min(16, Math.max(6, editing.split("\n").length + 1))}
              value={editing}
              onChange={(e) => setEditing(e.target.value)}
              className={`w-full font-mono ${textareaClass}`}
            />
          )}
          <div className="mt-2 flex flex-wrap gap-2">
            <Button
              variant="primary"
              size="sm"
              disabled={saving}
              // Close the editor only once the save succeeds, so a failed save keeps your text.
              onClick={() => onUpdate({ override: editing }, () => setEditing(null))}
            >
              Save hand edit
            </Button>
            <Button size="sm" onClick={() => setEditing(null)}>
              Cancel
            </Button>
            <span className="self-center text-xs text-muted">It's checked against YouTube's limits when you save.</span>
          </div>
        </div>
      ) : item.changed ? (
        <DiffView before={item.before} after={item.after} />
      ) : (
        <p className="text-xs text-muted">The {field.singular} stays as it is.</p>
      )}
      </Card>
    </li>
  );
}
