import { CONFIG } from '../config.js';

/**
 * Validate a return URL to prevent open redirect attacks.
 * Must be a relative path starting with / and resolving to our origin.
 *
 * Shared by the token (one-time) and subscription Stripe checkout flows. Lives
 * here — not in stripeService — because subscriptionService also needs it and
 * stripeService already imports from subscriptionService (importing back would
 * create a service-level circular dependency).
 */
export function isValidReturnUrl(url: string): boolean {
  if (typeof url !== 'string') return false;
  if (!url.startsWith('/')) return false;
  if (url.startsWith('//')) return false;
  if (url.includes('://')) return false;
  if (url.includes('\\')) return false;
  if (url.length > 500) return false;
  try {
    const parsed = new URL(url, CONFIG.baseUrl);
    if (parsed.origin !== new URL(CONFIG.baseUrl).origin) return false;
  } catch {
    return false;
  }
  return true;
}
