import type { PageServerLoad } from './$types';
import { error } from '@sveltejs/kit';
import { fetchBackend } from '$lib/backend';
import {
  categoryTitle,
  categoryDescription,
  categoryNoindex,
  categoryLongDescriptionFallback,
  buildCategoryJsonLd,
  buildProgrammaticJsonLd,
  categoryCanonical,
  parentCategoryDescription,
} from '$lib/seo/catalogSeo';
import { buildMeta } from '$lib/seo/meta';
import { LAUNCH_GATE_ON } from '$lib/seo/launchGate';
import type { CategoryLandingPayload, IdeaPreview } from '$lib/types/catalog-landing';
import type { CatalogCollectionSummary } from '$lib/types/publicCatalog';
import { findProgrammaticIdeaPage } from '$lib/data/programmaticIdeaPages';

async function fetchLanding(slug: string): Promise<
  | { kind: 'ok'; payload: CategoryLandingPayload }
  | { kind: 'gone' }
  | { kind: 'missing' }
  | { kind: 'error' }
> {
  try {
    const res = await fetchBackend(
      `/api/public/catalog/landing/${encodeURIComponent(slug)}`,
    );
    if (res.status === 200) return { kind: 'ok', payload: await res.json() };
    if (res.status === 404) return { kind: 'missing' };
    if (res.status === 410) return { kind: 'gone' };
    return { kind: 'error' };
  } catch (err) {
    console.error('landing fetch failed', err);
    return { kind: 'error' };
  }
}

async function fetchIdeaBySlug(slug: string): Promise<IdeaPreview | null> {
  try {
    const res = await fetchBackend(
      `/api/public/catalog/idea-by-slug/${encodeURIComponent(slug)}`,
    );
    if (!res.ok) return null;
    return (await res.json()) as IdeaPreview;
  } catch {
    return null;
  }
}

// Best-effort fetch of active collections — used to surface a Featured
// Collection Teaser on category pages whose slug is touched by a collection.
// Failure is swallowed: the teaser silently disappears, the rest of the
// category page renders normally.
async function fetchCollections(): Promise<CatalogCollectionSummary[]> {
  try {
    const res = await fetchBackend('/api/public/catalog/collections');
    if (!res.ok) return [];
    const data = await res.json();
    return (data?.collections ?? []) as CatalogCollectionSummary[];
  } catch (err) {
    console.error('collections fetch failed', err);
    return [];
  }
}

// Pick the first collection (by sortOrder, since the backend already orders
// them) whose categorySlugs include the current category. Returns null if
// none match — the route hides the teaser silently.
function pickFeaturedCollection(
  collections: CatalogCollectionSummary[],
  categorySlug: string,
): CatalogCollectionSummary | null {
  for (const c of collections) {
    if (c.categorySlugs.includes(categorySlug)) return c;
  }
  return null;
}

export const load: PageServerLoad = async ({ params, url, setHeaders }) => {
  setHeaders({
    'Cache-Control': 'public, max-age=300, s-maxage=900, stale-while-revalidate=86400',
  });

  // 1. Try real category landing. Fetch collections in parallel — the
  // featured-collection teaser is optional, so its failure shouldn't block
  // the page (fetchCollections already returns [] on error).
  const [landing, collections] = await Promise.all([
    fetchLanding(params.niche),
    fetchCollections(),
  ]);

  if (landing.kind === 'gone') throw error(410, 'Gone');
  if (landing.kind === 'error') throw error(500, 'Failed to load');

  if (landing.kind === 'ok') {
    const { payload } = landing;
    const canonical = categoryCanonical(payload.category.slug, null, url.searchParams);
    const description = parentCategoryDescription(payload);

    const meta = buildMeta({
      title: categoryTitle(payload.category, payload.parent),
      description,
      canonical,
      type: 'website',
      noindex: categoryNoindex({ payload, searchParams: url.searchParams, launchGateOn: LAUNCH_GATE_ON }),
    });

    const jsonld = buildCategoryJsonLd(payload, canonical, description);

    const featuredCollection = pickFeaturedCollection(
      collections,
      payload.category.slug,
    );

    return {
      kind: 'category' as const,
      meta,
      jsonld,
      payload,
      featuredCollection,
      longDescription:
        payload.category.longDescription ??
        categoryLongDescriptionFallback(
          payload.category.name,
          payload.totalIdeas,
          payload.totalPainPoints,
        ),
    };
  }

  // 2. Real category not found — try programmatic SEO fallback.
  const pseo = findProgrammaticIdeaPage(params.niche);
  if (!pseo) throw error(404, 'Not found');

  // Resolve featured idea slugs (best-effort; nulls filtered out).
  const featuredIdeas = (
    await Promise.all(pseo.featuredIdeaSlugs.map((s) => fetchIdeaBySlug(s)))
  ).filter((i): i is IdeaPreview => i !== null);

  const canonical = categoryCanonical(pseo.slug, null, url.searchParams);
  const meta = buildMeta({
    title: pseo.seoTitle,
    description: pseo.seoDescription,
    canonical,
    type: 'website',
    noindex: LAUNCH_GATE_ON,
  });

  const jsonld = buildProgrammaticJsonLd(pseo, featuredIdeas, canonical);

  return {
    kind: 'pseo' as const,
    meta,
    jsonld,
    pseo,
    featuredIdeas,
  };
};
