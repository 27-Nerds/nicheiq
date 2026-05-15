import { env } from '$env/dynamic/private';

// Single source of truth for backend HTTP communication. Every SSR route /
// API proxy that talks to the Express backend (`backend/`) goes through
// `fetchBackend()`; constants are exported for the few callsites that need
// to compose URLs or merge headers manually (e.g., POST with JSON body,
// admin-authenticated calls that layer `X-User-ID` on top).
//
// Why this exists: prior to this module, `BACKEND_URL` was redeclared in
// 100+ files and `'X-Internal-Service': env.INTERNAL_SERVICE_SECRET || ''`
// was inlined on every single fetch — drift hazard plus painful greppability.

export const BACKEND_URL = env.BACKEND_URL || 'http://localhost:3001';

// Internal-service auth header. The Express backend's `requireInternalService`
// middleware (and `requireInternalAuth` for in-app routes) checks this on
// every protected route. Routes that also forward user identity should spread
// additional headers (e.g. `X-User-ID`, `Content-Type`) via the `init.headers`
// argument to `fetchBackend` — INTERNAL_HEADERS stays as the base.
export const INTERNAL_HEADERS: Record<string, string> = {
  'X-Internal-Service': env.INTERNAL_SERVICE_SECRET || '',
};

/**
 * Backend fetch wrapper. Prepends `BACKEND_URL`, merges `INTERNAL_HEADERS`
 * into the request, and forwards everything else through. Caller-supplied
 * `init.headers` win on conflict (so e.g. setting `Content-Type` overrides
 * any default we add later if any).
 *
 * Example:
 *   const res = await fetchBackend('/api/public/catalog/totals');
 *   const res = await fetchBackend(`/api/jobs/${id}`, {
 *     method: 'POST',
 *     headers: { 'X-User-ID': session.user.id, 'Content-Type': 'application/json' },
 *     body: JSON.stringify(payload),
 *   });
 */
export function fetchBackend(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  return fetch(`${BACKEND_URL}${path}`, {
    ...init,
    headers: { ...INTERNAL_HEADERS, ...(init.headers ?? {}) },
  });
}
