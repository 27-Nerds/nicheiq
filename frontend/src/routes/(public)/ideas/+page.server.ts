import type { PageServerLoad } from './$types';
import { env } from '$env/dynamic/private';
import { canonicalUrl } from '$lib/seo/canonical';
import { buildMeta } from '$lib/seo/meta';
import { breadcrumbList, collectionPage, itemList } from '$lib/seo/jsonld';
import { siteOrigin } from '$lib/seo/canonical';
import type {
  CatalogTotals,
  CatalogCollectionSummary,
  CatalogCollectionDetail,
} from '$lib/types/publicCatalog';

const LAUNCH_GATE_ON = (env.SEO_LAUNCH_GATE ?? 'true') !== 'false';
const BACKEND_URL = env.BACKEND_URL || 'http://localhost:3001';

const HEADERS = (): Record<string, string> => ({
  'X-Internal-Service': env.INTERNAL_SERVICE_SECRET || '',
});

// Aggregate counts for the index hero stat strip. Defensive: if the endpoint
// is unavailable (rare — the backend is required to boot the frontend),
// fall back to zero counts so the page still renders.
async function fetchTotals(): Promise<CatalogTotals> {
  try {
    const res = await fetch(`${BACKEND_URL}/api/public/catalog/totals`, {
      headers: HEADERS(),
    });
    if (res.ok) return (await res.json()) as CatalogTotals;
  } catch (err) {
    console.error('totals fetch failed', err);
  }
  return {
    totalIdeas: 0,
    totalCategories: 0,
    totalSubcategories: 0,
    contentItemsMined: 0,
    lastUpdated: null,
  };
}

// Featured collections (admin-curated). Endpoint returns active collections
// ordered by sortOrder; empty array hides the section on the page.
async function fetchCollections(): Promise<CatalogCollectionSummary[]> {
  try {
    const res = await fetch(`${BACKEND_URL}/api/public/catalog/collections`, {
      headers: HEADERS(),
    });
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
    const res = await fetch(`${BACKEND_URL}/api/public/catalog/collections/${slug}`, {
      headers: HEADERS(),
    });
    if (res.ok) return (await res.json()) as CatalogCollectionDetail;
  } catch (err) {
    console.error('collection detail fetch failed', err);
  }
  return null;
}

export const load: PageServerLoad = async ({ url, setHeaders, parent }) => {
  setHeaders({
    'Cache-Control': 'public, max-age=60, s-maxage=300, stale-while-revalidate=86400',
  });

  const collectionSlug = url.searchParams.get('collection');

  const [{ categoriesTree }, totals, collections, activeCollection] = await Promise.all([
    parent(),
    fetchTotals(),
    fetchCollections(),
    collectionSlug ? fetchCollectionDetail(collectionSlug) : Promise.resolve(null),
  ]);
  const origin = siteOrigin();
  const canonical = canonicalUrl('/ideas', url.searchParams);

  const meta = buildMeta({
    title: 'Startup Ideas & Pain Points | NicheIQ',
    description:
      'Browse hand-curated startup ideas and pain points sourced from Reddit and Hacker News, scored for market fit and feasibility. Updated weekly.',
    canonical,
    type: 'website',
    noindex: LAUNCH_GATE_ON,
  });

  // ItemList schema signals to crawlers that this hub aggregates 50+ niche
  // entry points; each top-level CatalogCategory becomes a ListItem.
  // Organization + WebSite are emitted once at the root layout — the index
  // page only contributes route-specific schema (Breadcrumb + Collection +
  // ItemList).
  const niches = (categoriesTree as Array<{ name: string; slug: string }>).map(
    (n) => ({
      name: n.name,
      url: `${origin}/ideas/${n.slug}`,
    }),
  );

  const jsonld = [
    breadcrumbList([
      { name: 'Home', url: `${origin}/` },
      { name: 'Ideas', url: `${origin}/ideas` },
    ]),
    collectionPage({
      name: 'Ideas Catalog',
      description:
        'Curated startup ideas and pain points sourced from Reddit and Hacker News, organized by niche.',
      url: canonical,
    }),
    itemList(niches, { numberOfItems: niches.length }),
  ];

  return {
    meta,
    jsonld,
    categoriesTree,
    totals,
    collections,
    activeCollection,
    collectionSlug,
  };
};
