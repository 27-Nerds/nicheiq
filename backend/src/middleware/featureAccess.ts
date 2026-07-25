import { Response, NextFunction } from 'express';
import { hasDecisionToolsAccess } from '../services/featureAccess.js';
import type { AuthenticatedRequest } from './auth.js';

/**
 * Gate for the optional decision tools. MUST be registered per-route, immediately after
 * `requireInternalAuth` — every one of these routers is mounted on the shared `/api/jobs`
 * prefix, so a router-level `.use()` would also run for requests headed for a later
 * router (chat, shares, events) and 403 them.
 *
 * 403 rather than 402: this is an admin grant, not something a user can buy.
 */
export async function requireDecisionToolsAccess(
  req: AuthenticatedRequest,
  res: Response,
  next: NextFunction,
): Promise<void> {
  if (await hasDecisionToolsAccess(req.user?.id)) {
    next();
    return;
  }
  res.status(403).json({
    error: 'Decision tools are not enabled for this account',
    code: 'FEATURE_NOT_ENABLED',
  });
}
