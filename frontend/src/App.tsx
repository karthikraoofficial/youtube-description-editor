import { useQuery } from "@tanstack/react-query";
import { useAuthStatus } from "./api/auth";
import { api, type Health } from "./api/client";
import { ChannelBadge } from "./components/ChannelBadge";
import { ThemeToggle } from "./components/ThemeToggle";
import { ConnectScreen } from "./screens/Connect";
import { VideosScreen } from "./screens/Videos";

export function App() {
  const health = useQuery({ queryKey: ["health"], queryFn: () => api<Health>("/health") });
  const auth = useAuthStatus();
  const channel = auth.data?.state === "connected" ? auth.data.channel : null;

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
        {channel && <VideosScreen />}
      </main>
    </div>
  );
}
