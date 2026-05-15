import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { fetchBackend } from '$lib/backend';


/**
 * GET /api/billing/transactions - Get paginated transaction history
 * Proxies to backend with internal service authentication
 */
export const GET: RequestHandler = async ({ locals, url }) => {
  const session = await locals.auth();
  if (!session?.user) {
    throw error(401, 'Unauthorized');
  }

  const page = url.searchParams.get('page') || '1';
  const limit = url.searchParams.get('limit') || '20';

  const response = await fetchBackend(
    `/api/billing/transactions?page=${page}&limit=${limit}`,
    {
      method: 'GET',
      headers: {
        'X-User-ID': session.user.id,
      },
    }
  );

  const data = await response.json();
  return json(data, { status: response.status });
};
