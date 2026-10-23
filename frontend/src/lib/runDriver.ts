import { type RunStatus, isActive } from "../api/runs";

/** How the last POST /runs/{id}/step went: "refused" is any other 4xx, "error" a 5xx or a network failure. */
export type StepOutcome =
  | { kind: "ok"; status: RunStatus }
  | { kind: "conflict" }
  | { kind: "refused" }
  | { kind: "error" };

/** What the Run screen does next (ADR-0017). */
export type NextMove = { action: "step"; delayMs: number } | { action: "watch"; delayMs: number } | { action: "stop" };

const RETRY_MS = 3000; // a dropped request; the Run's lease lasts two minutes, so retrying keeps it
const WATCH_MS = 2000;

export function nextMove(outcome: StepOutcome): NextMove {
  switch (outcome.kind) {
    case "ok":
      return isActive(outcome.status) ? { action: "step", delayMs: 0 } : { action: "stop" };
    case "conflict":
      // Another tab holds the lease, or another request from this tab is mid-Step: show progress, try again.
      return { action: "watch", delayMs: WATCH_MS };
    case "refused":
      return { action: "stop" }; // asking again won't change the answer
    case "error":
      return { action: "step", delayMs: RETRY_MS };
  }
}

const KEY = "yde-run-driver";
let fallback: string | undefined;

/** This tab's driver id. sessionStorage is per tab and survives a reload, so a reloaded tab keeps its Run. */
export function tabDriverId(storage: Pick<Storage, "getItem" | "setItem"> | undefined = globalThis.sessionStorage): string {
  try {
    const known = storage?.getItem(KEY);
    if (known) return known;
    const id = newId();
    storage?.setItem(KEY, id);
    return id;
  } catch {
    fallback ??= newId(); // storage blocked: one id for this page's lifetime
    return fallback;
  }
}

const newId = () => `tab-${crypto.randomUUID()}`;
