import { error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { env } from '$env/dynamic/private';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:3001';

/**
 * GET /api/shared/discovery/:shareToken - Public proxy for shared discovery (no auth)
 */
export const GET: RequestHandler = async ({ params }) => {
  const response = await fetch(`${BACKEND_URL}/api/shared/discovery/${params.shareToken}`);

  if (!response.ok) {
    const data = await response.json();
    throw error(response.status, data.error || 'Not found');
  }

  const body = await response.text();

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'Cache-Control': response.headers.get('Cache-Control') || 'private, no-store',
    'Referrer-Policy': response.headers.get('Referrer-Policy') || 'no-referrer',
  };
  const robotsTag = response.headers.get('X-Robots-Tag');
  if (robotsTag) headers['X-Robots-Tag'] = robotsTag;

  return new Response(body, { status: 200, headers });
};
