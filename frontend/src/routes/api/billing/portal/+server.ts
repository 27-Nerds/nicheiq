import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { fetchBackend } from '$lib/backend';

/**
 * POST /api/billing/portal - Open the Stripe Customer Portal (manage/cancel/switch).
 * Proxies to the backend with internal service auth. 400 if the user has no Stripe customer.
 */
export const POST: RequestHandler = async ({ locals }) => {
  const session = await locals.auth();
  if (!session?.user) {
    throw error(401, 'Unauthorized');
  }

  const response = await fetchBackend(`/api/billing/portal`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-User-ID': session.user.id,
      'X-User-Email': session.user.email || '',
    },
    body: '{}',
  });

  const data = await response.json();
  return json(data, { status: response.status });
};
