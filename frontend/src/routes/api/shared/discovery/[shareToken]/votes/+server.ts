import { error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { fetchBackend } from '$lib/backend';

export const GET: RequestHandler = async ({ params, url }) => {
  const viewerToken = url.searchParams.get('viewerToken');
  const suffix = viewerToken
    ? `?viewerToken=${encodeURIComponent(viewerToken)}`
    : '';
  const response = await fetchBackend(
    `/api/shared/discovery/${params.shareToken}/votes${suffix}`,
  );

  if (!response.ok) {
    const data = await response.json();
    throw error(response.status, data.error || 'Not found');
  }

  const body = await response.text();
  return new Response(body, {
    status: 200,
    headers: {
      'Content-Type': 'application/json',
      'Cache-Control': response.headers.get('Cache-Control') || 'private, no-store',
      'Referrer-Policy': response.headers.get('Referrer-Policy') || 'no-referrer',
      'X-Robots-Tag': response.headers.get('X-Robots-Tag') || 'noindex, nofollow',
    },
  });
};
