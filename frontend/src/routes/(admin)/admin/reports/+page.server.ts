import type { PageServerLoad } from './$types';
import { env } from '$env/dynamic/private';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:3001';

export const load: PageServerLoad = async ({ parent }) => {
  const { session } = await parent();

  try {
    const response = await fetch(`${BACKEND_URL}/api/admin/reports`, {
      headers: {
        'X-Internal-Service': env.INTERNAL_SERVICE_SECRET || '',
        'X-User-ID': session.user.id,
        'X-User-Role': session.user.role || '',
      },
    });

    if (response.ok) {
      const reportStats = await response.json();
      return { reportStats };
    }
  } catch (error) {
    console.error('Failed to fetch report stats:', error);
  }

  return { reportStats: null };
};
