import { error, redirect } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';
import { env } from '$env/dynamic/private';
import { buildLeafCategoryListingUrl } from '$lib/utils/catalog-utils';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:3001';

interface Category {
  id: string;
  name: string;
  slug: string;
  description?: string;
  parentId?: string | null;
  children?: Category[];
  _count?: { ideas: number; painPoints: number };
}

function findCategoryBySlug(categories: Category[], slug: string): { category: Category; parent: Category | null } | null {
  for (const parent of categories) {
    if (parent.slug === slug) {
      return { category: parent, parent: null };
    }
    for (const child of parent.children || []) {
      if (child.slug === slug) {
        return { category: child, parent };
      }
    }
  }
  return null;
}

export const load: PageServerLoad = async ({ params, parent }) => {
  const { session } = await parent();
  const { slug } = params;

  const headers = {
    'X-Internal-Service': env.INTERNAL_SERVICE_SECRET || '',
    'X-User-ID': session.user.id,
  };

  // Fetch categories first to check if this is a leaf category
  const categoriesRes = await fetch(`${BACKEND_URL}/api/catalog/categories`, { headers });
  const categoriesData = categoriesRes.ok ? await categoriesRes.json() : null;
  const allCategories: Category[] = categoriesData?.categories || [];
  const match = findCategoryBySlug(allCategories, slug);

  if (!match) {
    error(404, 'Category not found');
  }

  const children = match.category.children || [];

  // Leaf category: redirect directly to listing page
  if (children.length === 0) {
    const ideaCount = match.category._count?.ideas ?? 0;
    const painPointCount = match.category._count?.painPoints ?? 0;
    redirect(302, buildLeafCategoryListingUrl(slug, ideaCount, painPointCount));
  }

  // Parent category: fetch preview data
  const [ideasRes, painPointsRes] = await Promise.all([
    fetch(`${BACKEND_URL}/api/catalog/ideas?category=${slug}&sort=newest&limit=3&page=1`, { headers }),
    fetch(`${BACKEND_URL}/api/catalog/pain-points?category=${slug}&sort=newest&limit=3&page=1`, { headers }),
  ]);

  const ideasData = ideasRes.ok ? await ideasRes.json() : null;
  const painPointsData = painPointsRes.ok ? await painPointsRes.json() : null;

  return {
    category: match.category,
    children,
    parent: match.parent,
    previewIdeas: ideasData?.items || [],
    totalIdeas: ideasData?.total ?? 0,
    previewPainPoints: painPointsData?.items || [],
    totalPainPoints: painPointsData?.total ?? 0,
  };
};
