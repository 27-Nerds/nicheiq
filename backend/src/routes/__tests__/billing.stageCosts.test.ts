/**
 * GET /api/billing/stage-costs — flat stage-cost exposure.
 *
 * Pins that `seed_idea` (plans/eager-meandering-feather.md) rides alongside the other FLAT
 * stages (discovery, deep_research, landing_page, regenerate_ideas) rather than nesting inside
 * `guided` — that object is discovery-segment-only pricing, and folding seed_idea into it would
 * corrupt the guided total/BillingModel math.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import express, { Express } from 'express';
import request from 'supertest';

const mockGetStageCost = vi.fn();
const mockGetGuidedSegmentCosts = vi.fn();

vi.mock('../../services/creditService.js', () => ({
  getCreditDetails: vi.fn(),
  getTransactionHistory: vi.fn(),
  redeemPromoCode: vi.fn(),
  PromoCodeError: class extends Error {},
  RateLimitError: class extends Error {},
  getStageCost: (...args: any[]) => mockGetStageCost(...args),
  getGuidedSegmentCosts: (...args: any[]) => mockGetGuidedSegmentCosts(...args),
}));

vi.mock('../../services/stripeService.js', () => ({
  getPackages: vi.fn(),
  getPackageById: vi.fn(),
  createCheckoutSession: vi.fn(),
}));

vi.mock('../../services/subscriptionService.js', () => ({
  getActivePlans: vi.fn(),
  getPlanById: vi.fn(),
  getUserSubscription: vi.fn(),
  createSubscriptionCheckoutSession: vi.fn(),
  createBillingPortalSession: vi.fn(),
  ActiveSubscriptionError: class extends Error {},
  NoStripeCustomerError: class extends Error {},
}));

vi.mock('../../middleware/auth.js', () => ({
  requireInternalAuth: (req: any, _res: any, next: any) => {
    req.user = { id: 'user-1' };
    next();
  },
}));

let app: Express;

beforeEach(async () => {
  vi.clearAllMocks();
  mockGetStageCost.mockImplementation(async (stage: string) => {
    const costs: Record<string, number> = {
      discovery: 5, deep_research: 15, landing_page: 5, regenerate_ideas: 2, seed_idea: 2,
    };
    return costs[stage] ?? 0;
  });
  mockGetGuidedSegmentCosts.mockResolvedValue({ guided_s1: 1, guided_s2_4: 3, guided_s5: 1, total: 5 });

  const { billingRouter } = await import('../billing.js');
  app = express();
  app.use(express.json());
  app.use('/api/billing', billingRouter);
});

describe('GET /api/billing/stage-costs', () => {
  it('exposes seed_idea as a FLAT field, alongside the other flat stages', async () => {
    const res = await request(app).get('/api/billing/stage-costs');

    expect(res.status).toBe(200);
    expect(res.body.seed_idea).toBe(2);
    expect(mockGetStageCost).toHaveBeenCalledWith('seed_idea');
  });

  it('does NOT nest seed_idea inside guided — that object stays discovery-segment-only', async () => {
    const res = await request(app).get('/api/billing/stage-costs');

    expect(res.body.guided).toEqual({ s1: 1, s2_4: 3, s5: 1, total: 5 });
    expect(res.body.guided.seed_idea).toBeUndefined();
  });

  it('reflects an admin override for token_cost_seed_idea', async () => {
    mockGetStageCost.mockImplementation(async (stage: string) => (stage === 'seed_idea' ? 4 : 1));

    const res = await request(app).get('/api/billing/stage-costs');

    expect(res.body.seed_idea).toBe(4);
  });
});
