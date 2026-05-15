import { error, json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { fetchBackend } from '$lib/backend';


/**
 * GET /api/jobs/:jobId/report-summary - Lightweight report summary for preview cards
 * Proxies to backend with internal service authentication
 */
export const GET: RequestHandler = async ({ params, locals }) => {
  const session = await locals.auth();
  if (!session?.user) {
    throw error(401, 'Unauthorized');
  }

  const response = await fetchBackend(`/api/jobs/${params.jobId}/report-summary`, {
    headers: {
      'X-User-ID': session.user.id,
    },
  });

  if (!response.ok) {
    const data = await response.json();
    throw error(response.status, data.error || 'Failed to fetch report summary');
  }

  const data = await response.json();
  return json(data);
};
