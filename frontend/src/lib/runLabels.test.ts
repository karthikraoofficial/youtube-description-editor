import { describe, expect, it } from "vitest";
import { ITEM_STATUS, RUN_STATUS } from "./runLabels";

describe("RUN_STATUS tones", () => {
  it("shows a finished Run as ok and a running one as accent", () => {
    expect(RUN_STATUS.completed.tone).toBe("ok");
    expect(RUN_STATUS.running.tone).toBe("accent");
  });

  it("shows every Run waiting for Resume as warn", () => {
    expect(RUN_STATUS.paused.tone).toBe("warn");
    expect(RUN_STATUS.paused_quota.tone).toBe("warn");
    expect(RUN_STATUS.interrupted.tone).toBe("warn");
  });

  it("shows cancelled and starting Runs as neutral", () => {
    expect(RUN_STATUS.cancelled.tone).toBe("neutral");
    expect(RUN_STATUS.pending.tone).toBe("neutral");
  });
});

describe("ITEM_STATUS tones", () => {
  it("shows written Videos as ok and failed or blocked ones as danger", () => {
    expect(ITEM_STATUS.success.tone).toBe("ok");
    expect(ITEM_STATUS.failed.tone).toBe("danger");
    expect(ITEM_STATUS.blocked.tone).toBe("danger");
  });

  it("shows a Video skipped as stale as warn, and untouched ones as neutral", () => {
    expect(ITEM_STATUS.stale.tone).toBe("warn");
    expect(ITEM_STATUS.noop.tone).toBe("neutral");
    expect(ITEM_STATUS.pending.tone).toBe("neutral");
    expect(ITEM_STATUS.cancelled.tone).toBe("neutral");
  });
});
