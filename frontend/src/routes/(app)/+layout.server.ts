import { redirect } from '@sveltejs/kit';
import type { LayoutServerLoad } from './$types';
import { fetchBackend } from '$lib/backend';
import { DEFAULT_STAGE_COSTS } from '$lib/types/job';
import type { StageCosts } from '$lib/types/job';
import type { SavedCounts } from '$lib/types/saved';
import type { UserSubscription } from '$lib/types/billing';
import type { FeatureAccess } from '$lib/types/featureAccess';
import { nonNegativeInteger } from '$lib/utils/displayGuards';

export const load: LayoutServerLoad = async (event) => {
  const session = await event.locals.auth?.();

  if (!session?.user) {
    // Store intended destination for post-login redirect (query included so
    // intent params like /billing?plan=<id> survive the login bounce).
    const returnTo = encodeURIComponent(event.url.pathname + event.url.search);
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
  let balanceUnavailable = true;
  let costsUnavailable = true;
  let discoveryCostUnavailable = true;
  let guidedCostsUnavailable = true;
  // Admin-granted per-user features. Read fresh each navigation rather than carried in
  // the session JWT, so a grant or revocation lands without a re-login. Fails CLOSED:
  // the backend re-checks on every gated route, this only drives what we render.
  let featureAccess: FeatureAccess = { analyst: false, decisionTools: false };
  // Same distinction the billing flags make: a request that never answered is not
  // a revoked grant. Consumers that would otherwise tell a paying subscriber to
  // subscribe on a network blip check this before claiming anything.
  let featureAccessUnavailable = true;

  const headers = { 'X-User-ID': session.user.id };

  try {
    const [balanceRes, costsRes, savedRes, subRes, accessRes] = await Promise.all([
      fetchBackend('/api/billing/balance', { headers }).catch(() => null),
      fetchBackend('/api/billing/stage-costs', { headers }).catch(() => null),
      fetchBackend('/api/saves/counts', { headers }).catch(() => null),
      fetchBackend('/api/billing/subscription', { headers }).catch(() => null),
      fetchBackend(`/api/users/${session.user.id}/feature-access`, { headers }).catch(() => null),
    ]);

    if (balanceRes?.ok) {
      const data = await balanceRes.json();
      const available = nonNegativeInteger(data.available ?? data.balance);
      // `balance` stays = available for back-compat.
      if (available !== null) {
        creditBalance = available;
        balanceUnavailable = false;
      }
      monthlyAllowance = data.monthlyAllowance ?? 0;
      purchasedBalance = data.purchasedBalance ?? data.balance ?? 0;
      monthlyAllowancePeriodEnd = data.monthlyAllowancePeriodEnd ?? null;
    }
    if (costsRes?.ok) {
      const data = await costsRes.json();
      stageCosts = { ...stageCosts, ...data };
      costsUnavailable = nonNegativeInteger(data.deep_research) === null;
      discoveryCostUnavailable = nonNegativeInteger(data.discovery) === null;
      guidedCostsUnavailable = nonNegativeInteger(data.guided?.s1) === null;
    }
    if (savedRes?.ok) {
      savedCounts = (await savedRes.json()) as SavedCounts;
    }
    if (subRes?.ok) {
      const data = await subRes.json();
      subscription = data.subscription ?? null;
    }
    if (accessRes?.ok) {
      const data = await accessRes.json();
      featureAccess = {
        analyst: data.analyst === true,
        decisionTools: data.decisionTools === true,
      };
      featureAccessUnavailable = false;
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
    featureAccess,
    featureAccessUnavailable,
    stageCosts,
    billingLoadState: {
      balanceUnavailable,
      costsUnavailable,
      discoveryCostUnavailable,
      guidedCostsUnavailable,
    },
    savedCounts,
  };
};
