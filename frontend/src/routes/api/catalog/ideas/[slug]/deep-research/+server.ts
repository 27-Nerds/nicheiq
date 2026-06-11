import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { fetchBackend } from '$lib/backend';

/**
 * POST /api/catalog/ideas/[slug]/deep-research — start a deep-research job seeded
 * from a catalog idea. Proxies to the backend with the session user.
 */
export const POST: RequestHandler = async ({ params, locals }) => {
  const session = await locals.auth();
  if (!session?.user) {
    throw error(401, 'Unauthorized');
  }

  const response = await fetchBackend(`/api/catalog/ideas/${params.slug}/deep-research`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-User-ID': session.user.id,
    },
    body: JSON.stringify({}),
  });

  const data = await response.json();
  return json(data, { status: response.status });
};
