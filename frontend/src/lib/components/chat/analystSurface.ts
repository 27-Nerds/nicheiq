/**
 * One source for what the analyst is CALLED and who is allowed to use it.
 *
 * The analyst is a single product with three entry points — the ranked-ideas
 * workbench, the decision-tool routes, and the completed report — reached
 * through EIGHT `ChatThread` mounts (selection `+layout.svelte`,
 * `SelectionWorkbench`, `CompletedAnalyst`, `GateWorkbench`, and the four
 * `SegmentedLedger` slots), and each one used to answer those two questions for
 * itself. The panel called itself "Analyst" in one dock and "Conversation" in
 * the other, and only the report page consulted the grant, so on every other
 * surface the refusal arrived as a 402 after the user had already written their
 * message.
 *
 * The entitlement value here is the same one the (app) layout loads on every
 * navigation (`page.data.featureAccess`), so the surface knows before it offers
 * a composer. It drives RENDERING only: the backend re-checks the grant on every
 * send, which is what actually protects the endpoint.
 */
import type { FeatureAccess } from "$lib/types/featureAccess";

/** In-panel title and dialog title, every dock, every entry point. */
export const ANALYST_PANEL_TITLE = "Analyst";

/** Where a reader without the grant goes to get one. */
export const ANALYST_BILLING_HREF = "/billing#plans";

/**
 * Shown in place of the composer when the grant is absent. Split so the render
 * can make "Subscribe" a real link to billing: naming an action the user cannot
 * take from where they are is the same defect as a live-but-dead button.
 */
export const ANALYST_LOCKED_LEAD = "The analyst is included with a subscription.";
export const ANALYST_LOCKED_LINK = "Subscribe";
export const ANALYST_LOCKED_TAIL = "to ask questions about this research.";
export const ANALYST_LOCKED_NOTICE =
  `${ANALYST_LOCKED_LEAD} ${ANALYST_LOCKED_LINK} ${ANALYST_LOCKED_TAIL}`;

/**
 * Shown ALONGSIDE a working composer when the entitlement fetch failed. A
 * transient network blip must never tell a paying subscriber to subscribe, so
 * this state claims nothing about the grant and leaves the 402 as the authority.
 */
export const ANALYST_ENTITLEMENT_UNAVAILABLE_NOTICE =
  "We couldn't check your analyst access just now. You can still ask; if your subscription isn't active the send will be refused.";

/**
 * Shown in place of a proposal card's action when the host that mounted this
 * conversation cannot perform it. The proposal is history on this screen.
 * Split so the render can link the destination rather than merely name it.
 */
export const ANALYST_ACTION_NOT_HERE_LEAD = "Proposed here.";
export const ANALYST_ACTION_NOT_HERE_LINK = "Open ranked ideas";
export const ANALYST_ACTION_NOT_HERE_TAIL = "to act on it.";
export const ANALYST_ACTION_NOT_HERE =
  `${ANALYST_ACTION_NOT_HERE_LEAD} ${ANALYST_ACTION_NOT_HERE_LINK} ${ANALYST_ACTION_NOT_HERE_TAIL}`;

/**
 * Three states, because "we could not read the grant" is not "you do not have
 * the grant". The layout loads feature access with a `.catch(() => null)`, so a
 * single failed request used to be indistinguishable from a revoked grant and
 * would have shown a subscriber the locked notice on every analyst surface.
 *
 * - `granted`    — the grant is present. Composer, no notice.
 * - `denied`     — the grant was READ and is absent (or there is no layout data
 *                  at all, e.g. a shared/visitor view). Locked notice, no
 *                  composer. Fails closed, exactly as before.
 * - `unavailable`— the entitlement request failed. Composer stays, with a notice
 *                  that says the check failed; the backend's 402 remains the
 *                  authority and still flips the surface to locked.
 */
export type AnalystEntitlement = "granted" | "denied" | "unavailable";

export function analystEntitlement(data: unknown): AnalystEntitlement {
  const layout = data as
    | { featureAccess?: Partial<FeatureAccess>; featureAccessUnavailable?: boolean }
    | null
    | undefined;
  if (layout?.featureAccess?.analyst === true) return "granted";
  if (layout?.featureAccessUnavailable === true) return "unavailable";
  return "denied";
}
