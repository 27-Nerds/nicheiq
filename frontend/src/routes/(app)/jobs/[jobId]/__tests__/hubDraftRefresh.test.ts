import { describe, it, expect, vi, beforeEach } from "vitest";

// Spy-wrap the SHARED workspace helper so the tests assert the hub guard REUSES it
// (same semantics as selection/+layout.svelte) instead of duplicating the logic.
vi.mock("$lib/selection/workspaceLifecycle", async (importOriginal) => {
  const actual = await importOriginal<typeof import("$lib/selection/workspaceLifecycle")>();
  return {
    ...actual,
    shouldRefreshForDraftVersion: vi.fn(actual.shouldRefreshForDraftVersion),
  };
});

import { shouldRefreshForDraftVersion } from "$lib/selection/workspaceLifecycle";
import { createHubDraftRefreshGuard } from "../hubDraftRefresh";

const payload = (version: number) => ({ selectionDraft: { version } });

describe("createHubDraftRefreshGuard", () => {
  beforeEach(() => {
    vi.mocked(shouldRefreshForDraftVersion).mockClear();
  });

  it("delegates drift detection to the shared shouldRefreshForDraftVersion helper", () => {
    const refresh = vi.fn();
    const guard = createHubDraftRefreshGuard(refresh);
    guard.seedBaseline(2);
    guard.handleSsePayload(payload(3));
    expect(shouldRefreshForDraftVersion).toHaveBeenCalledWith(3, 2, 0);
    expect(refresh).toHaveBeenCalledTimes(1);
  });

  it("refreshes when another tab's broadcast carries a newer draft version", () => {
    const refresh = vi.fn();
    const guard = createHubDraftRefreshGuard(refresh);
    guard.seedBaseline(1);
    guard.handleSsePayload(payload(2));
    expect(refresh).toHaveBeenCalledTimes(1);
  });

  it("dedupes repeated broadcasts of the same version while a refresh is in flight", () => {
    const refresh = vi.fn();
    const guard = createHubDraftRefreshGuard(refresh);
    guard.seedBaseline(1);
    guard.handleSsePayload(payload(2));
    guard.handleSsePayload(payload(2));
    expect(refresh).toHaveBeenCalledTimes(1);
  });

  it("excludes own saves: the workbench reports its bumped version before the broadcast", () => {
    const refresh = vi.fn();
    const guard = createHubDraftRefreshGuard(refresh);
    guard.seedBaseline(1);
    guard.reportLocalVersion(2); // own save bumped the workbench version
    guard.handleSsePayload(payload(2)); // own broadcast round-trips
    expect(refresh).not.toHaveBeenCalled();
    guard.handleSsePayload(payload(3)); // a genuinely newer save elsewhere still refreshes
    expect(refresh).toHaveBeenCalledTimes(1);
  });

  it("re-seeding from fresh server data resets the baseline", () => {
    const refresh = vi.fn();
    const guard = createHubDraftRefreshGuard(refresh);
    guard.seedBaseline(1);
    guard.handleSsePayload(payload(2));
    guard.seedBaseline(2); // invalidateAll landed: server data now carries v2
    guard.handleSsePayload(payload(2));
    expect(refresh).toHaveBeenCalledTimes(1);
  });

  it("ignores payloads without a draft version (progress-only broadcasts)", () => {
    const refresh = vi.fn();
    const guard = createHubDraftRefreshGuard(refresh);
    guard.seedBaseline(undefined);
    guard.handleSsePayload(null);
    guard.handleSsePayload({});
    guard.handleSsePayload({ selectionDraft: null });
    expect(refresh).not.toHaveBeenCalled();
  });
});
