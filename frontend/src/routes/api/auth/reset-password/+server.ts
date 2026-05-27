import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { fetchBackend } from '$lib/backend';

/**
 * POST /api/auth/reset-password - Complete a password reset using a one-time token
 * Proxies to backend (no authentication required)
 */
export const POST: RequestHandler = async ({ request }) => {
  const body = await request.json();

  const response = await fetchBackend(`/api/auth/reset-password`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });

  const data = await response.json();
  return json(data, { status: response.status });
};
