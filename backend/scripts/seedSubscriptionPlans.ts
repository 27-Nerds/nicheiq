/**
 * Seed the two starter subscription plans:
 *   1. "Catalog Access" — $19/mo (launch sale $9), full catalog access, NO monthly credits.
 *   2. "Pro" — $49/mo, full catalog access + 25 monthly credits (~5 Discovery runs).
 *
 * Idempotent: upsert keyed on a FIXED id with an empty `update`, so re-runs never duplicate
 * and never clobber later admin edits (stripePriceId, coupon, prices, copy).
 *
 * Usage:
 *   cd backend && npm run seed:plans           # local/dev
 *   docker exec -it nicheiq-api npm run seed:plans   # production (see DEPLOYMENT.md)
 *
 * ⚠ The stripePriceId values below are PLACEHOLDERS. Before checkout works you MUST:
 *   - create the recurring Prices in Stripe and put their ids on the plans (admin Plans page);
 *   - for the $9 launch price on "Catalog Access", attach a Stripe COUPON (e.g. $10 off /
 *     ~53% off, repeating) via the plan's stripeCouponId — `promoPriceInCents` is display only.
 */

import { pathToFileURL } from 'node:url';
import { prisma } from '../src/services/db.js';
import type { Prisma } from '@prisma/client';

const PLANS: Prisma.SubscriptionPlanCreateInput[] = [
  {
    id: '5e0d0000-0000-4000-8000-000000000019',
    name: 'Catalog Access',
    description: 'Browse every validated idea and pain point in the catalog.',
    monthlyCredits: 0, // catalog-access-only
    priceInCents: 1900,
    interval: 'month',
    stripePriceId: 'price_seed_catalog_access', // PLACEHOLDER — replace with the real Stripe Price
    isActive: true,
    isPopular: false,
    sortOrder: 0,
    // Heading must differ from the 0-credit chip (which renders "Full catalog access").
    tagline: 'The complete idea catalog',
    // creditsInfo is a SECONDARY qualifier after the credits line; omitted here because the
    // 0-credit card already renders "Full catalog access" (don't duplicate it).
    promoPriceInCents: 900, // launch-sale DISPLAY price; real $9 charge needs a Stripe coupon
    promoBadge: 'Launch sale',
    promoLine: 'Intro price — limited time',
    ctaText: 'Get catalog access',
    features: [
      { text: 'Unlock every validated idea & pain point', icon: 'check' },
      { text: 'Demand scores, audience & competitive insights', icon: 'check' },
      { text: 'Save unlimited ideas', icon: 'check' },
    ],
  },
  {
    id: '5e0d0000-0000-4000-8000-000000000049',
    name: 'Pro',
    description: 'Full catalog access plus 25 monthly credits — about 5 Discovery runs each month.',
    monthlyCredits: 25, // ~5 Discovery runs (5 credits each); Deep Research costs extra
    priceInCents: 4900,
    interval: 'month',
    stripePriceId: 'price_seed_pro', // PLACEHOLDER — replace with the real Stripe Price
    isActive: true,
    isPopular: true,
    sortOrder: 1,
    tagline: 'Catalog access + monthly research',
    // Qualifier only — the card already shows "25 credits/mo"; this appends "· ~5 Discovery runs".
    creditsInfo: '~5 Discovery runs',
    badgeLabel: 'Most popular',
    ctaText: 'Start researching',
    features: [
      { text: 'Everything in Catalog Access', icon: 'check' },
      { text: '25 research credits every month (~5 Discovery runs)', icon: 'star', highlight: true },
      { text: 'Run custom research on your own niches', icon: 'check' },
      { text: 'Monthly credits reset each billing cycle', icon: 'check' },
    ],
  },
];

async function main(): Promise<void> {
  for (const plan of PLANS) {
    // Create-if-missing keyed on the fixed id: never duplicate, never overwrite admin edits.
    const existing = await prisma.subscriptionPlan.findUnique({
      where: { id: plan.id as string },
      select: { id: true },
    });
    if (existing) {
      console.log(`[seedSubscriptionPlans] exists (unchanged): ${plan.name}`);
      continue;
    }
    const res = await prisma.subscriptionPlan.create({ data: plan });
    console.log(`[seedSubscriptionPlans] created: ${res.name} ($${res.priceInCents / 100}/mo, monthlyCredits=${res.monthlyCredits}, stripePriceId=${res.stripePriceId})`);
  }
  console.log('[seedSubscriptionPlans] Done. ⚠ Replace placeholder stripePriceId values with real Stripe Prices (admin Plans page), and attach a Stripe coupon for the $9 launch price.');
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main()
    .catch((err) => {
      console.error('[seedSubscriptionPlans] Error:', err);
      process.exit(1);
    })
    .finally(() => prisma.$disconnect());
}
