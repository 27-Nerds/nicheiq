import { describe, it, expect, vi, beforeEach } from 'vitest';
import express, { Express } from 'express';
import request from 'supertest';

// ============================================
// Mock stripeService
// ============================================
const mockGetPackages = vi.fn();
const mockGetPackageById = vi.fn();
const mockCreateCheckoutSession = vi.fn();

vi.mock('../../services/stripeService.js', () => ({
  getPackages: mockGetPackages,
  getPackageById: mockGetPackageById,
  createCheckoutSession: mockCreateCheckoutSession,
}));

// Mock other creditService functions used by billing router
vi.mock('../../services/creditService.js', () => ({
  getOrCreateUserCredits: vi.fn().mockResolvedValue({ balance: 10 }),
  getCreditDetails: vi.fn().mockResolvedValue({
    balance: 10,
    totalPurchased: 15,
    totalUsed: 5,
    recentTransactions: [],
  }),
  getTransactionHistory: vi.fn().mockResolvedValue({
    transactions: [],
    total: 0,
    page: 1,
    limit: 20,
    totalPages: 0,
  }),
  redeemPromoCode: vi.fn(),
  PromoCodeError: class PromoCodeError extends Error {
    code: string;
    constructor(message: string, code: string) {
      super(message);
      this.code = code;
    }
  },
  RateLimitError: class RateLimitError extends Error {},
}));

// Mock auth middleware
vi.mock('../../middleware/auth.js', () => ({
  requireInternalAuth: (req: any, res: any, next: any) => {
    const userId = req.headers['x-user-id'];
    const userEmail = req.headers['x-user-email'];
    if (userId) {
      req.user = { id: userId, email: userEmail };
      return next();
    }
    res.status(401).json({ error: 'Unauthorized' });
  },
  AuthenticatedRequest: {},
}));

// ============================================
// Test Fixtures
// ============================================
const fixtures = {
  packages: [
    {
      id: 'pkg-starter',
      name: 'Starter',
      description: '5 credits',
      credits: 5,
      priceInCents: 999,
      isPopular: false,
    },
    {
      id: 'pkg-pro',
      name: 'Pro',
      description: '15 credits',
      credits: 15,
      priceInCents: 2499,
      isPopular: true,
    },
  ],
  activePackage: {
    id: 'pkg-starter',
    name: 'Starter',
    description: '5 credits',
    credits: 5,
    priceInCents: 999,
    stripePriceId: 'price_xxx',
    isActive: true,
    isPopular: false,
    sortOrder: 1,
  },
  inactivePackage: {
    id: 'pkg-old',
    name: 'Old',
    description: 'Deprecated',
    credits: 10,
    priceInCents: 1999,
    stripePriceId: 'price_old',
    isActive: false,
    isPopular: false,
    sortOrder: 99,
  },
};

// ============================================
// Setup Express App
// ============================================
let app: Express;

beforeEach(async () => {
  vi.clearAllMocks();

  app = express();
  app.use(express.json());

  // Import router after mocks are set up
  const { billingRouter } = await import('../billing.js');
  app.use('/api/billing', billingRouter);
});

// ============================================
// T7: GET /api/billing/packages tests
// ============================================
describe('GET /api/billing/packages', () => {
  it('returns packages array', async () => {
    mockGetPackages.mockResolvedValue(fixtures.packages);

    const response = await request(app).get('/api/billing/packages');

    expect(response.status).toBe(200);
    expect(response.body.packages).toHaveLength(2);
    expect(response.body.packages[0]).toEqual({
      id: 'pkg-starter',
      name: 'Starter',
      description: '5 credits',
      credits: 5,
      priceInCents: 999,
      isPopular: false,
    });
  });

  it('returns empty array when no packages', async () => {
    mockGetPackages.mockResolvedValue([]);

    const response = await request(app).get('/api/billing/packages');

    expect(response.status).toBe(200);
    expect(response.body.packages).toEqual([]);
  });

  it('does not require authentication', async () => {
    mockGetPackages.mockResolvedValue(fixtures.packages);

    // No auth headers
    const response = await request(app).get('/api/billing/packages');

    expect(response.status).toBe(200);
  });

  it('handles service error', async () => {
    mockGetPackages.mockRejectedValue(new Error('Database error'));

    const response = await request(app).get('/api/billing/packages');

    expect(response.status).toBe(500);
    expect(response.body.error).toBe('Failed to get packages');
  });
});

// ============================================
// T8: POST /api/billing/checkout tests
// ============================================
describe('POST /api/billing/checkout', () => {
  const authHeaders = {
    'x-user-id': 'user-123',
    'x-user-email': 'user@example.com',
  };

  it('returns checkout URL on success', async () => {
    mockGetPackageById.mockResolvedValue(fixtures.activePackage);
    mockCreateCheckoutSession.mockResolvedValue({
      url: 'https://checkout.stripe.com/xxx',
    });

    const response = await request(app)
      .post('/api/billing/checkout')
      .set(authHeaders)
      .send({ packageId: 'pkg-starter' });

    expect(response.status).toBe(200);
    expect(response.body.url).toBe('https://checkout.stripe.com/xxx');
    expect(mockCreateCheckoutSession).toHaveBeenCalledWith(
      'user-123',
      'user@example.com',
      'pkg-starter'
    );
  });

  it('returns 401 when not authenticated', async () => {
    const response = await request(app)
      .post('/api/billing/checkout')
      .send({ packageId: 'pkg-starter' });

    expect(response.status).toBe(401);
  });

  it('returns 400 when packageId missing', async () => {
    const response = await request(app)
      .post('/api/billing/checkout')
      .set(authHeaders)
      .send({});

    expect(response.status).toBe(400);
    expect(response.body.code).toBe('MISSING_PACKAGE_ID');
  });

  it('returns 400 when packageId is not a string', async () => {
    const response = await request(app)
      .post('/api/billing/checkout')
      .set(authHeaders)
      .send({ packageId: 123 });

    expect(response.status).toBe(400);
    expect(response.body.code).toBe('MISSING_PACKAGE_ID');
  });

  it('returns 404 when package not found', async () => {
    mockGetPackageById.mockResolvedValue(null);

    const response = await request(app)
      .post('/api/billing/checkout')
      .set(authHeaders)
      .send({ packageId: 'nonexistent' });

    expect(response.status).toBe(404);
    expect(response.body.code).toBe('PACKAGE_NOT_FOUND');
  });

  it('returns 400 when package is inactive', async () => {
    mockGetPackageById.mockResolvedValue(fixtures.inactivePackage);

    const response = await request(app)
      .post('/api/billing/checkout')
      .set(authHeaders)
      .send({ packageId: 'pkg-old' });

    expect(response.status).toBe(400);
    expect(response.body.code).toBe('PACKAGE_INACTIVE');
  });

  it('returns 500 when checkout session creation fails', async () => {
    mockGetPackageById.mockResolvedValue(fixtures.activePackage);
    mockCreateCheckoutSession.mockRejectedValue(new Error('Stripe error'));

    const response = await request(app)
      .post('/api/billing/checkout')
      .set(authHeaders)
      .send({ packageId: 'pkg-starter' });

    expect(response.status).toBe(500);
    expect(response.body.code).toBe('CHECKOUT_FAILED');
  });
});
