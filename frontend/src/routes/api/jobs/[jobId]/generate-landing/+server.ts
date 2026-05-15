import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { fetchBackend } from '$lib/backend';


/**
 * POST /api/jobs/:jobId/generate-landing - Generate landing page for a completed job
 * Proxies to backend with internal service authentication
 * Charges landing_page stage credits
 */
export const POST: RequestHandler = async ({ params, locals }) => {
  const session = await locals.auth();
  if (!session?.user) {
    throw error(401, 'Unauthorized');
  }

  const response = await fetchBackend(`/api/jobs/${params.jobId}/generate-landing`, {
    method: 'POST',
    headers: {
      'X-User-ID': session.user.id,
    },
  });

  const data = await response.json();
  return json(data, { status: response.status });
};
