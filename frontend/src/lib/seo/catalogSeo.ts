import { canonicalUrl, shouldNoindex, siteOrigin } from './canonical';
import {
  breadcrumbList,
  collectionPage,
  itemList,
  faqPage,
  article,
  type JsonLd,
} from './jsonld';
import { categoryPath, ideaPath, painPointPath, programmaticPath } from '$lib/utils/urls';
import type {
  CategoryLandingPayload,
  CategoryLandingParent,
  CategoryLandingCategory,
  IdeaPreview,
  PainPointPreview,
  ProgrammaticIdeaPage,
} from '$lib/types/catalog-landing';

/**
 * Per-page SEO helpers for `/ideas/*`, `/idea/[slug]`, `/pain-point/[slug]`.
 * Centralised so all five route loaders stay consistent.
 */

const ORIGIN = siteOrigin();

// =====================================================================
// Title / description / noindex
// =====================================================================

export function categoryTitle(
  c: Pick<CategoryLandingCategory, 'name' | 'seoTitle'>,
  parent: { name: string } | null,
): string {
  if (c.seoTitle) return c.seoTitle;
  if (parent) return `${parent.name} → ${c.name} Ideas | NicheIQ`;
  return `${c.name} Ideas & Pain Points | NicheIQ`;
}

export function categoryDescription(
  c: Pick<CategoryLandingCategory, 'name' | 'seoDescription'>,
  totalIdeas: number,
  totalPainPoints: number,
): string {
  if (c.seoDescription) return c.seoDescription;
  return `${totalIdeas} startup ideas and ${totalPainPoints} pain points in ${c.name}, sourced from Reddit and Hacker News. Updated weekly.`;
}

export function categoryLongDescriptionFallback(
  name: string,
  totalIdeas: number,
  totalPainPoints: number,
): string {
  return `${name} is a niche we actively track on NicheIQ. So far we've surfaced ${totalIdeas} startup ideas and ${totalPainPoints} pain points in this space, drawn from Reddit and Hacker News discussions.`;
}

export interface NoindexInputs {
  payload?: Pick<CategoryLandingPayload, 'totalIdeas' | 'totalPainPoints' | 'category'>;
  searchParams: URLSearchParams;
  launchGateOn: boolean;
}

/**
 * Decide whether a category landing page should ship with `noindex,follow`.
 *
 * Triggers:
 * 1. Phase 4.5 launch gate is on (default until baseline curation).
 * 2. Filter overlay query params (`?page>1`, `?sort=` non-default, `?tag=` etc.).
 * 3. Empty leaf (zero ideas + zero pain-points) — Google flags thin content.
 * 4. Pre-launch category with no `longDescription` set yet.
 */
export function categoryNoindex({ payload, searchParams, launchGateOn }: NoindexInputs): boolean {
  if (launchGateOn) return true;
  if (shouldNoindex(searchParams)) return true;
  if (!payload) return false;
  if (payload.totalIdeas + payload.totalPainPoints === 0) return true;
  if (!payload.category.longDescription) return true;
  return false;
}

export interface DetailNoindexInputs {
  searchParams: URLSearchParams;
  launchGateOn: boolean;
}

export function detailNoindex({ searchParams, launchGateOn }: DetailNoindexInputs): boolean {
  if (launchGateOn) return true;
  if (shouldNoindex(searchParams)) return true;
  return false;
}

// =====================================================================
// JSON-LD builders
// =====================================================================

interface BreadcrumbStop {
  name: string;
  url: string;
}

function homeStop(): BreadcrumbStop {
  return { name: 'Home', url: `${ORIGIN}/` };
}

function ideasStop(): BreadcrumbStop {
  return { name: 'Ideas', url: `${ORIGIN}/ideas` };
}

function categoryStops(payload: CategoryLandingPayload): BreadcrumbStop[] {
  const stops: BreadcrumbStop[] = [homeStop(), ideasStop()];
  if (payload.parent) {
    stops.push({
      name: payload.parent.name,
      url: `${ORIGIN}${categoryPath({ slug: payload.parent.slug })}`,
    });
  }
  stops.push({
    name: payload.category.name,
    url: `${ORIGIN}${categoryPath({
      slug: payload.category.slug,
      parentSlug: payload.parent?.slug ?? null,
    })}`,
  });
  return stops;
}

