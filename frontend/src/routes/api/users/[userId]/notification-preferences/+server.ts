import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { fetchBackend } from '$lib/backend';


/**
 * GET /api/users/[userId]/notification-preferences
 * Get user's notification preferences
 */
export const GET: RequestHandler = async ({ locals, params }) => {
  const session = await locals.auth();
  if (!session?.user) {
    throw error(401, 'Unauthorized');
  }

  // Users can only access their own preferences
  if (session.user.id !== params.userId) {
    throw error(403, 'Forbidden');
  }

  const response = await fetchBackend(`/api/users/${params.userId}/notification-preferences`, {
    method: 'GET',
    headers: {
      'X-User-ID': session.user.id,
    },
  });

  const data = await response.json();
  return json(data, { status: response.status });
};

/**
 * PUT /api/users/[userId]/notification-preferences
 * Update user's notification preferences
 */
export const PUT: RequestHandler = async ({ locals, params, request }) => {
  const session = await locals.auth();
  if (!session?.user) {
    throw error(401, 'Unauthorized');
  }

  // Users can only update their own preferences
  if (session.user.id !== params.userId) {
    throw error(403, 'Forbidden');
  }

  const body = await request.json();

  const response = await fetchBackend(`/api/users/${params.userId}/notification-preferences`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      'X-User-ID': session.user.id,
    },
    body: JSON.stringify(body),
  });

  const data = await response.json();
  return json(data, { status: response.status });
};
