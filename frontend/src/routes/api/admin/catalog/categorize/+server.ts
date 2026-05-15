import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { fetchBackend } from '$lib/backend';


export const POST: RequestHandler = async ({ request, locals }) => {
  const session = await locals.auth();
  if (!session?.user) throw error(401, 'Unauthorized');
  if (session.user.role !== 'ADMIN') throw error(403, 'Admin access required');

  const body = await request.json();

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 90_000);

  try {
    const response = await fetchBackend(`/api/admin/catalog/categorize`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-User-ID': session.user.id,
        'X-User-Role': session.user.role,
      },
      body: JSON.stringify(body),
      signal: controller.signal,
    });

    const data = await response.json();
    return json(data, { status: response.status });
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      return json({ error: 'Categorization request timed out' }, { status: 504 });
    }
    throw err;
  } finally {
    clearTimeout(timeout);
  }
};
