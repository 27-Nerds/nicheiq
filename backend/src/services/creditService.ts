import { prisma } from './db.js';
import {
  CreditTransactionType,
  JobStatus,
  StageStatus,
  Prisma,
  UserCredits,
  CreditTransaction,
  Job,
  BillingModel,
  DispatchKind,
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

/**
 * The price the client confirmed no longer matches the price actually in effect. Thrown from
 * INSIDE the charging transaction (see chargeForStageWithPriceCasInTx) — by the time this is
 * thrown, nothing has been charged and nothing else in that transaction commits.
 */
export class PriceChangedError extends Error {
  public expectedCost: number;
  public actualCost: number;

  constructor(expectedCost: number, actualCost: number) {
    super(`Price changed: client expected ${expectedCost}, actual price is ${actualCost}`);
    this.name = 'PriceChangedError';
    this.expectedCost = expectedCost;
    this.actualCost = actualCost;
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

/**
 * Guided mode pays for discovery a segment at a time, as the user authorizes each one — rather
 * than paying for the whole phase up front and arguing about refunds afterwards. The segments are
 * the three points where the user is actually present and deciding:
 *
 *   guided_s1     job creation      buys stage 1  (niche validation)   -> lands at G1
 *   guided_s2_4   Continue at G1    buys stages 2-4                    -> lands at G2
 *   guided_s5     Continue at G2    buys stage 5                       -> lands at selection
 *
 * NAMING IS LOad-BEARING: cost lookup builds its settings key mechanically as
 * `token_cost_${stage}` (see below), so these names are what produce `token_cost_guided_s1` etc.
 * Name them anything else and the admin override silently never loads — the panel would appear to
 * work while changing nothing.
 */
export const GUIDED_SEGMENTS = ['guided_s1', 'guided_s2_4', 'guided_s5'] as const;
export type GuidedSegment = (typeof GUIDED_SEGMENTS)[number];

/** How many pipeline stages each segment actually runs — the basis of the default split. */
const GUIDED_SEGMENT_WEIGHT: Record<GuidedSegment, number> = {
  guided_s1: 1,
  guided_s2_4: 3,
  guided_s5: 1,
};
const GUIDED_TOTAL_WEIGHT = 5; // stages 1..5 = the whole discovery phase

export type StageName =
  | 'discovery'
  | 'deep_research'
  | 'landing_page'
  | 'regenerate_ideas'
  // Selection-chat "generate an idea from your own idea" (plans/eager-meandering-feather.md).
  // FLAT, like regenerate_ideas — deliberately NOT inside the `guided` segment group, which is
  // discovery-segment-only pricing; folding this in there would corrupt the guided total and
  // BillingModel math. Numbered per-seed ledger stages (`seed_idea_1`, `seed_idea_2`, ...) look
  // their PRICE up under this flat name but record/refund under the numbered one — see
  // chargeForSeedIdeaInTx.
  | 'seed_idea'
  | GuidedSegment;

const DEFAULT_STAGE_COSTS: Record<Exclude<StageName, GuidedSegment>, number> = {
  discovery: 5,
  deep_research: 15,
  landing_page: 5,
  regenerate_ideas: 2,
  seed_idea: 2,
};

const STAGE_LABELS: Record<StageName, string> = {
  discovery: 'Discovery',
  deep_research: 'Deep Research',
  landing_page: 'Landing Page',
  regenerate_ideas: 'Generate More Ideas',
  seed_idea: 'Generate From Your Idea',
  guided_s1: 'Niche validation',
  guided_s2_4: 'Audience & pain analysis',
  guided_s5: 'Idea generation',
};

export function isGuidedSegment(stage: string): stage is GuidedSegment {
  return (GUIDED_SEGMENTS as readonly string[]).includes(stage);
}

/**
 * The default price of a guided segment: discovery's price, split in proportion to the work each
 * segment does. So a 5-credit discovery becomes 1 / 3 / 1 — NOT equal thirds, which would charge
 * the same for the segment that runs three stages as for the ones that run one.
 *
 * Floor each share, then give the remainder to the LAST segment, so the three always sum to
 * exactly the discovery price and a full guided run costs the same as a standard one.
 */
function deriveGuidedSegmentCost(discoveryCost: number, segment: GuidedSegment): number {
  const floors = GUIDED_SEGMENTS.map((s) =>
    Math.floor((discoveryCost * GUIDED_SEGMENT_WEIGHT[s]) / GUIDED_TOTAL_WEIGHT),
  );
  const remainder = discoveryCost - floors.reduce((a, b) => a + b, 0);
  const idx = GUIDED_SEGMENTS.indexOf(segment);
  return floors[idx] + (idx === GUIDED_SEGMENTS.length - 1 ? remainder : 0);
}

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
    // Exact integers only. parseInt would happily read "1.5" and "1abc" as 1 — a silent price
    // change nobody typed.
    if (/^\d+$/.test(setting.value.trim())) {
      const parsed = Number(setting.value.trim());
      if (Number.isSafeInteger(parsed) && parsed >= 0) return parsed;
    }
    console.warn(`[Credits] Ignoring non-integer price for ${stage}: ${JSON.stringify(setting.value)}`);
  }

  // Unset -> derive automatically from the discovery price ("if it's not set, do it
  // automatically"). Derived, not a static default, so an admin who re-prices discovery re-prices
  // the guided segments with it and the two can never silently disagree.
  if (isGuidedSegment(stage)) {
    const discoveryCost = await _getStageCostWithClient(client, 'discovery');
    return deriveGuidedSegmentCost(discoveryCost, stage);
  }

  return DEFAULT_STAGE_COSTS[stage];
}

/** The three guided prices, and their total. Used by the gate UI and the billing endpoint. */
export async function getGuidedSegmentCosts(): Promise<{
  guided_s1: number;
  guided_s2_4: number;
  guided_s5: number;
  total: number;
}> {
  const [s1, s24, s5] = await Promise.all(GUIDED_SEGMENTS.map((s) => getStageCost(s)));
  return { guided_s1: s1, guided_s2_4: s24, guided_s5: s5, total: s1 + s24 + s5 };
}

/** Which segment a Continue at this gate buys. G1 buys stages 2-4; G2 buys stage 5. */
export function segmentForGateContinue(gateStage: 1 | 4): GuidedSegment {
  return gateStage === 1 ? 'guided_s2_4' : 'guided_s5';
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
 * Charge for a stage inside an existing transaction, with a HARDENED price compare-and-swap.
 *
 * The plain pattern (gate-action's original guided-Continue check) read the price ONCE before
 * the transaction to compare against `expectedCost`, then let `chargeForStageInTx` read the
 * price AGAIN, separately, inside the transaction to actually charge. A reprice landing between
 * those two reads could still charge a number the CAS never saw — the check passed against a
 * price that was, by the time of the charge, already stale.
 *
 * This closes that gap by reading the price exactly ONCE, inside this same transaction, comparing
 * it to `expectedCost`, and charging with that identical number — there is no second read left to
 * race. `expectedCost` is REQUIRED (not optional): this helper exists specifically for money
 * paths where a missing price confirmation must 400 before ever reaching here, never fall through
 * to a charge.
 *
 * `priceStage` is the flat stage the price is looked up (and admin-priced) under; `ledgerStage`
 * is the stage the CreditTransaction is recorded under, which may be numbered (e.g. `seed_idea_2`)
 * so repeated attempts don't collide on the (job, type, stage, cycle) unique constraint.
 *
 * Unlike the numbered callers (seed idea, regeneration), a flat `ledgerStage` like a gate segment
 * (`guided_s2_4`) is charged under the SAME name every time — there is no per-attempt numbering to
 * dodge the unique constraint with. So if an earlier attempt at this exact stage already charged
 * (e.g. the charge committed but the subsequent enqueue failed, and compensation refunded it —
 * refunding adds an offsetting ledger row, it does not remove the original charge), a naive
 * cycle=0 retry would collide with that row and 500 with P2002 even though the money was already
 * made whole. Auto-detecting the next unused cycle — exactly the arithmetic `chargeForResume`
 * already does for a whole-job resume — is what lets that retry actually succeed.
 */
export async function chargeForStageWithPriceCasInTx(
  tx: Prisma.TransactionClient,
  userId: string,
  jobId: string,
  priceStage: StageName,
  ledgerStage: string,
  niche: string,
  expectedCost: number,
  description?: string,
): Promise<{ cost: number; transaction?: CreditTransaction }> {
  const cost = await _getStageCostWithClient(tx, priceStage);
  if (cost !== expectedCost) {
    throw new PriceChangedError(expectedCost, cost);
  }
  if (cost === 0) return { cost: 0 };

  const priorCharges = await tx.creditTransaction.findMany({
    where: { relatedJobId: jobId, type: CreditTransactionType.JOB_DEDUCTION, stage: ledgerStage },
    select: { cycle: true },
  });
  const cycle = priorCharges.length ? Math.max(...priorCharges.map((c) => c.cycle)) + 1 : 0;

  const transaction = await _chargeForStageImpl(tx, userId, jobId, ledgerStage, niche, cost, description, cycle);
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
 * Charge for a user-composed idea seed inside an existing transaction, with a required price CAS.
 * Mirrors chargeForRegenerationInTx's numbered-stage shape (regenerate_ideas_N), but MUST use the
 * price CAS: unlike regeneration, seed pricing is shown to the user as a specific number right
 * before they click, so the confirmed price and the charged price must be provably the same read.
 *
 * Looks the PRICE up under the flat `seed_idea` stage (what admins price), but records/refunds
 * under the numbered `seed_idea_${seedOrdinal}` ledger stage — a constant stage would collide
 * with the FIRST seed's charge on the (job, type, stage, cycle) unique constraint the moment a
 * second seed is submitted.
 */
export async function chargeForSeedIdeaInTx(
  tx: Prisma.TransactionClient,
  userId: string,
  jobId: string,
  seedOrdinal: number,
  niche: string,
  expectedCost: number,
): Promise<{ cost: number; transaction?: CreditTransaction }> {
  return chargeForStageWithPriceCasInTx(
    tx,
    userId,
    jobId,
    'seed_idea',
    `seed_idea_${seedOrdinal}`,
    niche,
    expectedCost,
    `Generate From Your Idea (#${seedOrdinal}): ${niche.substring(0, 100)}`,
  );
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
 * Refund credits for a numbered seed-idea stage (e.g., seed_idea_2).
 */
export async function refundForSeedIdeaStage(
  jobId: string,
  seedOrdinal: number,
): Promise<CreditTransaction | null> {
  return _refundForStageImpl(jobId, `seed_idea_${seedOrdinal}`);
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

      // Restore each portion of the charge to the bucket it actually came from.
      //
      // A charge can be SPLIT — say 4 credits of expiring monthly allowance plus 1 purchased. The
      // two halves are not the same kind of money, and a refund must not launder one into the
      // other:
      //
      //   monthly portion, SAME (unexpired) cycle -> back to the monthly allowance. Still expiring.
      //   monthly portion, cycle already ENDED    -> NOTHING. Those credits were use-it-or-lose-it
      //                                              and the period they belonged to is over. They
      //                                              cannot come back as anything.
      //   purchased portion                       -> ALWAYS back to the purchased balance. That is
      //                                              money the user actually paid; it is owed back
      //                                              regardless of when the refund happens.
      //
      // The previous version paid the whole refund into `balance` whenever the cycle had expired,
      // which turned expiring allowance into PERMANENT purchased credit. That was reachable on
      // purpose: burn a lapsing allowance on jobs at the end of the month, cancel them the next
      // month, and collect credits that never expire.
      const fromMonthly = unrefundedCharge.fromMonthly ?? 0;
      const fromPurchased = refundAmount - fromMonthly;
      const sameCycle =
        fromMonthly > 0 &&
        unrefundedCharge.monthlyPeriodStart != null &&
        row.monthlyAllowancePeriodStart != null &&
        unrefundedCharge.monthlyPeriodStart.getTime() === row.monthlyAllowancePeriodStart.getTime() &&
        row.monthlyAllowancePeriodEnd != null &&
        row.monthlyAllowancePeriodEnd.getTime() > Date.now();
      const monthlyRestore = sameCycle ? fromMonthly : 0;
      const purchasedRestore = fromPurchased;

      // What the user actually gets back. Less than the charge when a lapsed monthly portion is
      // written off — so the ledger row, the balance change and totalUsed must all agree on THIS
      // number, not on the original charge.
      const actualRefund = monthlyRestore + purchasedRestore;
      const availableBefore = spendableMonthly(row) + row.balance;

      if (actualRefund < refundAmount) {
        console.log(
          `[CreditService] Job ${jobId} stage ${stage}: writing off ${refundAmount - actualRefund} ` +
          `credit(s) of expired monthly allowance (refunding ${actualRefund} of ${refundAmount})`
        );
      }

      await tx.userCredits.update({
        where: { userId: job.userId! },
        data: {
          monthlyAllowance: { increment: monthlyRestore },
          balance: { increment: purchasedRestore },
          totalUsed: { decrement: actualRefund },
        },
      });

      return tx.creditTransaction.create({
        data: {
          userId: job.userId!,
          type: CreditTransactionType.REFUND,
          amount: actualRefund,
          balanceBefore: availableBefore,
          balanceAfter: availableBefore + actualRefund,
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
 *
 * `activeDispatchKind` is an optional hint for the SEED_IDEA case: unlike regeneration, a seed
 * op does not move the parent job out of AWAITING_SELECTION (the pool stays visible while it
 * runs), so jobStatus alone can never distinguish "this job is just sitting at selection" from
 * "this job is sitting at selection with a seed attempt in flight" — the dispatch kind is the
 * only signal that can. Callers that know the job's active dispatch (or the dispatch a callback
 * named) should pass its kind through; callers that don't simply omit it and fall through to the
 * existing heuristics unchanged.
 */
export function determineFailedStage(
  errorStage: number | null | undefined,
  jobStatus: string,
  activeDispatchKind?: DispatchKind | string | null,
): StageName | null {
  if (jobStatus === JobStatus.REGENERATING) return null; // Handled separately with numbered stages
  // Handled separately with numbered seed_idea_N stages — see chargeForSeedIdeaInTx /
  // refundForSeedIdeaStage. Refunding via the flat 'discovery'/'deep_research' guess below would
  // refund the WRONG charge (or none at all): the seed never paid for either of those stages.
  if (activeDispatchKind === DispatchKind.SEED_IDEA) return null;
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
  chatMode?: boolean,
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
        chatMode: chatMode ?? false,
        // The billing contract this run is sold under, fixed at creation and never changed.
        // Guided runs pay per segment as the user authorizes each one; everything else pays for
        // the whole discovery phase up front, exactly as before.
        //
        // Every money branch (Continue, cancel, failure, price display) reads this marker rather
        // than inferring from chatMode or a date — jobs that predate segment billing are stamped
        // DISCOVERY_PREPAID_V1 by the migration's default, so they can never be charged twice.
        billingModel: chatMode
          ? BillingModel.GUIDED_SEGMENTS_V1
          : BillingModel.DISCOVERY_PREPAID_V1,
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

    // What creating the job actually buys.
    //
    // Guided: only the first segment (stage 1, niche validation) — enough to reach the first
    // checkpoint. The user pays for the rest at the checkpoints, where they can see what they're
    // buying and decline. This is what makes the checkpoint mean something: before, all 5 credits
    // were taken here and Continue was free, so the gate could not gate spend at all.
    //
    // Everything else: the whole discovery phase, unchanged.
    const entryStage: StageName = chatMode ? 'guided_s1' : 'discovery';
    const chargeResult = await chargeForStageInTx(tx, userId, job.id, entryStage, niche);

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
