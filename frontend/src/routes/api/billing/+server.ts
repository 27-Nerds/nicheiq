import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { env } from '$env/dynamic/private';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:3001';

/**
 * GET /api/billing - Get user's credit balance and stats
 * Proxies to backend with internal service authentication
 */
export const GET: RequestHandler = async ({ locals }) => {
  const session = await locals.auth();
  if (!session?.user) {
    throw error(401, 'Unauthorized');
  }

  const response = await fetch(`${BACKEND_URL}/api/billing`, {
    method: 'GET',
    headers: {
      'X-Internal-Service': env.INTERNAL_SERVICE_SECRET,
      'X-User-ID': session.user.id,
    },
  });

  const data = await response.json();
  return json(data, { status: response.status });
};
