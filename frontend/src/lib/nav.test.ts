import { describe, expect, it } from "vitest";
import { activeNav, screenTitle } from "./nav";

describe("activeNav", () => {
  it("keeps Videos highlighted through the edit flow", () => {
    expect(activeNav("videos", "videos")).toBe("videos");
    expect(activeNav("edit", "videos")).toBe("videos");
    expect(activeNav("review", "videos")).toBe("videos");
  });

  it("highlights History on the History screen", () => {
    expect(activeNav("history", "videos")).toBe("history");
  });

  it("highlights where a Run was opened from", () => {
    expect(activeNav("run", "videos")).toBe("videos");
    expect(activeNav("run", "history")).toBe("history");
  });
});

describe("screenTitle", () => {
  it("names each screen for the phone top bar", () => {
    expect(screenTitle("videos")).toBe("Videos");
    expect(screenTitle("edit")).toBe("Edit");
    expect(screenTitle("review")).toBe("Review");
    expect(screenTitle("run")).toBe("Run");
    expect(screenTitle("history")).toBe("History");
  });
});
