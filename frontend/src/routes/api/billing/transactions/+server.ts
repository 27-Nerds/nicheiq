import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { env } from '$env/dynamic/private';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:3001';

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

  const response = await fetch(
    `${BACKEND_URL}/api/billing/transactions?page=${page}&limit=${limit}`,
    {
      method: 'GET',
      headers: {
        'X-Internal-Service': env.INTERNAL_SERVICE_SECRET,
        'X-User-ID': session.user.id,
      },
    }
  );

  const data = await response.json();
  return json(data, { status: response.status });
};
