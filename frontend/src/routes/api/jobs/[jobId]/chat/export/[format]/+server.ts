import { error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { fetchBackend } from '$lib/backend';

export const GET: RequestHandler = async ({ params, locals, url }) => {
  const session = await locals.auth();
  if (!session?.user) throw error(401, 'Unauthorized');

  const query = new URLSearchParams();
  const sections = url.searchParams.get('sections');
  if (sections) query.set('sections', sections);
  const response = await fetchBackend(
    `/api/jobs/${params.jobId}/chat/export/${params.format}?${query.toString()}`,
    { headers: { 'X-User-ID': session.user.id } },
  );
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw error(response.status, data.error || 'Failed to create report export');
  }
  return new Response(response.body, {
    status: response.status,
    headers: {
      'Content-Type': response.headers.get('Content-Type') || 'application/octet-stream',
      'Content-Disposition': response.headers.get('Content-Disposition') || '',
    },
  });
};
