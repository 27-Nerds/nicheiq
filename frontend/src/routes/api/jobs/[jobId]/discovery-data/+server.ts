import { error, json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { env } from '$env/dynamic/private';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:3001';

/**
 * GET /api/jobs/:jobId/discovery-data - Materialized discovery evidence
 * Proxies to backend with internal service authentication
 */
export const GET: RequestHandler = async ({ params, locals }) => {
  const session = await locals.auth();
  if (!session?.user) {
    throw error(401, 'Unauthorized');
  }

  const response = await fetch(`${BACKEND_URL}/api/jobs/${params.jobId}/discovery-data`, {
    headers: {
      'X-Internal-Service': env.INTERNAL_SERVICE_SECRET || '',
      'X-User-ID': session.user.id,
    },
  });

  if (!response.ok) {
    if (response.status === 404) {
      throw error(404, 'Discovery data not available');
    }
    const data = await response.json().catch(() => ({ error: 'Unknown error' }));
    throw error(response.status, data.error || 'Failed to fetch discovery data');
  }

  const data = await response.json();
  return json(data);
};
