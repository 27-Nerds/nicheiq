import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { fetchBackend } from '$lib/backend';
import { requireUser } from '$lib/server/requireUser';

async function proxy(
  method: 'GET' | 'POST',
  jobId: string,
  userId: string,
  body?: string,
) {
  const response = await fetchBackend(`/api/jobs/${jobId}/founder-fit`, {
    method,
    headers: {
      ...(body ? { 'Content-Type': 'application/json' } : {}),
      'X-User-ID': userId,
    },
    body,
  });
  return json(await response.json(), { status: response.status });
}

export const GET: RequestHandler = async ({ params, locals }) => {
  const user = await requireUser(locals);
  return proxy('GET', params.jobId, user.id);
};

export const POST: RequestHandler = async ({ params, locals, request }) => {
  const user = await requireUser(locals);
  return proxy('POST', params.jobId, user.id, await request.text());
};
