import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { env } from '$env/dynamic/private';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:3001';

/**
 * Proxy: POST /api/admin/catalog/faq/save → backend /faq/save.
 * Persists faqJson + faqJsonMeta on the entity and busts the parent category
 * landing cache. Used by both the preview-modal Save button (source:
 * 'generated') and could be used by manual edits (source: 'manual') if we
 * ever migrate the manual category editor off PATCH /categories/:id.
 */
export const POST: RequestHandler = async ({ request, locals }) => {
  const session = await locals.auth();
  if (!session?.user) throw error(401, 'Unauthorized');
  if (session.user.role !== 'ADMIN') throw error(403, 'Admin access required');

  const body = await request.json();
  const response = await fetch(`${BACKEND_URL}/api/admin/catalog/faq/save`, {
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
