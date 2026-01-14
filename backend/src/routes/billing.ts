import { Router, Response } from 'express';
import { requireInternalAuth, AuthenticatedRequest } from '../middleware/auth.js';
import {
  getOrCreateUserCredits,
  getCreditDetails,
  getTransactionHistory,
  redeemPromoCode,
  PromoCodeError,
  RateLimitError,
} from '../services/creditService.js';

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
