import type Stripe from 'stripe';
import { Prisma, SubscriptionStatus } from '@prisma/client';
import { prisma } from './db.js';
import { CONFIG } from '../config.js';
import { getStripe } from './stripeClient.js';
import { resetMonthlyAllowance } from './creditService.js';

// ============================================
// Errors (mapped to HTTP status by the billing route)
// ============================================
export class ActiveSubscriptionError extends Error {
  constructor() {
    super('User already has a live subscription — manage via the customer portal');
    this.name = 'ActiveSubscriptionError';
  }
}
export class NoStripeCustomerError extends Error {
  constructor() {
    super('User has no Stripe customer');
    this.name = 'NoStripeCustomerError';
  }
}

// Live statuses block a NEW checkout (the portal is the switch path). Only no row or a
// terminal status (CANCELED / INCOMPLETE_EXPIRED) may start a fresh subscription.
const LIVE_STATUSES: SubscriptionStatus[] = [
  SubscriptionStatus.ACTIVE,
  SubscriptionStatus.TRIALING,
  SubscriptionStatus.PAST_DUE,
  SubscriptionStatus.INCOMPLETE,
  SubscriptionStatus.UNPAID,
  SubscriptionStatus.PAUSED,
];

// ============================================
// Plan reads
// ============================================
export async function getActivePlans() {
  return prisma.subscriptionPlan.findMany({
    where: { isActive: true },
    orderBy: { sortOrder: 'asc' },
  });
}

export async function getPlanById(planId: string) {
  return prisma.subscriptionPlan.findUnique({ where: { id: planId } });
}

// ============================================
// Stripe field helpers (Clover API — periods on items, sub ref under invoice.parent)
// ============================================
function mapStatus(s: Stripe.Subscription.Status): SubscriptionStatus {
  switch (s) {
    case 'active': return SubscriptionStatus.ACTIVE;
    case 'trialing': return SubscriptionStatus.TRIALING;
    case 'past_due': return SubscriptionStatus.PAST_DUE;
    case 'canceled': return SubscriptionStatus.CANCELED;
    case 'incomplete': return SubscriptionStatus.INCOMPLETE;
    case 'incomplete_expired': return SubscriptionStatus.INCOMPLETE_EXPIRED;
    case 'unpaid': return SubscriptionStatus.UNPAID;
    case 'paused': return SubscriptionStatus.PAUSED;
    default: return SubscriptionStatus.INCOMPLETE;
  }
}

const asId = (v: string | { id: string } | null | undefined): string | null =>
  typeof v === 'string' ? v : v?.id ?? null;

const toDate = (unixSeconds: number | null | undefined): Date | null =>
  unixSeconds == null ? null : new Date(unixSeconds * 1000);

function subPeriod(sub: Stripe.Subscription): { start: Date | null; end: Date | null } {
  const item = sub.items?.data?.[0] as unknown as
    | { current_period_start?: number; current_period_end?: number }
    | undefined;
  return { start: toDate(item?.current_period_start), end: toDate(item?.current_period_end) };
}

// ============================================
// Customer + checkout + portal
// ============================================
export async function getOrCreateStripeCustomer(userId: string, email: string): Promise<string> {
  const existing = await prisma.user.findUnique({ where: { id: userId }, select: { stripeCustomerId: true } });
  if (existing?.stripeCustomerId) return existing.stripeCustomerId;

  const customer = await getStripe().customers.create(
    { email, metadata: { userId } },
    { idempotencyKey: `cust_${userId}` },
  );
  try {
    await prisma.user.update({ where: { id: userId }, data: { stripeCustomerId: customer.id } });
    return customer.id;
  } catch (error) {
    // Lost a race — re-read the winner.
    if (error instanceof Prisma.PrismaClientKnownRequestError && error.code === 'P2002') {
      const reread = await prisma.user.findUnique({ where: { id: userId }, select: { stripeCustomerId: true } });
      if (reread?.stripeCustomerId) return reread.stripeCustomerId;
    }
    throw error;
  }
}

