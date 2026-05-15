import { error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { fetchBackend } from '$lib/backend';


export const DELETE: RequestHandler = async ({ params, locals }) => {
  const session = await locals.auth();
  if (!session?.user) throw error(401, 'Unauthorized');
  if (session.user.role !== 'ADMIN') throw error(403, 'Admin access required');

  const res = await fetchBackend(
    `/api/admin/catalog/collections/${params.id}/items/${params.itemId}`,
    {
      method: 'DELETE',
      headers: {
        'X-User-ID': session.user.id,
        'X-User-Role': session.user.role || '',
      },
    },
  );
  return new Response(null, { status: res.status });
};
