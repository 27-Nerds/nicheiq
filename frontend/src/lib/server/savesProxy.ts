import { error } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import type { RequestEvent } from '@sveltejs/kit';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:3001';

/**
 * Authenticated proxy to the backend /api/saves/* surface. Handles:
 *   - 401 if no session
 *   - X-Internal-Service + X-User-ID headers
 *   - Cache-Control: private, no-store on the response (per-user data)
 *   - JSON body forwarding for POST/PATCH
 *   - Query-string forwarding for GET
 *
 * Response status and body are passed through verbatim from the backend.
 */
export async function proxyToSaves(
  event: RequestEvent,
  method: 'GET' | 'POST' | 'PATCH' | 'DELETE',
  path: string,
): Promise<Response> {
  const session = await event.locals.auth();
  if (!session?.user) {
    throw error(401, 'Unauthorized');
  }

  // Append the original query string (used by GET list/status).
  const search = event.url.search; // includes leading '?' if any
  const url = `${BACKEND_URL}/api/saves${path}${search}`;

  const headers: Record<string, string> = {
    'X-Internal-Service': env.INTERNAL_SERVICE_SECRET || '',
    'X-User-ID': session.user.id,
  };

  let body: string | undefined;
  if (method === 'POST' || method === 'PATCH') {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(await event.request.json());
  }

  const upstream = await fetch(url, { method, headers, body });

  // 204 No Content has no body — pass through directly.
  if (upstream.status === 204) {
    return new Response(null, {
      status: 204,
      headers: { 'Cache-Control': 'private, no-store' },
    });
  }

  const text = await upstream.text();
  return new Response(text, {
    status: upstream.status,
    headers: {
      'Content-Type': upstream.headers.get('content-type') ?? 'application/json',
      'Cache-Control': 'private, no-store',
    },
  });
}
