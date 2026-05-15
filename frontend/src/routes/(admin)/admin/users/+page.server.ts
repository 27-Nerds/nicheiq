import type { PageServerLoad } from './$types';
import { fetchBackend } from '$lib/backend';


export const load: PageServerLoad = async ({ parent, url }) => {
  const { session } = await parent();
  const page = url.searchParams.get('page') || '1';
  const search = url.searchParams.get('search') || '';

  const params = new URLSearchParams({ page, limit: '20' });
  if (search) params.set('search', search);

  try {
    const response = await fetchBackend(`/api/admin/users?${params}`, {
      headers: {
        'X-User-ID': session.user.id,
        'X-User-Role': session.user.role || '',
      },
    });

    if (response.ok) {
      const data = await response.json();
      return { usersData: data, search };
    }
  } catch (error) {
    console.error('Failed to fetch users:', error);
  }

  return { usersData: null, search };
};
