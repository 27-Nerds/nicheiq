import type { PageServerLoad } from './$types';
import { env } from '$env/dynamic/private';
import type {
  SavedIdeaItem,
  SavedPainPointItem,
  SavedListResponse,
  SavedCounts,
} from '$lib/types/saved';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:3001';

export const load: PageServerLoad = async ({ url, parent, setHeaders }) => {
  // Saved data is per-user — never CDN-cacheable.
  setHeaders({ 'Cache-Control': 'private, no-store' });

  const { session } = await parent();
  const userId = session?.user?.id;
  if (!userId) {
    // The (app) layout guard already redirects to /login, but defensive check
    // here avoids a runtime crash if someone wires this up under a non-guarded
    // surface in the future.
    return {
      ideas: [] as SavedIdeaItem[],
      painPoints: [] as SavedPainPointItem[],
      counts: { ideas: 0, painPoints: 0 } as SavedCounts,
      ideasNextCursor: null as string | null,
      painPointsNextCursor: null as string | null,
      filters: { hasNotes: false },
    };
  }

  const headers = {
    'X-Internal-Service': env.INTERNAL_SERVICE_SECRET || '',
    'X-User-ID': userId,
  };

  const hasNotes = url.searchParams.get('hasNotes') === '1';
  const ideasQs = new URLSearchParams({ limit: '50' });
  const painsQs = new URLSearchParams({ limit: '50' });
  if (hasNotes) {
    ideasQs.set('hasNotes', 'true');
    painsQs.set('hasNotes', 'true');
  }

  async function fetchJson<T>(path: string, fallback: T): Promise<T> {
    try {
      const res = await fetch(`${BACKEND_URL}${path}`, { headers });
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
    ideas: ideas.items,
    painPoints: painPoints.items,
    counts,
    ideasNextCursor: ideas.nextCursor,
    painPointsNextCursor: painPoints.nextCursor,
    filters: { hasNotes },
  };
};
