import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { fetchBackend } from '$lib/backend';


export const GET: RequestHandler = async ({ locals, url }) => {
  const session = await locals.auth();
  if (!session?.user) throw error(401, 'Unauthorized');

  const q = url.searchParams.get('q') || '';
  if (q.length < 2) return json({ categories: [], ideas: [], painPoints: [] });

  const response = await fetchBackend(`/api/catalog/search?q=${encodeURIComponent(q)}`, {
    headers: {
      'X-User-ID': session.user.id,
    },
  });

  const data = await response.json();
  return json(data, { status: response.status });
};
