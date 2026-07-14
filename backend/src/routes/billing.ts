import { Router, Response } from 'express';
import { requireInternalAuth, AuthenticatedRequest } from '../middleware/auth.js';
import {
  getCreditDetails,
  getTransactionHistory,
  redeemPromoCode,
  PromoCodeError,
  RateLimitError,
  getStageCost,
  getGuidedSegmentCosts,
} from '../services/creditService.js';
import { getPackages, getPackageById, createCheckoutSession } from '../services/stripeService.js';
import {
  getActivePlans,
  getPlanById,
  getUserSubscription,
  createSubscriptionCheckoutSession,
  createBillingPortalSession,
  ActiveSubscriptionError,
  NoStripeCustomerError,
} from '../services/subscriptionService.js';

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
      balance: details.balance, // = available (back-compat)
      available: details.available,
      monthlyAllowance: details.monthlyAllowance,
      purchasedBalance: details.purchasedBalance,
      monthlyAllowancePeriodEnd: details.monthlyAllowancePeriodEnd?.toISOString() ?? null,
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
    const details = await getCreditDetails(userId);

    res.json({
      balance: details.available, // = available (monthly spendable + purchased), back-compat
      available: details.available,
      monthlyAllowance: details.monthlyAllowance,
      purchasedBalance: details.purchasedBalance,
      monthlyAllowancePeriodEnd: details.monthlyAllowancePeriodEnd?.toISOString() ?? null,
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
    const [discovery, deep_research, landing_page, regenerate_ideas, seed_idea, guidedSegmentCosts] = await Promise.all([
      getStageCost('discovery'),
      getStageCost('deep_research'),
      getStageCost('landing_page'),
      getStageCost('regenerate_ideas'),
      getStageCost('seed_idea'),
      getGuidedSegmentCosts(),
    ]);

    res.json({
      discovery,
      deep_research,
      landing_page,
      regenerate_ideas,
      seed_idea,
      guided: {
        s1: guidedSegmentCosts.guided_s1,
        s2_4: guidedSegmentCosts.guided_s2_4,
        s5: guidedSegmentCosts.guided_s5,
        total: guidedSegmentCosts.total,
      },
    });
  } catch (error) {
    console.error('Failed to get stage costs:', error);
    res.status(500).json({ error: 'Failed to get stage costs' });
  }
});

// ============================================
// Subscriptions
// ============================================

/** Map a SubscriptionPlan to the public card shape — never leak the Stripe coupon id. */
function toPlanCard(plan: Awaited<ReturnType<typeof getActivePlans>>[number]) {
  return {
    id: plan.id,
    name: plan.name,
    description: plan.description,
    monthlyCredits: plan.monthlyCredits,
    priceInCents: plan.priceInCents,
    interval: plan.interval,
    trialDays: plan.trialDays,
    isPopular: plan.isPopular,
    tagline: plan.tagline,
    includesLabel: plan.includesLabel,
    creditsInfo: plan.creditsInfo,
    features: Array.isArray(plan.features) ? plan.features : null,
    ctaText: plan.ctaText,
    badgeLabel: plan.badgeLabel,
    promoLine: plan.promoLine,
    promoPriceInCents: plan.promoPriceInCents,
    promoBadge: plan.promoBadge,
    ctaSubText: plan.ctaSubText,
    ctaSubUrl: plan.ctaSubUrl,
  };
}

/** GET /api/billing/plans — active subscription plans (public). */
billingRouter.get('/plans', async (_req, res: Response) => {
  try {
    const plans = await getActivePlans();
    res.setHeader('Cache-Control', 'public, max-age=300');
    res.json({ plans: plans.map(toPlanCard) });
  } catch (error) {
    console.error('Failed to get plans:', error);
    res.status(500).json({ error: 'Failed to get plans' });
  }
});

/** GET /api/billing/subscription — the current user's subscription summary. */
billingRouter.get('/subscription', requireInternalAuth, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const sub = await getUserSubscription(req.user!.id);
    if (!sub) {
      res.json({ subscription: null });
      return;
    }
    res.json({
      subscription: {
        status: sub.status,
        planId: sub.planId,
        planName: sub.plan?.name ?? null,
        monthlyCredits: sub.plan?.monthlyCredits ?? null,
        interval: sub.plan?.interval ?? null,
        currentPeriodEnd: sub.currentPeriodEnd?.toISOString() ?? null,
        cancelAtPeriodEnd: sub.cancelAtPeriodEnd,
        canceledAt: sub.canceledAt?.toISOString() ?? null,
      },
    });
  } catch (error) {
    console.error('Failed to get subscription:', error);
    res.status(500).json({ error: 'Failed to get subscription' });
  }
});

/** POST /api/billing/subscribe — start a subscription checkout (409 if already live). */
billingRouter.post('/subscribe', requireInternalAuth, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const userId = req.user!.id;
    const userEmail = req.user!.email || '';
    const { planId } = req.body;
    // Normalize to a string so arrays/objects never reach the returnUrl?: string param;
    // the service's isValidReturnUrl remains the security boundary.
    const returnUrl = typeof req.body.returnUrl === 'string' ? req.body.returnUrl : undefined;
    if (!planId || typeof planId !== 'string') {
      res.status(400).json({ error: 'Plan ID is required', code: 'MISSING_PLAN_ID' });
      return;
    }
    const plan = await getPlanById(planId);
    if (!plan) {
      res.status(404).json({ error: 'Plan not found', code: 'PLAN_NOT_FOUND' });
      return;
    }
    if (!plan.isActive) {
      res.status(400).json({ error: 'Plan is no longer available', code: 'PLAN_INACTIVE' });
      return;
    }
    const { url } = await createSubscriptionCheckoutSession(userId, userEmail, planId, returnUrl);
    res.json({ url });
  } catch (error) {
    if (error instanceof ActiveSubscriptionError) {
      res.status(409).json({ error: 'Already subscribed — use Manage subscription', code: 'ALREADY_SUBSCRIBED' });
      return;
    }
    console.error('Failed to create subscription checkout:', error);
    res.status(500).json({ error: 'Failed to start subscription', code: 'SUBSCRIBE_FAILED' });
  }
});

/** POST /api/billing/portal — Stripe Customer Portal session (400 if no customer). */
billingRouter.post('/portal', requireInternalAuth, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const { url } = await createBillingPortalSession(req.user!.id);
    res.json({ url });
  } catch (error) {
    if (error instanceof NoStripeCustomerError) {
      res.status(400).json({ error: 'No active billing account', code: 'NO_CUSTOMER' });
      return;
    }
    console.error('Failed to create portal session:', error);
    res.status(500).json({ error: 'Failed to open billing portal', code: 'PORTAL_FAILED' });
  }
});
