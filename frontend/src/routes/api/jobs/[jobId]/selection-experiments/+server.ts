import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { fetchBackend } from '$lib/backend';
import { requireUser } from '$lib/server/requireUser';

export const GET: RequestHandler = async ({ params, locals }) => {
  const user = await requireUser(locals);
  const response = await fetchBackend(`/api/jobs/${params.jobId}/selection-experiments`, {
    headers: { 'X-User-ID': user.id },
  });
  return json(await response.json(), { status: response.status });
};

export const POST: RequestHandler = async ({ params, locals, request }) => {
  const user = await requireUser(locals);
  const response = await fetchBackend(`/api/jobs/${params.jobId}/selection-experiments`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-User-ID': user.id,
    },
    body: await request.text(),
  });
  return json(await response.json(), { status: response.status });
};
