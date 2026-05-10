import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { env } from '$env/dynamic/private';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:3001';

/**
 * Proxy: POST /api/admin/catalog/faq/generate → backend /faq/generate.
 * No DB write; returns the LLM draft for the admin preview modal.
 *
 * 429 handling: backend returns rate-limit hits; we forward the status
 * unchanged but ensure the response body has a clean `error` string so the
 * admin UI can surface a friendly toast without parsing internal details.
 */
export const POST: RequestHandler = async ({ request, locals }) => {
  const session = await locals.auth();
  if (!session?.user) throw error(401, 'Unauthorized');
  if (session.user.role !== 'ADMIN') throw error(403, 'Admin access required');

  const body = await request.json();
  const response = await fetch(`${BACKEND_URL}/api/admin/catalog/faq/generate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Internal-Service': env.INTERNAL_SERVICE_SECRET || '',
      'X-User-ID': session.user.id,
      'X-User-Role': session.user.role,
    },
    body: JSON.stringify(body),
  });

  const data = (await response.json().catch(() => ({}))) as Record<string, unknown>;
  return json(data, { status: response.status });
};
