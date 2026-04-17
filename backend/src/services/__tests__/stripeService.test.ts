import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import type Stripe from 'stripe';

// ============================================
// T1: Stripe Mock Utilities
// ============================================

const mockCheckoutSessionCreate = vi.fn();
const mockWebhooksConstructEvent = vi.fn();

vi.mock('stripe', () => {
  const MockStripe = function() {
    return {
      checkout: {
        sessions: {
          create: mockCheckoutSessionCreate,
        },
      },
      webhooks: {
        constructEvent: mockWebhooksConstructEvent,
      },
    };
  };
  return { default: MockStripe };
});

// Mock Prisma
const mockPrismaTokenPackage = {
  findMany: vi.fn(),
  findUnique: vi.fn(),
};

const mockPrismaCreditTransaction = {
  findFirst: vi.fn(),
};

vi.mock('../db.js', () => ({
  prisma: {
    tokenPackage: mockPrismaTokenPackage,
    creditTransaction: mockPrismaCreditTransaction,
  },
}));

// Mock creditService
const mockAddCredits = vi.fn();
vi.mock('../creditService.js', () => ({
  addCredits: mockAddCredits,
}));

// Mock config
vi.mock('../../config.js', () => ({
  CONFIG: {
    baseUrl: 'http://localhost:3000',
    stripe: {
      secretKey: 'sk_test_xxx',
      webhookSecret: 'whsec_xxx',
    },
  },
}));

// ============================================
// T2: Test Fixtures
// ============================================

const fixtures = {
  packages: {
    starter: {
      id: 'pkg-starter-123',
      name: 'Starter',
      description: '5 research credits',
      credits: 5,
      priceInCents: 999,
      stripePriceId: 'price_starter_xxx',
      isActive: true,
      isPopular: false,
      sortOrder: 1,
      createdAt: new Date(),
      updatedAt: new Date(),
    },
    pro: {
      id: 'pkg-pro-123',
      name: 'Pro',
      description: '15 research credits',
      credits: 15,
      priceInCents: 2499,
      stripePriceId: 'price_pro_xxx',
      isActive: true,
      isPopular: true,
      sortOrder: 2,
      createdAt: new Date(),
      updatedAt: new Date(),
    },
    inactive: {
      id: 'pkg-inactive-123',
      name: 'Old Package',
      description: 'Deprecated',
      credits: 10,
      priceInCents: 1999,
      stripePriceId: 'price_old_xxx',
      isActive: false,
      isPopular: false,
      sortOrder: 99,
      createdAt: new Date(),
      updatedAt: new Date(),
    },
  },

  checkoutSession: {
    id: 'cs_test_xxx',
    url: 'https://checkout.stripe.com/c/pay/cs_test_xxx',
    client_reference_id: 'user-123',
    metadata: {
      userId: 'user-123',
      packageId: 'pkg-starter-123',
      packageName: 'Starter',
      credits: '5',
    },
  } as unknown as Stripe.Checkout.Session,

  webhookEvents: {
    checkoutCompleted: {
      id: 'evt_test_xxx',
      type: 'checkout.session.completed',
      data: {
        object: {
          id: 'cs_test_xxx',
          client_reference_id: 'user-123',
          metadata: {
            userId: 'user-123',
            packageId: 'pkg-starter-123',
            packageName: 'Starter',
            credits: '5',
          },
        },
      },
    } as unknown as Stripe.Event,

    checkoutExpired: {
      id: 'evt_expired_xxx',
      type: 'checkout.session.expired',
      data: {
        object: {
          id: 'cs_expired_xxx',
        },
      },
    } as unknown as Stripe.Event,
  },
};

// ============================================
// Tests
// ============================================

