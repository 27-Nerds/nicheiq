import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { env } from '$env/dynamic/private';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:3001';

/**
 * POST /api/jobs/:jobId/cancel - Cancel a job with credit refund
 * Proxies to backend with internal service authentication
 */
export const POST: RequestHandler = async ({ params, locals }) => {
  const session = await locals.auth();
  if (!session?.user) {
    throw error(401, 'Unauthorized');
  }

  const response = await fetch(`${BACKEND_URL}/api/jobs/${params.jobId}/cancel`, {
    method: 'POST',
    headers: {
      'X-Internal-Service': env.INTERNAL_SERVICE_SECRET || '',
      'X-User-ID': session.user.id,
    },
  });

  const data = await response.json();
  return json(data, { status: response.status });
};
