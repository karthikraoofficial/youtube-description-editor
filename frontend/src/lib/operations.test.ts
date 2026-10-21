import { describe, expect, it } from "vitest";
import { OPERATIONS, isReady } from "./operations";

describe("operation metadata", () => {
  it("lists Append to Description as its own option", () => {
    expect(OPERATIONS.map((o) => o.label)).toContain("Append to Description");
  });

  it("starts every operation empty and not ready to preview", () => {
    for (const o of OPERATIONS) expect(isReady(o.empty)).toBe(false);
  });

  it("is ready once the required text is filled in", () => {
    expect(isReady({ type: "find_replace", find: "a", replace: "", regex: false, case_sensitive: true })).toBe(true);
    expect(isReady({ type: "append", text: "  \n ", separator: "blank_line", skip_if_present: false })).toBe(false);
    expect(isReady({ type: "append", text: "Footer", separator: "blank_line", skip_if_present: false })).toBe(true);
  });
});
