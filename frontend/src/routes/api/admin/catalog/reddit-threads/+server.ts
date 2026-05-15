import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { fetchBackend } from '$lib/backend';


export const GET: RequestHandler = async ({ locals, url }) => {
  const session = await locals.auth();
  if (!session?.user) throw error(401, 'Unauthorized');
  if (session.user.role !== 'ADMIN') throw error(403, 'Admin access required');

  const params = new URLSearchParams(url.searchParams);

  const response = await fetchBackend(`/api/admin/catalog/reddit-threads?${params}`, {
    headers: {
      'X-User-ID': session.user.id,
      'X-User-Role': session.user.role,
    },
  });

  const data = await response.json();
  return json(data, { status: response.status });
};

export const DELETE: RequestHandler = async ({ locals }) => {
  const session = await locals.auth();
  if (!session?.user) throw error(401, 'Unauthorized');
  if (session.user.role !== 'ADMIN') throw error(403, 'Admin access required');

  const response = await fetchBackend(`/api/admin/catalog/reddit-threads/cleanup`, {
    method: 'DELETE',
    headers: {
      'X-User-ID': session.user.id,
      'X-User-Role': session.user.role,
    },
  });

  const data = await response.json();
  return json(data, { status: response.status });
};
