import type { PageServerLoad } from './$types';
import { fetchBackend } from '$lib/backend';


export const load: PageServerLoad = async ({ parent }) => {
  const { session } = await parent();

  try {
    const response = await fetchBackend(`/api/admin/reports`, {
      headers: {
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
