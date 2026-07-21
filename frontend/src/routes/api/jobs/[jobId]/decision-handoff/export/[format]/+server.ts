import { error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { fetchBackend } from '$lib/backend';
import { requireUser } from '$lib/server/requireUser';

export const GET: RequestHandler = async ({ params, locals }) => {
  const user = await requireUser(locals);
  const response = await fetchBackend(
    `/api/jobs/${params.jobId}/decision-handoff/export/${params.format}`,
    { headers: { 'X-User-ID': user.id } },
  );
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw error(response.status, data.error || 'Failed to export decision handoff');
  }
  return new Response(response.body, {
    status: response.status,
    headers: {
      'Content-Type': response.headers.get('Content-Type') || 'application/octet-stream',
      'Content-Disposition': response.headers.get('Content-Disposition') || '',
      'Cache-Control': 'private, no-store',
    },
  });
};
