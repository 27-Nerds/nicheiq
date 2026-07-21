import { error, json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { fetchBackend } from '$lib/backend';
import { requireUser } from '$lib/server/requireUser';

export const GET: RequestHandler = async ({ params, locals }) => {
  const user = await requireUser(locals);
  const response = await fetchBackend(`/api/jobs/${params.jobId}/discovery-annotations`, {
    headers: { 'X-User-ID': user.id },
  });
  const data = await response.json();
  if (!response.ok) throw error(response.status, data.error || 'Failed to load annotations');
  return json(data);
};

export const PUT: RequestHandler = async ({ params, locals, request }) => {
  const user = await requireUser(locals);
  const body = await request.text();
  const response = await fetchBackend(`/api/jobs/${params.jobId}/discovery-annotations`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      'X-User-ID': user.id,
    },
    body,
  });
  const data = await response.json();
  if (!response.ok) throw error(response.status, data.error || 'Failed to save annotations');
  return json(data);
};
