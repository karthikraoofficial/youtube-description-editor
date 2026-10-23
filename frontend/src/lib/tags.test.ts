import { describe, expect, it } from "vitest";
import { parseTags } from "./tags";

describe("parseTags", () => {
  it("takes tags separated by commas or on their own lines, trimmed", () => {
    expect(parseTags("guitar, live\n  late night ,")).toEqual(["guitar", "live", "late night"]);
  });

  it("drops blanks between them", () => {
    expect(parseTags("Guitar\n\n, live")).toEqual(["Guitar", "live"]);
  });

  it("gives nothing for empty text", () => {
    expect(parseTags(" \n , ")).toEqual([]);
  });
});
