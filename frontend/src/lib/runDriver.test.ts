import { describe, expect, it } from "vitest";
import { nextMove, tabDriverId } from "./runDriver";

describe("nextMove", () => {
  it("steps again straight away while the run is still writing", () => {
    expect(nextMove({ kind: "ok", status: "running" })).toEqual({ action: "step", delayMs: 0 });
  });

  it("stops once the run has stopped", () => {
    for (const status of ["completed", "paused", "paused_quota", "interrupted", "cancelled"] as const) {
      expect(nextMove({ kind: "ok", status })).toEqual({ action: "stop" });
    }
  });

  it("watches, and tries again shortly, when another tab or request is writing the run", () => {
    expect(nextMove({ kind: "conflict" })).toEqual({ action: "watch", delayMs: 2000 });
  });

  it("retries after a network or server error, well inside the two-minute lease", () => {
    expect(nextMove({ kind: "error" })).toEqual({ action: "step", delayMs: 3000 });
  });

  it("stops when the server refuses the request outright (gone, signed out, invalid)", () => {
    expect(nextMove({ kind: "refused" })).toEqual({ action: "stop" });
  });
});

describe("tabDriverId", () => {
  const memory = (): Pick<Storage, "getItem" | "setItem"> => {
    const values = new Map<string, string>();
    return { getItem: (k) => values.get(k) ?? null, setItem: (k, v) => void values.set(k, v) };
  };

  it("keeps one id per tab, so a reloaded tab carries on driving its run", () => {
    const storage = memory();
    const first = tabDriverId(storage);
    expect(first).toMatch(/^tab-.{8,}/);
    expect(tabDriverId(storage)).toBe(first);
  });

  it("still gives an id when storage is unavailable", () => {
    const broken = {
      getItem: () => {
        throw new Error("blocked");
      },
      setItem: () => {
        throw new Error("blocked");
      },
    };
    expect(tabDriverId(broken)).toMatch(/^tab-.{8,}/);
  });
});
