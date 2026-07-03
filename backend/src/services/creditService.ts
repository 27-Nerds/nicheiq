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
  /** Total AVAILABLE = spendable monthly allowance + purchased balance. */
  public currentBalance: number;
  public required: number;
  public monthlyAllowance: number;
  public purchasedBalance: number;

  constructor(
    currentBalance: number,
    required: number,
    opts?: { monthlyAllowance?: number; purchasedBalance?: number },
  ) {
    super(`Insufficient credits: have ${currentBalance}, need ${required}`);
    this.name = 'InsufficientCreditsError';
    this.currentBalance = currentBalance;
    this.required = required;
    this.monthlyAllowance = opts?.monthlyAllowance ?? 0;
    this.purchasedBalance = opts?.purchasedBalance ?? currentBalance;
  }
}

// ============================================
// Credit-bucket helpers (monthly allowance + purchased balance)
// ============================================

/** Monthly allowance is use-it-or-lose-it: spendable only while its period hasn't ended. */
function spendableMonthly(c: { monthlyAllowance: number; monthlyAllowancePeriodEnd: Date | null }): number {
  if (c.monthlyAllowancePeriodEnd && c.monthlyAllowancePeriodEnd.getTime() > Date.now()) {
    return c.monthlyAllowance;
  }
  return 0;
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
  cycle: number = 0,
): Promise<CreditTransaction> {
  // 1. Ensure the row exists, then lock it FOR UPDATE so concurrent charges serialize
  //    (prevents lost-update races + negative balances; the DB CHECK is a final backstop).
  await tx.userCredits.upsert({
    where: { userId },
    create: { userId, balance: 0, totalPurchased: 0, totalUsed: 0, monthlyAllowance: 0 },
    update: {},
  });
  const locked = await tx.$queryRaw<
    Array<{ balance: number; monthlyAllowance: number; monthlyAllowancePeriodStart: Date | null; monthlyAllowancePeriodEnd: Date | null }>
  >`SELECT "balance", "monthlyAllowance", "monthlyAllowancePeriodStart", "monthlyAllowancePeriodEnd"
    FROM "UserCredits" WHERE "userId" = ${userId} FOR UPDATE`;
  const row = locked[0];

  // 2. Monthly-first, expiry-aware availability check.
  const monthly = spendableMonthly(row);
  const available = monthly + row.balance;
  if (available < cost) {
    throw new InsufficientCreditsError(available, cost, {
      monthlyAllowance: monthly,
      purchasedBalance: row.balance,
    });
  }

  // 3. Deduct monthly-first, then purchased. If the monthly period has expired, zero it out
  //    (use-it-or-lose-it) in the same write.
  const fromMonthly = Math.min(monthly, cost);
  const fromPurchased = cost - fromMonthly;
  const expired = monthly === 0 && row.monthlyAllowance > 0;
  await tx.userCredits.update({
    where: { userId },
    data: {
      monthlyAllowance: expired ? 0 : { decrement: fromMonthly },
      balance: { decrement: fromPurchased },
      totalUsed: { increment: cost },
    },
  });

  // 4. Ledger row. balanceBefore/After = total AVAILABLE; record the bucket split + origin cycle.
  return tx.creditTransaction.create({
    data: {
      userId,
      type: CreditTransactionType.JOB_DEDUCTION,
      amount: -cost,
      balanceBefore: available,
      balanceAfter: available - cost,
      fromMonthly,
      monthlyPeriodStart: fromMonthly > 0 ? row.monthlyAllowancePeriodStart : null,
      relatedJobId: jobId,
      stage,
      cycle,
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
 * Internal implementation for refunding a stage. Uses cycle-based matching:
 * finds the highest-cycle unrefunded charge for the given stage and refunds it.
 */
async function _refundForStageImpl(
  jobId: string,
  stage: string,
): Promise<CreditTransaction | null> {
  const job = await prisma.job.findUnique({
    where: { id: jobId },
    select: { userId: true, niche: true },
  });

  if (!job?.userId) return null;

  // Fetch charges and refunds for this specific stage in parallel
  const [charges, refunds] = await Promise.all([
    prisma.creditTransaction.findMany({
      where: { relatedJobId: jobId, type: CreditTransactionType.JOB_DEDUCTION, stage },
      orderBy: { cycle: 'desc' },
    }),
    prisma.creditTransaction.findMany({
      where: { relatedJobId: jobId, type: CreditTransactionType.REFUND, stage },
    }),
  ]);

  const refundedCycles = new Set(refunds.map(r => r.cycle));
  const unrefundedCharge = charges.find(c => !refundedCycles.has(c.cycle));

  if (!unrefundedCharge) {
    if (charges.length === 0) {
      console.log(`[CreditService] No charge found for job ${jobId} stage ${stage} — nothing to refund`);
      return null;
    }
    console.log(`[CreditService] Job ${jobId} stage ${stage} already refunded`);
    return refunds.sort((a, b) => b.cycle - a.cycle)[0] ?? null;
  }

  const refundAmount = Math.abs(unrefundedCharge.amount);
  const label = STAGE_LABELS[stage as StageName] ?? stage;

  try {
    return await prisma.$transaction(async (tx) => {
      const locked = await tx.$queryRaw<
        Array<{ balance: number; monthlyAllowance: number; monthlyAllowancePeriodStart: Date | null; monthlyAllowancePeriodEnd: Date | null }>
      >`SELECT "balance", "monthlyAllowance", "monthlyAllowancePeriodStart", "monthlyAllowancePeriodEnd"
        FROM "UserCredits" WHERE "userId" = ${job.userId!} FOR UPDATE`;
      const row = locked[0];
      if (!row) return null;

      // Restore to the ORIGINATING bucket. The monthly portion goes back to the monthly
      // allowance ONLY if it's still the same (unexpired) cycle — otherwise those
      // use-it-or-lose-it credits are gone and the whole refund lands in purchased. This
      // closes the monthly→purchased laundering vector (same-cycle monthly stays monthly)
      // without resurrecting expired monthly credits into a new cycle.
      const fromMonthly = unrefundedCharge.fromMonthly ?? 0;
      const sameCycle =
        fromMonthly > 0 &&
        unrefundedCharge.monthlyPeriodStart != null &&
        row.monthlyAllowancePeriodStart != null &&
        unrefundedCharge.monthlyPeriodStart.getTime() === row.monthlyAllowancePeriodStart.getTime() &&
        row.monthlyAllowancePeriodEnd != null &&
        row.monthlyAllowancePeriodEnd.getTime() > Date.now();
      const monthlyRestore = sameCycle ? fromMonthly : 0;
      const purchasedRestore = refundAmount - monthlyRestore;
      const availableBefore = spendableMonthly(row) + row.balance;

      await tx.userCredits.update({
        where: { userId: job.userId! },
        data: {
          monthlyAllowance: { increment: monthlyRestore },
          balance: { increment: purchasedRestore },
          totalUsed: { decrement: refundAmount },
        },
      });

      return tx.creditTransaction.create({
        data: {
          userId: job.userId!,
          type: CreditTransactionType.REFUND,
          amount: refundAmount,
          balanceBefore: availableBefore,
          balanceAfter: availableBefore + refundAmount,
          fromMonthly: monthlyRestore,
          relatedJobId: jobId,
          stage,
          cycle: unrefundedCharge.cycle,
          description: `Refund ${label}: ${job.niche?.substring(0, 100)}`,
        },
      });
    });
  } catch (error) {
    if (error instanceof Prisma.PrismaClientKnownRequestError && error.code === 'P2002') {
      console.log(`[CreditService] Job ${jobId} stage ${stage} cycle ${unrefundedCharge.cycle} refund race condition — returning existing`);
      return prisma.creditTransaction.findFirst({
        where: { relatedJobId: jobId, type: CreditTransactionType.REFUND, stage, cycle: unrefundedCharge.cycle },
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
  entryMode?: string,
  ideaFocus?: string,
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
        entryMode: entryMode || null,
        ideaFocus: ideaFocus || null,
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

/**
 * Determine if a resume requires re-charging and charge if needed.
 * Uses cycle-based matching: a refund is "unmatched" if no charge exists at cycle + 1.
 */
export async function chargeForResume(
  userId: string,
  jobId: string,
): Promise<{ charged: boolean; amount: number }> {
  const [allCharges, allRefunds] = await Promise.all([
    prisma.creditTransaction.findMany({
      where: { relatedJobId: jobId, type: CreditTransactionType.JOB_DEDUCTION },
    }),
    prisma.creditTransaction.findMany({
      where: { relatedJobId: jobId, type: CreditTransactionType.REFUND },
    }),
  ]);

  // Find the most recent refund that hasn't been re-charged at the next cycle
  const sortedRefunds = [...allRefunds].sort((a, b) => b.createdAt.getTime() - a.createdAt.getTime());
  const unmatchedRefund = sortedRefunds.find(refund => {
    return !allCharges.some(c => c.stage === refund.stage && c.cycle === refund.cycle + 1);
  });

  if (!unmatchedRefund) {
    return { charged: false, amount: 0 };
  }

  const nextCycle = unmatchedRefund.cycle + 1;
  const refundAmount = Math.abs(unmatchedRefund.amount);
  const job = await prisma.job.findUnique({ where: { id: jobId }, select: { niche: true } });

  try {
    await prisma.$transaction(async (tx) => {
      // Route through the shared monthly-first deduction: it does the availability check,
      // records the bucket split, and enforces the unique (job,stage,cycle) constraint.
      await _chargeForStageImpl(
        tx,
        userId,
        jobId,
        unmatchedRefund.stage,
        job?.niche ?? '',
        refundAmount,
        `Resume: re-charge ${STAGE_LABELS[unmatchedRefund.stage as StageName] ?? unmatchedRefund.stage}`,
        nextCycle,
      );
    });

    console.log(`[CreditService] Re-charged ${refundAmount} credits for job ${jobId} stage ${unmatchedRefund.stage} cycle ${nextCycle}`);
    return { charged: true, amount: refundAmount };
  } catch (error) {
    if (error instanceof Prisma.PrismaClientKnownRequestError && error.code === 'P2002') {
      console.log(`[CreditService] Resume charge already exists for job ${jobId} (concurrent request)`);
      return { charged: false, amount: 0 };
    }
    throw error; // InsufficientCreditsError etc. propagate to the caller
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
      monthlyAllowance: 0,
    },
    update: {}, // No-op if exists
  });
}

/**
 * Get user's total AVAILABLE balance = spendable monthly allowance + purchased balance.
 * (Expired monthly credits count as 0 — see spendableMonthly.) Returns 0 if no record.
 */
export async function getUserBalance(userId: string): Promise<number> {
  const credits = await prisma.userCredits.findUnique({
    where: { userId },
    select: { balance: true, monthlyAllowance: true, monthlyAllowancePeriodEnd: true },
  });
  if (!credits) return 0;
  return spendableMonthly(credits) + credits.balance;
}

/**
 * Reset the subscription monthly allowance to `amount` for a billing cycle.
 * Idempotent on `monthlyAllowancePeriodStart` (re-delivered invoice → no-op). OVERWRITES the
 * allowance (use-it-or-lose-it); never touches the purchased `balance`. Whole op is one
 * transaction so the allowance update + audit ledger row commit together.
 */
export async function resetMonthlyAllowance(
  userId: string,
  amount: number,
  periodStart: Date,
  periodEnd: Date,
  invoiceId: string | null,
  reason: string,
): Promise<{ applied: boolean }> {
  return prisma.$transaction(async (tx) => {
    await tx.userCredits.upsert({
      where: { userId },
      create: { userId, balance: 0, totalPurchased: 0, totalUsed: 0, monthlyAllowance: 0 },
      update: {},
    });

    const before = await tx.userCredits.findUnique({ where: { userId } });

    // Conditional update = idempotency guard (a re-delivered invoice has the same periodStart).
    const res = await tx.userCredits.updateMany({
      where: {
        userId,
        OR: [{ monthlyAllowancePeriodStart: null }, { monthlyAllowancePeriodStart: { not: periodStart } }],
      },
      data: {
        monthlyAllowance: amount,
        monthlyAllowancePeriodStart: periodStart,
        monthlyAllowancePeriodEnd: periodEnd,
      },
    });
    if (res.count === 0) return { applied: false }; // already granted for this cycle

    if (amount > 0 && before) {
      const availableBefore = spendableMonthly(before) + before.balance;
      const availableAfter = amount + before.balance; // new monthly (period in future) + purchased
      try {
        await tx.creditTransaction.create({
          data: {
            userId,
            type: CreditTransactionType.SUBSCRIPTION_GRANT,
            amount,
            balanceBefore: availableBefore,
            balanceAfter: availableAfter,
            stage: 'subscription',
            description: reason,
            stripeInvoiceId: invoiceId,
          },
        });
      } catch (error) {
        // Unique stripeInvoiceId → a concurrent delivery already wrote the grant ledger row.
        if (!(error instanceof Prisma.PrismaClientKnownRequestError && error.code === 'P2002')) throw error;
      }
    }
    return { applied: true };
  });
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
  type: CreditTransactionType = CreditTransactionType.PURCHASE,
  opts?: { stripeCheckoutSessionId?: string; stripeInvoiceId?: string },
): Promise<{ credits: UserCredits; transaction: CreditTransaction }> {
  if (amount <= 0) {
    throw new Error(`addCredits requires a positive amount, got ${amount}`);
  }

  const stage = type === CreditTransactionType.ADMIN_ADJUSTMENT ? 'admin' : 'purchase';

  try {
    return await prisma.$transaction(async (tx) => {
      await tx.userCredits.upsert({
        where: { userId },
        create: { userId, balance: 0, totalPurchased: 0, totalUsed: 0, monthlyAllowance: 0 },
        update: {},
      });
      const before = (await tx.userCredits.findUnique({ where: { userId } }))!;
      const availableBefore = spendableMonthly(before) + before.balance;

      // Ledger FIRST so the unique stripe id (if any) rolls back the whole tx on a duplicate
      // delivery — no double credit. balanceBefore/After = total AVAILABLE.
      const transaction = await tx.creditTransaction.create({
        data: {
          userId,
          type,
          amount,
          balanceBefore: availableBefore,
          balanceAfter: availableBefore + amount,
          stage,
          description,
          stripeCheckoutSessionId: opts?.stripeCheckoutSessionId ?? null,
          stripeInvoiceId: opts?.stripeInvoiceId ?? null,
        },
      });

      const credits = await tx.userCredits.update({
        where: { userId },
        data: {
          balance: { increment: amount },
          totalPurchased: { increment: amount },
        },
      });

      return { credits, transaction };
    });
  } catch (error) {
    // Duplicate Stripe-driven grant (unique stripeCheckoutSessionId/stripeInvoiceId) → already
    // credited; return the existing row without double-crediting.
    if (
      error instanceof Prisma.PrismaClientKnownRequestError &&
      error.code === 'P2002' &&
      (opts?.stripeCheckoutSessionId || opts?.stripeInvoiceId)
    ) {
      const existing = await prisma.creditTransaction.findFirst({
        where: opts.stripeCheckoutSessionId
          ? { stripeCheckoutSessionId: opts.stripeCheckoutSessionId }
          : { stripeInvoiceId: opts.stripeInvoiceId },
      });
      const credits = await getOrCreateUserCredits(userId);
      if (existing) return { credits, transaction: existing };
    }
    throw error;
  }
}

/**
 * Get full credit details for a user (balance + stats)
 */
export async function getCreditDetails(userId: string): Promise<{
  balance: number; // = available (back-compat: monthly spendable + purchased)
  available: number;
  monthlyAllowance: number; // spendable this cycle (0 if expired)
  purchasedBalance: number;
  monthlyAllowancePeriodEnd: Date | null; // "resets on"
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

  const monthly = spendableMonthly(credits);
  const available = monthly + credits.balance;
  return {
    balance: available,
    available,
    monthlyAllowance: monthly,
    purchasedBalance: credits.balance,
    monthlyAllowancePeriodEnd: credits.monthlyAllowancePeriodEnd,
    totalPurchased: credits.totalPurchased,
    totalUsed: credits.totalUsed,
    recentTransactions,
  };
}