export async function createSubscriptionCheckoutSession(
  userId: string,
  email: string,
  planId: string,
): Promise<{ url: string }> {
  // Guard: block a new checkout while any LIVE subscription exists (portal is the switch path).
  const current = await prisma.userSubscription.findUnique({ where: { userId }, select: { status: true } });
  if (current && LIVE_STATUSES.includes(current.status)) {
    throw new ActiveSubscriptionError();
  }

  const plan = await getPlanById(planId);
  if (!plan || !plan.isActive) throw new Error('Plan not found or inactive');

  const customerId = await getOrCreateStripeCustomer(userId, email);

  const session = await getStripe().checkout.sessions.create({
    mode: 'subscription',
    customer: customerId,
    line_items: [{ price: plan.stripePriceId, quantity: 1 }],
    subscription_data: {
      metadata: { userId, planId },
      ...(plan.trialDays ? { trial_period_days: plan.trialDays } : {}),
    },
    client_reference_id: userId,
    metadata: { userId, planId, kind: 'subscription' },
    // Auto-apply the admin-attached coupon if present. `discounts` and `allow_promotion_codes`
    // are mutually exclusive — when there's no coupon we set NEITHER (no user-entered codes).
    ...(plan.stripeCouponId ? { discounts: [{ coupon: plan.stripeCouponId }] } : {}),
    success_url: `${CONFIG.baseUrl}/billing?sub_success=true&session_id={CHECKOUT_SESSION_ID}`,
    cancel_url: `${CONFIG.baseUrl}/billing?sub_canceled=true`,
  });

  if (!session.url) throw new Error('Failed to create subscription checkout session');
  return { url: session.url };
}

// Versioned so a future change to the portal features can be rolled out by bumping the suffix
// (a one-time unversioned cache would never pick up config changes).
const PORTAL_CONFIG_KEY = 'stripe_portal_config_id_v1';

/**
 * Lazily create + cache a Stripe billing portal Configuration that enables cancellation at the
 * END of the billing period with NO proration (active till cycle end → stop charging → revoked by
 * the customer.subscription.deleted webhook). Cached in AppSettings (direct prisma — NOT the
 * adminService settings helpers, which whitelist keys). Returns the configuration id, or null if
 * Stripe rejects creation (e.g. the account has no public business profile) so the caller can fall
 * back to the account-default portal config.
 */
async function ensurePortalConfigurationId(): Promise<string | null> {
  const cached = await prisma.appSettings.findUnique({ where: { key: PORTAL_CONFIG_KEY } });
  if (cached?.value) return cached.value;

  try {
    const cfg = await getStripe().billingPortal.configurations.create({
      business_profile: { privacy_policy_url: `${CONFIG.baseUrl}/privacy` },
      features: {
        subscription_cancel: { enabled: true, mode: 'at_period_end', proration_behavior: 'none' },
        payment_method_update: { enabled: true },
        invoice_history: { enabled: true },
      },
    });
    // Race: two first-time opens may each create a config; last writer wins and only the cached id
    // is ever used, so a duplicate Stripe config is harmless/orphaned.
    await prisma.appSettings.upsert({
      where: { key: PORTAL_CONFIG_KEY },
      create: { key: PORTAL_CONFIG_KEY, value: cfg.id },
      update: { value: cfg.id },
    });
    return cfg.id;
  } catch (err) {
    console.error(
      '[subscription] could not create billing portal configuration — falling back to the account-default portal config. Enable "cancel at end of billing period (no proration)" in the Stripe Dashboard portal settings.',
      err,
    );
    return null;
  }
}

export async function createBillingPortalSession(userId: string): Promise<{ url: string }> {
  const user = await prisma.user.findUnique({ where: { id: userId }, select: { stripeCustomerId: true } });
  if (!user?.stripeCustomerId) throw new NoStripeCustomerError(); // never create a customer here

  const configuration = await ensurePortalConfigurationId();
  try {
    const session = await getStripe().billingPortal.sessions.create({
      customer: user.stripeCustomerId,
      return_url: `${CONFIG.baseUrl}/billing`,
      ...(configuration ? { configuration } : {}),
    });
    return { url: session.url };
  } catch (err) {
    // A stale/deleted/wrong-environment cached configuration id would fail here — clear it and
    // retry with the account default so portal access self-heals and is never worse than before.
    if (configuration) {
      console.error('[subscription] portal session failed with cached configuration — clearing it and retrying with the account default.', err);
      await prisma.appSettings.deleteMany({ where: { key: PORTAL_CONFIG_KEY } });
      const session = await getStripe().billingPortal.sessions.create({
        customer: user.stripeCustomerId,
        return_url: `${CONFIG.baseUrl}/billing`,
      });
      return { url: session.url };
    }
    throw err;
  }
}

export async function getUserSubscription(userId: string) {
  return prisma.userSubscription.findUnique({
    where: { userId },
    include: { plan: { select: { name: true, monthlyCredits: true, priceInCents: true, interval: true } } },
  });
}

// ============================================
// Webhook handlers
// ============================================

/** Resolve the userId for a subscription: metadata first, else by stored customer id. */
async function resolveUserId(sub: Stripe.Subscription): Promise<string | null> {
  if (sub.metadata?.userId) return sub.metadata.userId;
  const customerId = asId(sub.customer);
  if (!customerId) return null;
  const u = await prisma.user.findFirst({ where: { stripeCustomerId: customerId }, select: { id: true } });
  return u?.id ?? null;
}

