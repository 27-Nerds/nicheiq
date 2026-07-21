import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { fetchBackend } from '$lib/backend';
import { requireUser } from '$lib/server/requireUser';

export const PATCH: RequestHandler = async ({ params, locals, request }) => {
  const user = await requireUser(locals);
  const response = await fetchBackend(
    `/api/jobs/${params.jobId}/selection-assumptions/${params.assumptionId}`,
    {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        'X-User-ID': user.id,
      },
      body: await request.text(),
    },
  );
  return json(await response.json(), { status: response.status });
};
