import type { LayoutServerLoad } from './$types';
import { fetchBackend } from '$lib/backend';

interface NicheTreeNode {
  id: string;
  name: string;
  slug: string;
  description?: string | null;
  superGroup?: { id: string; name: string; slug: string; sortOrder: number } | null;
  children?: NicheTreeNode[];
  _count?: { ideas: number; painPoints: number };
}

/**
 * Layout loader for the public catalog. Fetches the niche tree once and exposes
 * it to all child routes so breadcrumbs/related/niche-grid renders never
 * re-fetch.
 *
 * Note: Cache-Control headers are set by the most-specific page loader (not
 * here) — SvelteKit refuses duplicate Cache-Control headers across layout +
 * page loaders.
 */
export const load: LayoutServerLoad = async () => {
  try {
    const res = await fetchBackend('/api/public/catalog/tree');
    if (!res.ok) {
      console.error('Failed to fetch catalog tree:', res.status);
      return { categoriesTree: [] as NicheTreeNode[] };
    }
    const data = await res.json();
    return { categoriesTree: (data.categories ?? []) as NicheTreeNode[] };
  } catch (error) {
    console.error('Failed to fetch catalog tree:', error);
    return { categoriesTree: [] as NicheTreeNode[] };
  }
};
