import { describe, it, expect, vi, beforeAll, afterAll, beforeEach } from 'vitest';
import express, { Express } from 'express';
import request from 'supertest';

const SECRET = 'test-internal-secret';

const mockSubscribe = vi.fn();
const mockPortal = vi.fn();
const mockGetPlanById = vi.fn();

vi.mock('../../services/subscriptionService.js', () => {
  class ActiveSubscriptionError extends Error {}
  class NoStripeCustomerError extends Error {}
  return {
    getActivePlans: vi.fn().mockResolvedValue([]),
    getUserSubscription: vi.fn().mockResolvedValue(null),
    getPlanById: (...a: any[]) => mockGetPlanById(...a),
    createSubscriptionCheckoutSession: (...a: any[]) => mockSubscribe(...a),
    createBillingPortalSession: (...a: any[]) => mockPortal(...a),
    ActiveSubscriptionError,
    NoStripeCustomerError,
  };
});

let app: Express;
let prevSecret: string | undefined;

beforeAll(() => {
  prevSecret = process.env.INTERNAL_SERVICE_SECRET;
  process.env.INTERNAL_SERVICE_SECRET = SECRET;
});
afterAll(() => {
  if (prevSecret === undefined) delete process.env.INTERNAL_SERVICE_SECRET;
  else process.env.INTERNAL_SERVICE_SECRET = prevSecret;
});

beforeEach(async () => {
  vi.clearAllMocks();
  mockGetPlanById.mockResolvedValue({ id: 'plan_1', isActive: true });
  const { billingRouter } = await import('../billing.js');
  app = express();
  app.use(express.json());
  app.use('/api/billing', billingRouter);
});

const auth = { 'X-Internal-Service': SECRET, 'X-User-ID': 'u1' };

describe('POST /api/billing/subscribe', () => {
  it('200 + url for a valid plan', async () => {
    mockSubscribe.mockResolvedValue({ url: 'https://stripe/checkout' });
    const res = await request(app).post('/api/billing/subscribe').set(auth).send({ planId: 'plan_1' });
    expect(res.status).toBe(200);
    expect(res.body.url).toContain('stripe');
  });

  it('409 when the user already has a live subscription', async () => {
    const { ActiveSubscriptionError } = await import('../../services/subscriptionService.js');
    mockSubscribe.mockRejectedValue(new ActiveSubscriptionError());
    const res = await request(app).post('/api/billing/subscribe').set(auth).send({ planId: 'plan_1' });
    expect(res.status).toBe(409);
    expect(res.body.code).toBe('ALREADY_SUBSCRIBED');
  });

  it('404 for an unknown plan, 400 for a missing planId', async () => {
    mockGetPlanById.mockResolvedValueOnce(null);
    const r404 = await request(app).post('/api/billing/subscribe').set(auth).send({ planId: 'nope' });
    expect(r404.status).toBe(404);
    const r400 = await request(app).post('/api/billing/subscribe').set(auth).send({});
    expect(r400.status).toBe(400);
  });

  it('401 without X-User-ID', async () => {
    const res = await request(app).post('/api/billing/subscribe').set('X-Internal-Service', SECRET).send({ planId: 'plan_1' });
    expect(res.status).toBe(401);
  });
});

describe('POST /api/billing/portal', () => {
  it('200 + url when the user has a customer', async () => {
    mockPortal.mockResolvedValue({ url: 'https://stripe/portal' });
    const res = await request(app).post('/api/billing/portal').set(auth).send({});
    expect(res.status).toBe(200);
    expect(res.body.url).toContain('portal');
  });

  it('400 when the user has no Stripe customer (and does not create one)', async () => {
    const { NoStripeCustomerError } = await import('../../services/subscriptionService.js');
    mockPortal.mockRejectedValue(new NoStripeCustomerError());
    const res = await request(app).post('/api/billing/portal').set(auth).send({});
    expect(res.status).toBe(400);
    expect(res.body.code).toBe('NO_CUSTOMER');
  });
});
