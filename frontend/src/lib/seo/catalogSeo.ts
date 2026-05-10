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

/**
 * Truncate an Article `description` to a SERP-friendly length. Google's
 * Article rich-result truncates around 160 characters; longer payloads still
 * validate but read awkwardly when AI search engines or SERPs surface them
 * as standalone snippets. Cuts at the last word boundary inside the limit
 * and appends an ellipsis only when the input was actually trimmed.
 */
function trimArticleDescription(text: string | null | undefined, max = 160): string {
  if (!text) return '';
  const clean = text.trim();
  if (clean.length <= max) return clean;
  const slice = clean.slice(0, max);
  const lastSpace = slice.lastIndexOf(' ');
  const cut = lastSpace > max * 0.6 ? slice.slice(0, lastSpace) : slice;
  return `${cut.replace(/[\s.,;:—-]+$/, '')}…`;
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
  const ideaItems = payload.topIdeas.map((i) => ({
    name: i.solution_name,
    url: `${ORIGIN}${ideaPath(i.slug)}`,
  }));
  const painItems = payload.topPainPoints.map((p) => ({
    name: p.title,
    url: `${ORIGIN}${painPointPath(p.slug)}`,
  }));

  const blocks: JsonLd[] = [
    breadcrumbList(stops),
    collectionPage({
      name: payload.category.name,
      description,
      url: canonical,
      about: payload.category.name,
    }),
  ];
  // Two distinct ItemLists rather than a flat combined list — ideas and
  // pain-points are semantically different content types and the visible page
  // already renders them as separate sections (`AllIdeasSection` +
  // `PainPointRankTable`). Splitting matches the visible structure and gives
  // crawlers a precise signal per type.
  if (ideaItems.length > 0) {
    blocks.push(
      itemList(ideaItems, {
        name: `Ideas in ${payload.category.name}`,
        numberOfItems: payload.totalIdeas,
      }),
    );
  }
  if (painItems.length > 0) {
    blocks.push(
      itemList(painItems, {
        name: `Pain points in ${payload.category.name}`,
        numberOfItems: payload.totalPainPoints,
      }),
    );
  }
  // FAQPage gated on faqJson having >= 2 entries — same threshold as the
  // visible <CategoryFAQ> render gate, so visible-vs-schema match holds by
  // construction (both sides driven by the same field). See plan B10.
  if ((payload.category.faqJson?.length ?? 0) >= 2) {
    blocks.push(faqPage(payload.category.faqJson!));
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
        {
          name: `Ideas — ${pseo.title}`,
          numberOfItems: featuredIdeas.length,
        },
      ),
    );
  }
  // PSEO faqJson is hardcoded in programmaticIdeaPages.ts and rendered visibly
  // via <CategoryFAQ> on the PSEO branch of the public route, so the schema
  // match is structural. Same gate as real-category and detail pages.
  if (pseo.faqJson.length >= 2) {
    blocks.push(faqPage(pseo.faqJson));
  }
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

  // Article description prefers `short_description` (the Pydantic
  // BaseSolutionIdea.short_description — purpose-built 1-2 sentence card
  // summary) when available, falling back to a trimmed `description` so SERP
  // snippets and AI-search citations don't get a 600-char wall of text.
  const articleDescription = idea.short_description?.trim()
    ? idea.short_description.trim()
    : trimArticleDescription(idea.description);

  const blocks: JsonLd[] = [
    breadcrumbList(stops),
    article({
      headline: idea.solution_name,
      description: articleDescription,
      datePublished: idea.created_at,
      dateModified: idea.updated_at ?? idea.created_at,
      url: canonical,
      author: 'NicheIQ Research Team',
    }),
  ];
  // FAQPage gated on the same threshold as the visible <CategoryFAQ> render
  // — both sides driven by the same idea.faqJson field.
  if ((idea.faqJson?.length ?? 0) >= 2) {
    blocks.push(faqPage(idea.faqJson!));
  }
  return blocks;
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

  const blocks: JsonLd[] = [
    breadcrumbList(stops),
    article({
      headline: pp.title,
      description: trimArticleDescription(pp.description),
      datePublished: pp.createdAt,
      dateModified: pp.updatedAt ?? pp.createdAt,
      url: canonical,
      author: 'NicheIQ Research Team',
    }),
  ];
  if ((pp.faqJson?.length ?? 0) >= 2) {
    blocks.push(faqPage(pp.faqJson!));
  }
  return blocks;
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
