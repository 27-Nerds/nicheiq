import type { PageServerLoad } from './$types';
import { fetchBackend } from '$lib/backend';

export const load: PageServerLoad = async ({ parent }) => {
  const { session } = await parent();

  const headers = { 'X-User-ID': session.user.id };

  let catalogPainPoints: any[] = [];
  let hasCatalogData = false;
  let sampleReportAvailable = false;

  try {
    const [catalogRes, sampleRes] = await Promise.all([
      fetchBackend('/api/public/catalog/discover', { headers }).catch(() => null),
      fetchBackend('/api/settings/sample-report-url').catch(() => null),
    ]);
    if (catalogRes?.ok) {
      const data = await catalogRes.json();
      catalogPainPoints = data.items || [];
      hasCatalogData = catalogPainPoints.length > 0;
    }
    if (sampleRes?.ok) {
      const data = await sampleRes.json();
      sampleReportAvailable = typeof data.url === 'string' && data.url.length > 0;
    }
  } catch (error) {
    console.error('Failed to fetch discover data for /new:', error);
  }

  return { catalogPainPoints, hasCatalogData, sampleReportAvailable };
};
