import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useAuthStatus } from "./api/auth";
import { api, type Health } from "./api/client";
import type { Field, Operation } from "./api/preview";
import { useChangeset, useOpenChangesetId } from "./api/changesets";
import { useUnfinishedRuns } from "./api/runs";
import { useVideos } from "./api/videos";
import { ChannelBadge } from "./components/ChannelBadge";
import { QuotaMeter } from "./components/QuotaMeter";
import { ThemeToggle } from "./components/ThemeToggle";
import type { Selection } from "./lib/selection";
import { ConnectScreen } from "./screens/Connect";
import { EditBuilder, INITIAL_OPERATION } from "./screens/EditBuilder";
import { ReviewScreen } from "./screens/Review";
import { HistoryScreen } from "./screens/History";
import { RunScreen } from "./screens/RunScreen";
import { VideosScreen } from "./screens/Videos";

export function App() {
  const health = useQuery({ queryKey: ["health"], queryFn: () => api<Health>("/health") });
  const auth = useAuthStatus();
  const channel = auth.data?.state === "connected" ? auth.data.channel : null;
  const [selected, setSelected] = useState<Selection>(() => new Set());
  const [screen, setScreen] = useState<"videos" | "edit" | "review" | "run" | "history">("videos");
  const [runId, setRunId] = useState<number | null>(null);
  const [runFrom, setRunFrom] = useState<"videos" | "history">("videos");
  const openRun = (id: number, from: "videos" | "history") => {
    setRunId(id);
    setRunFrom(from);
    setScreen("run");
  };
  const [changesetId, setChangesetId] = useState<number | null>(null);
  const [field, setField] = useState<Field>("description");
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

  // Runs waiting for Resume (paused, out of quota, or interrupted), so they're easy to find again.
  const unfinished = useUnfinishedRuns();

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
      <header className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 whitespace-nowrap border-b sm:flex-nowrap border-line bg-surface px-4 py-3 sm:px-6">
        <div className="flex min-w-0 items-center gap-3 sm:gap-5">
          <h1 className={`truncate text-base font-semibold tracking-tight ${channel ? "hidden sm:block" : ""}`} title="YouTube Description Editor">
            <span className="hidden xl:inline">YouTube </span>Description Editor
          </h1>
          {channel && (
            <nav className="flex gap-1 text-sm" aria-label="Main">
              {(
                [
                  ["videos", "Videos"],
                  ["history", "History"],
                ] as const
              ).map(([target, label]) => (
                <button
                  key={target}
                  type="button"
                  onClick={() => setScreen(target)}
                  aria-current={screen === target ? "page" : undefined}
                  className={`rounded-md px-3 py-1.5 ${screen === target ? "bg-line/70 font-medium" : "text-muted hover:text-fg"}`}
                >
                  {label}
                </button>
              ))}
            </nav>
          )}
        </div>
        <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-2 sm:shrink-0 sm:flex-nowrap">
          {health.data?.fake && (
            <span
              data-fake-badge
              className="rounded-full bg-warn/15 px-2.5 py-0.5 text-xs font-medium text-warn"
              title="Fake mode: an in-memory channel. Nothing is sent to Google."
            >
              Fake<span className="hidden sm:inline"> mode</span><span className="sr-only">: an in-memory channel. Nothing is sent to Google.</span>
            </span>
          )}
          {channel && <QuotaMeter compact />}
          {channel && <ChannelBadge channel={channel} />}
          <ThemeToggle />
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-10">
        {(health.isError || auth.isError) && (
          <p className="text-danger" role="alert">
            The app's server isn't answering. Running locally? Check that <code>python dev.py</code> is still running.
          </p>
        )}
        {auth.isPending && !auth.isError && <p className="text-muted">Loading…</p>}
        {auth.data && !channel && <ConnectScreen status={auth.data} />}
        {channel && screen === "videos" && (
          <>
            {unfinished.data?.filter((run) => run.counts.pending > 0).map((run) => (
              <div
                key={run.id}
                className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-warn/30 bg-warn/10 px-4 py-3 text-sm"
              >
                <span>
                  Run #{run.id} stopped with {run.counts.pending} video{run.counts.pending === 1 ? "" : "s"} still queued
                  {run.status === "paused_quota" ? " (daily quota ran out)" : ""}.
                </span>
                <button
                  type="button"
                  onClick={() => {
                    setRunId(run.id);
                    setScreen("run");
                  }}
                  className="font-medium text-accent hover:underline"
                >
                  Open the run →
                </button>
              </div>
            ))}
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
            field={field}
            onFieldChange={setField}
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
          <ReviewScreen
            changesetId={changesetId}
            onBackToEdit={() => setScreen("edit")}
            onApplied={(id) => {
              setRunId(id);
              setSelected(new Set());
              setScreen("run");
            }}
          />
        )}
        {channel && screen === "run" && runId !== null && (
          <RunScreen
            key={runId}
            runId={runId}
            onDone={() => setScreen(runFrom)}
            doneLabel={runFrom === "history" ? "Back to history" : "Back to videos"}
            onOpenRun={(id) => openRun(id, runFrom)}
          />
        )}
        {channel && screen === "history" && (
          <HistoryScreen onOpenRun={(id) => openRun(id, "history")} />
        )}
      </main>
    </div>
  );
}
