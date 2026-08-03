import { describe, expect, it } from "vitest";
import {
  selectionAnalystMode,
  shouldForceCloseToolsOnStatus,
  shouldRefreshForDraftVersion,
} from "$lib/selection/workspaceLifecycle";

describe("selectionAnalystMode", () => {
  it("keeps selection and completed-report chat interactive", () => {
    expect(selectionAnalystMode("AWAITING_SELECTION")).toBe("interactive");
    expect(selectionAnalystMode("COMPLETED")).toBe("interactive");
  });

  it("keeps failed terminal transcripts read-only", () => {
    expect(selectionAnalystMode("FAILED")).toBe("read_only");
    expect(selectionAnalystMode("CANCELLED")).toBe("read_only");
  });

  it("blocks new turns while research or a selection operation is in flight", () => {
    for (const status of ["PENDING", "QUEUED", "RUNNING", "RUNNING_PHASE2", "REGENERATING", "AWAITING_GATE", ""] as const) {
      expect(selectionAnalystMode(status)).toBe("blocked");
    }
  });
});

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
