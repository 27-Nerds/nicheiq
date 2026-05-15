import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { fetchBackend } from '$lib/backend';


function adminHeaders(session: { user: { id: string; role?: string | null } }): HeadersInit {
  return {
    'Content-Type': 'application/json',
    'X-User-ID': session.user.id,
    'X-User-Role': session.user.role || '',
  };
}

export const GET: RequestHandler = async ({ locals }) => {
  const session = await locals.auth();
  if (!session?.user) throw error(401, 'Unauthorized');
  if (session.user.role !== 'ADMIN') throw error(403, 'Admin access required');

  const res = await fetchBackend(`/api/admin/catalog/collections`, {
    headers: adminHeaders(session),
  });
  return json(await res.json(), { status: res.status });
};

export const POST: RequestHandler = async ({ request, locals }) => {
  const session = await locals.auth();
  if (!session?.user) throw error(401, 'Unauthorized');
  if (session.user.role !== 'ADMIN') throw error(403, 'Admin access required');

  const body = await request.json();
  const res = await fetchBackend(`/api/admin/catalog/collections`, {
    method: 'POST',
    headers: adminHeaders(session),
    body: JSON.stringify(body),
  });
  return json(await res.json(), { status: res.status });
};
