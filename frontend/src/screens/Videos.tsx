import { useSync, useSyncStatus, useVideos } from "../api/videos";
import { formatDate, formatDateTime, formatDuration } from "../lib/format";

export function VideosScreen() {
  const videos = useVideos();
  const status = useSyncStatus();
  const sync = useSync();
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
        <button
          type="button"
          onClick={() => sync.mutate()}
          disabled={sync.isPending}
          className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:opacity-60"
        >
          {sync.isPending ? "Syncing…" : neverSynced ? "Sync videos" : "Sync"}
        </button>
      </div>

      {sync.isError && (
        <p className="mb-4 rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger" role="alert">
          {sync.error.message}
        </p>
      )}

      <div className="overflow-hidden rounded-xl border border-line bg-surface">
        {videos.isPending && <p className="p-8 text-muted">Loading videos…</p>}
        {videos.data?.length === 0 && (
          <div className="p-10 text-center">
            <p className="font-medium">No videos cached yet</p>
            <p className="mt-1 text-sm text-muted">
              Click <strong>Sync videos</strong> to fetch your public uploads from YouTube. It costs a few quota units.
            </p>
          </div>
        )}
        {!!videos.data?.length && (
          <ul className="divide-y divide-line">
            {videos.data.map((v) => (
              <li key={v.id} className="flex items-center gap-4 px-4 py-2.5">
                {v.thumbnail_url ? (
                  <img src={v.thumbnail_url} alt="" className="h-10 w-[72px] rounded object-cover" loading="lazy" />
                ) : (
                  <span className="h-10 w-[72px] rounded bg-line" aria-hidden />
                )}
                <span className="min-w-0 flex-1 truncate text-sm font-medium" title={v.title}>
                  {v.title}
                </span>
                <span className="shrink-0 text-sm tabular-nums text-muted">{formatDuration(v.duration_s)}</span>
                <span className="w-28 shrink-0 text-right text-sm text-muted">{formatDate(v.published_at)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
