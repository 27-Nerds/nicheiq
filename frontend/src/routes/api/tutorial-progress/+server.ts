import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { fetchBackend } from '$lib/backend';

/**
 * Tutorial progress for the CURRENT session user. The user id is taken from the session,
 * never from the path or body, so one user can't read or write another's progress.
 *
 * Fetched client-side on demand rather than in the (app) layout load: it is only needed
 * on the job/selection surfaces, and keeping it out of the layout avoids paying for it on
 * every navigation (and avoids an SSR flash of the invitation).
 */

export const GET: RequestHandler = async ({ locals }) => {
  const session = await locals.auth();
  if (!session?.user) throw error(401, 'Unauthorized');

  const response = await fetchBackend(`/api/users/${session.user.id}/tutorial-progress`, {
    headers: { 'X-User-ID': session.user.id },
  });
  return json(await response.json(), { status: response.status });
};

export const PATCH: RequestHandler = async ({ request, locals }) => {
  const session = await locals.auth();
  if (!session?.user) throw error(401, 'Unauthorized');

  const body = await request.json();
  const response = await fetchBackend(`/api/users/${session.user.id}/tutorial-progress`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      'X-User-ID': session.user.id,
    },
    body: JSON.stringify(body),
  });
  return json(await response.json(), { status: response.status });
};
