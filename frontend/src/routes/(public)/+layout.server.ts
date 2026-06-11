import type { LayoutServerLoad } from './$types';
import { fetchBackend } from '$lib/backend';
import { isCatalogPath } from '$lib/utils/urls';
import type { CtaConfig } from '$lib/types/cta';
import { DEFAULT_STAGE_COSTS } from '$lib/types/job';
import type { StageCosts } from '$lib/types/job';
import type { UserSubscription } from '$lib/types/billing';

export const load: LayoutServerLoad = async (event) => {
  let ctaTexts: Record<string, CtaConfig | null> = {};
  try {
    const res = await fetchBackend('/api/settings/cta-texts');
    const data = res.ok ? await res.json() : { ctas: {} };
    ctaTexts = data.ctas ?? {};
  } catch (error) {
    console.error('Failed to fetch CTA texts:', error);
  }

  // Logged-in users browsing the catalog see the dashboard chrome (AppHeader),
  // which needs the same credit fields the (app) layout loads. Scope the extra
  // backend call to catalog routes so landing/login/register stay lean and
  // per-user-invariant.
  //
  // CACHE INVARIANT: any (public) route matching isCatalogPath() that surfaces
  // these per-user fields MUST set `private, no-store` for authenticated users
  // (see (public)/ideas/+page.server.ts) — otherwise a shared/CDN cache could
  // replay one user's balance to anonymous visitors.
  let creditBalance = 0;
  let monthlyAllowance = 0;
  let purchasedBalance = 0;
  let monthlyAllowancePeriodEnd: string | null = null;
  let subscription: UserSubscription | null = null;
  // Stage costs power the research confirmation modal on catalog detail pages
  // ("this costs N credits") + CreditTopUpModal. Default until the per-user fetch lands.
  let stageCosts: StageCosts = { ...DEFAULT_STAGE_COSTS };

  const session = await event.locals.auth?.();
  if (session?.user?.id && isCatalogPath(event.url.pathname)) {
    const headers = { 'X-User-ID': session.user.id };
    try {
      const [balanceRes, costsRes, subRes] = await Promise.all([
        fetchBackend('/api/billing/balance', { headers }),
        fetchBackend('/api/billing/stage-costs', { headers }),
        fetchBackend('/api/billing/subscription', { headers }).catch(() => null),
      ]);
      if (balanceRes.ok) {
        const data = await balanceRes.json();
        creditBalance = data.available ?? data.balance ?? 0;
        monthlyAllowance = data.monthlyAllowance ?? 0;
        purchasedBalance = data.purchasedBalance ?? data.balance ?? 0;
        monthlyAllowancePeriodEnd = data.monthlyAllowancePeriodEnd ?? null;
      }
      if (costsRes.ok) {
        stageCosts = { ...stageCosts, ...(await costsRes.json()) };
      }
      if (subRes?.ok) {
        subscription = (await subRes.json()).subscription ?? null;
      }
    } catch (error) {
      console.error('Failed to fetch catalog header credit data:', error);
    }
  }

  return {
    ctaTexts,
    creditBalance,
    monthlyAllowance,
    purchasedBalance,
    monthlyAllowancePeriodEnd,
    subscription,
    stageCosts,
  };
};
