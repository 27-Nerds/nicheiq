import type { PageServerLoad } from './$types';
import { error } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import {
  buildPainPointDetailJsonLd,
  detailNoindex,
  painPointDetailCanonical,
} from '$lib/seo/catalogSeo';
import { buildMeta } from '$lib/seo/meta';
import type { PainPointPreview } from '$lib/types/catalog-landing';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:3001';
const LAUNCH_GATE_ON = (env.SEO_LAUNCH_GATE ?? 'true') !== 'false';

export const load: PageServerLoad = async ({ params, url, setHeaders }) => {
  setHeaders({
    'Cache-Control': 'public, max-age=300, s-maxage=3600, stale-while-revalidate=86400',
  });

  let res: Response;
  try {
    res = await fetch(
      `${BACKEND_URL}/api/public/catalog/pain-point-by-slug/${encodeURIComponent(params.slug)}`,
      { headers: { 'X-Internal-Service': env.INTERNAL_SERVICE_SECRET || '' } },
    );
  } catch (err) {
    console.error('pain-point fetch failed', err);
    throw error(500, 'Failed to load');
  }

  if (res.status === 404) throw error(404, 'Not found');
  if (!res.ok) throw error(500, 'Failed to load');

  const pp = (await res.json()) as PainPointPreview;
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
