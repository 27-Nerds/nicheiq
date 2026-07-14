import { error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { fetchBackend } from '$lib/backend';

/**
 * POST /api/jobs/:jobId/chat - Guided-chat message (streamed reply)
 * Proxies to the backend with internal service authentication. `EventSource` is
 * GET-only, so unlike /events this is a plain fetch+ReadableStream transport on
 * the client (see `streamChat` in $lib/api) — the proxy just passes the stream
 * straight through, same as /events does for progress SSE.
 */
export const POST: RequestHandler = async ({ params, locals, request }) => {
  const session = await locals.auth();
  if (!session?.user) {
    throw error(401, 'Unauthorized');
  }

  const body = await request.json().catch(() => ({}));

  const response = await fetchBackend(`/api/jobs/${params.jobId}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-User-ID': session.user.id,
    },
    body: JSON.stringify(body ?? {}),
    // Propagate client disconnects to the backend fetch so an abandoned chat
    // request doesn't keep streaming from OpenAI after the browser gave up.
    signal: request.signal,
  });

  if (!response.ok) {
    const contentType = response.headers.get('Content-Type') || '';
    if (contentType.includes('application/json')) {
      const data = await response.json();
      return new Response(JSON.stringify(data), {
        status: response.status,
        headers: { 'Content-Type': 'application/json' },
      });
    }
    throw error(response.status, 'Chat request failed');
  }

  return new Response(response.body, {
    status: response.status,
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
      'X-Accel-Buffering': 'no',
    },
  });
};
