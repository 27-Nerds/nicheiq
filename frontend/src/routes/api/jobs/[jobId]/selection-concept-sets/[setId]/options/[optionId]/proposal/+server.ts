import type { RequestHandler } from './$types';
import { fetchBackend } from '$lib/backend';
import { proxyConceptForge } from '$lib/server/conceptForgeProxy';
import { requireUser } from '$lib/server/requireUser';

export const POST: RequestHandler = async ({ params, locals, request }) => {
  const user = await requireUser(locals);
  const body = await request.text();
  return proxyConceptForge(() => fetchBackend(
    `/api/jobs/${params.jobId}/selection-concept-sets/${encodeURIComponent(params.setId)}/options/${encodeURIComponent(params.optionId)}/proposal`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-User-ID': user.id,
      },
      body,
    },
  ));
};
