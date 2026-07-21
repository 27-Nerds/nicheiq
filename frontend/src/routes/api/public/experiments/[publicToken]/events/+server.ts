import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { fetchBackend } from '$lib/backend';

export const POST: RequestHandler = async ({ params, request, getClientAddress }) => {
  const response = await fetchBackend(
    `/api/public/experiments/${params.publicToken}/events`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Client-IP': getClientAddress(),
      },
      body: await request.text(),
    },
  );

  return json(await response.json(), {
    status: response.status,
    headers: {
      'Cache-Control': 'private, no-store',
      'Referrer-Policy': 'no-referrer',
    },
  });
};
