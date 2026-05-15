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

export const load: PageServerLoad = async ({ params, url, setHeaders }) => {
  setHeaders({
    'Cache-Control': 'public, max-age=300, s-maxage=900, stale-while-revalidate=86400',
  });

  let res: Response;
  try {
    res = await fetchBackend(
      `/api/public/catalog/landing/${encodeURIComponent(params.niche)}/${encodeURIComponent(params.sub)}`,
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

  const jsonld = buildCategoryJsonLd(payload, canonical, description);

  return {
    meta,
    jsonld,
    payload,
    longDescription:
      payload.category.longDescription ??
      categoryLongDescriptionFallback(
        payload.category.name,
        payload.totalIdeas,
        payload.totalPainPoints,
      ),
  };
};
