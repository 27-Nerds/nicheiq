import { error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { fetchBackend } from '$lib/backend';

export const GET: RequestHandler = async ({ params }) => {
  const response = await fetchBackend(`/api/public/experiments/${params.publicToken}`);

  if (!response.ok) {
    const body = await response.json().catch(() => ({ error: 'Not found' }));
    throw error(response.status, body.error || 'Not found');
  }

  return new Response(await response.text(), {
    status: 200,
    headers: {
      'Content-Type': 'application/json',
      'Cache-Control': 'private, no-store',
      'Referrer-Policy': 'no-referrer',
      'X-Robots-Tag': 'noindex, nofollow',
    },
  });
};
