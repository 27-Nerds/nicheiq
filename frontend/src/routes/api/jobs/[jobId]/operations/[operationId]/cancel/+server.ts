import { error, json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { fetchBackend } from '$lib/backend';

export const POST: RequestHandler = async ({ params, locals }) => {
  const session = await locals.auth();
  if (!session?.user) throw error(401, 'Unauthorized');

  const response = await fetchBackend(
    `/api/jobs/${params.jobId}/operations/${params.operationId}/cancel`,
    {
      method: 'POST',
      headers: { 'X-User-ID': session.user.id },
    },
  );
  const data = await response.json().catch(() => ({}));
  return json(data, { status: response.status });
};
