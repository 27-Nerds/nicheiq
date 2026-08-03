import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { fetchBackend } from '$lib/backend';
import { requireUser } from '$lib/server/requireUser';

export const PUT: RequestHandler = async ({ params, locals, request }) => {
  const user = await requireUser(locals);

  const response = await fetchBackend(
    `/api/jobs/${params.jobId}/selection-experiments/${params.experimentId}`,
    {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'X-User-ID': user.id,
      },
      body: await request.text(),
    },
  );
  return json(await response.json(), { status: response.status });
};

export const DELETE: RequestHandler = async ({ params, locals, request }) => {
  const user = await requireUser(locals);

  const response = await fetchBackend(
    `/api/jobs/${params.jobId}/selection-experiments/${params.experimentId}`,
    {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
        'X-User-ID': user.id,
      },
      body: await request.text(),
    },
  );
  if (response.status === 204) return new Response(null, { status: 204 });
  return json(await response.json(), { status: response.status });
};