/** Resolve planId from sub metadata, else from the price id. */
async function resolvePlanId(sub: Stripe.Subscription): Promise<string | null> {
  if (sub.metadata?.planId) return sub.metadata.planId;
  const priceId = sub.items?.data?.[0]?.price?.id;
  if (!priceId) return null;
  const plan = await prisma.subscriptionPlan.findUnique({ where: { stripePriceId: priceId }, select: { id: true } });
  return plan?.id ?? null;
}

const isActiveSub = (s: SubscriptionStatus, end: Date | null) =>
  (s === SubscriptionStatus.ACTIVE || s === SubscriptionStatus.TRIALING) && end != null && end.getTime() > Date.now();

/** Create/update the per-user subscription row from a Stripe Subscription object. */
export async function upsertSubscriptionFromStripe(sub: Stripe.Subscription): Promise<void> {
  const userId = await resolveUserId(sub);
  if (!userId) {
    console.error('[subscription] could not resolve userId for', sub.id);
    return;
  }
  const planId = await resolvePlanId(sub);
  const status = mapStatus(sub.status);
  const { start, end } = subPeriod(sub);
  const stripeCreatedAt = toDate(sub.created);
  const customerId = asId(sub.customer);

  // Staleness guard: don't let a late event for an OLDER subscription clobber a newer row.
  const existing = await prisma.userSubscription.findUnique({ where: { userId } });
  if (
    existing &&
    existing.stripeSubscriptionId !== sub.id &&
    existing.stripeCreatedAt != null &&
    stripeCreatedAt != null &&
    stripeCreatedAt.getTime() < existing.stripeCreatedAt.getTime()
  ) {
    console.log('[subscription] ignoring stale event for older sub', sub.id);
    return;
  }

  const data = {
    planId,
    stripeSubscriptionId: sub.id,
    stripeCustomerId: customerId ?? existing?.stripeCustomerId ?? '',
    stripePriceId: sub.items?.data?.[0]?.price?.id ?? null,
    status,
    currentPeriodStart: start,
    currentPeriodEnd: end,
    cancelAtPeriodEnd: sub.cancel_at_period_end ?? false,
    canceledAt: toDate(sub.canceled_at),
    stripeCreatedAt,
  };

  await prisma.$transaction([
    prisma.userSubscription.upsert({ where: { userId }, create: { userId, ...data }, update: data }),
    prisma.user.update({ where: { id: userId }, data: { hasActiveSubscription: isActiveSub(status, end) } }),
  ]);
  // No credit grant here — credits are granted on invoice.paid (avoids double-grant on upgrade).
}

/** Checkout completed for a subscription — link customer + delegate to the upsert. */
export async function handleSubscriptionCheckoutCompleted(session: Stripe.Checkout.Session): Promise<void> {
  const userId = session.metadata?.userId ?? asId(session.client_reference_id as string | null);
  const customerId = asId(session.customer);
  if (userId && customerId) {
    await prisma.user.updateMany({ where: { id: userId, stripeCustomerId: null }, data: { stripeCustomerId: customerId } });
  }
  const subId = asId(session.subscription);
  if (!subId) return;
  const sub = await getStripe().subscriptions.retrieve(subId);
  await upsertSubscriptionFromStripe(sub);
}

/** invoice.paid — the monthly-credit reset trigger. Only subscription create/cycle invoices,
 *  and never while trialing (a $0 trial-start invoice must not grant). */
export async function handleInvoicePaid(invoice: Stripe.Invoice): Promise<void> {
  const reason = invoice.billing_reason;
  if (reason !== 'subscription_create' && reason !== 'subscription_cycle') return;

  const parent = (invoice as unknown as { parent?: { subscription_details?: { subscription?: string | { id: string } } } }).parent;
  const subId = asId(parent?.subscription_details?.subscription);
  if (!subId) return;

  const sub = await getStripe().subscriptions.retrieve(subId);
  if (sub.status === 'trialing') return; // credits start on first NON-trial paid invoice

  const userId = await resolveUserId(sub);
  const planId = await resolvePlanId(sub);
  if (!userId) return;

  // Force entitlement (an invoice payment is a strong activation signal that may beat sub.updated).
  const { start, end } = subPeriod(sub);
  await prisma.$transaction([
    prisma.userSubscription.updateMany({
      where: { userId },
      data: { status: SubscriptionStatus.ACTIVE, currentPeriodStart: start, currentPeriodEnd: end },
    }),
    prisma.user.update({ where: { id: userId }, data: { hasActiveSubscription: true } }),
  ]);

  const plan = planId ? await getPlanById(planId) : null;
  const monthlyCredits = plan?.monthlyCredits ?? 0;
  // Period for the reset/idempotency key comes from the invoice LINE (the subscription period).
  const line = invoice.lines?.data?.[0];
  const periodStart = toDate(line?.period?.start) ?? start;
  const periodEnd = toDate(line?.period?.end) ?? end;
  if (monthlyCredits > 0 && periodStart && periodEnd) {
    await resetMonthlyAllowance(userId, monthlyCredits, periodStart, periodEnd, invoice.id ?? null, `Monthly credits: ${plan?.name ?? 'subscription'}`);
  }
}

