import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { fetchBackend } from '$lib/backend';

/**
 * GET /api/jobs/:jobId/chat/history - Persisted chat transcript for a job.
 * Proxies to the backend with internal service authentication.
 */
export const GET: RequestHandler = async ({ params, locals }) => {
  const session = await locals.auth();
  if (!session?.user) {
    throw error(401, 'Unauthorized');
  }

  const response = await fetchBackend(`/api/jobs/${params.jobId}/chat/history`, {
    headers: { 'X-User-ID': session.user.id },
  });

  const data = await response.json();
  return json(data, { status: response.status });
};
