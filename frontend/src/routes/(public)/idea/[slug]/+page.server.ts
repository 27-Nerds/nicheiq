import type { PageServerLoad } from './$types';
import { error } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import {
  buildIdeaDetailJsonLd,
  detailNoindex,
  ideaDetailCanonical,
} from '$lib/seo/catalogSeo';
import { buildMeta } from '$lib/seo/meta';
import type { IdeaDetailResponse } from '$lib/types/catalog-landing';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:3001';
const LAUNCH_GATE_ON = (env.SEO_LAUNCH_GATE ?? 'true') !== 'false';

export const load: PageServerLoad = async ({ params, url, setHeaders }) => {
  setHeaders({
    // Aligned with [niche] and [niche]/[sub] catalog routes (s-maxage=900) so a
    // user can't see a stale category page next to a fresh idea detail page (or
    // vice versa) for the same job. stale-while-revalidate keeps perceived
    // latency low while the cache refreshes in the background.
    'Cache-Control': 'public, max-age=300, s-maxage=900, stale-while-revalidate=86400',
  });

  let res: Response;
  try {
    res = await fetch(
      `${BACKEND_URL}/api/public/catalog/idea-by-slug/${encodeURIComponent(params.slug)}`,
      { headers: { 'X-Internal-Service': env.INTERNAL_SERVICE_SECRET || '' } },
    );
  } catch (err) {
    console.error('idea fetch failed', err);
    throw error(500, 'Failed to load');
  }

  if (res.status === 404) throw error(404, 'Not found');
  if (!res.ok) throw error(500, 'Failed to load');

  const idea = (await res.json()) as IdeaDetailResponse;
  const canonical = ideaDetailCanonical(idea.slug, url.searchParams);

  const description =
    (idea.value_proposition ?? idea.description ?? '').slice(0, 200);

  const meta = buildMeta({
    title: `${idea.solution_name} | NicheIQ Ideas`,
    description: description || `Validated startup idea in ${idea.category.name}.`,
    canonical,
    type: 'article',
    noindex: detailNoindex({ searchParams: url.searchParams, launchGateOn: LAUNCH_GATE_ON }),
  });

  const jsonld = buildIdeaDetailJsonLd(idea, canonical);

  return { meta, jsonld, idea };
};
