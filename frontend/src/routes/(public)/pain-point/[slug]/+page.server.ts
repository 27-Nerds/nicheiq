import type { PageServerLoad } from './$types';
import { error, redirect } from '@sveltejs/kit';
import { fetchBackend } from '$lib/backend';
import {
  buildPainPointDetailJsonLd,
  painPointDetailCanonical,
} from '$lib/seo/catalogSeo';
import { buildMeta } from '$lib/seo/meta';
import type { PainPointDetailResponse } from '$lib/types/catalog-landing';

export const load: PageServerLoad = async ({ params, url, setHeaders, locals }) => {
  // Login gate: pain-point detail pages are available only to authenticated users.
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
      `/api/public/catalog/pain-point-by-slug/${encodeURIComponent(params.slug)}`,
      // Forward role so the backend can apply the entitlement gate.
      { headers: { 'X-User-ID': session.user.id, 'X-User-Role': session.user.role ?? 'USER' } },
    );
  } catch (err) {
    console.error('pain-point fetch failed', err);
    throw error(500, 'Failed to load');
  }

  // 403 = a non-featured pain the user isn't entitled to → send them to subscribe.
  if (res.status === 403) throw redirect(302, '/unlock-catalog');
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
    noindex: true,
  });

  const jsonld = buildPainPointDetailJsonLd(pp, canonical);

  return { meta, jsonld, painPoint: pp };
};
