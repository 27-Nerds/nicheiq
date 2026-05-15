import type { PageServerLoad } from './$types';
import { error } from '@sveltejs/kit';
import { fetchBackend } from '$lib/backend';
import {
  buildIdeaDetailJsonLd,
  detailNoindex,
  ideaDetailCanonical,
} from '$lib/seo/catalogSeo';
import { buildMeta } from '$lib/seo/meta';
import { LAUNCH_GATE_ON } from '$lib/seo/launchGate';
import type { IdeaDetailResponse } from '$lib/types/catalog-landing';

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
    res = await fetchBackend(
      `/api/public/catalog/idea-by-slug/${encodeURIComponent(params.slug)}`,
    );
  } catch (err) {
    console.error('idea fetch failed', err);
    throw error(500, 'Failed to load');
  }

  if (res.status === 404) throw error(404, 'Not found');
  if (!res.ok) throw error(500, 'Failed to load');

  const idea = (await res.json()) as IdeaDetailResponse;
  // Rollout safety: cached responses from before `addressedPainTitles` shipped
  // (s-maxage=900) may not carry the field. Default to [] so the page renders
  // with the section gated off rather than throwing on undefined access.
  // Removable once both backend + frontend have been deployed and the cache
  // window has rolled.
  if (!Array.isArray((idea as { addressedPainTitles?: unknown }).addressedPainTitles)) {
    (idea as { addressedPainTitles: string[] }).addressedPainTitles = [];
  }
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
