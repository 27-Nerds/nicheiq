import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { fetchBackend } from '$lib/backend';
import { requireUser } from '$lib/server/requireUser';

export const POST: RequestHandler = async ({ params, locals, request }) => {
  const user = await requireUser(locals);
  const response = await fetchBackend(
    `/api/jobs/${params.jobId}/selection-evidence/${params.evidenceId}/retract`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-User-ID': user.id,
      },
      body: await request.text(),
    },
  );
  return json(await response.json(), {
    status: response.status,
    headers: { 'Cache-Control': 'private, no-store' },
  });
};
