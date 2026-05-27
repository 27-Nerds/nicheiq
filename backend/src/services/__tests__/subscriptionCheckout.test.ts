import { describe, it, expect, vi, beforeEach } from 'vitest';

// Stripe: capture the checkout session args; existing customer avoids customers.create.
const mockSessionsCreate = vi.fn();
vi.mock('../stripeClient.js', () => ({
  getStripe: () => ({
    checkout: { sessions: { create: mockSessionsCreate } },
    customers: { create: vi.fn() },
  }),
}));

const mockUserSubFindUnique = vi.fn();
const mockUserFindUnique = vi.fn();
const mockPlanFindUnique = vi.fn();
vi.mock('../db.js', () => ({
  prisma: {
    userSubscription: { findUnique: (...a: any[]) => mockUserSubFindUnique(...a) },
    user: { findUnique: (...a: any[]) => mockUserFindUnique(...a), update: vi.fn() },
    subscriptionPlan: {
      findUnique: (...a: any[]) => mockPlanFindUnique(...a),
      findMany: vi.fn(),
    },
  },
}));

vi.mock('../creditService.js', () => ({ resetMonthlyAllowance: vi.fn() }));

vi.mock('../../config.js', () => ({ CONFIG: { baseUrl: 'http://localhost:3000' } }));

beforeEach(() => {
  vi.clearAllMocks();
  mockUserSubFindUnique.mockResolvedValue(null); // no live subscription → checkout allowed
  mockUserFindUnique.mockResolvedValue({ stripeCustomerId: 'cus_existing' });
  mockPlanFindUnique.mockResolvedValue({
    id: 'plan_1',
    isActive: true,
    stripePriceId: 'price_x',
    trialDays: null,
    stripeCouponId: null,
  });
  mockSessionsCreate.mockResolvedValue({ url: 'https://stripe/checkout' });
});

describe('createSubscriptionCheckoutSession returnUrl', () => {
  it('uses a valid returnUrl for sub_success / sub_canceled URLs', async () => {
    const { createSubscriptionCheckoutSession } = await import('../subscriptionService.js');
    await createSubscriptionCheckoutSession('u1', 'u@e.com', 'plan_1', '/ideas/saas-tools');
    expect(mockSessionsCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        success_url:
          'http://localhost:3000/ideas/saas-tools?sub_success=true&session_id={CHECKOUT_SESSION_ID}',
        cancel_url: 'http://localhost:3000/ideas/saas-tools?sub_canceled=true',
      }),
    );
  });

  it('appends with & when the returnUrl already has a query string', async () => {
    const { createSubscriptionCheckoutSession } = await import('../subscriptionService.js');
    await createSubscriptionCheckoutSession('u1', 'u@e.com', 'plan_1', '/ideas/saas?collection=x');
    expect(mockSessionsCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        success_url:
          'http://localhost:3000/ideas/saas?collection=x&sub_success=true&session_id={CHECKOUT_SESSION_ID}',
        cancel_url: 'http://localhost:3000/ideas/saas?collection=x&sub_canceled=true',
      }),
    );
  });

  it('falls back to /billing when returnUrl is absent', async () => {
    const { createSubscriptionCheckoutSession } = await import('../subscriptionService.js');
    await createSubscriptionCheckoutSession('u1', 'u@e.com', 'plan_1');
    expect(mockSessionsCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        success_url: 'http://localhost:3000/billing?sub_success=true&session_id={CHECKOUT_SESSION_ID}',
        cancel_url: 'http://localhost:3000/billing?sub_canceled=true',
      }),
    );
  });

  it('falls back to /billing when returnUrl is off-origin', async () => {
    const { createSubscriptionCheckoutSession } = await import('../subscriptionService.js');
    await createSubscriptionCheckoutSession('u1', 'u@e.com', 'plan_1', 'https://evil.com/x');
    expect(mockSessionsCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        success_url: 'http://localhost:3000/billing?sub_success=true&session_id={CHECKOUT_SESSION_ID}',
        cancel_url: 'http://localhost:3000/billing?sub_canceled=true',
      }),
    );
  });
});
