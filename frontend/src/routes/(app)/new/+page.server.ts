import type { PageServerLoad } from './$types';
import { env } from '$env/dynamic/private';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:3001';

export const load: PageServerLoad = async ({ parent }) => {
  const { session } = await parent();

  const headers = {
    'X-Internal-Service': env.INTERNAL_SERVICE_SECRET || '',
    'X-User-ID': session.user.id,
  };

  let catalogPainPoints: any[] = [];
  let hasCatalogData = false;

  try {
    const res = await fetch(`${BACKEND_URL}/api/catalog/discover`, { headers });
    if (res.ok) {
      const data = await res.json();
      catalogPainPoints = data.items || [];
      hasCatalogData = catalogPainPoints.length > 0;
    }
  } catch (error) {
    console.error('Failed to fetch discover data for /new:', error);
  }

  return { catalogPainPoints, catalogIdeas: [], hasCatalogData };
};
