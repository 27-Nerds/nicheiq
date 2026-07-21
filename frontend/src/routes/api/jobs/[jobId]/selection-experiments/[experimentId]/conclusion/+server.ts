import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { fetchBackend } from '$lib/backend';
import { requireUser } from '$lib/server/requireUser';

export const GET: RequestHandler = async ({ params, locals }) => {
  const user = await requireUser(locals);
  const response = await fetchBackend(
    `/api/jobs/${params.jobId}/selection-experiments/${params.experimentId}/conclusion`,
    { headers: { 'X-User-ID': user.id } },
  );
  return json(await response.json(), {
    status: response.status,
    headers: { 'Cache-Control': 'private, no-store' },
  });
};

export const POST: RequestHandler = async ({ params, request, locals }) => {
  const user = await requireUser(locals);
  const response = await fetchBackend(
    `/api/jobs/${params.jobId}/selection-experiments/${params.experimentId}/conclusion`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-User-ID': user.id,
      },
      body: JSON.stringify(await request.json()),
    },
  );
  return json(await response.json(), {
    status: response.status,
    headers: { 'Cache-Control': 'private, no-store' },
  });
};
