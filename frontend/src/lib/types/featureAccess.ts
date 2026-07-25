/**
 * Admin-granted per-user feature flags, served by GET /api/users/:userId/feature-access
 * and exposed on `page.data.featureAccess` by (app)/+layout.server.ts.
 *
 * These drive RENDERING only. Every gated endpoint re-checks the grant server-side, so a
 * stale or spoofed client value cannot reach the data.
 */
export interface FeatureAccess {
  /** Chat with Analyst — `isEntitledUser` OR the `chatAnalystAccess` grant. */
  analyst: boolean;
  /**
   * The optional selection checks (build limits, evidence check + risk areas, questions
   * to resolve, test plans, fit-for-you, branch a direction) and the post-research
   * Decision Lab. The required path — ranked ideas, shortlist, compare, review — is
   * never gated by this.
   */
  decisionTools: boolean;
}

/** Fail-closed default for any consumer that has no layout data (visitor/shared views). */
export const NO_FEATURE_ACCESS: FeatureAccess = { analyst: false, decisionTools: false };
