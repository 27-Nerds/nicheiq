import type { PageServerLoad } from './$types';
import { fetchBackend } from '$lib/backend';

export const load: PageServerLoad = async () => {
  let report = null;

  try {
    // 1. Get configured share URL
    const settingsRes = await fetchBackend('/api/settings/sample-report-url');
    if (!settingsRes.ok) return { report: null };

    const data = await settingsRes.json();
    if (!data.url) return { report: null };

    // 2. Extract share token from URL like "/shared/AbCdEf..."
    const match = data.url.match(/\/shared\/([A-Za-z0-9_-]+)$/);
    const token = match?.[1];
    if (!token) return { report: null };

    // 3. Fetch report data using existing shared report endpoint. This is a
    // public-token route so internal headers aren't strictly required, but
    // fetchBackend adds them harmlessly and the URL composition stays
    // consistent with the rest of the route.
    const reportRes = await fetchBackend(`/api/shared/${token}`);
    if (reportRes.ok) {
      report = await reportRes.json();
    }
  } catch (e) {
    console.error('Failed to load sample report:', e);
  }

  return { report };
};