export function buildCategoryJsonLd(
  payload: CategoryLandingPayload,
  canonical: string,
  description: string,
): JsonLd[] {
  const stops = categoryStops(payload);
  const items = [
    ...payload.topIdeas.map((i) => ({
      name: i.solution_name,
      url: `${ORIGIN}${ideaPath(i.slug)}`,
    })),
    ...payload.topPainPoints.map((p) => ({
      name: p.title,
      url: `${ORIGIN}${painPointPath(p.slug)}`,
    })),
  ];

  const blocks: JsonLd[] = [
    breadcrumbList(stops),
    collectionPage({
      name: payload.category.name,
      description,
      url: canonical,
      about: payload.category.name,
    }),
  ];
  if (items.length > 0) blocks.push(itemList(items));
  if (payload.category.faqJson && payload.category.faqJson.length > 0) {
    blocks.push(faqPage(payload.category.faqJson));
  }
  return blocks;
}

export function buildProgrammaticJsonLd(
  pseo: ProgrammaticIdeaPage,
  featuredIdeas: IdeaPreview[],
  canonical: string,
): JsonLd[] {
  const stops: BreadcrumbStop[] = [
    homeStop(),
    ideasStop(),
    { name: pseo.title, url: `${ORIGIN}${programmaticPath(pseo.slug)}` },
  ];
  const blocks: JsonLd[] = [
    breadcrumbList(stops),
    collectionPage({
      name: pseo.title,
      description: pseo.seoDescription,
      url: canonical,
      about: pseo.title,
    }),
  ];
  if (featuredIdeas.length > 0) {
    blocks.push(
      itemList(
        featuredIdeas.map((i) => ({
          name: i.solution_name,
          url: `${ORIGIN}${ideaPath(i.slug)}`,
        })),
      ),
    );
  }
  if (pseo.faqJson.length > 0) blocks.push(faqPage(pseo.faqJson));
  return blocks;
}

export function buildIdeaDetailJsonLd(idea: IdeaPreview, canonical: string): JsonLd[] {
  const parent = idea.category.parent ?? null;
  const stops: BreadcrumbStop[] = [homeStop(), ideasStop()];
  if (parent) {
    stops.push({ name: parent.name, url: `${ORIGIN}${categoryPath({ slug: parent.slug })}` });
  }
  stops.push({
    name: idea.category.name,
    url: `${ORIGIN}${categoryPath({
      slug: idea.category.slug,
      parentSlug: parent?.slug ?? null,
    })}`,
  });
  stops.push({ name: idea.solution_name, url: canonical });

  return [
    breadcrumbList(stops),
    article({
      headline: idea.solution_name,
      description: idea.description,
      datePublished: idea.created_at,
      dateModified: idea.updated_at ?? idea.created_at,
      url: canonical,
      author: 'NicheIQ Research Team',
    }),
  ];
}

export function buildPainPointDetailJsonLd(pp: PainPointPreview, canonical: string): JsonLd[] {
  const parent = pp.category.parent ?? null;
  const stops: BreadcrumbStop[] = [homeStop(), ideasStop()];
  if (parent) {
    stops.push({ name: parent.name, url: `${ORIGIN}${categoryPath({ slug: parent.slug })}` });
  }
  stops.push({
    name: pp.category.name,
    url: `${ORIGIN}${categoryPath({
      slug: pp.category.slug,
      parentSlug: parent?.slug ?? null,
    })}`,
  });
  stops.push({ name: pp.title, url: canonical });

  return [
    breadcrumbList(stops),
    article({
      headline: pp.title,
      description: pp.description,
      datePublished: pp.createdAt,
      dateModified: pp.updatedAt ?? pp.createdAt,
      url: canonical,
      author: 'NicheIQ Research Team',
    }),
  ];
}

// =====================================================================
// Canonical helpers (light wrappers for consistency)
// =====================================================================

export function categoryCanonical(
  parentSlug: string,
  childSlug: string | null,
  searchParams: URLSearchParams,
): string {
  const path = childSlug ? `/ideas/${parentSlug}/${childSlug}` : `/ideas/${parentSlug}`;
  return canonicalUrl(path, searchParams);
}

export function ideaDetailCanonical(slug: string, searchParams: URLSearchParams): string {
  return canonicalUrl(ideaPath(slug), searchParams);
}

export function painPointDetailCanonical(slug: string, searchParams: URLSearchParams): string {
  return canonicalUrl(painPointPath(slug), searchParams);
}

// =====================================================================
// Re-exports for convenience
// =====================================================================

export { canonicalUrl, shouldNoindex } from './canonical';
