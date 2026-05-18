import type { PageServerLoad } from './$types';
import { fetchBackend } from '$lib/backend';
import type { TokenPackage } from '$lib/types/billing';
import type { CatalogTopPainPoint, CatalogTotals } from '$lib/types/publicCatalog';

export const load: PageServerLoad = async ({ setHeaders }) => {
  setHeaders({ 'cache-control': 'public, max-age=60' });

  let reportsDelivered: number | null = null;
  let hasSampleReport = false;
  let packages: TokenPackage[] = [];
  let topPainPoints: CatalogTopPainPoint[] = [];
  let threadsAnalyzed: number | null = null;
  let nichesResearched: number | null = null;

  try {
    const [statsRes, settingsRes, packagesRes, topPainPointsRes, totalsRes] = await Promise.all([
      fetchBackend('/api/stats/public'),
      fetchBackend('/api/settings/sample-report-url'),
      fetchBackend('/api/billing/packages', {
        signal: AbortSignal.timeout(3000),
      }).catch(() => null),
      fetchBackend('/api/public/catalog/top-pain-points?limit=8', {
        signal: AbortSignal.timeout(3000),
      }).catch((err) => {
        console.error('top-pain-points fetch failed', err);
        return null;
      }),
      fetchBackend('/api/public/catalog/totals', {
        signal: AbortSignal.timeout(3000),
      }).catch((err) => {
        console.error('totals fetch failed', err);
        return null;
      }),
    ]);

    if (statsRes.ok) {
      const stats = await statsRes.json();
      reportsDelivered = stats.completedJobs;
    }

    if (settingsRes.ok) {
      const data = await settingsRes.json();
      hasSampleReport = !!data.url;
    }

    if (packagesRes?.ok) {
      const data = await packagesRes.json();
      packages = data.packages ?? [];
    }

    if (topPainPointsRes?.ok) {
      const data = await topPainPointsRes.json();
      topPainPoints = Array.isArray(data) ? data : (data.painPoints ?? []);
    }

    if (totalsRes?.ok) {
      const totals: CatalogTotals = await totalsRes.json();
      threadsAnalyzed = totals.contentItemsMined ?? null;
      nichesResearched = totals.totalIdeas ?? null;
    }
  } catch (error) {
    console.error('Failed to fetch landing page data:', error);
  }

  return {
    reportsDelivered,
    hasSampleReport,
    packages,
    topPainPoints,
    threadsAnalyzed,
    nichesResearched,
  };
};
