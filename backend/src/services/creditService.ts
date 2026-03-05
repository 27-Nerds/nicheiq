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
import { PIPELINE_STAGES, DISCOVERY_PHASE_MAX_STAGE } from '../types/job.js';

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
// Per-Stage Token Charging
// ============================================

export type StageName = 'discovery' | 'deep_research' | 'landing_page' | 'regenerate_ideas';

const DEFAULT_STAGE_COSTS: Record<StageName, number> = {
  discovery: 5,
  deep_research: 15,
  landing_page: 5,
  regenerate_ideas: 2,
};

const STAGE_LABELS: Record<StageName, string> = {
  discovery: 'Discovery',
  deep_research: 'Deep Research',
  landing_page: 'Landing Page',
  regenerate_ideas: 'Generate More Ideas',
};

/**
 * Internal helper: get cost for a stage using any Prisma client (regular or tx).
 */
async function _getStageCostWithClient(
  client: Prisma.TransactionClient | typeof prisma,
  stage: StageName,
): Promise<number> {
  const setting = await client.appSettings.findUnique({
    where: { key: 'token_cost_' + stage },
  });
  if (setting?.value != null) {
    const parsed = parseInt(setting.value, 10);
    if (!isNaN(parsed) && parsed >= 0) return parsed;
  }
  return DEFAULT_STAGE_COSTS[stage];
}

/**
 * Get the cost for a stage (checks admin overrides, falls back to defaults)
 */
export async function getStageCost(stage: StageName): Promise<number> {
  return _getStageCostWithClient(prisma, stage);
}

/**
 * Charge a user for a specific stage (standalone transaction).
 * Idempotent via unique constraint on (jobId, JOB_DEDUCTION, stage).
 * If cost is 0, skips transaction entirely.
 */
export async function chargeForStage(
  userId: string,
  jobId: string,
  stage: StageName,
  niche: string,
): Promise<{ cost: number; transaction?: CreditTransaction }> {
  const cost = await getStageCost(stage);
  if (cost === 0) return { cost: 0 };

  const transaction = await prisma.$transaction(async (tx) => {
    return _chargeForStageImpl(tx, userId, jobId, stage, niche, cost);
  });

  return { cost, transaction };
}

/**
 * Charge for a stage inside an existing Prisma transaction.
 * Use this when the charge must be atomic with other operations (e.g. job creation, state transitions).
 */
export async function chargeForStageInTx(
  tx: Prisma.TransactionClient,
  userId: string,
  jobId: string,
  stage: StageName,
  niche: string,
): Promise<{ cost: number; transaction?: CreditTransaction }> {
  const cost = await _getStageCostWithClient(tx, stage);

  if (cost === 0) return { cost: 0 };

  const transaction = await _chargeForStageImpl(tx, userId, jobId, stage, niche, cost);
  return { cost, transaction };
}

/**
 * Internal implementation for charging a stage. Works with any Prisma client (regular or tx).
 */
async function _chargeForStageImpl(
  tx: Prisma.TransactionClient,
  userId: string,
  jobId: string,
  stage: string,
  niche: string,
  cost: number,
  description?: string,
): Promise<CreditTransaction> {
  // 1. Get or create credits record
  let credits = await tx.userCredits.findUnique({ where: { userId } });
  if (!credits) {
    credits = await tx.userCredits.create({
      data: { userId, balance: 0, totalPurchased: 0, totalUsed: 0 },
    });
  }

  // 2. Check balance
  if (credits.balance < cost) {
    throw new InsufficientCreditsError(credits.balance, cost);
  }

  // 3. Deduct credits
  const updatedCredits = await tx.userCredits.update({
    where: { userId },
    data: {
      balance: { decrement: cost },
      totalUsed: { increment: cost },
    },
  });

  // 4. Create transaction record (unique constraint prevents double-charge)
  return tx.creditTransaction.create({
    data: {
      userId,
      type: CreditTransactionType.JOB_DEDUCTION,
      amount: -cost,
      balanceBefore: credits.balance,
      balanceAfter: updatedCredits.balance,
      relatedJobId: jobId,
      stage,
      description: description ?? `${STAGE_LABELS[stage as StageName] ?? stage}: ${niche.substring(0, 100)}`,
    },
  });
}

/**
 * Charge for a regeneration inside an existing transaction.
 * Uses numbered stage strings (regenerate_ideas_1, regenerate_ideas_2, etc.)
 * to allow multiple regenerations per job.
 */
export async function chargeForRegenerationInTx(
  tx: Prisma.TransactionClient,
  userId: string,
  jobId: string,
  regenerationNumber: number,
  niche: string,
): Promise<CreditTransaction> {
  const cost = await _getStageCostWithClient(tx, 'regenerate_ideas');
  if (cost === 0) {
    // Still create a zero-cost transaction record for audit
    return _chargeForStageImpl(tx, userId, jobId, `regenerate_ideas_${regenerationNumber}`, niche, 0, `Generate More Ideas (#${regenerationNumber}): ${niche.substring(0, 100)}`);
  }
  return _chargeForStageImpl(tx, userId, jobId, `regenerate_ideas_${regenerationNumber}`, niche, cost, `Generate More Ideas (#${regenerationNumber}): ${niche.substring(0, 100)}`);
}

/**
 * Refund credits for a specific stage of a job.
 * Only refunds if: (a) an original charge exists and (b) no refund for that stage yet.
 */
export async function refundForStage(
  jobId: string,
  stage: StageName,
): Promise<CreditTransaction | null> {
  return _refundForStageImpl(jobId, stage);
}

/**
 * Refund credits for a numbered regeneration stage (e.g., regenerate_ideas_2).
 */
