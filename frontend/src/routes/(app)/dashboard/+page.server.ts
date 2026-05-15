import type { PageServerLoad } from './$types';
import { fetchBackend } from '$lib/backend';
import type { Job } from '$lib/types/job';

export const load: PageServerLoad = async ({ parent }) => {
  const { session } = await parent();

  // Get the user's ID from the session
  const userId = session?.user?.id;

  if (!userId) {
    return { jobs: [] };
  }

  try {
    // Fetch jobs by userId from backend with internal service authentication
    const response = await fetchBackend(`/api/users/${userId}/jobs`, {
      headers: { 'X-User-ID': userId },
    });

    if (!response.ok) {
      console.error('Failed to fetch jobs:', response.statusText);
      return { jobs: [] };
    }

    const data = await response.json();
    const jobs: Job[] = data.jobs || [];

    // Jobs are already sorted by createdAt desc from the backend
    return { jobs };
  } catch (error) {
    console.error('Error fetching jobs:', error);
    return { jobs: [] };
  }
};
