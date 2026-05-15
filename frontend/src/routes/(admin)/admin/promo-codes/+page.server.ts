import type { PageServerLoad } from './$types';
import { fetchBackend } from '$lib/backend';


export const load: PageServerLoad = async ({ parent, url }) => {
  const { session } = await parent();
  const page = url.searchParams.get('page') || '1';

  try {
    const response = await fetchBackend(`/api/admin/promo-codes?page=${page}&limit=20`, {
      headers: {
        'X-User-ID': session.user.id,
        'X-User-Role': session.user.role || '',
      },
    });

    if (response.ok) {
      const data = await response.json();
      return { promoData: data };
    }
  } catch (error) {
    console.error('Failed to fetch promo codes:', error);
  }

  return { promoData: null };
};
