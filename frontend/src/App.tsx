import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useAuthStatus } from "./api/auth";
import { api, type Health } from "./api/client";
import type { Operation } from "./api/preview";
import { useChangeset, useOpenChangesetId } from "./api/changesets";
import { useVideos } from "./api/videos";
import { ChannelBadge } from "./components/ChannelBadge";
import { ThemeToggle } from "./components/ThemeToggle";
import type { Selection } from "./lib/selection";
import { ConnectScreen } from "./screens/Connect";
import { EditBuilder, INITIAL_OPERATION } from "./screens/EditBuilder";
import { ReviewScreen } from "./screens/Review";
import { VideosScreen } from "./screens/Videos";

export function App() {
  const health = useQuery({ queryKey: ["health"], queryFn: () => api<Health>("/health") });
  const auth = useAuthStatus();
  const channel = auth.data?.state === "connected" ? auth.data.channel : null;
  const [selected, setSelected] = useState<Selection>(() => new Set());
  const [screen, setScreen] = useState<"videos" | "edit" | "review">("videos");
  const [changesetId, setChangesetId] = useState<number | null>(null);
  const [draft, setDraft] = useState<Operation>(INITIAL_OPERATION);
  // A different Channel means different Videos (ADR-0008): start over.
  useEffect(() => {
    setSelected(new Set());
    setScreen("videos");
  }, [channel?.id]);

  // After a reload, pick the open review back up so its choices aren't lost silently.
  const openId = useOpenChangesetId();
  useEffect(() => {
    if (changesetId === null && openId.data != null) setChangesetId(openId.data);
  }, [changesetId, openId.data]);

  // What a new review would throw away: hand edits and exclusions in the open one (ADR-0012).
  const openReview = useChangeset(changesetId);
  const atRisk =
    openReview.data?.status === "draft"
      ? { overrides: openReview.data.overrides, excluded: openReview.data.counts.excluded }
      : null;

  // Selected ids in table order (newest first), so the preview sample is predictable.
  const videos = useVideos();
  const selectedIds = useMemo(
    () => (videos.data ?? []).filter((v) => selected.has(v.id)).map((v) => v.id),
    [videos.data, selected],
  );

  return (
    <div className="min-h-screen bg-bg text-fg">
      <header className="flex items-center justify-between gap-4 border-b border-line bg-surface px-6 py-3">
        <h1 className="text-base font-semibold tracking-tight">YouTube Description Editor</h1>
        <div className="flex items-center gap-4">
          {health.data?.fake && (
            <span className="rounded-full bg-warn/15 px-2.5 py-0.5 text-xs font-medium text-warn">
              Fake mode: no Google calls
            </span>
          )}
          {channel && <ChannelBadge channel={channel} />}
          <ThemeToggle />
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-10">
        {(health.isError || auth.isError) && (
          <p className="text-danger" role="alert">
            Backend not reachable. Is it running on 127.0.0.1:8000?
          </p>
        )}
        {auth.isPending && !auth.isError && <p className="text-muted">Loading…</p>}
        {auth.data && !channel && <ConnectScreen status={auth.data} />}
        {channel && screen === "videos" && (
          <>
            {openReview.data?.status === "draft" && (
              <div className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-accent/30 bg-accent/5 px-4 py-3 text-sm">
                <span>
                  You have an open review: {openReview.data.counts.to_write} to write
                  {openReview.data.overrides > 0 && `, ${openReview.data.overrides} edited by hand`}.
                </span>
                <button type="button" onClick={() => setScreen("review")} className="font-medium text-accent hover:underline">
                  Continue the review →
                </button>
              </div>
            )}
            <VideosScreen selected={selected} onSelectedChange={setSelected} onEdit={() => setScreen("edit")} />
          </>
        )}
        {channel && screen === "edit" && (
          <EditBuilder
            selectedIds={selectedIds}
            draft={draft}
            onDraftChange={setDraft}
            onBack={() => setScreen("videos")}
            atRisk={atRisk}
            onReview={(id) => {
              setChangesetId(id);
              setScreen("review");
            }}
          />
        )}
        {channel && screen === "review" && changesetId !== null && (
          <ReviewScreen changesetId={changesetId} onBackToEdit={() => setScreen("edit")} />
        )}
      </main>
    </div>
  );
}
