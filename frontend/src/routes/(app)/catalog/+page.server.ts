import type { PageServerLoad } from './$types';
import { env } from '$env/dynamic/private';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:3001';

interface CategoryData {
  id: string;
  name: string;
  slug: string;
  description?: string;
  children?: CategoryData[];
  superGroup?: { id: string; name: string; slug: string; sortOrder: number } | null;
  _count?: { ideas: number; painPoints: number };
  totalItems?: number;
}

function computeTotalItems(cat: CategoryData): number {
  let total = (cat._count?.ideas ?? 0) + (cat._count?.painPoints ?? 0);
  if (cat.children) {
    for (const child of cat.children) {
      total += (child._count?.ideas ?? 0) + (child._count?.painPoints ?? 0);
    }
  }
  return total;
}

export const load: PageServerLoad = async ({ parent }) => {
  const { session } = await parent();

  const headers = {
    'X-Internal-Service': env.INTERNAL_SERVICE_SECRET || '',
    'X-User-ID': session.user.id,
  };

  try {
    const [statsRes, categoriesRes, ideasRes, painPointsRes] = await Promise.all([
      fetch(`${BACKEND_URL}/api/catalog/stats`, { headers }),
      fetch(`${BACKEND_URL}/api/catalog/categories`, { headers }),
      fetch(`${BACKEND_URL}/api/catalog/ideas?sort=newest&limit=3&page=1`, { headers }),
      fetch(`${BACKEND_URL}/api/catalog/pain-points?sort=newest&limit=3&page=1`, { headers }),
    ]);

    const stats = statsRes.ok ? await statsRes.json() : null;
    const categoriesData = categoriesRes.ok ? await categoriesRes.json() : null;
    const ideasData = ideasRes.ok ? await ideasRes.json() : null;
    const painPointsData = painPointsRes.ok ? await painPointsRes.json() : null;

    // Enrich parent categories with totalItems for sorting
    const categories: CategoryData[] = (categoriesData?.categories || []).map((cat: CategoryData) => ({
      ...cat,
      totalItems: computeTotalItems(cat),
    }));

    return {
      stats,
      categories,
      newestIdeas: ideasData?.items || [],
      newestPainPoints: painPointsData?.items || [],
    };
  } catch (error) {
    console.error('Failed to fetch catalog data:', error);
  }

  return { stats: null, categories: [], newestIdeas: [], newestPainPoints: [] };
};
