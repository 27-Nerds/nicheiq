import type { PageServerLoad } from './$types';
import { env } from '$env/dynamic/private';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:3001';

export const load: PageServerLoad = async ({ parent }) => {
  const { session } = await parent();

  const headers = {
    'X-Internal-Service': env.INTERNAL_SERVICE_SECRET || '',
    'X-User-ID': session.user.id,
  };

  // Fetch catalog data for Mode 3 (trending discovery)
  let catalogPainPoints: any[] = [];
  let catalogIdeas: any[] = [];
  let hasCatalogData = false;

  try {
    const [painPointsRes, ideasRes] = await Promise.all([
      fetch(`${BACKEND_URL}/api/catalog/pain-points?sort=highest_severity&limit=8&page=1`, { headers }),
      fetch(`${BACKEND_URL}/api/catalog/ideas?sort=highest_novelty&limit=8&page=1`, { headers }),
    ]);

    if (painPointsRes.ok) {
      const data = await painPointsRes.json();
      catalogPainPoints = data.items || [];
    }
    if (ideasRes.ok) {
      const data = await ideasRes.json();
      catalogIdeas = data.items || [];
    }

    hasCatalogData = catalogPainPoints.length > 0 || catalogIdeas.length > 0;
  } catch (error) {
    console.error('Failed to fetch catalog data for /new:', error);
  }

  return {
    catalogPainPoints,
    catalogIdeas,
    hasCatalogData,
  };
};
