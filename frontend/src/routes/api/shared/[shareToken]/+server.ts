import { error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { env } from '$env/dynamic/private';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:3001';

/**
 * GET /api/shared/:shareToken - Public proxy for shared report (no auth)
 */
export const GET: RequestHandler = async ({ params }) => {
  const response = await fetch(`${BACKEND_URL}/api/shared/${params.shareToken}`);

  if (!response.ok) {
    const data = await response.json();
    throw error(response.status, data.error || 'Not found');
  }

  const body = await response.text();

  return new Response(body, {
    status: 200,
    headers: {
      'Content-Type': 'application/json',
      'X-Robots-Tag': response.headers.get('X-Robots-Tag') || 'noindex, nofollow',
      'Cache-Control': response.headers.get('Cache-Control') || 'private, no-store',
      'Referrer-Policy': response.headers.get('Referrer-Policy') || 'no-referrer',
    },
  });
};
