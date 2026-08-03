import type { Job } from "$lib/types/job";

export type SelectionAnalystMode = "interactive" | "blocked" | "read_only";

/**
 * Keep the saved analyst transcript available throughout the run, while matching
 * the chat endpoint's lifecycle boundary for new turns on selection routes.
 * Completed-report chat is intentionally interactive; failed terminal runs are
 * history only, and every in-flight/non-selection state blocks the composer.
 */
export function selectionAnalystMode(status: Job["status"] | ""): SelectionAnalystMode {
  if (status === "AWAITING_SELECTION" || status === "COMPLETED") return "interactive";
  if (status === "FAILED" || status === "CANCELLED") return "read_only";
  return "blocked";
}

/**
 * Whether a status flip observed mid-session must force-close the open
 * selection tools (discarding any in-progress drafts).
 *
 * - AWAITING_SELECTION: nothing to close.
 * - REGENERATING is transient — the job returns to AWAITING_SELECTION — so
 *   open tools stay mounted with their drafts; `interactive` gating disables
 *   their submits while it lasts.
 * - Every other status means the job left selection for good, so force-close
 *   is acceptable (the tools' content is no longer actionable).
 */
export function shouldForceCloseToolsOnStatus(status: Job["status"] | ""): boolean {
  return status !== "AWAITING_SELECTION" && status !== "REGENERATING";
}

/**
 * Whether an SSE job payload's selection-draft version warrants a data
 * refresh. Own saves never trigger it: `persistShortlist` bumps the local
 * version before this can observe the broadcast, so `incoming` is only newer
 * when ANOTHER tab saved. `lastHandled` dedupes repeated broadcasts of the
 * same version while `invalidateAll` is still in flight.
 */
export function shouldRefreshForDraftVersion(
  incoming: number | undefined,
  localVersion: number,
  lastHandled: number,
): boolean {
  return typeof incoming === "number"
    && Number.isFinite(incoming)
    && incoming > localVersion
    && incoming > lastHandled;
}
