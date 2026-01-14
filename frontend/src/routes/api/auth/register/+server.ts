import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { env } from '$env/dynamic/private';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:3001';

/**
 * POST /api/auth/register - Register a new user
 * Proxies to backend (no authentication required)
 */
export const POST: RequestHandler = async ({ request }) => {
  const body = await request.json();

  const response = await fetch(`${BACKEND_URL}/api/auth/register`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });

  const data = await response.json();
  return json(data, { status: response.status });
};
