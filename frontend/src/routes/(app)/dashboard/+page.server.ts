import type { PageServerLoad } from './$types';
import { env } from '$env/dynamic/private';
import type { Job } from '$lib/types/job';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:3001';

export const load: PageServerLoad = async ({ parent }) => {
  const { session } = await parent();

  // Get the user's ID from the session
  const userId = session?.user?.id;

  if (!userId) {
    return { jobs: [] };
  }

  try {
    // Fetch jobs by userId from backend with internal service authentication
    const response = await fetch(`${BACKEND_URL}/api/users/${userId}/jobs`, {
      headers: {
        'X-Internal-Service': env.INTERNAL_SERVICE_SECRET || '',
        'X-User-ID': userId,
      },
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
