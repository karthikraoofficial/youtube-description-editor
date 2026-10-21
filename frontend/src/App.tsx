import { useQuery } from "@tanstack/react-query";
import { api, type Health } from "./api/client";
import { ThemeToggle } from "./components/ThemeToggle";

export function App() {
  const health = useQuery({ queryKey: ["health"], queryFn: () => api<Health>("/health") });

  return (
    <div className="min-h-screen bg-bg text-fg">
      <header className="flex items-center justify-between border-b border-line px-6 py-3">
        <h1 className="text-base font-semibold tracking-tight">YouTube Description Editor</h1>
        <div className="flex items-center gap-3">
          {health.data?.fake && (
            <span className="rounded-full bg-warn/15 px-2.5 py-0.5 text-xs font-medium text-warn">
              Fake mode: no Google calls
            </span>
          )}
          <ThemeToggle />
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-6 py-12">
        <div className="rounded-xl border border-line bg-surface p-8">
          {health.isPending && <p className="text-muted">Connecting to backend…</p>}
          {health.isError && (
            <p className="text-danger">Backend not reachable. Is it running on 127.0.0.1:8000?</p>
          )}
          {health.isSuccess && (
            <p className="flex items-center gap-2">
              <span className="inline-block h-2.5 w-2.5 rounded-full bg-ok" aria-hidden />
              Backend connected
            </p>
          )}
        </div>
      </main>
    </div>
  );
}
