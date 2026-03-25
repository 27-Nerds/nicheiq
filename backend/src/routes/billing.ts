import { Router, Response } from 'express';
import { requireInternalAuth, AuthenticatedRequest } from '../middleware/auth.js';
import {
  getOrCreateUserCredits,
  getCreditDetails,
  getTransactionHistory,
  redeemPromoCode,
  PromoCodeError,
  RateLimitError,
  getStageCost,
} from '../services/creditService.js';
import { getPackages, getPackageById, createCheckoutSession } from '../services/stripeService.js';

export const billingRouter = Router();

/**
 * GET /api/billing
 * Get user's credit balance and stats
 */
billingRouter.get('/', requireInternalAuth, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const userId = req.user!.id;
    const details = await getCreditDetails(userId);

    res.json({
      balance: details.balance,
      totalPurchased: details.totalPurchased,
      totalUsed: details.totalUsed,
      recentTransactions: details.recentTransactions.map((tx) => ({
        id: tx.id,
        type: tx.type,
        amount: tx.amount,
        balanceAfter: tx.balanceAfter,
        description: tx.description,
        createdAt: tx.createdAt.toISOString(),
      })),
    });
  } catch (error) {
    console.error('Failed to get billing info:', error);
    res.status(500).json({ error: 'Failed to get billing information' });
  }
});

/**
 * GET /api/billing/transactions
 * Get paginated transaction history
 */
billingRouter.get('/transactions', requireInternalAuth, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const userId = req.user!.id;
    const page = parseInt(req.query.page as string) || 1;
    const limit = Math.min(parseInt(req.query.limit as string) || 20, 100);

    const result = await getTransactionHistory(userId, page, limit);

    res.json({
      transactions: result.transactions.map((tx) => ({
        id: tx.id,
        type: tx.type,
        amount: tx.amount,
        balanceBefore: tx.balanceBefore,
        balanceAfter: tx.balanceAfter,
        description: tx.description,
        stage: tx.stage,
        relatedJobId: tx.relatedJobId,
        createdAt: tx.createdAt.toISOString(),
      })),
      pagination: {
        page: result.page,
        limit: result.limit,
        total: result.total,
        totalPages: result.totalPages,
      },
    });
  } catch (error) {
    console.error('Failed to get transaction history:', error);
    res.status(500).json({ error: 'Failed to get transaction history' });
  }
});

/**
 * POST /api/billing/redeem
 * Redeem a promo code for credits
 */
billingRouter.post('/redeem', requireInternalAuth, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const userId = req.user!.id;
    const { code } = req.body;

    if (!code || typeof code !== 'string') {
      res.status(400).json({
        error: 'Promo code is required',
        code: 'MISSING_CODE',
      });
      return;
    }

    const trimmedCode = code.trim();
    if (trimmedCode.length === 0 || trimmedCode.length > 50) {
      res.status(400).json({
        error: 'Invalid promo code format',
        code: 'INVALID_FORMAT',
      });
      return;
    }

    const result = await redeemPromoCode(userId, trimmedCode);

    res.json({
      success: true,
      creditsGranted: result.creditsGranted,
      newBalance: result.credits.balance,
      message: `Successfully redeemed ${result.creditsGranted} research credit${result.creditsGranted > 1 ? 's' : ''}!`,
    });
  } catch (error) {
    if (error instanceof PromoCodeError) {
      res.status(400).json({
        error: error.message,
        code: error.code,
      });
      return;
    }

    if (error instanceof RateLimitError) {
      res.status(429).json({
        error: error.message,
        code: 'PROMO_RATE_LIMITED',
      });
      return;
    }

    console.error('Failed to redeem promo code:', error);
    res.status(500).json({
      error: 'Failed to redeem promo code',
      code: 'INTERNAL_ERROR',
    });
  }
});

/**
 * GET /api/billing/balance
 * Quick endpoint to get just the balance (for header display)
 */
billingRouter.get('/balance', requireInternalAuth, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const userId = req.user!.id;
    const credits = await getOrCreateUserCredits(userId);

    res.json({
      balance: credits.balance,
    });
  } catch (error) {
    console.error('Failed to get balance:', error);
    res.status(500).json({ error: 'Failed to get balance' });
  }
});

/**
 * GET /api/billing/packages
 * Get available token packages for purchase
 */
billingRouter.get('/packages', async (_req, res: Response) => {
  try {
    const packages = await getPackages();

    res.setHeader('Cache-Control', 'public, max-age=300');
    res.json({
      packages: packages.map((pkg) => ({
        id: pkg.id,
        name: pkg.name,
        description: pkg.description,
        credits: pkg.credits,
        priceInCents: pkg.priceInCents,
        isPopular: pkg.isPopular,
        tagline: pkg.tagline,
        includesLabel: pkg.includesLabel,
        creditsInfo: pkg.creditsInfo,
        features: Array.isArray(pkg.features) ? pkg.features : null,
        ctaText: pkg.ctaText,
        badgeLabel: pkg.badgeLabel,
        promoLine: pkg.promoLine,
        promoPriceInCents: pkg.promoPriceInCents,
        promoBadge: pkg.promoBadge,
        ctaSubText: pkg.ctaSubText,
        ctaSubUrl: pkg.ctaSubUrl,
      })),
    });
  } catch (error) {
    console.error('Failed to get packages:', error);
    res.status(500).json({ error: 'Failed to get packages' });
  }
});

/**
 * POST /api/billing/checkout
 * Create a Stripe Checkout Session for purchasing credits
 */
billingRouter.post('/checkout', requireInternalAuth, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const userId = req.user!.id;
    const userEmail = req.user!.email || '';
    const { packageId, returnUrl } = req.body;

    if (!packageId || typeof packageId !== 'string') {
      res.status(400).json({
        error: 'Package ID is required',
        code: 'MISSING_PACKAGE_ID',
      });
      return;
    }

    // Verify package exists
    const pkg = await getPackageById(packageId);
    if (!pkg) {
      res.status(404).json({
        error: 'Package not found',
        code: 'PACKAGE_NOT_FOUND',
      });
      return;
    }

    if (!pkg.isActive) {
      res.status(400).json({
        error: 'Package is no longer available',
        code: 'PACKAGE_INACTIVE',
      });
      return;
    }

    const { url } = await createCheckoutSession(userId, userEmail, packageId, returnUrl);

    res.json({ url });
  } catch (error) {
    console.error('Failed to create checkout session:', error);
    res.status(500).json({
      error: 'Failed to create checkout session',
      code: 'CHECKOUT_FAILED',
    });
  }
});

/**
 * GET /api/billing/stage-costs
 * Get current token costs for each stage
 */
billingRouter.get('/stage-costs', requireInternalAuth, async (_req: AuthenticatedRequest, res: Response) => {
  try {
    const [discovery, deep_research, landing_page, regenerate_ideas] = await Promise.all([
      getStageCost('discovery'),
      getStageCost('deep_research'),
      getStageCost('landing_page'),
      getStageCost('regenerate_ideas'),
    ]);

    res.json({ discovery, deep_research, landing_page, regenerate_ideas });
  } catch (error) {
    console.error('Failed to get stage costs:', error);
    res.status(500).json({ error: 'Failed to get stage costs' });
  }
});
