import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { fetchBackend } from '$lib/backend';


/**
 * POST /api/jobs/:jobId/regenerate-ideas - Regenerate solution ideas
 * Proxies to backend with internal service authentication
 */
export const POST: RequestHandler = async ({ params, locals, request }) => {
  const session = await locals.auth();
  if (!session?.user) {
    throw error(401, 'Unauthorized');
  }

  // Forward the optional body (e.g. { idea_focus }) to the backend.
  const body = await request.json().catch(() => ({}));

  const response = await fetchBackend(`/api/jobs/${params.jobId}/regenerate-ideas`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-User-ID': session.user.id,
    },
    body: JSON.stringify(body ?? {}),
  });

  const data = await response.json();
  return json(data, { status: response.status });
};
