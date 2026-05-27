import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { fetchBackend } from '$lib/backend';

/**
 * GET /api/billing/plans - Get active subscription plans.
 * Proxies the public backend endpoint (no auth needed) and forwards its
 * Cache-Control so the public, non-user plan list stays cacheable.
 */
export const GET: RequestHandler = async () => {
  const response = await fetchBackend(`/api/billing/plans`);
  const data = await response.json();
  const cacheControl = response.headers.get('cache-control');
  return json(data, {
    status: response.status,
    headers: response.ok && cacheControl ? { 'cache-control': cacheControl } : {},
  });
};
