import type { RequestHandler } from './$types';
import { fetchBackend } from '$lib/backend';
import { proxyConceptForge } from '$lib/server/conceptForgeProxy';
import { requireUser } from '$lib/server/requireUser';

async function proxy(method: 'GET' | 'POST', jobId: string, userId: string, body?: string) {
  return proxyConceptForge(() => fetchBackend(`/api/jobs/${jobId}/selection-concept-sets`, {
    method,
    headers: {
      ...(body ? { 'Content-Type': 'application/json' } : {}),
      'X-User-ID': userId,
    },
    body,
  }));
}

export const GET: RequestHandler = async ({ params, locals }) => {
  const user = await requireUser(locals);
  return proxy('GET', params.jobId, user.id);
};

export const POST: RequestHandler = async ({ params, locals, request }) => {
  const user = await requireUser(locals);
  return proxy('POST', params.jobId, user.id, await request.text());
};
