import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { fetchBackend } from '$lib/backend';

/**
 * POST /api/auth/forgot-password - Begin a password reset
 * Proxies to backend (no authentication required)
 */
export const POST: RequestHandler = async ({ request }) => {
  const body = await request.json();

  const response = await fetchBackend(`/api/auth/forgot-password`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });

  const data = await response.json();
  return json(data, { status: response.status });
};
