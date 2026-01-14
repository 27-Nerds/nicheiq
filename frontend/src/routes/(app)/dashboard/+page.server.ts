import type { PageServerLoad } from './$types';
import { env } from '$env/dynamic/private';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:3001';

interface Job {
  id: string;
  niche: string;
  status: string;
  currentStage: number;
  currentStageName: string | null;
  progressPercent: number;
  errorMessage: string | null;
  createdAt: string;
  startedAt: string | null;
  completedAt: string | null;
  hasReport: boolean;
  hasLandingPage: boolean;
}

export const load: PageServerLoad = async ({ parent, fetch }) => {
  const { session } = await parent();

  // Get the user's ID from the session
  const userId = session?.user?.id;

  if (!userId) {
    return { jobs: [] };
  }

  try {
    // Fetch jobs by userId from backend
    const response = await fetch(`${BACKEND_URL}/api/users/${userId}/jobs`);

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
