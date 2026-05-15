import type { PageServerLoad } from './$types';
import { fetchBackend } from '$lib/backend';


export const load: PageServerLoad = async ({ parent, url }) => {
  const { session } = await parent();
  const page = url.searchParams.get('page') || '1';

  const params = new URLSearchParams({ page, limit: '20' });

  try {
    const response = await fetchBackend(`/api/admin/shares?${params}`, {
      headers: {
        'X-User-ID': session.user.id,
        'X-User-Role': session.user.role || '',
      },
    });

    if (response.ok) {
      const data = await response.json();
      return { sharesData: data };
    }
  } catch (error) {
    console.error('Failed to fetch shares:', error);
  }

  return { sharesData: null };
};
