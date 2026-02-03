import type { PageServerLoad } from './$types';
import { env } from '$env/dynamic/private';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:3001';

export const load: PageServerLoad = async () => {
  try {
    const response = await fetch(`${BACKEND_URL}/api/stats/public`, {
      headers: {
        'X-Internal-Service': env.INTERNAL_SERVICE_SECRET || '',
      },
    });

    if (response.ok) {
      const stats = await response.json();
      return { reportsDelivered: stats.completedJobs };
    }
  } catch (error) {
    console.error('Failed to fetch public stats:', error);
  }

  return { reportsDelivered: null };
};
