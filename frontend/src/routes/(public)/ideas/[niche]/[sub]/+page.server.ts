import type { PageServerLoad } from './$types';
import { error } from '@sveltejs/kit';
import { fetchBackend } from '$lib/backend';
import {
  categoryTitle,
  categoryDescription,
  categoryNoindex,
  categoryLongDescriptionFallback,
  buildCategoryJsonLd,
  categoryCanonical,
} from '$lib/seo/catalogSeo';
import { buildMeta } from '$lib/seo/meta';
import { LAUNCH_GATE_ON } from '$lib/seo/launchGate';
import type { CategoryLandingPayload } from '$lib/types/catalog-landing';

export const load: PageServerLoad = async ({ params, url, setHeaders, locals }) => {
  // Entitled users (ADMIN / subscriber / fullCatalogAccess) get the FULL list, so the
  // response varies per user → forward X-User-ID and mark it private (uncacheable).
  // Anonymous visitors get the public, CDN-cacheable featured-only teaser.
  const session = await locals?.auth?.();
  const userId = session?.user?.id;
  setHeaders({
    'Cache-Control': userId
      ? 'private, no-store'
      : 'public, max-age=300, s-maxage=900, stale-while-revalidate=86400',
  });

  let res: Response;
  try {
    res = await fetchBackend(
      `/api/public/catalog/landing/${encodeURIComponent(params.niche)}/${encodeURIComponent(params.sub)}`,
      userId ? { headers: { 'X-User-ID': userId } } : {},
    );
  } catch (err) {
    console.error('nested landing fetch failed', err);
    throw error(500, 'Failed to load');
  }

  if (res.status === 404) throw error(404, 'Not found');
  if (res.status === 410) throw error(410, 'Gone');
  if (!res.ok) throw error(500, 'Failed to load');

  const payload = (await res.json()) as CategoryLandingPayload;

  const canonical = categoryCanonical(
    payload.parent?.slug ?? params.niche,
    payload.category.slug,
    url.searchParams,
  );
  const description = categoryDescription(payload.category, payload.totalIdeas, payload.totalPainPoints);

  const meta = buildMeta({
    title: categoryTitle(payload.category, payload.parent),
    description,
    canonical,
    type: 'website',
    noindex: categoryNoindex({ payload, searchParams: url.searchParams, launchGateOn: LAUNCH_GATE_ON }),
  });

  // GO-count comes from the backend aggregate (counted across the full subtree,
  // independent of the featured-only visible set the backend now returns).
  const goCount = payload.verdictGoCount ?? 0;

  // Public teaser: the backend already returns the featured-only visible set
  // (1 for a leaf sub-niche), so non-featured items never reach the browser.
  // `lockedIdeaCount` stays frontend-derived; `lockedPainCount` is server-
  // authoritative (see commentary in the parent-niche loader and
  // catalogService for why).
  const lockedIdeaCount = Math.max(0, payload.totalIdeas - payload.topIdeas.length);
  const lockedPainCount = payload.lockedPainCount;

  // includeItemLists: false → JSON-LD must not enumerate the login-gated
  // idea/pain detail URLs (noindex + out of sitemap + robots Disallow).
  const jsonld = buildCategoryJsonLd(payload, canonical, description, false);

  return {
    meta,
    jsonld,
    payload,
    goCount,
    lockedIdeaCount,
    lockedPainCount,
    longDescription:
      payload.category.longDescription ??
      categoryLongDescriptionFallback(
        payload.category.name,
        payload.totalIdeas,
        payload.totalPainPoints,
      ),
  };
};
