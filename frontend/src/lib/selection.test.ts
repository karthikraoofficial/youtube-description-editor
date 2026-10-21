import { describe, expect, it } from "vitest";
import { pruned, toggled, withMany } from "./selection";

describe("selection updates", () => {
  it("toggles one id", () => {
    expect([...toggled(new Set(["a"]), "b")]).toEqual(["a", "b"]);
    expect([...toggled(new Set(["a", "b"]), "a")]).toEqual(["b"]);
  });

  it("selects or deselects many ids", () => {
    expect([...withMany(new Set(["a"]), ["b", "c"], true)]).toEqual(["a", "b", "c"]);
    expect([...withMany(new Set(["a", "b", "c"]), ["a", "c"], false)]).toEqual(["b"]);
  });

  it("prunes ids that no longer exist, and keeps identity when nothing changes", () => {
    const prev = new Set(["a", "gone"]);
    expect([...pruned(prev, new Set(["a", "b"]))]).toEqual(["a"]);
    const same = new Set(["a"]);
    expect(pruned(same, new Set(["a", "b"]))).toBe(same);
  });
});
