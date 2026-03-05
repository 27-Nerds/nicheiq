/**
 * Shared utilities for catalog pages.
 */

/**
 * Maps an opportunity level string to a Badge variant.
 */
export function opportunityVariant(level: string): "success" | "warning" | "error" | "default" {
  if (level === "high") return "success";
  if (level === "medium") return "warning";
  if (level === "low") return "error";
  return "default";
}

export interface CategoryInfo {
  parent: { name: string; slug: string } | null;
  child: { name: string; slug: string } | null;
  /** The full parent object with children[], for rendering sidebar */
  activeParent: { name: string; slug: string; children?: Array<{ name: string; slug: string }> } | null;
}

/**
 * Resolves which parent/child category is active from a flat slug.
 */
export function resolveActiveCategory(
  categories: Array<{ name: string; slug: string; children?: Array<{ name: string; slug: string }> }>,
  activeSlug: string
): CategoryInfo {
  if (!activeSlug) return { parent: null, child: null, activeParent: null };
  for (const parent of categories) {
    if (parent.slug === activeSlug) {
      return { parent: { name: parent.name, slug: parent.slug }, child: null, activeParent: parent };
    }
    for (const child of parent.children || []) {
      if (child.slug === activeSlug) {
        return { parent: { name: parent.name, slug: parent.slug }, child: { name: child.name, slug: child.slug }, activeParent: parent };
      }
    }
  }
  return { parent: null, child: null, activeParent: null };
}

/**
 * Builds a filter URL preserving category and sort params.
 */
export function buildFilterUrl(basePath: string, category: string, sort?: string): string {
  const params = new URLSearchParams();
  if (category) params.set('category', category);
  if (sort && sort !== 'newest') params.set('sort', sort);
  const qs = params.toString();
  return qs ? `${basePath}?${qs}` : basePath;
}

// ============================================
// Super-group types and grouping logic
// ============================================

export interface CategoryGroup {
  name: string;
  slug: string;
  children?: Array<{ name: string; slug: string; _count?: { ideas: number; painPoints: number } }>;
  _count?: { ideas: number; painPoints: number };
  superGroup?: { id: string; name: string; slug: string; sortOrder: number } | null;
  /** Enriched by page server load — total items across this category and all children */
  totalItems?: number;
}

export interface SuperGroup {
  name: string;
  categories: CategoryGroup[];
}

/**
 * Groups parent categories into super-groups using API-provided superGroup data.
 * Categories without a superGroup go into "Other" at the end.
 */
export function groupCategories(categories: CategoryGroup[]): SuperGroup[] {
  const groupMap = new Map<string, { sortOrder: number; categories: CategoryGroup[] }>();

  const other: CategoryGroup[] = [];

  for (const cat of categories) {
    if (cat.superGroup?.name) {
      const key = cat.superGroup.name;
      let group = groupMap.get(key);
      if (!group) {
        group = { sortOrder: cat.superGroup.sortOrder, categories: [] };
        groupMap.set(key, group);
      }
      group.categories.push(cat);
    } else {
      other.push(cat);
    }
  }

  // Sort groups by sortOrder, then build result
  const sorted = [...groupMap.entries()]
    .sort((a, b) => a[1].sortOrder - b[1].sortOrder);

  const groups: SuperGroup[] = sorted.map(([name, g]) => ({
    name,
    categories: g.categories,
  }));

  // "Other" at the end
  if (other.length > 0) {
    groups.push({ name: "Other", categories: other });
  }

  return groups;
}

/**
 * Computes total published items for a parent category, including all its children's counts.
 * When `countField` is provided, counts only that field; otherwise sums both.
 */
export function computeCategoryTotalItems(category: CategoryGroup, countField?: 'ideas' | 'painPoints'): number {
  const count = (c: { _count?: { ideas: number; painPoints: number } }) =>
    countField ? (c._count?.[countField] ?? 0) : (c._count?.ideas ?? 0) + (c._count?.painPoints ?? 0);
  let total = count(category);
  if (category.children) {
    for (const child of category.children as Array<CategoryGroup>) {
      total += count(child);
    }
  }
  return total;
}

/**
 * Builds a cross-navigation URL between Ideas and Pain Points pages,
 * preserving category but resetting sort/page (sorts differ between the two).
 */
export function buildCrossNavUrl(targetPath: string, category: string): string {
  const params = new URLSearchParams();
  if (category) params.set('category', category);
  const qs = params.toString();
  return qs ? `${targetPath}?${qs}` : targetPath;
}

/**
 * Builds a listing URL for a leaf category (no children).
 * Routes to pain-points if painPointCount > ideaCount, otherwise ideas.
 */
export function buildLeafCategoryListingUrl(slug: string, ideaCount: number, painPointCount: number): string {
  const target = painPointCount > ideaCount ? '/catalog/pain-points' : '/catalog/ideas';
  return buildCrossNavUrl(target, slug);
}

/**
 * Formats item counts for display, e.g. "3 ideas · 5 pain points" or "No items yet".
 */
export function formatItemCounts(ideas: number, painPoints: number): string {
  if (ideas === 0 && painPoints === 0) return 'No items yet';
  const parts: string[] = [];
  if (ideas > 0) parts.push(`${ideas} ${ideas === 1 ? 'idea' : 'ideas'}`);
  if (painPoints > 0) parts.push(`${painPoints} ${painPoints === 1 ? 'pain point' : 'pain points'}`);
  return parts.join(' · ');
}

/**
 * Splits L2 children into populated (have items) and empty (no items) groups.
 * Populated are sorted by total item count descending, then alphabetically.
 * Empty are sorted alphabetically.
 */
export function splitChildren<T extends { name: string; slug: string; _count?: { ideas: number; painPoints: number } }>(
  children: T[]
): { populated: T[]; empty: T[] } {
  const populated: T[] = [];
  const empty: T[] = [];
  for (const c of children) {
    if ((c._count?.ideas ?? 0) + (c._count?.painPoints ?? 0) > 0) populated.push(c);
    else empty.push(c);
  }
  populated.sort((a, b) => {
    const aT = (a._count?.ideas ?? 0) + (a._count?.painPoints ?? 0);
    const bT = (b._count?.ideas ?? 0) + (b._count?.painPoints ?? 0);
    return bT !== aT ? bT - aT : a.name.localeCompare(b.name);
  });
  empty.sort((a, b) => a.name.localeCompare(b.name));
  return { populated, empty };
}
