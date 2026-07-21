import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { fetchBackend } from '$lib/backend';
import { requireUser } from '$lib/server/requireUser';

export const GET: RequestHandler = async ({ params, locals }) => {
  const user = await requireUser(locals);
  const response = await fetchBackend(`/api/jobs/${params.jobId}/selection-decision-state`, {
    headers: { 'X-User-ID': user.id },
  });
  return json(await response.json(), {
    status: response.status,
    headers: { 'Cache-Control': 'private, no-store' },
  });
};
