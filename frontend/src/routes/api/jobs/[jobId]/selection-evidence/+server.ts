import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { fetchBackend } from '$lib/backend';
import { requireUser } from '$lib/server/requireUser';

function privateJson(body: unknown, status: number) {
  return json(body, { status, headers: { 'Cache-Control': 'private, no-store' } });
}

export const GET: RequestHandler = async ({ params, locals }) => {
  const user = await requireUser(locals);
  const response = await fetchBackend(`/api/jobs/${params.jobId}/selection-evidence`, {
    headers: { 'X-User-ID': user.id },
  });
  return privateJson(await response.json(), response.status);
};

export const POST: RequestHandler = async ({ params, locals, request }) => {
  const user = await requireUser(locals);
  const response = await fetchBackend(`/api/jobs/${params.jobId}/selection-evidence`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-User-ID': user.id,
    },
    body: await request.text(),
  });
  return privateJson(await response.json(), response.status);
};
