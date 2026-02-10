import { prisma } from './db.js';
import {
  CreditTransactionType,
  JobStatus,
  StageStatus,
  Prisma,
  UserCredits,
  CreditTransaction,
  Job,
} from '@prisma/client';
import { PIPELINE_STAGES } from '../types/job.js';

// ============================================
// Custom Error Classes
// ============================================

export class InsufficientCreditsError extends Error {
  public currentBalance: number;
  public required: number;

  constructor(currentBalance: number, required: number) {
    super(`Insufficient credits: have ${currentBalance}, need ${required}`);
    this.name = 'InsufficientCreditsError';
    this.currentBalance = currentBalance;
    this.required = required;
  }
}

export class PromoCodeError extends Error {
  public code: string;

  constructor(message: string, code: string) {
    super(message);
    this.name = 'PromoCodeError';
    this.code = code;
  }
}

export class RateLimitError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'RateLimitError';
  }
}

// ============================================
// Credit Service Functions
// ============================================

/**
 * Get or create user credits record (upsert pattern)
 * Lazily initializes UserCredits on first access
 */
export async function getOrCreateUserCredits(userId: string): Promise<UserCredits> {
  return prisma.userCredits.upsert({
    where: { userId },
    create: {
      userId,
      balance: 0,
      totalPurchased: 0,
      totalUsed: 0,
    },
    update: {}, // No-op if exists
  });
}

/**
 * Get user's credit balance (returns 0 if no credits record exists)
 */
export async function getUserBalance(userId: string): Promise<number> {
  const credits = await prisma.userCredits.findUnique({
    where: { userId },
    select: { balance: true },
  });
  return credits?.balance ?? 0;
}

/**
 * Create a job with credit deduction in a single atomic transaction
 * This prevents race conditions where two jobs could be created with 1 credit
 */
export async function createJobWithCreditDeduction(
  userId: string,
  niche: string,
  creditCost: number = 1,
  allowedProjectTypes?: string[],
  generateLandingPage?: boolean,
  jobMode?: string
): Promise<{ job: Job; transaction: CreditTransaction }> {
  return prisma.$transaction(async (tx) => {
    // 1. Get or create credits record and lock the row
    let credits = await tx.userCredits.findUnique({
      where: { userId },
    });

    // Create credits record if it doesn't exist
    if (!credits) {
      credits = await tx.userCredits.create({
        data: {
          userId,
          balance: 0,
          totalPurchased: 0,
          totalUsed: 0,
        },
      });
    }

    // 2. Check balance
    if (credits.balance < creditCost) {
      throw new InsufficientCreditsError(credits.balance, creditCost);
    }

    // 3. Deduct credits FIRST (before job creation)
    const updatedCredits = await tx.userCredits.update({
      where: { userId },
      data: {
        balance: { decrement: creditCost },
        totalUsed: { increment: creditCost },
      },
    });

    // 4. Create the job AFTER credits are deducted
    const wantLanding = generateLandingPage === true;
    const stages = wantLanding
      ? PIPELINE_STAGES
      : PIPELINE_STAGES.filter(s => s.number !== 11);

    const job = await tx.job.create({
      data: {
        niche,
        userId,
        allowedProjectTypes: allowedProjectTypes as Prisma.InputJsonValue,
        generateLandingPage: wantLanding,
        jobMode,
        status: JobStatus.PENDING,
        totalStages: stages.length,
        progress: {
          create: stages.map((stage) => ({
            stageNumber: stage.number,
            stageName: stage.name,
            status: StageStatus.PENDING,
          })),
        },
      },
      include: {
        progress: {
          orderBy: { stageNumber: 'asc' },
        },
        assets: true,
      },
    });

    // 5. Log the transaction
    const transaction = await tx.creditTransaction.create({
      data: {
        userId,
        type: CreditTransactionType.JOB_DEDUCTION,
        amount: -creditCost,
        balanceBefore: credits.balance,
        balanceAfter: updatedCredits.balance,
        relatedJobId: job.id,
        description: `Research job: ${niche.substring(0, 100)}`,
      },
    });

    return { job, transaction };
  });
}

