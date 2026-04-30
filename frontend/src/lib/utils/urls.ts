/**
 * Catalog URL builders — single source of truth for /ideas/*, /idea/*,
 * /pain-point/* paths.
 *
 * Components that link to a category, idea, or pain-point MUST use these
 * helpers. Manual concatenation breaks when the slug becomes nested
 * (e.g. /ideas/saas/b2b-tools), and forces every callsite to know the parent
 * slug for child categories.
 */

export interface CategoryRef {
  slug: string;
  /**
   * Parent niche slug. `null` or omitted for top-level categories. When
   * present, the resulting URL is nested: `/ideas/{parentSlug}/{slug}`.
   */
  parentSlug?: string | null;
}

export function categoryPath(c: CategoryRef): string {
  return c.parentSlug ? `/ideas/${c.parentSlug}/${c.slug}` : `/ideas/${c.slug}`;
}

export function ideaPath(slug: string): string {
  return `/idea/${slug}`;
}

export function painPointPath(slug: string): string {
  return `/pain-point/${slug}`;
}

/**
 * Programmatic-SEO landing pages share the top-level `/ideas/[niche]` slot.
 * Helper exists for symmetry / readability at callsites.
 */
export function programmaticPath(slug: string): string {
  return `/ideas/${slug}`;
}

export const IDEAS_HUB_PATH = '/ideas';
