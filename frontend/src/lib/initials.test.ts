import { describe, expect, it } from "vitest";
import { initials } from "./initials";

describe("initials", () => {
  it("takes the first letter of the first two words", () => {
    expect(initials("Fake Channel")).toBe("FC");
    expect(initials("karthik rao official")).toBe("KR");
  });

  it("handles one word, extra spaces and empty names", () => {
    expect(initials("  Solo  ")).toBe("S");
    expect(initials("")).toBe("?");
  });

  it("keeps emoji and non-Latin letters whole", () => {
    expect(initials("🎬 Studio")).toBe("🎬S");
    expect(initials("Ünïcode")).toBe("Ü");
  });
});
