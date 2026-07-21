import { error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { fetchBackend } from '$lib/backend';

/**
 * GET /api/jobs/:jobId/solutions/:ideaId/export/:format?revision=N
 * Private download of one exact stored candidate (md or json). Proxies to the
 * backend with the session user's identity.
 */
export const GET: RequestHandler = async ({ params, locals, url }) => {
  const session = await locals.auth();
  if (!session?.user) throw error(401, 'Unauthorized');

  const query = new URLSearchParams();
  const revision = url.searchParams.get('revision');
  if (revision) query.set('revision', revision);
  const response = await fetchBackend(
    `/api/jobs/${params.jobId}/solutions/${params.ideaId}/export/${params.format}?${query.toString()}`,
    { headers: { 'X-User-ID': session.user.id } },
  );
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw error(response.status, data.error || 'Failed to create idea export');
  }
  return new Response(response.body, {
    status: response.status,
    headers: {
      'Content-Type': response.headers.get('Content-Type') || 'application/octet-stream',
      'Content-Disposition': response.headers.get('Content-Disposition') || '',
    },
  });
};
