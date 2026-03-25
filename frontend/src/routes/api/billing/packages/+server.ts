import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { env } from '$env/dynamic/private';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:3001';

/**
 * GET /api/billing/packages - Get available token packages
 * Proxies to backend. Public endpoint (no auth needed), but proxied for consistency.
 */
export const GET: RequestHandler = async () => {
  const response = await fetch(`${BACKEND_URL}/api/billing/packages`);
  const data = await response.json();
  return json(data, { status: response.status });
};
