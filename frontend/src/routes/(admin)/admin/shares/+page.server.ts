import type { PageServerLoad } from './$types';
import { env } from '$env/dynamic/private';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:3001';

export const load: PageServerLoad = async ({ parent, url }) => {
  const { session } = await parent();
  const page = url.searchParams.get('page') || '1';

  const params = new URLSearchParams({ page, limit: '20' });

  try {
    const response = await fetch(`${BACKEND_URL}/api/admin/shares?${params}`, {
      headers: {
        'X-Internal-Service': env.INTERNAL_SERVICE_SECRET || '',
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
