import type { PageServerLoad } from './$types';
import { env } from '$env/dynamic/private';
import { canonicalUrl } from '$lib/seo/canonical';
import { buildMeta } from '$lib/seo/meta';
import { organization, website, breadcrumbList, itemList } from '$lib/seo/jsonld';
import { siteOrigin } from '$lib/seo/canonical';
import type { CatalogTotals, CatalogCollectionSummary } from '$lib/types/publicCatalog';

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

export const load: PageServerLoad = async ({ url, setHeaders, parent }) => {
  setHeaders({
    'Cache-Control': 'public, max-age=60, s-maxage=300, stale-while-revalidate=86400',
  });

  const [{ categoriesTree }, totals, collections] = await Promise.all([
    parent(),
    fetchTotals(),
    fetchCollections(),
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
  const niches = (categoriesTree as Array<{ name: string; slug: string }>).map(
    (n) => ({
      name: n.name,
      url: `${origin}/ideas/${n.slug}`,
    }),
  );

  const jsonld = [
    organization(),
    website(),
    breadcrumbList([
      { name: 'Home', url: `${origin}/` },
      { name: 'Ideas', url: `${origin}/ideas` },
    ]),
    itemList(niches),
  ];

  return {
    meta,
    jsonld,
    categoriesTree,
    totals,
    collections,
  };
};
