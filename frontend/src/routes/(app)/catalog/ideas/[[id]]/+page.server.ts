import type { PageServerLoad } from './$types';
import { env } from '$env/dynamic/private';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:3001';

export const load: PageServerLoad = async ({ params, parent, url }) => {
  const { session } = await parent();

  const category = url.searchParams.get('category') || '';
  const page = url.searchParams.get('page') || '1';
  const sort = url.searchParams.get('sort') || 'newest';
  const openId = params.id || '';

  const headers = {
    'X-Internal-Service': env.INTERNAL_SERVICE_SECRET || '',
    'X-User-ID': session.user.id,
  };

  try {
    const ideaParams = new URLSearchParams({ page, limit: '20', sort });
    if (category) ideaParams.set('category', category);

    const fetches: Promise<Response>[] = [
      fetch(`${BACKEND_URL}/api/catalog/ideas?${ideaParams}`, { headers }),
      fetch(`${BACKEND_URL}/api/catalog/categories`, { headers }),
    ];

    if (openId) {
      fetches.push(fetch(`${BACKEND_URL}/api/catalog/ideas/${openId}`, { headers }));
    }

    const [ideasRes, categoriesRes, openIdeaRes] = await Promise.all(fetches);

    const ideasData = ideasRes.ok ? await ideasRes.json() : null;
    const categoriesData = categoriesRes.ok ? await categoriesRes.json() : null;
    const openIdea = openIdeaRes?.ok ? await openIdeaRes.json() : null;

    return {
      ideasData,
      categories: categoriesData?.categories || [],
      filters: { category, sort },
      openIdea,
    };
  } catch (error) {
    console.error('Failed to fetch ideas:', error);
  }

  return { ideasData: null, categories: [], filters: { category, sort }, openIdea: null };
};
