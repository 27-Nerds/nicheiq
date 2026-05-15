import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { fetchBackend } from '$lib/backend';


export const GET: RequestHandler = async ({ locals, url }) => {
  const session = await locals.auth();
  if (!session?.user) throw error(401, 'Unauthorized');

  const params = new URLSearchParams();
  for (const [key, value] of url.searchParams) {
    params.set(key, value);
  }

  const response = await fetchBackend(`/api/catalog/ideas?${params}`, {
    headers: {
      'X-User-ID': session.user.id,
    },
  });

  const data = await response.json();
  return json(data, { status: response.status });
};