/** Payment failed / requires action → revoke access + zero the monthly allowance. */
export async function handleInvoicePaymentFailed(invoice: Stripe.Invoice): Promise<void> {
  const parent = (invoice as unknown as { parent?: { subscription_details?: { subscription?: string | { id: string } } } }).parent;
  const subId = asId(parent?.subscription_details?.subscription);
  if (!subId) return;
  const sub = await getStripe().subscriptions.retrieve(subId);
  const userId = await resolveUserId(sub);
  if (!userId) return;
  await revokeAccess(userId, SubscriptionStatus.PAST_DUE);
}

/** Subscription deleted (cancel at period end reached, or immediate cancel). */
export async function handleSubscriptionDeleted(sub: Stripe.Subscription): Promise<void> {
  const userId = await resolveUserId(sub);
  if (!userId) return;
  await prisma.userSubscription.updateMany({
    where: { userId },
    data: { status: SubscriptionStatus.CANCELED, canceledAt: new Date(), cancelAtPeriodEnd: false },
  });
  await revokeAccess(userId, SubscriptionStatus.CANCELED);
}

/** Revoke catalog access + zero the monthly allowance (so no leftover monthly credits are spendable). */
async function revokeAccess(userId: string, status: SubscriptionStatus): Promise<void> {
  await prisma.$transaction([
    prisma.userSubscription.updateMany({ where: { userId }, data: { status } }),
    prisma.user.update({ where: { id: userId }, data: { hasActiveSubscription: false } }),
    prisma.userCredits.updateMany({ where: { userId }, data: { monthlyAllowance: 0 } }),
  ]);
}

// ============================================
// Reconciliation (daily backstop)
// ============================================
/**
 * Reconcile subscriptions whose stored period has passed (regardless of stored status — the
 * dangerous case is status-still-ACTIVE + a missed webhook). Pulls the live sub from Stripe and:
 *  - negative drift (no longer active) → revoke + zero monthly;
 *  - positive drift (renewed, missed invoice.paid) → update period + grant the cycle's allowance.
 */
let reconcileTimer: NodeJS.Timeout | null = null;
const RECONCILE_INTERVAL_MS = 24 * 60 * 60 * 1000; // daily backstop

export function startSubscriptionReconciliation(): void {
  if (reconcileTimer) return;
  reconcileTimer = setInterval(() => {
    reconcileSubscriptions().catch((e) => console.error('[subscription] reconciliation tick failed', e));
  }, RECONCILE_INTERVAL_MS);
  if (typeof reconcileTimer.unref === 'function') reconcileTimer.unref();
}

export function stopSubscriptionReconciliation(): void {
  if (reconcileTimer) {
    clearInterval(reconcileTimer);
    reconcileTimer = null;
  }
}

export async function reconcileSubscriptions(): Promise<{ checked: number; revoked: number; renewed: number }> {
  const stale = await prisma.userSubscription.findMany({
    where: { currentPeriodEnd: { lt: new Date() } },
    select: { userId: true, stripeSubscriptionId: true },
  });
  let revoked = 0;
  let renewed = 0;
  for (const row of stale) {
    try {
      const sub = await getStripe().subscriptions.retrieve(row.stripeSubscriptionId);
      const status = mapStatus(sub.status);
      const { start, end } = subPeriod(sub);
      if (isActiveSub(status, end)) {
        await upsertSubscriptionFromStripe(sub);
        const planId = await resolvePlanId(sub);
        const plan = planId ? await getPlanById(planId) : null;
        if (plan && plan.monthlyCredits > 0 && start && end) {
          await resetMonthlyAllowance(row.userId, plan.monthlyCredits, start, end, null, `Monthly credits (reconciled): ${plan.name}`);
        }
        renewed += 1;
      } else {
        await revokeAccess(row.userId, status);
        revoked += 1;
      }
    } catch (error) {
      console.error('[subscription] reconcile failed for', row.stripeSubscriptionId, error);
    }
  }
  return { checked: stale.length, revoked, renewed };
}
