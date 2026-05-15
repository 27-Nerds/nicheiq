import { error, json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { fetchBackend } from '$lib/backend';


/**
 * POST /api/jobs/:jobId/share/regenerate - Generate new share token
 */
export const POST: RequestHandler = async ({ params, locals }) => {
  const session = await locals.auth();
  if (!session?.user) {
    throw error(401, 'Unauthorized');
  }

  const response = await fetchBackend(`/api/jobs/${params.jobId}/share/regenerate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-User-ID': session.user.id,
    },
  });

  const data = await response.json();
  if (!response.ok) {
    throw error(response.status, data.error || 'Failed to regenerate share link');
  }

  return json(data);
};
