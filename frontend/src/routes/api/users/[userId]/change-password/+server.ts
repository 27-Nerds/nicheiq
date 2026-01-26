import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { env } from '$env/dynamic/private';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:3001';

/**
 * POST /api/users/[userId]/change-password
 * Change user's password
 */
export const POST: RequestHandler = async ({ locals, params, request }) => {
  const session = await locals.auth();
  if (!session?.user) {
    throw error(401, 'Unauthorized');
  }

  // Users can only change their own password
  if (session.user.id !== params.userId) {
    throw error(403, 'Forbidden');
  }

  const body = await request.json();

  const response = await fetch(`${BACKEND_URL}/api/users/${params.userId}/change-password`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Internal-Service': env.INTERNAL_SERVICE_SECRET || '',
      'X-User-ID': session.user.id,
    },
    body: JSON.stringify(body),
  });

  const data = await response.json();
  return json(data, { status: response.status });
};
