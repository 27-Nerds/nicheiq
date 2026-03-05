import type { PageServerLoad } from './$types';
import { env } from '$env/dynamic/private';
import type { TokenPackage } from '$lib/types/billing';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:3001';

export const load: PageServerLoad = async () => {
  let reportsDelivered: number | null = null;
  let hasSampleReport = false;
  let packages: TokenPackage[] = [];

  try {
    const [statsRes, settingsRes, packagesRes] = await Promise.all([
      fetch(`${BACKEND_URL}/api/stats/public`, {
        headers: { 'X-Internal-Service': env.INTERNAL_SERVICE_SECRET || '' },
      }),
      fetch(`${BACKEND_URL}/api/settings/sample-report-url`, {
        headers: { 'X-Internal-Service': env.INTERNAL_SERVICE_SECRET || '' },
      }),
      fetch(`${BACKEND_URL}/api/billing/packages`, {
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
