import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';
import { fetchBackend } from '$lib/backend';


interface PainPointFaqEditorPayload {
  id: string;
  slug: string | null;
  title: string;
  faqJson: { q: string; a: string }[] | null;
  faqJsonMeta: import('$lib/types/catalog-landing').FaqJsonMeta | null;
  updatedAt: string;
  category: {
    id: string;
    name: string;
    parent: { name: string | null } | null;
  };
}

export const load: PageServerLoad = async ({ params, locals }) => {
  const session = await locals.auth();
  if (!session?.user) throw error(401, 'Unauthorized');
  if (session.user.role !== 'ADMIN') throw error(403, 'Admin access required');

  const res = await fetchBackend(
    `/api/admin/catalog/pain-points/${encodeURIComponent(params.id)}`,
    {
      headers: {
        'X-User-ID': session.user.id,
        'X-User-Role': session.user.role,
      },
    },
  );

  if (res.status === 404) throw error(404, 'Pain point not found');
  if (!res.ok) throw error(res.status, 'Failed to load pain point');

  const painPoint = (await res.json()) as PainPointFaqEditorPayload;
  return { painPoint };
};
