import type { PageServerLoad } from './$types';
import { fetchBackend } from '$lib/backend';


export const load: PageServerLoad = async ({ parent }) => {
  const { session } = await parent();

  try {
    const response = await fetchBackend(`/api/admin/packages`, {
      headers: {
        'X-User-ID': session.user.id,
        'X-User-Role': session.user.role || '',
      },
    });

    if (response.ok) {
      const data = await response.json();
      return { packagesData: data };
    }
  } catch (error) {
    console.error('Failed to fetch packages:', error);
  }

  return { packagesData: null };
};
