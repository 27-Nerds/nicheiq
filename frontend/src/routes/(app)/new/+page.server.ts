import type { PageServerLoad } from './$types';
import { fetchBackend } from '$lib/backend';

export const load: PageServerLoad = async ({ parent }) => {
  const { session } = await parent();

  const headers = { 'X-User-ID': session.user.id };

  let catalogPainPoints: any[] = [];
  let hasCatalogData = false;

  try {
    const res = await fetchBackend('/api/catalog/discover', { headers });
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
