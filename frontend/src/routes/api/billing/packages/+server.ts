import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { fetchBackend } from '$lib/backend';


/**
 * GET /api/billing/packages - Get available token packages
 * Proxies to backend. Public endpoint (no auth needed), but proxied for consistency.
 */
export const GET: RequestHandler = async () => {
  const response = await fetchBackend(`/api/billing/packages`);
  const data = await response.json();
  return json(data, { status: response.status });
};
