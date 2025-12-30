import { error } from '@sveltejs/kit';
import type { PageLoad } from './$types';
import type { Report } from '$lib/types/report';

export const load: PageLoad = async ({ params, fetch }) => {
  const { jobId } = params;

  try {
    // Fetch the report JSON from the backend
    const res = await fetch(`/api/jobs/${jobId}/reportjson`);

    if (!res.ok) {
      if (res.status === 400) {
        // Job not completed yet
        const data = await res.json();
        throw error(400, data.error || 'Report not ready yet');
      }
      if (res.status === 404) {
        throw error(404, 'Report not found');
      }
      throw error(res.status, 'Failed to load report');
    }

    const report: Report = await res.json();

    return {
      report,
      jobId,
    };
  } catch (e) {
    if (e && typeof e === 'object' && 'status' in e) {
      throw e; // Re-throw SvelteKit errors
    }
    console.error('Failed to load report:', e);
    throw error(500, 'Failed to load report');
  }
};