export async function refundForRegenerationStage(
  jobId: string,
  regenerationNumber: number,
): Promise<CreditTransaction | null> {
  return _refundForStageImpl(jobId, `regenerate_ideas_${regenerationNumber}`);
}

/**
 * Internal implementation for refunding a stage. Works with any stage string.
 * Only refunds if: (a) an original charge exists and (b) no refund for that stage yet.
 */
async function _refundForStageImpl(
  jobId: string,
  stage: string,
): Promise<CreditTransaction | null> {
  // Find the job to get userId
  const job = await prisma.job.findUnique({
    where: { id: jobId },
    select: { userId: true, niche: true },
  });

  if (!job?.userId) return null;

  // Find the original charge for this stage
  const originalCharge = await prisma.creditTransaction.findFirst({
    where: {
      relatedJobId: jobId,
      type: CreditTransactionType.JOB_DEDUCTION,
      stage,
    },
  });

  if (!originalCharge) {
    console.log(`[CreditService] No charge found for job ${jobId} stage ${stage} — nothing to refund`);
    return null;
  }

  // Check if already refunded for this stage
  const existingRefund = await prisma.creditTransaction.findFirst({
    where: {
      relatedJobId: jobId,
      type: CreditTransactionType.REFUND,
      stage,
    },
  });

  if (existingRefund) {
    console.log(`[CreditService] Job ${jobId} stage ${stage} already refunded`);
    return existingRefund;
  }

  const refundAmount = Math.abs(originalCharge.amount);

  try {
    return await prisma.$transaction(async (tx) => {
      const credits = await tx.userCredits.findUnique({
        where: { userId: job.userId! },
      });

      if (!credits) return null;

      const updatedCredits = await tx.userCredits.update({
        where: { userId: job.userId! },
        data: {
          balance: { increment: refundAmount },
          totalUsed: { decrement: refundAmount },
        },
      });

      return tx.creditTransaction.create({
        data: {
          userId: job.userId!,
          type: CreditTransactionType.REFUND,
          amount: refundAmount,
          balanceBefore: credits.balance,
          balanceAfter: updatedCredits.balance,
          relatedJobId: jobId,
          stage,
          description: `Refund ${STAGE_LABELS[stage as StageName] ?? stage}: ${job.niche?.substring(0, 100)}`,
        },
      });
    });
  } catch (error) {
    if (error instanceof Prisma.PrismaClientKnownRequestError && error.code === 'P2002') {
      console.log(`[CreditService] Job ${jobId} stage ${stage} refund race condition — returning existing`);
      return prisma.creditTransaction.findFirst({
        where: { relatedJobId: jobId, type: CreditTransactionType.REFUND, stage },
      });
    }
    throw error;
  }
}

/**
 * Map numeric errorStage + job status to the StageName that should be refunded.
 */
export function determineFailedStage(
  errorStage: number | null | undefined,
  jobStatus: string,
): StageName | null {
  if (jobStatus === JobStatus.REGENERATING) return null; // Handled separately with numbered stages
  if (errorStage === 15) return 'landing_page';
  if (errorStage != null && errorStage > DISCOVERY_PHASE_MAX_STAGE) return 'deep_research';
  if (errorStage != null && errorStage <= DISCOVERY_PHASE_MAX_STAGE) return 'discovery';
  // Fallback heuristics based on status
  if (jobStatus === JobStatus.RUNNING_PHASE2) return 'deep_research';
  if (jobStatus === JobStatus.RUNNING) return 'discovery';
  return 'discovery'; // conservative default
}

// ============================================
// Job Creation (replaces createJobWithCreditDeduction)
// ============================================

/**
 * Create a job and charge for discovery in a single atomic transaction.
 * Always excludes stage 15 (landing page is on-demand).
 */
export async function createJobAndChargeDiscovery(
  userId: string,
  niche: string,
  allowedProjectTypes?: string[],
  jobMode?: string,
): Promise<{ job: Job; transaction?: CreditTransaction }> {
  const stages = PIPELINE_STAGES.filter(s => s.number !== 15);

  return prisma.$transaction(async (tx) => {
    // Create the job first so we have a real ID for the FK
    const job = await tx.job.create({
      data: {
        niche,
        userId,
        allowedProjectTypes: allowedProjectTypes as Prisma.InputJsonValue,
        generateLandingPage: false,
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
        progress: { orderBy: { stageNumber: 'asc' } },
        assets: true,
      },
    });

    // Charge for discovery with the real job ID (rolls back job on insufficient credits)
    const chargeResult = await chargeForStageInTx(tx, userId, job.id, 'discovery', niche);

    return { job, transaction: chargeResult.transaction };
  });
}

/**
 * Legacy wrapper - refund credits for a failed job using stage-aware logic.
 * Determines the failed stage and refunds accordingly.
 */
export async function refundCreditsForJob(
  jobId: string,
  _creditAmount: number = 1
): Promise<CreditTransaction | null> {
  const job = await prisma.job.findUnique({
    where: { id: jobId },
    select: { userId: true, niche: true, status: true, errorStage: true },
  });

  if (!job?.userId) return null;

  const failedStage = determineFailedStage(job.errorStage, job.status);
  if (!failedStage) return null;

  return refundForStage(jobId, failedStage);
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
        stage: 'promo',
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
  if (amount <= 0) {
    throw new Error(`addCredits requires a positive amount, got ${amount}`);
  }

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

    // Determine stage based on type
    const stage = type === CreditTransactionType.PURCHASE ? 'purchase'
      : type === CreditTransactionType.ADMIN_ADJUSTMENT ? 'admin'
      : 'purchase';

    // Log transaction
    const transaction = await tx.creditTransaction.create({
      data: {
        userId,
        type,
        amount,
        balanceBefore: credits.balance,
        balanceAfter: updatedCredits.balance,
        stage,
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
