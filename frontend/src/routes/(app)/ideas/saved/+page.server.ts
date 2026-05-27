import type { PageServerLoad } from './$types';
import { fetchBackend } from '$lib/backend';
import { siteOrigin, canonicalUrl } from '$lib/seo/canonical';
import { buildMeta } from '$lib/seo/meta';
import { breadcrumbList, collectionPage } from '$lib/seo/jsonld';
import type {
  SavedIdeaItem,
  SavedPainPointItem,
  SavedListResponse,
  SavedCounts,
} from '$lib/types/saved';

export const load: PageServerLoad = async ({ url, parent, setHeaders }) => {
  // Saved data is per-user — never CDN-cacheable.
  setHeaders({ 'Cache-Control': 'private, no-store' });

  // Page-level SEO. This surface is per-user and noindexed, so the metadata
  // exists for clean link unfurls + a consistent breadcrumb entity chain —
  // not for ranking. None of it depends on the session, so compute it once
  // up front and return it from both branches. Canonical drops the
  // ?hasNotes filter so the filtered view points back to the base docket.
  const origin = siteOrigin();
  const canonical = canonicalUrl('/ideas/saved');
  const description =
    "Ideas and pain points you've kept for later validation — your research docket.";
  const meta = buildMeta({
    title: 'Saved · NicheIQ',
    description,
    canonical,
    type: 'website',
    noindex: true,
  });
  const jsonld = [
    breadcrumbList([
      { name: 'Home', url: `${origin}/` },
      { name: 'Catalog', url: `${origin}/ideas` },
      { name: 'Saved', url: canonical },
    ]),
    collectionPage({ name: 'Your research docket', description, url: canonical }),
  ];

  const { session } = await parent();
  const userId = session?.user?.id;
  if (!userId) {
    // The (app) layout guard already redirects to /login, but defensive check
    // here avoids a runtime crash if someone wires this up under a non-guarded
    // surface in the future.
    return {
      meta,
      jsonld,
      ideas: [] as SavedIdeaItem[],
      painPoints: [] as SavedPainPointItem[],
      counts: { ideas: 0, painPoints: 0 } as SavedCounts,
      ideasNextCursor: null as string | null,
      painPointsNextCursor: null as string | null,
      filters: { hasNotes: false },
    };
  }

  const headers = { 'X-User-ID': userId };

  const hasNotes = url.searchParams.get('hasNotes') === '1';
  const ideasQs = new URLSearchParams({ limit: '50' });
  const painsQs = new URLSearchParams({ limit: '50' });
  if (hasNotes) {
    ideasQs.set('hasNotes', 'true');
    painsQs.set('hasNotes', 'true');
  }

  async function fetchJson<T>(path: string, fallback: T): Promise<T> {
    try {
      const res = await fetchBackend(path, { headers });
      if (res.ok) return (await res.json()) as T;
    } catch (err) {
      console.error(`saves fetch failed: ${path}`, err);
    }
    return fallback;
  }

  const [ideas, painPoints, counts] = await Promise.all([
    fetchJson<SavedListResponse<SavedIdeaItem>>(
      `/api/saves/ideas?${ideasQs.toString()}`,
      { items: [], nextCursor: null },
    ),
    fetchJson<SavedListResponse<SavedPainPointItem>>(
      `/api/saves/pain-points?${painsQs.toString()}`,
      { items: [], nextCursor: null },
    ),
    fetchJson<SavedCounts>('/api/saves/counts', { ideas: 0, painPoints: 0 }),
  ]);

  return {
    meta,
    jsonld,
    ideas: ideas.items,
    painPoints: painPoints.items,
    counts,
    ideasNextCursor: ideas.nextCursor,
    painPointsNextCursor: painPoints.nextCursor,
    filters: { hasNotes },
  };
};
