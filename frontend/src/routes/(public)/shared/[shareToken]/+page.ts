import { error } from '@sveltejs/kit';
import type { PageLoad } from './$types';
import type { Report } from '$lib/types/report';

export const load: PageLoad = async ({ params, fetch }) => {
  const { shareToken } = params;

  try {
    const res = await fetch(`/api/shared/${shareToken}`);

    if (!res.ok) {
      if (res.status === 404) {
        // Return null report to show "no longer available" page
        return { report: null, shareToken };
      }
      throw error(res.status, 'Failed to load shared report');
    }

    const report: Report = await res.json();
    const allowIndexing = report?._shareAllowIndexing ?? false;

    return {
      report,
      shareToken,
      allowIndexing,
    };
  } catch (e) {
    if (e && typeof e === 'object' && 'status' in e) {
      throw e; // Re-throw SvelteKit errors
    }
    console.error('Failed to load shared report:', e);
    // Return null report to show "no longer available" page
    return { report: null, shareToken };
  }
};
