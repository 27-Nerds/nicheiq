import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { env } from '$env/dynamic/private';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:3001';

export const GET: RequestHandler = async ({ locals, url }) => {
  const session = await locals.auth();
  if (!session?.user) {
    throw error(401, 'Unauthorized');
  }
  if (session.user.role !== 'ADMIN') {
    throw error(403, 'Admin access required');
  }

  const params = new URLSearchParams();
  if (url.searchParams.has('page')) params.set('page', url.searchParams.get('page')!);
  if (url.searchParams.has('limit')) params.set('limit', url.searchParams.get('limit')!);

  const response = await fetch(`${BACKEND_URL}/api/admin/shares?${params}`, {
    headers: {
      'X-Internal-Service': env.INTERNAL_SERVICE_SECRET || '',
      'X-User-ID': session.user.id,
      'X-User-Role': session.user.role,
    },
  });

  const data = await response.json();
  return json(data, { status: response.status });
};
