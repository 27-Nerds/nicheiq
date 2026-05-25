import { redirect } from '@sveltejs/kit';
import type { LayoutServerLoad } from './$types';
import { fetchBackend } from '$lib/backend';
import { DEFAULT_STAGE_COSTS } from '$lib/types/job';
import type { StageCosts } from '$lib/types/job';
import type { SavedCounts } from '$lib/types/saved';
import type { UserSubscription } from '$lib/types/billing';

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
  let monthlyAllowance = 0;
  let purchasedBalance = 0;
  let monthlyAllowancePeriodEnd: string | null = null;
  let subscription: UserSubscription | null = null;
  let stageCosts: StageCosts = { ...DEFAULT_STAGE_COSTS };
  let savedCounts: SavedCounts = { ideas: 0, painPoints: 0 };

  const headers = { 'X-User-ID': session.user.id };

  try {
    const [balanceRes, costsRes, savedRes, subRes] = await Promise.all([
      fetchBackend('/api/billing/balance', { headers }),
      fetchBackend('/api/billing/stage-costs', { headers }),
      fetchBackend('/api/saves/counts', { headers }),
      fetchBackend('/api/billing/subscription', { headers }).catch(() => null),
    ]);

    if (balanceRes.ok) {
      const data = await balanceRes.json();
      // `balance` stays = available for back-compat.
      creditBalance = data.available ?? data.balance ?? 0;
      monthlyAllowance = data.monthlyAllowance ?? 0;
      purchasedBalance = data.purchasedBalance ?? data.balance ?? 0;
      monthlyAllowancePeriodEnd = data.monthlyAllowancePeriodEnd ?? null;
    }
    if (costsRes.ok) {
      const data = await costsRes.json();
      stageCosts = { ...stageCosts, ...data };
    }
    if (savedRes.ok) {
      savedCounts = (await savedRes.json()) as SavedCounts;
    }
    if (subRes?.ok) {
      const data = await subRes.json();
      subscription = data.subscription ?? null;
    }
  } catch (error) {
    console.error('Failed to fetch layout data:', error);
  }

  return {
    session,
    creditBalance,
    monthlyAllowance,
    purchasedBalance,
    monthlyAllowancePeriodEnd,
    subscription,
    stageCosts,
    savedCounts,
  };
};
