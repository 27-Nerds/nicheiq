import type { PageServerLoad } from './$types';
import { env } from '$env/dynamic/private';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:3001';

export const load: PageServerLoad = async () => {
  let report = null;

  try {
    // 1. Get configured share URL
    const settingsRes = await fetch(`${BACKEND_URL}/api/settings/sample-report-url`, {
      headers: { 'X-Internal-Service': env.INTERNAL_SERVICE_SECRET || '' },
    });
    if (!settingsRes.ok) return { report: null };

    const data = await settingsRes.json();
    if (!data.url) return { report: null };

    // 2. Extract share token from URL like "/shared/AbCdEf..."
    const match = data.url.match(/\/shared\/([A-Za-z0-9_-]+)$/);
    const token = match?.[1];
    if (!token) return { report: null };

    // 3. Fetch report data using existing shared report endpoint
    const reportRes = await fetch(`${BACKEND_URL}/api/shared/${token}`);
    if (reportRes.ok) {
      report = await reportRes.json();
    }
  } catch (e) {
    console.error('Failed to load sample report:', e);
  }

  return { report };
};
