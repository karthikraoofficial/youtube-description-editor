import { describe, expect, it } from "vitest";
import { sampleIds } from "./sample";

describe("sampleIds", () => {
  const ids = ["a", "b", "c", "d", "e", "f", "g"];

  it("takes the first page", () => {
    expect(sampleIds(ids, 0, 3)).toEqual(["a", "b", "c"]);
  });

  it("pages forward and wraps around", () => {
    expect(sampleIds(ids, 1, 3)).toEqual(["d", "e", "f"]);
    expect(sampleIds(ids, 2, 3)).toEqual(["g", "a", "b"]);
    expect(sampleIds(ids, 3, 3)).toEqual(["c", "d", "e"]);
  });

  it("never repeats when the selection is smaller than a page", () => {
    expect(sampleIds(["a", "b"], 0, 5)).toEqual(["a", "b"]);
    expect(sampleIds(["a", "b"], 4, 5)).toEqual(["a", "b"]);
    expect(sampleIds([], 0, 5)).toEqual([]);
  });
});
