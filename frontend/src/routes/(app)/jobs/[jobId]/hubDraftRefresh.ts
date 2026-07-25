import { shouldRefreshForDraftVersion } from "$lib/selection/workspaceLifecycle";

/**
 * Hub-page mirror of the selection workspace's draft-version SSE refresh guard
 * (selection/+layout.svelte): when a draft-PUT broadcast from ANOTHER tab carries a
 * selectionDraft.version newer than the version this page already knows, the page must
 * refresh (invalidateAll) so the hub's SelectionWorkbench doesn't go stale.
 *
 * Own-save dedupe works the same way as the workspace: SelectionWorkbench reports its
 * post-save draft version up (reportLocalVersion) before its own broadcast round-trips,
 * so `incoming > known` only holds for another tab's save. Versioning/dedup semantics
 * live in the SHARED `shouldRefreshForDraftVersion` helper — not duplicated here.
 */
export interface HubDraftRefreshGuard {
  /** Baseline from fresh server data (navigation / post-invalidate). */
  seedBaseline(version: number | null | undefined): void;
  /** SelectionWorkbench's current draft version (hydration + own saves). */
  reportLocalVersion(version: number): void;
  /** Inspect an incoming SSE job payload; triggers `refresh` on version drift. */
  handleSsePayload(
    job: { selectionDraft?: { version: number } | null } | null | undefined,
  ): void;
}

export function createHubDraftRefreshGuard(refresh: () => void): HubDraftRefreshGuard {
  let knownVersion = 0;
  // Dedupes repeated broadcasts of the same version while a refresh is in flight.
  let lastHandledVersion = 0;

  return {
    seedBaseline(version) {
      knownVersion = version ?? 0;
    },
    reportLocalVersion(version) {
      if (version > knownVersion) knownVersion = version;
    },
    handleSsePayload(job) {
      const incoming = job?.selectionDraft?.version;
      if (shouldRefreshForDraftVersion(incoming, knownVersion, lastHandledVersion)) {
        lastHandledVersion = incoming!;
        refresh();
      }
    },
  };
}
