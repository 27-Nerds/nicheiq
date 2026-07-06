import type { PageServerLoad } from './$types';
import { fetchBackend } from '$lib/backend';
import type { SubscriptionPlan } from '$lib/types/billing';
import type { CatalogTopPainPoint, CatalogTotals } from '$lib/types/publicCatalog';

export const load: PageServerLoad = async ({ setHeaders }) => {
  setHeaders({ 'cache-control': 'public, max-age=60' });

  let reportsDelivered: number | null = null;
  let activeFounders: number | null = null;
  let hasSampleReport = false;
  let plans: SubscriptionPlan[] = [];
  let topPainPoints: CatalogTopPainPoint[] = [];
  let commentsAnalyzed: number | null = null;
  let subNiches: number | null = null;
  let contentItemsMined: number | null = null;
  let catalogLastUpdated: string | null = null;

  try {
    const [statsRes, settingsRes, plansRes, topPainPointsRes, totalsRes] = await Promise.all([
      fetchBackend('/api/stats/public'),
      fetchBackend('/api/settings/sample-report-url'),
      fetchBackend('/api/billing/plans', {
        signal: AbortSignal.timeout(3000),
      }).catch(() => null),
      // freePreview=true → the "Sample Reports" marquee shows the items a non-subscriber can
      // actually open (the free-preview pains), not the top-by-severity ones.
      fetchBackend('/api/public/catalog/top-pain-points?limit=8&freePreview=true', {
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
      activeFounders = stats.activeFounders ?? null;
    }

    if (settingsRes.ok) {
      const data = await settingsRes.json();
      hasSampleReport = !!data.url;
    }

    if (plansRes?.ok) {
      const data = await plansRes.json();
      plans = data.plans ?? [];
    }

    if (topPainPointsRes?.ok) {
      const data = await topPainPointsRes.json();
      topPainPoints = Array.isArray(data) ? data : (data.painPoints ?? []);
    }

    if (totalsRes?.ok) {
      const totals: CatalogTotals = await totalsRes.json();
      commentsAnalyzed = totals.commentsAnalyzed ?? null;
      subNiches = totals.totalSubcategories ?? null;
      contentItemsMined = totals.contentItemsMined ?? null;
      catalogLastUpdated = totals.lastUpdated ?? null;
    }
  } catch (error) {
    console.error('Failed to fetch landing page data:', error);
  }

  return {
    reportsDelivered,
    activeFounders,
    hasSampleReport,
    plans,
    topPainPoints,
    commentsAnalyzed,
    subNiches,
    contentItemsMined,
    catalogLastUpdated,
  };
};
