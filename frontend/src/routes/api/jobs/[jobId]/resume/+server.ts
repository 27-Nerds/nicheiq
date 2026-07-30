import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { fetchBackend } from '$lib/backend';


/**
 * POST /api/jobs/:jobId/resume - Resume a failed job from checkpoint
 * Proxies to backend with internal service authentication
 * Catalog Deep Research retries also forward the user's confirmed current price.
 */
export const POST: RequestHandler = async ({ params, locals, request }) => {
  const session = await locals.auth();
  if (!session?.user) {
    throw error(401, 'Unauthorized');
  }

  const body = await request.json().catch(() => ({}));

  const response = await fetchBackend(`/api/jobs/${params.jobId}/resume`, {
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
