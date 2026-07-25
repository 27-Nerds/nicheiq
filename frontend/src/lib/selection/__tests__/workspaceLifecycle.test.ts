import { describe, expect, it } from "vitest";
import {
  shouldForceCloseToolsOnStatus,
  shouldRefreshForDraftVersion,
} from "$lib/selection/workspaceLifecycle";

describe("shouldForceCloseToolsOnStatus", () => {
  it("keeps tools (and their dirty drafts) open through a transient REGENERATING flip", () => {
    expect(shouldForceCloseToolsOnStatus("REGENERATING")).toBe(false);
  });

  it("does not close anything while selection is still interactive", () => {
    expect(shouldForceCloseToolsOnStatus("AWAITING_SELECTION")).toBe(false);
  });

  it("force-closes tools when the job leaves selection for good", () => {
    for (const status of ["QUEUED", "RUNNING_PHASE2", "RUNNING", "COMPLETED", "FAILED", "CANCELLED", "AWAITING_GATE"] as const) {
      expect(shouldForceCloseToolsOnStatus(status)).toBe(true);
    }
  });
});

describe("shouldRefreshForDraftVersion", () => {
  it("refreshes when another tab saved a newer draft version", () => {
    expect(shouldRefreshForDraftVersion(5, 4, 0)).toBe(true);
  });

  it("skips the tab's own save (local version already caught up)", () => {
    expect(shouldRefreshForDraftVersion(5, 5, 0)).toBe(false);
  });

  it("skips stale or repeated broadcasts", () => {
    expect(shouldRefreshForDraftVersion(4, 5, 0)).toBe(false);
    expect(shouldRefreshForDraftVersion(6, 4, 6)).toBe(false);
  });

  it("ignores payloads without a draft version", () => {
    expect(shouldRefreshForDraftVersion(undefined, 4, 0)).toBe(false);
  });
});
