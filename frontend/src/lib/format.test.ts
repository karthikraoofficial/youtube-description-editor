import { describe, expect, it } from "vitest";
import { formatDuration } from "./format";

describe("formatDuration", () => {
  it("shows m:ss under an hour", () => {
    expect(formatDuration(0)).toBe("0:00");
    expect(formatDuration(45)).toBe("0:45");
    expect(formatDuration(185)).toBe("3:05");
  });

  it("shows h:mm:ss from an hour", () => {
    expect(formatDuration(3600)).toBe("1:00:00");
    expect(formatDuration(3723)).toBe("1:02:03");
  });
});
