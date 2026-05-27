import type { PageServerLoad } from './$types';
import { fetchBackend } from '$lib/backend';
import { canonicalUrl } from '$lib/seo/canonical';
import { buildMeta } from '$lib/seo/meta';
import { breadcrumbList, collectionPage, itemList } from '$lib/seo/jsonld';
import { siteOrigin } from '$lib/seo/canonical';
import { editionLabel } from '$lib/seo/edition';
import { LAUNCH_GATE_ON } from '$lib/seo/launchGate';
import { formatCompact } from '$lib/utils/format-numbers';
import { categoryPath } from '$lib/utils/urls';
import type {
  CatalogTotals,
  CatalogTopPainPoint,
  CatalogCollectionSummary,
  CatalogCollectionDetail,
} from '$lib/types/publicCatalog';

// Aggregate counts for the index hero stat strip. Defensive: if the endpoint
// is unavailable (rare — the backend is required to boot the frontend),
// fall back to zero counts so the page still renders.
async function fetchTotals(): Promise<CatalogTotals> {
  try {
    const res = await fetchBackend('/api/public/catalog/totals');
    if (res.ok) return (await res.json()) as CatalogTotals;
  } catch (err) {
    console.error('totals fetch failed', err);
  }
  return {
    totalIdeas: 0,
    totalCategories: 0,
    totalSubcategories: 0,
    contentItemsMined: 0,
    commentsAnalyzed: 0,
    lastUpdated: null,
  };
}

// Featured collections (admin-curated). Endpoint returns active collections
// ordered by sortOrder; empty array hides the section on the page.
async function fetchCollections(): Promise<CatalogCollectionSummary[]> {
  try {
    const res = await fetchBackend('/api/public/catalog/collections');
    if (res.ok) {
      const data = await res.json();
      return (data?.collections ?? []) as CatalogCollectionSummary[];
    }
  } catch (err) {
    console.error('collections fetch failed', err);
  }
  return [];
}

// Single collection detail — only fetched when ?collection=<slug> is present
// in the URL. Used to filter the catalog accordion to categories the
// collection's items live in (including descendants — see B4).
async function fetchCollectionDetail(slug: string): Promise<CatalogCollectionDetail | null> {
  try {
    const res = await fetchBackend(`/api/public/catalog/collections/${slug}`);
    if (res.ok) return (await res.json()) as CatalogCollectionDetail;
  } catch (err) {
    console.error('collection detail fetch failed', err);
  }
  return null;
}

// Top 10 highest-severity pain points across the whole catalog. Feeds the
// "Most In-Demand SaaS Niches — {month}" SEO surface at the bottom of /ideas.
// Defensive fallback to an empty array hides the section when the backend
// can't answer.
async function fetchTopPainPoints(): Promise<CatalogTopPainPoint[]> {
  try {
    const res = await fetchBackend('/api/public/catalog/top-pain-points?limit=10');
    if (res.ok) return (await res.json()) as CatalogTopPainPoint[];
  } catch (err) {
    console.error('top-pain-points fetch failed', err);
  }
  return [];
}

export const load: PageServerLoad = async ({ url, setHeaders, parent, locals }) => {
  // Logged-in users get the dashboard chrome, which puts their per-user credit
  // balance (from the public layout load) into the SSR payload — so their
  // response must NOT be shared/CDN-cached. Anonymous visitors keep the public,
  // cacheable policy. Mirrors the gate in (public)/ideas/[niche]/+page.server.ts.
  const session = await locals?.auth?.();
  setHeaders({
    'Cache-Control': session?.user?.id
      ? 'private, no-store'
      : 'public, max-age=60, s-maxage=300, stale-while-revalidate=86400',
  });

  const collectionSlug = url.searchParams.get('collection');

  const [{ categoriesTree }, totals, collections, activeCollection, topPainPoints] =
    await Promise.all([
      parent(),
      fetchTotals(),
      fetchCollections(),
      collectionSlug ? fetchCollectionDetail(collectionSlug) : Promise.resolve(null),
      fetchTopPainPoints(),
    ]);
  const origin = siteOrigin();
  const canonical = canonicalUrl('/ideas', url.searchParams);

  // SEO copy + edition label both derive from the catalog's freshness signal
  // so the head meta, JSON-LD CollectionPage.description, and on-page intro
  // all read the same numbers. `editionLabel()` guards against stale or
  // missing `lastUpdated` (>45 days or null) → returns "Latest edition".
  const edition = editionLabel(totals.lastUpdated);
  const description =
    `Browse ${totals.totalIdeas.toLocaleString()} hand-curated startup ideas across ` +
    `${totals.totalCategories.toLocaleString()} categories — scored on demand, ` +
    `feasibility, and SEO opportunity from ${formatCompact(totals.contentItemsMined)}+ ` +
    `community discussions.`;

  const meta = buildMeta({
    title: 'SaaS Startup Ideas & Pain Points | NicheIQ',
    description,
    canonical,
    type: 'website',
    noindex: LAUNCH_GATE_ON,
  });

  // Two ItemLists are emitted on /ideas:
  //  1. Top-level niche entry points (existing) — surfaced as the browse hub.
  //  2. Top 10 cross-catalog pain points (new) — referenced as the page's
  //     `mainEntity` so AI Overviews / Knowledge Graph consumers can read
  //     the page's primary editorial payload from a single @id.
  // Organization + WebSite are emitted once at the root layout.
  const niches = (categoriesTree as Array<{ name: string; slug: string }>).map(
    (n) => ({
      name: n.name,
      url: `${origin}/ideas/${n.slug}`,
    }),
  );

  const topPainsListId = `${origin}/ideas/#top-pains`;
  const topPainsListName = `Most In-Demand SaaS Niches — ${edition}`;
  const topPainsItems = topPainPoints.map((pp) => ({
    name: pp.title,
    url:
      origin +
      categoryPath({
        slug: pp.category.slug,
        parentSlug: pp.category.parent?.slug ?? null,
      }),
    description: pp.title,
  }));

  const jsonld = [
    breadcrumbList([
      { name: 'Home', url: `${origin}/` },
      { name: 'Ideas', url: `${origin}/ideas` },
    ]),
    collectionPage({
      name: 'Ideas Catalog',
      description,
      url: canonical,
      dateModified: totals.lastUpdated ?? null,
      mainEntityId: topPainPoints.length > 0 ? topPainsListId : null,
    }),
    itemList(niches, { numberOfItems: niches.length }),
    ...(topPainPoints.length > 0
      ? [
          itemList(topPainsItems, {
            id: topPainsListId,
            name: topPainsListName,
            numberOfItems: topPainPoints.length,
          }),
        ]
      : []),
  ];

  // The hub only uses a collection's `categorySlugs` (+ name) to filter the
  // accordion — it never renders the collection's items. Strip `items` so the
  // (admin-curated) collection's idea/pain previews — which may include
  // non-featured items — don't leak into the public `__data.json`.
  const activeCollectionSafe = activeCollection ? { ...activeCollection, items: [] } : null;

  return {
    meta,
    jsonld,
    categoriesTree,
    totals,
    collections,
    activeCollection: activeCollectionSafe,
    collectionSlug,
    topPainPoints,
    editionLabel: edition,
  };
};
