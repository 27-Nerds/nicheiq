import type { PageServerLoad } from './$types';
import { env } from '$env/dynamic/private';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:3001';

export const load: PageServerLoad = async ({ parent, url }) => {
  const { session } = await parent();

  const headers = {
    'X-Internal-Service': env.INTERNAL_SERVICE_SECRET || '',
    'X-User-ID': session.user.id,
    'X-User-Role': session.user.role || '',
  };

  const q = url.searchParams.get('q') || '';
  const subreddit = url.searchParams.get('subreddit') || '';
  const sortBy = url.searchParams.get('sortBy') || 'fetchedAt';
  const sortDir = url.searchParams.get('sortDir') || 'desc';
  const page = url.searchParams.get('page') || '1';

  const params = new URLSearchParams({
    page,
    limit: '20',
    sort: sortBy,
    sortDir,
  });
  if (q) params.set('search', q);
  if (subreddit) params.set('subreddit', subreddit);

  try {
    const [threadsRes, statsRes] = await Promise.all([
      fetch(`${BACKEND_URL}/api/admin/catalog/reddit-threads?${params}`, { headers }),
      fetch(`${BACKEND_URL}/api/admin/catalog/reddit-threads/stats`, { headers }),
    ]);

    const threadsData = threadsRes.ok ? await threadsRes.json() : null;
    const stats = statsRes.ok ? await statsRes.json() : null;

    return {
      threadsData,
      stats,
      filters: { q, subreddit, sortBy, sortDir, page: parseInt(page) },
    };
  } catch (error) {
    console.error('Failed to fetch reddit threads:', error);
  }

  return {
    threadsData: null,
    stats: null,
    filters: { q: '', subreddit: '', sortBy: 'fetchedAt', sortDir: 'desc', page: 1 },
  };
};
