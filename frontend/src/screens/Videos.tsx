import { useCallback, useEffect, useMemo, useState } from "react";
import { type Video, useOverrideShort, useSync, useSyncStatus, useVideos } from "../api/videos";
import { VideoFiltersBar } from "../components/VideoFiltersBar";
import { VideoTable } from "../components/VideoTable";
import { DEFAULT_FILTERS, filterVideos, isFiltered, type VideoFilters } from "../lib/filters";
import { formatDateTime } from "../lib/format";
import { type Selection, type SelectionUpdate, pruned, toggled, withMany } from "../lib/selection";

type Props = { selected: Selection; onSelectedChange: SelectionUpdate; onEdit: () => void };

const NO_VIDEOS: Video[] = [];

export function VideosScreen({ selected, onSelectedChange, onEdit }: Props) {
  const videos = useVideos();
  const status = useSyncStatus();
  const sync = useSync();
  const overrideShort = useOverrideShort();
  const onOverrideShort = useCallback(
    (id: string, isShort: boolean) => overrideShort.mutate({ id, isShort }),
    [overrideShort.mutate],
  );
  const [filters, setFilters] = useState<VideoFilters>(DEFAULT_FILTERS);

  const all = videos.data ?? NO_VIDEOS;
  const matching = useMemo(() => filterVideos(all, filters), [all, filters]);

  // A Sync can drop Videos; drop them from the Selection too so later steps never see stale ids.
  useEffect(() => {
    if (!videos.data) return;
    const existing = new Set(videos.data.map((v) => v.id));
    onSelectedChange((prev) => pruned(prev, existing));
  }, [videos.data, onSelectedChange]);

  const hiddenSelected = useMemo(() => {
    const shown = new Set(matching.map((v) => v.id));
    return [...selected].filter((id) => !shown.has(id)).length;
  }, [matching, selected]);
  const unselectedMatching = matching.length - (selected.size - hiddenSelected);

  const onToggle = useCallback((id: string) => onSelectedChange((prev) => toggled(prev, id)), [onSelectedChange]);
  const onSetMany = useCallback(
    (ids: string[], select: boolean) => onSelectedChange((prev) => withMany(prev, ids, select)),
    [onSelectedChange],
  );

  const neverSynced = status.data && !status.data.last_sync_at;

  return (
    <section>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Videos</h2>
          <p className="text-sm text-muted">
            {status.data?.last_sync_at
              ? `${status.data.video_count} public videos · last synced ${formatDateTime(status.data.last_sync_at)}`
              : "Not synced yet"}
          </p>
        </div>
        <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onEdit}
          disabled={selected.size === 0}
          title={selected.size === 0 ? "Select videos first" : undefined}
          className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-40"
        >
          Edit {selected.size || ""} selected →
        </button>
        <button
          type="button"
          onClick={() => sync.mutate()}
          disabled={sync.isPending}
          className="rounded-md border border-line bg-surface px-4 py-2 text-sm font-medium hover:bg-line/50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:opacity-60"
        >
          {sync.isPending ? "Syncing…" : neverSynced ? "Sync videos" : "Sync"}
        </button>
        </div>
      </div>

      {sync.isPending && (
        <p className="mb-4 text-sm text-muted" role="status">
          Syncing… New videos are checked once to see whether they're Shorts, so the first sync can take about a minute.
        </p>
      )}
      {sync.isError && <ErrorBanner>{sync.error.message}</ErrorBanner>}
      {overrideShort.isError && <ErrorBanner>Couldn't change the Short label: {overrideShort.error.message}</ErrorBanner>}
      {videos.isError && <ErrorBanner>Couldn't load your videos: {videos.error.message}</ErrorBanner>}

      {videos.isPending && <TableMessage>Loading videos…</TableMessage>}
      {videos.isSuccess && all.length === 0 && (
        <TableMessage>
          <p className="font-medium text-fg">No videos cached yet</p>
          <p className="mt-1">
            Click <strong>Sync videos</strong> to fetch your public uploads from YouTube. It costs a few quota units.
          </p>
        </TableMessage>
      )}

      {all.length > 0 && (
        <>
          <VideoFiltersBar filters={filters} onChange={setFilters} />
          <div className="mb-2 flex min-h-8 flex-wrap items-center gap-x-3 gap-y-1 text-sm" aria-live="polite">
            <span className="text-muted">
              {isFiltered(filters) ? `${matching.length} of ${all.length} match` : `${all.length} videos`}
            </span>
            <span className={selected.size ? "font-medium" : "text-muted"}>
              {selected.size} selected
              {hiddenSelected > 0 && <span className="font-normal text-muted"> ({hiddenSelected} hidden by filters)</span>}
            </span>
            {unselectedMatching > 0 && (
              <button
                type="button"
                onClick={() => onSetMany(matching.map((v) => v.id), true)}
                className="text-accent hover:underline"
              >
                Select all {matching.length} matching
              </button>
            )}
            {selected.size > 0 && (
              <button
                type="button"
                onClick={() => onSelectedChange(() => new Set())}
                className="text-muted hover:text-fg hover:underline"
              >
                Clear selection{hiddenSelected > 0 ? " (including hidden)" : ""}
              </button>
            )}
          </div>
          {matching.length === 0 ? (
            <TableMessage>No videos match these filters.</TableMessage>
          ) : (
            <VideoTable
              videos={matching}
              selected={selected}
              onToggle={onToggle}
              onSetMany={onSetMany}
              onOverrideShort={onOverrideShort}
            />
          )}
          <p className="mt-2 text-xs text-muted">
            Keyboard: ↑/↓ move · Space selects · S flips Short · Home/End · PageUp/PageDown · / search. Short: click or S to correct it
            (≈ guessed from length, ✎ set by you).
          </p>
        </>
      )}
    </section>
  );
}

function ErrorBanner({ children }: { children: React.ReactNode }) {
  return (
    <p className="mb-4 rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger" role="alert">
      {children}
    </p>
  );
}

function TableMessage({ children }: { children: React.ReactNode }) {
  return <div className="rounded-xl border border-line bg-surface p-10 text-center text-sm text-muted">{children}</div>;
}
