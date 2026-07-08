import type { PageServerLoad } from './$types';
import { fetchBackend } from '$lib/backend';
import { INITIAL_VISIBLE_COMPLETED } from '$lib/config/dashboard';
import type { Job, ReportSummary } from '$lib/types/job';
import type {
  SavedIdeaItem,
  SavedPainPointItem,
  SavedListResponse,
  SavedCounts,
} from '$lib/types/saved';

const EMPTY_SAVED = {
  savedIdeas: [] as SavedIdeaItem[],
  savedPainPoints: [] as SavedPainPointItem[],
  savedCounts: { ideas: 0, painPoints: 0 } as SavedCounts,
};

export const load: PageServerLoad = async ({ parent }) => {
  const { session } = await parent();

  // Get the user's ID from the session
  const userId = session?.user?.id;

  if (!userId) {
    // Not an error — no session yet. Distinct from a backend fetch failure below.
    return { jobs: [], summariesByJobId: {}, loadError: false, ...EMPTY_SAVED };
  }

  const headers = { 'X-User-ID': userId };

  // Saved ideas/pain points power the dashboard's "Saved" tab. Fetched here so
  // switching tabs is instant. Failures degrade gracefully to empty lists — a
  // saved-fetch hiccup should never blank out the research tab.
  async function fetchSaved<T>(path: string, fallback: T): Promise<T> {
    try {
      const res = await fetchBackend(path, { headers });
      if (res.ok) return (await res.json()) as T;
    } catch (err) {
      console.error(`dashboard saved fetch failed: ${path}`, err);
    }
    return fallback;
  }

  try {
    // Fetch jobs by userId from backend with internal service authentication
    const response = await fetchBackend(`/api/users/${userId}/jobs`, { headers });

    if (!response.ok) {
      console.error('Failed to fetch jobs:', response.statusText);
      // Backend reachable but errored — surface a load-error state, not "no research".
      return { jobs: [], summariesByJobId: {}, loadError: true, ...EMPTY_SAVED };
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

    const [summaryResults, savedIdeas, savedPainPoints, savedCounts] = await Promise.all([
      Promise.allSettled(
        initialCompletedIds.map((id) =>
          fetchBackend(`/api/jobs/${id}/report-summary`, { headers }).then((r) =>
            r.ok ? (r.json() as Promise<ReportSummary>) : null,
          ),
        ),
      ),
      fetchSaved<SavedListResponse<SavedIdeaItem>>('/api/saves/ideas?limit=50', {
        items: [],
        nextCursor: null,
      }),
      fetchSaved<SavedListResponse<SavedPainPointItem>>('/api/saves/pain-points?limit=50', {
        items: [],
        nextCursor: null,
      }),
      fetchSaved<SavedCounts>('/api/saves/counts', { ideas: 0, painPoints: 0 }),
    ]);

    const summariesByJobId: Record<string, ReportSummary> = {};
    summaryResults.forEach((r, i) => {
      if (r.status === 'fulfilled' && r.value) {
        summariesByJobId[initialCompletedIds[i]] = r.value;
      }
    });

    // Jobs are already sorted by createdAt desc from the backend
    return {
      jobs,
      summariesByJobId,
      loadError: false,
      savedIdeas: savedIdeas.items,
      savedPainPoints: savedPainPoints.items,
      savedCounts,
    };
  } catch (error) {
    console.error('Error fetching jobs:', error);
    // Fetch threw (network / backend down) — a load error, not an empty history.
    return { jobs: [], summariesByJobId: {}, loadError: true, ...EMPTY_SAVED };
  }
};
