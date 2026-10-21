import { describe, expect, it } from "vitest";
import { type DiffRow, sideBySide, withContext } from "./diff";

const show = (rows: DiffRow[]) =>
  rows.map((r) =>
    r.kind === "gap" ? `… ${r.hidden}` : `${r.kind}: ${r.left?.text ?? "∅"} | ${r.right?.text ?? "∅"}`,
  );

describe("sideBySide", () => {
  it("lines up unchanged lines and marks an appended block", () => {
    expect(show(sideBySide("Song\nby me", "Song\nby me\n\nFooter"))).toEqual([
      "same: Song | Song",
      "same: by me | by me",
      "added: ∅ | ",
      "added: ∅ | Footer",
    ]);
  });

  it("pairs an edited line with its replacement", () => {
    expect(show(sideBySide("a\nold link\nc", "a\nnew link\nc"))).toEqual([
      "same: a | a",
      "changed: old link | new link",
      "same: c | c",
    ]);
  });

  it("shows removals and keeps line numbers for each side", () => {
    const rows = sideBySide("a\nb\nc", "a\nc");
    expect(show(rows)).toEqual(["same: a | a", "removed: b | ∅", "same: c | c"]);
    expect(rows.map((r) => [r.left?.n, r.right?.n])).toEqual([
      [1, 1],
      [2, undefined],
      [3, 2],
    ]);
  });

  it("pairs uneven replacement blocks, leftovers become added or removed", () => {
    expect(show(sideBySide("x\none\ntwo\ny", "x\nONE\ny"))).toEqual([
      "same: x | x",
      "changed: one | ONE",
      "removed: two | ∅",
      "same: y | y",
    ]);
  });

  it("treats an empty description as having no lines", () => {
    expect(show(sideBySide("", "New"))).toEqual(["added: ∅ | New"]);
    expect(show(sideBySide("Old", ""))).toEqual(["removed: Old | ∅"]);
    expect(show(sideBySide("Same", "Same"))).toEqual(["same: Same | Same"]);
  });

  it("stays fast on long descriptions with an appended footer", () => {
    const long = Array.from({ length: 4000 }, (_, i) => `line ${i}`).join("\n");
    const started = performance.now();
    const rows = sideBySide(long, `${long}\n\nFooter`);
    expect(performance.now() - started).toBeLessThan(200);
    expect(rows.filter((r) => r.kind !== "same")).toHaveLength(2);
  });
});

describe("withContext", () => {
  it("keeps changes plus two lines of context and folds the rest", () => {
    const before = ["1", "2", "3", "4", "5", "6", "7", "8"].join("\n");
    const after = ["1", "2", "3", "4", "5", "6", "7", "EIGHT"].join("\n");
    expect(show(withContext(sideBySide(before, after), 2))).toEqual([
      "… 5",
      "same: 6 | 6",
      "same: 7 | 7",
      "changed: 8 | EIGHT",
    ]);
  });

  it("does not fold a gap of a single line", () => {
    const before = "a\nb\nc\nd\ne\nf\ng";
    const after = "A\nb\nc\nd\ne\nf\nG";
    expect(show(withContext(sideBySide(before, after), 2)).filter((l) => l.startsWith("…"))).toEqual([]);
  });
});
