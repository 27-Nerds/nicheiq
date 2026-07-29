import type { RequestHandler } from './$types';
import { fetchBackend } from '$lib/backend';
import { proxyConceptForge } from '$lib/server/conceptForgeProxy';
import { requireUser } from '$lib/server/requireUser';

export const POST: RequestHandler = async ({ params, locals }) => {
  const user = await requireUser(locals);
  return proxyConceptForge(() => fetchBackend(
    `/api/jobs/${params.jobId}/selection-concept-sets/${encodeURIComponent(params.setId)}/archive`,
    {
      method: 'POST',
      headers: { 'X-User-ID': user.id },
    },
  ));
};
