import type { PageServerLoad } from './$types';
import { fetchBackend } from '$lib/backend';
import type { TokenPackage } from '$lib/types/billing';

export const load: PageServerLoad = async () => {
  let reportsDelivered: number | null = null;
  let hasSampleReport = false;
  let packages: TokenPackage[] = [];

  try {
    const [statsRes, settingsRes, packagesRes] = await Promise.all([
      fetchBackend('/api/stats/public'),
      fetchBackend('/api/settings/sample-report-url'),
      fetchBackend('/api/billing/packages', {
        signal: AbortSignal.timeout(3000),
      }).catch(() => null),
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
  } catch (error) {
    console.error('Failed to fetch landing page data:', error);
  }

  return { reportsDelivered, hasSampleReport, packages };
};
