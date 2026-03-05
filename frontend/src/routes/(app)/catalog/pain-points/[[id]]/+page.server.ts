import type { PageServerLoad } from './$types';
import { env } from '$env/dynamic/private';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:3001';

export const load: PageServerLoad = async ({ params, parent, url }) => {
  const { session } = await parent();

  const category = url.searchParams.get('category') || '';
  const page = url.searchParams.get('page') || '1';
  const sort = url.searchParams.get('sort') || 'newest';
  const selectedId = params.id || '';

  const headers = {
    'X-Internal-Service': env.INTERNAL_SERVICE_SECRET || '',
    'X-User-ID': session.user.id,
  };

  try {
    const ppParams = new URLSearchParams({ page, limit: '20', sort });
    if (category) ppParams.set('category', category);

    const fetches: Promise<Response>[] = [
      fetch(`${BACKEND_URL}/api/catalog/pain-points?${ppParams}`, { headers }),
      fetch(`${BACKEND_URL}/api/catalog/categories`, { headers }),
    ];

    if (selectedId) {
      fetches.push(fetch(`${BACKEND_URL}/api/catalog/pain-points/${selectedId}`, { headers }));
    }

    const [ppRes, categoriesRes, selectedPpRes] = await Promise.all(fetches);

    const ppData = ppRes.ok ? await ppRes.json() : null;
    const categoriesData = categoriesRes.ok ? await categoriesRes.json() : null;
    const selectedPainPoint = selectedPpRes?.ok ? await selectedPpRes.json() : null;

    return {
      painPointsData: ppData,
      categories: categoriesData?.categories || [],
      filters: { category, sort },
      selectedPainPoint,
    };
  } catch (error) {
    console.error('Failed to fetch pain points:', error);
  }

  return { painPointsData: null, categories: [], filters: { category, sort }, selectedPainPoint: null };
};
