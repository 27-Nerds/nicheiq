import { describe, it, expect, vi, beforeEach } from 'vitest';

// Verifies the subscription webhook handlers: the monthly-grant gating on invoice.paid
// (billing_reason + trialing), the entitlement upsert + staleness guard, and revocation.

const mockSubRetrieve = vi.fn();
vi.mock('../stripeClient.js', () => ({
  getStripe: () => ({ subscriptions: { retrieve: (...a: any[]) => mockSubRetrieve(...a) } }),
}));

const resetMonthlyAllowance = vi.fn().mockResolvedValue({ applied: true });
vi.mock('../creditService.js', () => ({ resetMonthlyAllowance: (...a: any[]) => resetMonthlyAllowance(...a) }));

const subUpdateMany = vi.fn().mockResolvedValue({ count: 1 });
const subUpsert = vi.fn().mockResolvedValue({});
const subFindUnique = vi.fn().mockResolvedValue(null);
const userUpdate = vi.fn().mockResolvedValue({});
const userFindFirst = vi.fn().mockResolvedValue(null);
const planFindUnique = vi.fn();
const creditsUpdateMany = vi.fn().mockResolvedValue({ count: 1 });

vi.mock('../db.js', () => ({
  prisma: {
    $transaction: (ops: any) => (Array.isArray(ops) ? Promise.all(ops) : ops()),
    userSubscription: {
      updateMany: (...a: any[]) => subUpdateMany(...a),
      upsert: (...a: any[]) => subUpsert(...a),
      findUnique: (...a: any[]) => subFindUnique(...a),
    },
    user: { update: (...a: any[]) => userUpdate(...a), findFirst: (...a: any[]) => userFindFirst(...a) },
    subscriptionPlan: { findUnique: (...a: any[]) => planFindUnique(...a) },
    userCredits: { updateMany: (...a: any[]) => creditsUpdateMany(...a) },
  },
}));
vi.mock('../../config.js', () => ({ CONFIG: { baseUrl: 'http://localhost:3000', stripe: {} } }));

const futureSec = Math.floor((Date.now() + 30 * 86_400_000) / 1000);
const periodSec = Math.floor(Date.now() / 1000);

function subObj(status: string) {
  return {
    id: 'sub_1',
    status,
    customer: 'cus_1',
    created: periodSec,
    cancel_at_period_end: false,
    canceled_at: null,
    metadata: { userId: 'u1', planId: 'plan_1' },
    items: { data: [{ price: { id: 'price_1' }, current_period_start: periodSec, current_period_end: futureSec }] },
  };
}

function invoice(billingReason: string) {
  return {
    id: 'in_1',
    billing_reason: billingReason,
    parent: { subscription_details: { subscription: 'sub_1' } },
    lines: { data: [{ period: { start: periodSec, end: futureSec } }] },
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  resetMonthlyAllowance.mockResolvedValue({ applied: true });
  subUpdateMany.mockResolvedValue({ count: 1 });
  planFindUnique.mockResolvedValue({ id: 'plan_1', name: 'Pro', monthlyCredits: 50 });
});

describe('handleInvoicePaid — monthly grant gating', () => {
  it('subscription_cycle (active) → grants the monthly allowance', async () => {
    mockSubRetrieve.mockResolvedValue(subObj('active'));
    const { handleInvoicePaid } = await import('../subscriptionService.js');
    await handleInvoicePaid(invoice('subscription_cycle') as any);
    expect(resetMonthlyAllowance).toHaveBeenCalledWith('u1', 50, expect.any(Date), expect.any(Date), 'in_1', expect.any(String));
  });

  it('does NOT grant while the subscription is trialing (a $0 trial invoice)', async () => {
    mockSubRetrieve.mockResolvedValue(subObj('trialing'));
    const { handleInvoicePaid } = await import('../subscriptionService.js');
    await handleInvoicePaid(invoice('subscription_create') as any);
    expect(resetMonthlyAllowance).not.toHaveBeenCalled();
  });

  it('does NOT grant on subscription_update (proration — prevents plan-switch farming)', async () => {
    mockSubRetrieve.mockResolvedValue(subObj('active'));
    const { handleInvoicePaid } = await import('../subscriptionService.js');
    await handleInvoicePaid(invoice('subscription_update') as any);
    expect(mockSubRetrieve).not.toHaveBeenCalled(); // bailed on billing_reason before any work
    expect(resetMonthlyAllowance).not.toHaveBeenCalled();
  });

  it('0-credit (catalog-only) plan grants access but no credits', async () => {
    mockSubRetrieve.mockResolvedValue(subObj('active'));
    planFindUnique.mockResolvedValue({ id: 'plan_1', name: 'Catalog', monthlyCredits: 0 });
    const { handleInvoicePaid } = await import('../subscriptionService.js');
    await handleInvoicePaid(invoice('subscription_cycle') as any);
    expect(userUpdate).toHaveBeenCalled(); // entitlement set
    expect(resetMonthlyAllowance).not.toHaveBeenCalled(); // no credit grant
  });
});

describe('upsert + revoke', () => {
  it('upsert sets hasActiveSubscription true for an active in-period sub', async () => {
    const { upsertSubscriptionFromStripe } = await import('../subscriptionService.js');
    await upsertSubscriptionFromStripe(subObj('active') as any);
    expect(subUpsert).toHaveBeenCalled();
    expect(userUpdate).toHaveBeenCalledWith(expect.objectContaining({ data: { hasActiveSubscription: true } }));
    expect(resetMonthlyAllowance).not.toHaveBeenCalled(); // no grant on upsert
  });

  it('cancel-at-period-end: persists cancelAtPeriodEnd and keeps access until period end', async () => {
    const sub = subObj('active'); // status still active, period in the future
    sub.cancel_at_period_end = true;
    const { upsertSubscriptionFromStripe } = await import('../subscriptionService.js');
    await upsertSubscriptionFromStripe(sub as any);
    // The cancellation flag is persisted...
    expect(subUpsert.mock.calls[0][0].update.cancelAtPeriodEnd).toBe(true);
    // ...but access continues (still ACTIVE + future period → hasActiveSubscription stays true).
    expect(userUpdate).toHaveBeenCalledWith(expect.objectContaining({ data: { hasActiveSubscription: true } }));
  });

  it('staleness guard: a late event for an OLDER sub does not clobber the active row', async () => {
    subFindUnique.mockResolvedValue({
      stripeSubscriptionId: 'sub_NEW',
      stripeCreatedAt: new Date(Date.now()), // stored is newer
    });
    const stale = subObj('canceled');
    stale.id = 'sub_OLD';
    stale.created = Math.floor((Date.now() - 10 * 86_400_000) / 1000); // older
    const { upsertSubscriptionFromStripe } = await import('../subscriptionService.js');
    await upsertSubscriptionFromStripe(stale as any);
    expect(subUpsert).not.toHaveBeenCalled();
  });

  it('subscription.deleted revokes access + zeroes monthly allowance', async () => {
    const { handleSubscriptionDeleted } = await import('../subscriptionService.js');
    await handleSubscriptionDeleted(subObj('canceled') as any);
    expect(userUpdate).toHaveBeenCalledWith(expect.objectContaining({ data: { hasActiveSubscription: false } }));
    expect(creditsUpdateMany).toHaveBeenCalledWith(expect.objectContaining({ data: { monthlyAllowance: 0 } }));
  });
});
