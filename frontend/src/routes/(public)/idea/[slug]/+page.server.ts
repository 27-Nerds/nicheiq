import type { PageServerLoad } from './$types';
import { error, redirect } from '@sveltejs/kit';
import { fetchBackend } from '$lib/backend';
import {
  buildIdeaDetailJsonLd,
  ideaDetailCanonical,
} from '$lib/seo/catalogSeo';
import { buildMeta } from '$lib/seo/meta';
import type { IdeaDetailResponse } from '$lib/types/catalog-landing';

export const load: PageServerLoad = async ({ params, url, setHeaders, locals }) => {
  // Login gate: idea detail pages are available only to authenticated users.
  // Runs before setHeaders so the 302 doesn't carry a cache header.
  const session = await locals.auth?.();
  if (!session?.user) {
    throw redirect(302, `/login?returnTo=${encodeURIComponent(url.pathname)}`);
  }

  // Auth-gated content must not be stored by a shared/CDN cache.
  setHeaders({ 'Cache-Control': 'private, no-store' });

  let res: Response;
  try {
    res = await fetchBackend(
      `/api/public/catalog/idea-by-slug/${encodeURIComponent(params.slug)}`,
      // Forward the role so the backend can apply the entitlement gate (ADMIN /
      // fullCatalogAccess → full catalog; otherwise only the featured item).
      { headers: { 'X-User-ID': session.user.id, 'X-User-Role': session.user.role ?? 'USER' } },
    );
  } catch (err) {
    console.error('idea fetch failed', err);
    throw error(500, 'Failed to load');
  }

  // 403 = a non-featured idea the user isn't entitled to → send them to subscribe.
  if (res.status === 403) throw redirect(302, '/unlock-catalog');
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
    noindex: true,
  });

  const jsonld = buildIdeaDetailJsonLd(idea, canonical);

  return { meta, jsonld, idea };
};
