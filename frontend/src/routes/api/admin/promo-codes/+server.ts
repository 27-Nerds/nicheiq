import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { fetchBackend } from '$lib/backend';


export const GET: RequestHandler = async ({ locals, url }) => {
  const session = await locals.auth();
  if (!session?.user) {
    throw error(401, 'Unauthorized');
  }
  if (session.user.role !== 'ADMIN') {
    throw error(403, 'Admin access required');
  }

  const page = url.searchParams.get('page') || '1';
  const limit = url.searchParams.get('limit') || '20';

  const response = await fetchBackend(`/api/admin/promo-codes?page=${page}&limit=${limit}`, {
    headers: {
      'X-User-ID': session.user.id,
      'X-User-Role': session.user.role,
    },
  });

  const data = await response.json();
  return json(data, { status: response.status });
};

export const POST: RequestHandler = async ({ request, locals }) => {
  const session = await locals.auth();
  if (!session?.user) {
    throw error(401, 'Unauthorized');
  }
  if (session.user.role !== 'ADMIN') {
    throw error(403, 'Admin access required');
  }

  const body = await request.json();

  const response = await fetchBackend(`/api/admin/promo-codes`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-User-ID': session.user.id,
      'X-User-Role': session.user.role,
    },
    body: JSON.stringify(body),
  });

  const data = await response.json();
  return json(data, { status: response.status });
};