describe('stripeService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.resetModules();
  });

  // ============================================
  // T3: getPackages() tests
  // ============================================
  describe('getPackages', () => {
    it('returns active packages sorted by sortOrder', async () => {
      mockPrismaTokenPackage.findMany.mockResolvedValue([
        fixtures.packages.starter,
        fixtures.packages.pro,
      ]);

      const { getPackages } = await import('../stripeService.js');
      const packages = await getPackages();

      expect(packages).toHaveLength(2);
      expect(mockPrismaTokenPackage.findMany).toHaveBeenCalledWith({
        where: { isActive: true },
        orderBy: { sortOrder: 'asc' },
        select: {
          id: true,
          name: true,
          description: true,
          credits: true,
          priceInCents: true,
          isPopular: true,
          tagline: true,
          includesLabel: true,
          creditsInfo: true,
          features: true,
          ctaText: true,
          badgeLabel: true,
          promoLine: true,
          promoPriceInCents: true,
          promoBadge: true,
          ctaSubText: true,
          ctaSubUrl: true,
        },
      });
    });

    it('returns empty array when no active packages', async () => {
      mockPrismaTokenPackage.findMany.mockResolvedValue([]);

      const { getPackages } = await import('../stripeService.js');
      const packages = await getPackages();

      expect(packages).toEqual([]);
    });

    it('excludes inactive packages', async () => {
      mockPrismaTokenPackage.findMany.mockResolvedValue([
        fixtures.packages.starter,
      ]);

      const { getPackages } = await import('../stripeService.js');
      await getPackages();

      expect(mockPrismaTokenPackage.findMany).toHaveBeenCalledWith(
        expect.objectContaining({
          where: { isActive: true },
        })
      );
    });
  });

  // ============================================
  // T4: getPackageById() tests
  // ============================================
  describe('getPackageById', () => {
    it('returns package when found', async () => {
      mockPrismaTokenPackage.findUnique.mockResolvedValue(fixtures.packages.starter);

      const { getPackageById } = await import('../stripeService.js');
      const pkg = await getPackageById('pkg-starter-123');

      expect(pkg).toEqual(fixtures.packages.starter);
      expect(mockPrismaTokenPackage.findUnique).toHaveBeenCalledWith({
        where: { id: 'pkg-starter-123' },
      });
    });

    it('returns null when package not found', async () => {
      mockPrismaTokenPackage.findUnique.mockResolvedValue(null);

      const { getPackageById } = await import('../stripeService.js');
      const pkg = await getPackageById('nonexistent');

      expect(pkg).toBeNull();
    });
  });

  // ============================================
  // T5: createCheckoutSession() tests
  // ============================================
  describe('createCheckoutSession', () => {
    it('creates checkout session successfully', async () => {
      mockPrismaTokenPackage.findUnique.mockResolvedValue(fixtures.packages.starter);
      mockCheckoutSessionCreate.mockResolvedValue(fixtures.checkoutSession);

      const { createCheckoutSession } = await import('../stripeService.js');
      const result = await createCheckoutSession(
        'user-123',
        'user@example.com',
        'pkg-starter-123'
      );

      expect(result.url).toBe(fixtures.checkoutSession.url);
      expect(mockCheckoutSessionCreate).toHaveBeenCalledWith({
        mode: 'payment',
        payment_method_types: ['card'],
        customer_email: 'user@example.com',
        client_reference_id: 'user-123',
        line_items: [
          {
            price: fixtures.packages.starter.stripePriceId,
            quantity: 1,
          },
        ],
        metadata: {
          userId: 'user-123',
          packageId: fixtures.packages.starter.id,
          packageName: fixtures.packages.starter.name,
          credits: fixtures.packages.starter.credits.toString(),
        },
        success_url: 'http://localhost:3000/billing?success=true&session_id={CHECKOUT_SESSION_ID}',
        cancel_url: 'http://localhost:3000/billing?canceled=true',
      });
    });

    it('throws error when package not found', async () => {
      mockPrismaTokenPackage.findUnique.mockResolvedValue(null);

      const { createCheckoutSession } = await import('../stripeService.js');

      await expect(
        createCheckoutSession('user-123', 'user@example.com', 'nonexistent')
      ).rejects.toThrow('Package not found');
    });

    it('throws error when package is inactive', async () => {
      mockPrismaTokenPackage.findUnique.mockResolvedValue(fixtures.packages.inactive);

      const { createCheckoutSession } = await import('../stripeService.js');

      await expect(
        createCheckoutSession('user-123', 'user@example.com', 'pkg-inactive-123')
      ).rejects.toThrow('Package is no longer available');
    });

    it('throws error when Stripe fails to create session URL', async () => {
      mockPrismaTokenPackage.findUnique.mockResolvedValue(fixtures.packages.starter);
      mockCheckoutSessionCreate.mockResolvedValue({ id: 'cs_xxx', url: null });

      const { createCheckoutSession } = await import('../stripeService.js');

      await expect(
        createCheckoutSession('user-123', 'user@example.com', 'pkg-starter-123')
      ).rejects.toThrow('Failed to create checkout session');
    });
  });

  // ============================================
  // T6: handleWebhookEvent() tests
  // ============================================
  describe('handleWebhookEvent', () => {
    const validPayload = Buffer.from('valid-payload');
    const validSignature = 'valid-signature';

    it('verifies signature and processes checkout.session.completed', async () => {
      mockWebhooksConstructEvent.mockReturnValue(fixtures.webhookEvents.checkoutCompleted);
      mockPrismaCreditTransaction.findFirst.mockResolvedValue(null);
      mockAddCredits.mockResolvedValue({
        credits: { balance: 5 },
        transaction: { id: 'tx-123' },
      });

      const { handleWebhookEvent } = await import('../stripeService.js');
      const result = await handleWebhookEvent(validPayload, validSignature);

      expect(result.received).toBe(true);
      expect(result.event).toBe('checkout.session.completed');
      expect(mockAddCredits).toHaveBeenCalledWith(
        'user-123',
        5,
        expect.stringContaining('Purchased Starter')
      );
    });

    it('throws error on invalid signature', async () => {
      mockWebhooksConstructEvent.mockImplementation(() => {
        throw new Error('Invalid signature');
      });

      const { handleWebhookEvent } = await import('../stripeService.js');

      await expect(
        handleWebhookEvent(validPayload, 'invalid-signature')
      ).rejects.toThrow('Webhook signature verification failed');
    });

    it('handles checkout.session.expired without error', async () => {
      mockWebhooksConstructEvent.mockReturnValue(fixtures.webhookEvents.checkoutExpired);

      const { handleWebhookEvent } = await import('../stripeService.js');
      const result = await handleWebhookEvent(validPayload, validSignature);

      expect(result.received).toBe(true);
      expect(result.event).toBe('checkout.session.expired');
      expect(mockAddCredits).not.toHaveBeenCalled();
    });

    it('skips duplicate session (idempotency)', async () => {
      mockWebhooksConstructEvent.mockReturnValue(fixtures.webhookEvents.checkoutCompleted);
      mockPrismaCreditTransaction.findFirst.mockResolvedValue({
        id: 'existing-tx',
        description: 'Already processed cs_test_xxx',
      });

      const { handleWebhookEvent } = await import('../stripeService.js');
      const result = await handleWebhookEvent(validPayload, validSignature);

      expect(result.received).toBe(true);
      expect(mockAddCredits).not.toHaveBeenCalled();
    });

    it('handles missing userId in session', async () => {
      const eventWithoutUserId = {
        ...fixtures.webhookEvents.checkoutCompleted,
        data: {
          object: {
            id: 'cs_test_xxx',
            client_reference_id: null,
            metadata: null,
          },
        },
      } as unknown as Stripe.Event;

      mockWebhooksConstructEvent.mockReturnValue(eventWithoutUserId);

      const { handleWebhookEvent } = await import('../stripeService.js');
      const result = await handleWebhookEvent(validPayload, validSignature);

      expect(result.received).toBe(true);
      expect(mockAddCredits).not.toHaveBeenCalled();
    });

    it('handles invalid credits in metadata', async () => {
      const eventWithInvalidCredits = {
        ...fixtures.webhookEvents.checkoutCompleted,
        data: {
          object: {
            id: 'cs_test_xxx',
            client_reference_id: 'user-123',
            metadata: {
              userId: 'user-123',
              credits: 'invalid',
            },
          },
        },
      } as unknown as Stripe.Event;

      mockWebhooksConstructEvent.mockReturnValue(eventWithInvalidCredits);

      const { handleWebhookEvent } = await import('../stripeService.js');
      const result = await handleWebhookEvent(validPayload, validSignature);

      expect(result.received).toBe(true);
      expect(mockAddCredits).not.toHaveBeenCalled();
    });

    it('handles unknown event types gracefully', async () => {
      const unknownEvent = {
        id: 'evt_unknown',
        type: 'unknown.event.type',
        data: { object: {} },
      } as unknown as Stripe.Event;

      mockWebhooksConstructEvent.mockReturnValue(unknownEvent);

      const { handleWebhookEvent } = await import('../stripeService.js');
      const result = await handleWebhookEvent(validPayload, validSignature);

      expect(result.received).toBe(true);
      expect(result.event).toBe('unknown.event.type');
      expect(mockAddCredits).not.toHaveBeenCalled();
    });
  });
});
