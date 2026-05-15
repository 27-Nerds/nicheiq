import { error, json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { fetchBackend } from '$lib/backend';


/**
 * POST /api/shared/discovery/:shareToken/vote - Submit or update a vote (public, no auth)
 */
export const POST: RequestHandler = async ({ params, request }) => {
  const body = await request.json();

  const response = await fetchBackend(`/api/shared/discovery/${params.shareToken}/vote`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  const data = await response.json();
  if (!response.ok) {
    throw error(response.status, data.error || 'Failed to submit vote');
  }

  return json(data);
};
