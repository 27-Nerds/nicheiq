import { error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { env } from '$env/dynamic/private';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:3001';

/**
 * GET /api/jobs/:jobId/events - Server-Sent Events for job progress
 * Proxies SSE stream from backend with internal service authentication
 */
export const GET: RequestHandler = async ({ params, locals }) => {
  const session = await locals.auth();
  if (!session?.user) {
    throw error(401, 'Unauthorized');
  }

  const response = await fetch(`${BACKEND_URL}/api/jobs/${params.jobId}/events`, {
    headers: {
      'X-Internal-Service': env.INTERNAL_SERVICE_SECRET || '',
      'X-User-ID': session.user.id,
    },
  });

  if (!response.ok) {
    // If the job is already finished, backend returns JSON instead of SSE
    const contentType = response.headers.get('Content-Type') || '';
    if (contentType.includes('application/json')) {
      const data = await response.json();
      return new Response(JSON.stringify(data), {
        status: response.status,
        headers: {
          'Content-Type': 'application/json',
        },
      });
    }
    throw error(response.status, 'Failed to connect to events stream');
  }

  // Check if response is SSE or JSON (finished job returns JSON)
  const contentType = response.headers.get('Content-Type') || '';
  if (contentType.includes('application/json')) {
    const data = await response.json();
    return new Response(JSON.stringify(data), {
      status: response.status,
      headers: {
        'Content-Type': 'application/json',
      },
    });
  }

  // Stream the SSE response
  return new Response(response.body, {
    status: response.status,
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
      'X-Accel-Buffering': 'no',
    },
  });
};
