import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { fetchBackend } from '$lib/backend';


export const POST: RequestHandler = async ({ params, request, locals }) => {
  const session = await locals.auth();
  if (!session?.user) throw error(401, 'Unauthorized');
  if (session.user.role !== 'ADMIN') throw error(403, 'Admin access required');

  const body = await request.json();
  const res = await fetchBackend(`/api/admin/catalog/collections/${params.id}/items`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-User-ID': session.user.id,
      'X-User-Role': session.user.role || '',
    },
    body: JSON.stringify(body),
  });
  return json(await res.json(), { status: res.status });
};
