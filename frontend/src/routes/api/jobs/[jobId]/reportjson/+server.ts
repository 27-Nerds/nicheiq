import { error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { env } from '$env/dynamic/private';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:3001';

/**
 * GET /api/jobs/:jobId/reportjson - Download report JSON
 * Proxies to backend with internal service authentication, streams response
 */
export const GET: RequestHandler = async ({ params, locals }) => {
  const session = await locals.auth();
  if (!session?.user) {
    throw error(401, 'Unauthorized');
  }

  const response = await fetch(`${BACKEND_URL}/api/jobs/${params.jobId}/reportjson`, {
    headers: {
      'X-Internal-Service': env.INTERNAL_SERVICE_SECRET,
      'X-User-ID': session.user.id,
    },
  });

  if (!response.ok) {
    const data = await response.json();
    throw error(response.status, data.error || 'Failed to fetch report');
  }

  // Stream the response body
  return new Response(response.body, {
    status: response.status,
    headers: {
      'Content-Type': response.headers.get('Content-Type') || 'application/json',
      'Content-Disposition': response.headers.get('Content-Disposition') || '',
      'Content-Length': response.headers.get('Content-Length') || '',
    },
  });
};
