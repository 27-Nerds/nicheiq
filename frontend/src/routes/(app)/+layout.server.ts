import { redirect } from '@sveltejs/kit';
import type { LayoutServerLoad } from './$types';
import { env } from '$env/dynamic/private';
import { DEFAULT_STAGE_COSTS } from '$lib/types/job';
import type { StageCosts } from '$lib/types/job';
import type { SavedCounts } from '$lib/types/saved';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:3001';

export const load: LayoutServerLoad = async (event) => {
  const session = await event.locals.auth?.();

  if (!session?.user) {
    // Store intended destination for post-login redirect
    const returnTo = encodeURIComponent(event.url.pathname);
    throw redirect(302, `/login?returnTo=${returnTo}`);
  }

  // NOTE: Cache-Control is set elsewhere in the SvelteKit/Auth.js pipeline
  // for authenticated routes; setting it here would throw "header already
  // set". Each (app) page that needs an explicit no-store policy sets it
  // in its own +page.server.ts (e.g. /saved).

  // Fetch user's credit balance and stage costs for header display
  let creditBalance = 0;
  let stageCosts: StageCosts = { ...DEFAULT_STAGE_COSTS };
  let savedCounts: SavedCounts = { ideas: 0, painPoints: 0 };

  const headers = {
    'X-Internal-Service': env.INTERNAL_SERVICE_SECRET || '',
    'X-User-ID': session.user.id,
  };

  try {
    const [balanceRes, costsRes, savedRes] = await Promise.all([
      fetch(`${BACKEND_URL}/api/billing/balance`, { headers }),
      fetch(`${BACKEND_URL}/api/billing/stage-costs`, { headers }),
      fetch(`${BACKEND_URL}/api/saves/counts`, { headers }),
    ]);

    if (balanceRes.ok) {
      const data = await balanceRes.json();
      creditBalance = data.balance ?? 0;
    }
    if (costsRes.ok) {
      const data = await costsRes.json();
      stageCosts = { ...stageCosts, ...data };
    }
    if (savedRes.ok) {
      savedCounts = (await savedRes.json()) as SavedCounts;
    }
  } catch (error) {
    console.error('Failed to fetch layout data:', error);
  }

  return { session, creditBalance, stageCosts, savedCounts };
};
