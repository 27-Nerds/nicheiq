import type { PageServerLoad } from './$types';
import { fetchBackend } from '$lib/backend';
import { INITIAL_VISIBLE_COMPLETED } from '$lib/config/dashboard';
import type { Job, ReportSummary } from '$lib/types/job';

export const load: PageServerLoad = async ({ parent }) => {
  const { session } = await parent();

  // Get the user's ID from the session
  const userId = session?.user?.id;

  if (!userId) {
    return { jobs: [], summariesByJobId: {} };
  }

  try {
    // Fetch jobs by userId from backend with internal service authentication
    const response = await fetchBackend(`/api/users/${userId}/jobs`, {
      headers: { 'X-User-ID': userId },
    });

    if (!response.ok) {
      console.error('Failed to fetch jobs:', response.statusText);
      return { jobs: [], summariesByJobId: {} };
    }

    const data = await response.json();
    const jobs: Job[] = data.jobs || [];

    // Prefetch report summaries only for the initial-visible completed jobs.
    // Power users with many completed reports would otherwise pay N+1 latency
    // on first paint. Lazy-load the rest when the user clicks "Show more".
    const initialCompletedIds = jobs
      .filter((j) => j.status.toUpperCase() === 'COMPLETED')
      .slice(0, INITIAL_VISIBLE_COMPLETED)
      .map((j) => j.id);

    const summariesByJobId: Record<string, ReportSummary> = {};
    const results = await Promise.allSettled(
      initialCompletedIds.map((id) =>
        fetchBackend(`/api/jobs/${id}/report-summary`, {
          headers: { 'X-User-ID': userId },
        }).then((r) => (r.ok ? (r.json() as Promise<ReportSummary>) : null)),
      ),
    );
    results.forEach((r, i) => {
      if (r.status === 'fulfilled' && r.value) {
        summariesByJobId[initialCompletedIds[i]] = r.value;
      }
    });

    // Jobs are already sorted by createdAt desc from the backend
    return { jobs, summariesByJobId };
  } catch (error) {
    console.error('Error fetching jobs:', error);
    return { jobs: [], summariesByJobId: {} };
  }
};