/**
 * Refund credits for a failed job
 * Called by failJob() when a job fails
 */
export async function refundCreditsForJob(
  jobId: string,
  creditAmount: number = 1
): Promise<CreditTransaction | null> {
  // Find the job to get the userId
  const job = await prisma.job.findUnique({
    where: { id: jobId },
    select: { userId: true, niche: true },
  });

  if (!job?.userId) {
    // Job doesn't have a user or doesn't exist
    return null;
  }

  // Check if we already refunded this job
  const existingRefund = await prisma.creditTransaction.findFirst({
    where: {
      relatedJobId: jobId,
      type: CreditTransactionType.REFUND,
    },
  });

  if (existingRefund) {
    // Already refunded
    console.log(`[CreditService] Job ${jobId} already has a refund transaction`);
    return existingRefund;
  }

  // Perform refund in transaction
  try {
    return await prisma.$transaction(async (tx) => {
      const credits = await tx.userCredits.findUnique({
        where: { userId: job.userId! },
      });

      if (!credits) {
        // No credits record - shouldn't happen but handle gracefully
        return null;
      }

      // Add credits back
      const updatedCredits = await tx.userCredits.update({
        where: { userId: job.userId! },
        data: {
          balance: { increment: creditAmount },
          totalUsed: { decrement: creditAmount },
        },
      });

      // Log the refund transaction
      return tx.creditTransaction.create({
        data: {
          userId: job.userId!,
          type: CreditTransactionType.REFUND,
          amount: creditAmount,
          balanceBefore: credits.balance,
          balanceAfter: updatedCredits.balance,
          relatedJobId: jobId,
          description: `Refund for failed job: ${job.niche?.substring(0, 100)}`,
        },
      });
    });
  } catch (error) {
    // Handle unique constraint violation (race condition where two refunds tried simultaneously)
    if (error instanceof Prisma.PrismaClientKnownRequestError && error.code === 'P2002') {
      console.log(`[CreditService] Job ${jobId} refund race condition detected - returning existing refund`);
      // Return the existing refund that won the race
      return prisma.creditTransaction.findFirst({
        where: { relatedJobId: jobId, type: CreditTransactionType.REFUND },
      });
    }
    throw error;
  }
}

/**
 * Redeem a promo code for credits
 * Includes rate limiting (max 5 redemptions per hour)
 */
export async function redeemPromoCode(
  userId: string,
  code: string
): Promise<{ credits: UserCredits; transaction: CreditTransaction; creditsGranted: number }> {
  return prisma.$transaction(async (tx) => {
    // 1. Rate limiting - check recent redemption attempts
    const oneHourAgo = new Date(Date.now() - 60 * 60 * 1000);
    const recentRedemptions = await tx.promoRedemption.count({
      where: {
        userId,
        redeemedAt: { gte: oneHourAgo },
      },
    });

    if (recentRedemptions >= 5) {
      throw new RateLimitError('Too many promo code attempts. Please try again later.');
    }

    // 2. Find the promo code (case-insensitive)
    const promoCode = await tx.promoCode.findFirst({
      where: {
        code: { equals: code, mode: 'insensitive' },
      },
    });

    if (!promoCode) {
      throw new PromoCodeError('Invalid promo code', 'INVALID_PROMO_CODE');
    }

    // 3. Check if code is active
    if (!promoCode.isActive) {
      throw new PromoCodeError('This promo code is no longer active', 'INVALID_PROMO_CODE');
    }

    // 4. Check if code has expired
    if (promoCode.expiresAt && promoCode.expiresAt < new Date()) {
      throw new PromoCodeError('This promo code has expired', 'PROMO_CODE_EXPIRED');
    }

    // 5. Check if max redemptions reached
    if (promoCode.currentUses >= promoCode.maxRedemptions) {
      throw new PromoCodeError('This promo code has reached its maximum uses', 'PROMO_CODE_EXHAUSTED');
    }

    // 6. Check if user already redeemed this code
    const existingRedemption = await tx.promoRedemption.findUnique({
      where: {
        promoCodeId_userId: {
          promoCodeId: promoCode.id,
          userId,
        },
      },
    });

    if (existingRedemption) {
      throw new PromoCodeError('You have already redeemed this promo code', 'PROMO_ALREADY_REDEEMED');
    }

    // 7. Get or create user credits
    let credits = await tx.userCredits.findUnique({
      where: { userId },
    });

    if (!credits) {
      credits = await tx.userCredits.create({
        data: {
          userId,
          balance: 0,
          totalPurchased: 0,
          totalUsed: 0,
        },
      });
    }

    // 8. Add credits
    const updatedCredits = await tx.userCredits.update({
      where: { userId },
      data: {
        balance: { increment: promoCode.creditAmount },
        totalPurchased: { increment: promoCode.creditAmount },
      },
    });

    // 9. Record redemption
    await tx.promoRedemption.create({
      data: {
        promoCodeId: promoCode.id,
        userId,
        creditsGranted: promoCode.creditAmount,
      },
    });

    // 10. Update promo code usage count
    await tx.promoCode.update({
      where: { id: promoCode.id },
      data: {
        currentUses: { increment: 1 },
      },
    });

    // 11. Log the transaction
    const transaction = await tx.creditTransaction.create({
      data: {
        userId,
        type: CreditTransactionType.PROMO_REDEMPTION,
        amount: promoCode.creditAmount,
        balanceBefore: credits.balance,
        balanceAfter: updatedCredits.balance,
        promoCodeId: promoCode.id,
        description: `Promo code: ${code.toUpperCase()}`,
      },
    });

    return {
      credits: updatedCredits,
      transaction,
      creditsGranted: promoCode.creditAmount,
    };
  });
}

