import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { fetchBackend } from '$lib/backend';

/**
 * POST /api/catalog/pain-research — start a research job seeded from 1 (single CTA)
 * or 2-5 (remix) catalog pain points. Proxies to the backend with the session user.
 */
export const POST: RequestHandler = async ({ request, locals }) => {
  const session = await locals.auth();
  if (!session?.user) {
    throw error(401, 'Unauthorized');
  }

  const body = await request.json();

  const response = await fetchBackend(`/api/catalog/pain-research`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-User-ID': session.user.id,
    },
    body: JSON.stringify(body),
  });

  const data = await response.json();
  return json(data, { status: response.status });
};
