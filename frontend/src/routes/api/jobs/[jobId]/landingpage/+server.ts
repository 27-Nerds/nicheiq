import { error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { env } from '$env/dynamic/private';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:3001';

/**
 * GET /api/jobs/:jobId/landingpage - View or download landing page HTML
 * Proxies to backend with internal service authentication, streams response
 */
export const GET: RequestHandler = async ({ params, locals, url }) => {
  const session = await locals.auth();
  if (!session?.user) {
    throw error(401, 'Unauthorized');
  }

  // Forward the download query parameter if present
  const downloadParam = url.searchParams.get('download');
  const queryString = downloadParam ? `?download=${downloadParam}` : '';

  const response = await fetch(`${BACKEND_URL}/api/jobs/${params.jobId}/landingpage${queryString}`, {
    headers: {
      'X-Internal-Service': env.INTERNAL_SERVICE_SECRET || '',
      'X-User-ID': session.user.id,
    },
  });

  if (!response.ok) {
    const data = await response.json();
    throw error(response.status, data.error || 'Failed to fetch landing page');
  }

  // Stream the response body
  return new Response(response.body, {
    status: response.status,
    headers: {
      'Content-Type': response.headers.get('Content-Type') || 'text/html',
      'Content-Disposition': response.headers.get('Content-Disposition') || '',
      'Content-Length': response.headers.get('Content-Length') || '',
    },
  });
};
