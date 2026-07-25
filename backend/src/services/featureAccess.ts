import { prisma } from './db.js';
import { isEntitledUser } from './catalogService.js';

/**
 * Per-user feature grants toggled manually in the admin panel.
 *
 * Both helpers do a fresh authoritative DB read (header-independent) so a grant or a
 * revocation takes effect immediately, mirroring `isEntitledUser`.
 */

/**
 * Chat with Analyst. ADDITIVE grant: an entitled user (ADMIN / fullCatalogAccess /
 * active subscription) keeps the analyst regardless, and `chatAnalystAccess` widens it
 * to a user who is none of those. Narrowing it to the grant alone would revoke the
 * analyst from every paying subscriber.
 */
export async function hasAnalystAccess(userId: string | undefined): Promise<boolean> {
  if (!userId) return false;
  if (await isEntitledUser(userId)) return true;
  const u = await prisma.user.findUnique({
    where: { id: userId },
    select: { chatAnalystAccess: true },
  });
  return u?.chatAnalystAccess === true;
}

/**
 * The optional selection checks (build limits, evidence check, questions to resolve,
 * test plans, fit-for-you, branch a direction) and the post-research Decision Lab.
 * NOT tied to billing — a pure admin grant, plus ADMIN by role.
 */
export async function hasDecisionToolsAccess(userId: string | undefined): Promise<boolean> {
  if (!userId) return false;
  const u = await prisma.user.findUnique({
    where: { id: userId },
    select: { role: true, decisionToolsAccess: true },
  });
  if (!u) return false;
  return u.role === 'ADMIN' || u.decisionToolsAccess === true;
}

export interface FeatureAccess {
  analyst: boolean;
  decisionTools: boolean;
}

/** Both grants in one round trip — what the frontend layout loader reads. */
export async function getFeatureAccess(userId: string | undefined): Promise<FeatureAccess> {
  const [analyst, decisionTools] = await Promise.all([
    hasAnalystAccess(userId),
    hasDecisionToolsAccess(userId),
  ]);
  return { analyst, decisionTools };
}
