import { useQuery } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useAuthStatus } from "./api/auth";
import { api, type Health } from "./api/client";
import type { Field, Operation } from "./api/preview";
import { useChangeset, useOpenChangesetId } from "./api/changesets";
import { useUnfinishedRuns } from "./api/runs";
import { useVideos } from "./api/videos";
import { AppShell } from "./components/AppShell";
import { Card } from "./components/ui/Card";
import type { NavTarget, Screen } from "./lib/nav";
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
  const [screen, setScreen] = useState<Screen>("videos");
  const [runId, setRunId] = useState<number | null>(null);
  const [runFrom, setRunFrom] = useState<NavTarget>("videos");
  const openRun = (id: number, from: NavTarget) => {
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
    <AppShell
      screen={screen}
      runFrom={runFrom}
      onNavigate={setScreen}
      channel={channel}
      fake={!!health.data?.fake}
    >
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
              <Card
                key={run.id}
                className="mb-4 flex flex-wrap items-center justify-between gap-2 border-l-4 border-l-warn px-4 py-3 text-sm"
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
                  Open the run <ArrowRight aria-hidden className="inline size-4" />
                </button>
              </Card>
            ))}
            {openReview.data?.status === "draft" && (
              <Card className="mb-4 flex flex-wrap items-center justify-between gap-2 border-l-4 border-l-accent px-4 py-3 text-sm">
                <span>
                  You have an open review: {openReview.data.counts.to_write} to write
                  {openReview.data.overrides > 0 && `, ${openReview.data.overrides} edited by hand`}.
                </span>
                <button type="button" onClick={() => setScreen("review")} className="font-medium text-accent hover:underline">
                  Continue the review <ArrowRight aria-hidden className="inline size-4" />
                </button>
              </Card>
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
    </AppShell>
  );
}
