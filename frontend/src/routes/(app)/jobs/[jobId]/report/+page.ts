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
        const data = await res.json().catch(() => ({}));
        return {
          report: null,
          reportState: 'not_ready' as const,
          message: data.error || 'The Deep Research report is not ready yet.',
          jobId,
        };
      }
      if (res.status === 404) {
        return {
          report: null,
          reportState: 'not_found' as const,
          message: 'The report could not be found or is no longer available.',
          jobId,
        };
      }
      throw error(res.status, 'Failed to load report');
    }

    const report: Report = await res.json();

    return {
      report,
      reportState: 'ready' as const,
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
