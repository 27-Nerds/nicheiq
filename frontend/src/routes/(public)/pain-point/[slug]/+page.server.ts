import type { PageServerLoad } from './$types';
import { error } from '@sveltejs/kit';
import { fetchBackend } from '$lib/backend';
import {
  buildPainPointDetailJsonLd,
  detailNoindex,
  painPointDetailCanonical,
} from '$lib/seo/catalogSeo';
import { buildMeta } from '$lib/seo/meta';
import { LAUNCH_GATE_ON } from '$lib/seo/launchGate';
import type { PainPointDetailResponse } from '$lib/types/catalog-landing';

export const load: PageServerLoad = async ({ params, url, setHeaders }) => {
  setHeaders({
    'Cache-Control': 'public, max-age=300, s-maxage=3600, stale-while-revalidate=86400',
  });

  let res: Response;
  try {
    res = await fetchBackend(
      `/api/public/catalog/pain-point-by-slug/${encodeURIComponent(params.slug)}`,
    );
  } catch (err) {
    console.error('pain-point fetch failed', err);
    throw error(500, 'Failed to load');
  }

  if (res.status === 404) throw error(404, 'Not found');
  if (!res.ok) throw error(500, 'Failed to load');

  const pp = (await res.json()) as PainPointDetailResponse;
  const canonical = painPointDetailCanonical(pp.slug, url.searchParams);

  const description = (pp.description ?? '').slice(0, 200);

  const meta = buildMeta({
    title: `${pp.title} | NicheIQ Pain Points`,
    description: description || `Documented pain point in ${pp.category.name}.`,
    canonical,
    type: 'article',
    noindex: detailNoindex({ searchParams: url.searchParams, launchGateOn: LAUNCH_GATE_ON }),
  });

  const jsonld = buildPainPointDetailJsonLd(pp, canonical);

  return { meta, jsonld, painPoint: pp };
};
