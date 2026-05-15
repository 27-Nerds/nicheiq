import type { PageServerLoad } from './$types';
import { fetchBackend } from '$lib/backend';

export const load: PageServerLoad = async ({ parent }) => {
  const { session } = await parent();

  try {
    const response = await fetchBackend('/api/admin/dashboard', {
      headers: {
        'X-User-ID': session.user.id,
        'X-User-Role': session.user.role || '',
      },
    });

    if (response.ok) {
      const stats = await response.json();
      return { stats };
    }
  } catch (error) {
    console.error('Failed to fetch dashboard stats:', error);
  }

  return { stats: null };
};
