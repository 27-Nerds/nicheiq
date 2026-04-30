import { sequence } from '@sveltejs/kit/hooks';
import { redirect, type Handle } from '@sveltejs/kit';
import { handle as authHandle } from './auth';
import { env } from '$env/dynamic/private';
import { isLegacyCatalogPath, resolveLegacyPath } from '$lib/server/legacy-redirects';

// Fail fast if required env vars are not set
if (!env.INTERNAL_SERVICE_SECRET) {
  throw new Error('INTERNAL_SERVICE_SECRET environment variable is required');
}

const HUB = '/ideas';

/**
 * Phase 3.5 — 301-redirect every legacy `/catalog/*` URL to its new
 * `/ideas/*`, `/idea/*`, or `/pain-point/*` equivalent. Runs BEFORE the auth
 * handle so crawler traffic doesn't pay a session-decode cost just to be
 * redirected.
 *
 * Falls through to the `/ideas` hub on any failure (DB miss, backend down,
 * cache stampede) — legacy URLs must never 404.
 */
const legacyRedirectHandle: Handle = async ({ event, resolve }) => {
  const path = event.url.pathname;
  if (!isLegacyCatalogPath(path)) return resolve(event);

  const target = await resolveLegacyPath(path, event.url.searchParams);
  const finalTarget = target && target !== path ? target : HUB;
  // Defensive: if computed target equals current path, don't redirect.
  if (finalTarget === path) return resolve(event);
  throw redirect(301, finalTarget);
};

export const handle = sequence(legacyRedirectHandle, authHandle);