/**
 * Get paginated transaction history for a user
 */
export async function getTransactionHistory(
  userId: string,
  page: number = 1,
  limit: number = 20
): Promise<{
  transactions: CreditTransaction[];
  total: number;
  page: number;
  limit: number;
  totalPages: number;
}> {
  const offset = (page - 1) * limit;

  const [transactions, total] = await Promise.all([
    prisma.creditTransaction.findMany({
      where: { userId },
      orderBy: { createdAt: 'desc' },
      take: limit,
      skip: offset,
    }),
    prisma.creditTransaction.count({
      where: { userId },
    }),
  ]);

  return {
    transactions,
    total,
    page,
    limit,
    totalPages: Math.ceil(total / limit),
  };
}

/**
 * Add credits manually (for admin/purchase use)
 */
export async function addCredits(
  userId: string,
  amount: number,
  description: string,
  type: CreditTransactionType = CreditTransactionType.PURCHASE
): Promise<{ credits: UserCredits; transaction: CreditTransaction }> {
  return prisma.$transaction(async (tx) => {
    // Get or create credits
    let credits = await tx.userCredits.findUnique({
      where: { userId },
    });

    if (!credits) {
      credits = await tx.userCredits.create({
        data: {
          userId,
          balance: 0,
          totalPurchased: 0,
          totalUsed: 0,
        },
      });
    }

    // Add credits
    const updatedCredits = await tx.userCredits.update({
      where: { userId },
      data: {
        balance: { increment: amount },
        totalPurchased: { increment: amount },
      },
    });

    // Log transaction
    const transaction = await tx.creditTransaction.create({
      data: {
        userId,
        type,
        amount,
        balanceBefore: credits.balance,
        balanceAfter: updatedCredits.balance,
        description,
      },
    });

    return { credits: updatedCredits, transaction };
  });
}

/**
 * Get full credit details for a user (balance + stats)
 */
export async function getCreditDetails(userId: string): Promise<{
  balance: number;
  totalPurchased: number;
  totalUsed: number;
  recentTransactions: CreditTransaction[];
}> {
  const credits = await getOrCreateUserCredits(userId);

  const recentTransactions = await prisma.creditTransaction.findMany({
    where: { userId },
    orderBy: { createdAt: 'desc' },
    take: 5,
  });

  return {
    balance: credits.balance,
    totalPurchased: credits.totalPurchased,
    totalUsed: credits.totalUsed,
    recentTransactions,
  };
}
