import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { env } from '$env/dynamic/private';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:3001';

/**
 * POST /api/jobs/:jobId/select-solution - Select a solution for Phase 2
 * Proxies to backend with internal service authentication
 */
export const POST: RequestHandler = async ({ params, locals, request }) => {
  const session = await locals.auth();
  if (!session?.user) {
    throw error(401, 'Unauthorized');
  }

  const body = await request.json();

  const response = await fetch(`${BACKEND_URL}/api/jobs/${params.jobId}/select-solution`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Internal-Service': env.INTERNAL_SERVICE_SECRET || '',
      'X-User-ID': session.user.id,
    },
    body: JSON.stringify(body),
  });

  const data = await response.json();
  return json(data, { status: response.status });
};
