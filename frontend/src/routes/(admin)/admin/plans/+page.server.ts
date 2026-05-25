import type { PageServerLoad } from './$types';
import { fetchBackend } from '$lib/backend';


export const load: PageServerLoad = async ({ parent }) => {
  const { session } = await parent();

  try {
    const response = await fetchBackend(`/api/admin/plans`, {
      headers: {
        'X-User-ID': session.user.id,
        'X-User-Role': session.user.role || '',
      },
    });

    if (response.ok) {
      const data = await response.json();
      return { plansData: data };
    }
  } catch (error) {
    console.error('Failed to fetch plans:', error);
  }

  return { plansData: null };
};
