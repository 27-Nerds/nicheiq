import { error, json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { fetchBackend } from '$lib/backend';


/**
 * GET /api/jobs/:jobId/discovery-share - Get discovery share status
 */
export const GET: RequestHandler = async ({ params, locals }) => {
  const session = await locals.auth();
  if (!session?.user) {
    throw error(401, 'Unauthorized');
  }

  const response = await fetchBackend(`/api/jobs/${params.jobId}/discovery-share`, {
    headers: {
      'X-User-ID': session.user.id,
    },
  });

  const data = await response.json();
  if (!response.ok) {
    throw error(response.status, data.error || 'Failed to get discovery share status');
  }

  return json(data);
};

/**
 * POST /api/jobs/:jobId/discovery-share - Enable discovery sharing
 */
export const POST: RequestHandler = async ({ params, locals }) => {
  const session = await locals.auth();
  if (!session?.user) {
    throw error(401, 'Unauthorized');
  }

  const response = await fetchBackend(`/api/jobs/${params.jobId}/discovery-share`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-User-ID': session.user.id,
    },
  });

  const data = await response.json();
  if (!response.ok) {
    throw error(response.status, data.error || 'Failed to enable discovery sharing');
  }

  return json(data);
};

/**
 * DELETE /api/jobs/:jobId/discovery-share - Disable discovery sharing
 */
export const DELETE: RequestHandler = async ({ params, locals }) => {
  const session = await locals.auth();
  if (!session?.user) {
    throw error(401, 'Unauthorized');
  }

  const response = await fetchBackend(`/api/jobs/${params.jobId}/discovery-share`, {
    method: 'DELETE',
    headers: {
      'X-User-ID': session.user.id,
    },
  });

  const data = await response.json();
  if (!response.ok) {
    throw error(response.status, data.error || 'Failed to disable discovery sharing');
  }

  return json(data);
};
