/**
 * Seed-idea money paths (plans/eager-meandering-feather.md, Phases 1-2):
 *
 *   - numbered seed_idea_N charge/refund, mirroring regenerate_ideas_N but with a REQUIRED
 *     price CAS (chargeForSeedIdeaInTx / refundForSeedIdeaStage)
 *   - the shared hardened CAS helper itself (chargeForStageWithPriceCasInTx): drift throws
 *     PriceChangedError before any credit moves; the happy path charges exactly the confirmed
 *     price
 *   - no P2002 collision between seed_idea_N and regenerate_ideas_N on the same job — the
 *     unique constraint is (jobId, type, stage, cycle), so the stage STRING is what has to
 *     stay distinct
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';

const mockUserCreditsFindUnique = vi.fn();
const mockUserCreditsUpsert = vi.fn();
const mockUserCreditsUpdate = vi.fn();
const mockCreditTransactionCreate = vi.fn();
const mockAppSettingsFindUnique = vi.fn();
// chargeForStageWithPriceCasInTx's cycle auto-detect reads prior charges for this exact ledger
// stage via tx.creditTransaction.findMany — distinct from the module-level mockCreditTransactionFindMany
// below (used by refundForSeedIdeaStage, which reaches for the module-level `prisma`, not `tx`).
const mockTxCreditTransactionFindMany = vi.fn();
const mockTxCreditTransactionFindFirst = vi.fn();
// refundForSeedIdeaStage (-> _refundForStageImpl) reaches for the module-level `prisma`
// directly rather than a `tx` param, unlike the charge helpers below.
const mockJobFindUnique = vi.fn();
const mockCreditTransactionFindMany = vi.fn();
const mockPrismaTransaction = vi.fn();

vi.mock('../db.js', () => ({
  prisma: {
    job: { findUnique: (...args: any[]) => mockJobFindUnique(...args) },
    creditTransaction: { findMany: (...args: any[]) => mockCreditTransactionFindMany(...args) },
    $transaction: (cb: any) => mockPrismaTransaction(cb),
  },
}));

const USER_ID = 'user-123';
const JOB_ID = 'job-seed-1';

// A minimal Prisma.TransactionClient stand-in — every seed money function under test takes `tx`
// as its first argument rather than reaching for the module-level `prisma`.
let tx: any;

beforeEach(() => {
  vi.clearAllMocks();

  tx = {
    userCredits: {
      upsert: (...args: any[]) => mockUserCreditsUpsert(...args),
      update: (...args: any[]) => mockUserCreditsUpdate(...args),
    },
    creditTransaction: {
      create: (...args: any[]) => mockCreditTransactionCreate(...args),
      findMany: (...args: any[]) => mockTxCreditTransactionFindMany(...args),
      findFirst: (...args: any[]) => mockTxCreditTransactionFindFirst(...args),
    },
    appSettings: {
      findUnique: (...args: any[]) => mockAppSettingsFindUnique(...args),
    },
    $queryRaw: async () => {
      const c = await mockUserCreditsFindUnique();
      return [
        {
          balance: c?.balance ?? 0,
          monthlyAllowance: c?.monthlyAllowance ?? 0,
          monthlyAllowancePeriodStart: c?.monthlyAllowancePeriodStart ?? null,
          monthlyAllowancePeriodEnd: c?.monthlyAllowancePeriodEnd ?? null,
        },
      ];
    },
  };

  mockUserCreditsUpsert.mockResolvedValue({});
  mockUserCreditsUpdate.mockResolvedValue({});
  mockUserCreditsFindUnique.mockResolvedValue({ balance: 50, monthlyAllowance: 0 });
  // No prior charge for this ledger stage by default — cycle auto-detect resolves to 0.
  mockTxCreditTransactionFindMany.mockResolvedValue([]);
  mockTxCreditTransactionFindFirst.mockResolvedValue(null);
  mockCreditTransactionCreate.mockImplementation(async (args: any) => ({
    id: `txn-${args.data.stage}`,
    ...args.data,
  }));
  // No admin override — seed_idea falls back to its default (2 credits).
  mockAppSettingsFindUnique.mockResolvedValue(null);

  mockJobFindUnique.mockResolvedValue({ userId: USER_ID, niche: 'test niche' });
  mockPrismaTransaction.mockImplementation(async (cb: any) => cb(tx));
});

describe('chargeForStageInTx — retryable stage cycles', () => {
  it('places a retried landing-page charge after the immutable refunded attempt', async () => {
    mockTxCreditTransactionFindFirst.mockResolvedValue({ cycle: 2 });
    const { chargeForStageInTx } = await import('../creditService.js');

    await chargeForStageInTx(
      tx,
      USER_ID,
      JOB_ID,
      'landing_page',
      'test niche',
      { nextCycle: true },
    );

    expect(mockTxCreditTransactionFindFirst).toHaveBeenCalledWith({
      where: {
        relatedJobId: JOB_ID,
        type: 'JOB_DEDUCTION',
        stage: 'landing_page',
      },
      orderBy: { cycle: 'desc' },
      select: { cycle: true },
    });
    expect(mockCreditTransactionCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({ stage: 'landing_page', cycle: 3 }),
      }),
    );
  });
});

describe('chargeForStageWithPriceCasInTx — the shared hardened CAS', () => {
  it('happy path: charges exactly the confirmed price, reading it once inside the transaction', async () => {
    const { chargeForStageWithPriceCasInTx } = await import('../creditService.js');

    const result = await chargeForStageWithPriceCasInTx(
      tx, USER_ID, JOB_ID, 'seed_idea', 'seed_idea_1', 'test niche', 2,
    );

    expect(result.cost).toBe(2);
    expect(mockCreditTransactionCreate).toHaveBeenCalledWith(
      expect.objectContaining({ data: expect.objectContaining({ amount: -2, stage: 'seed_idea_1' }) }),
    );
    // The ledger stage is the NUMBERED one; the price was looked up under the flat one — proven
    // by the default (2) actually being used with no admin override present.
    expect(mockUserCreditsUpdate).toHaveBeenCalledWith(
      expect.objectContaining({ data: expect.objectContaining({ balance: { decrement: 2 } }) }),
    );
  });

  it('drift: throws PriceChangedError and charges nothing', async () => {
    const { chargeForStageWithPriceCasInTx, PriceChangedError } = await import('../creditService.js');

    // Client confirmed 2 (the default), but an admin repriced seed_idea to 5 before this ran.
    mockAppSettingsFindUnique.mockResolvedValue({ value: '5' });

    await expect(
      chargeForStageWithPriceCasInTx(tx, USER_ID, JOB_ID, 'seed_idea', 'seed_idea_1', 'test niche', 2),
    ).rejects.toThrow(PriceChangedError);

    expect(mockCreditTransactionCreate).not.toHaveBeenCalled();
    expect(mockUserCreditsUpdate).not.toHaveBeenCalled();
  });

  it('the thrown error carries both the expected and actual price for the 409 body', async () => {
    const { chargeForStageWithPriceCasInTx, PriceChangedError } = await import('../creditService.js');
    mockAppSettingsFindUnique.mockResolvedValue({ value: '5' });

    try {
      await chargeForStageWithPriceCasInTx(tx, USER_ID, JOB_ID, 'seed_idea', 'seed_idea_1', 'test niche', 2);
      expect.unreachable('should have thrown');
    } catch (error) {
      expect(error).toBeInstanceOf(PriceChangedError);
      expect((error as InstanceType<typeof PriceChangedError>).expectedCost).toBe(2);
      expect((error as InstanceType<typeof PriceChangedError>).actualCost).toBe(5);
    }
  });

  // Money-loss fix #4: a gate-Continue segment (e.g. 'guided_s2_4') is charged under the SAME
  // flat ledger stage every time — unlike seed_idea_N/regenerate_ideas_N, there is no numbering
  // to dodge the unique (job, type, stage, cycle) constraint with. If an earlier attempt at this
  // exact stage already charged (its enqueue failed after the charge committed, and compensation
  // refunded it — a refund adds an offsetting row, it does not remove the original charge), a
  // naive cycle=0 retry would collide with that row and 500 with P2002. Auto-detecting the next
  // unused cycle is what lets the retry actually succeed instead.
  describe('cycle auto-detect (retry-after-failed-enqueue safety)', () => {
    it('charges at cycle=0 when no prior charge exists for this ledger stage', async () => {
      const { chargeForStageWithPriceCasInTx } = await import('../creditService.js');
      mockTxCreditTransactionFindMany.mockResolvedValue([]);

      await chargeForStageWithPriceCasInTx(tx, USER_ID, JOB_ID, 'guided_s2_4', 'guided_s2_4', 'test niche', 3);

      expect(mockCreditTransactionCreate).toHaveBeenCalledWith(
        expect.objectContaining({ data: expect.objectContaining({ stage: 'guided_s2_4', cycle: 0 }) }),
      );
    });

    it('charges at cycle=1 when a prior (refunded-or-not) charge already exists at cycle=0 — the retry-after-failed-enqueue case', async () => {
      const { chargeForStageWithPriceCasInTx } = await import('../creditService.js');
      // An earlier gate-Continue attempt charged this exact segment and its enqueue failed —
      // the charge row is still there (a refund, if any, is a separate ledger row, not a
      // deletion of this one).
      mockTxCreditTransactionFindMany.mockResolvedValue([{ cycle: 0 }]);

      await chargeForStageWithPriceCasInTx(tx, USER_ID, JOB_ID, 'guided_s2_4', 'guided_s2_4', 'test niche', 3);

      expect(mockTxCreditTransactionFindMany).toHaveBeenCalledWith(
        expect.objectContaining({
          where: expect.objectContaining({ relatedJobId: JOB_ID, stage: 'guided_s2_4' }),
        }),
      );
      expect(mockCreditTransactionCreate).toHaveBeenCalledWith(
        expect.objectContaining({ data: expect.objectContaining({ stage: 'guided_s2_4', cycle: 1 }) }),
      );
    });

    it('skips straight to the next unused cycle across multiple prior attempts', async () => {
      const { chargeForStageWithPriceCasInTx } = await import('../creditService.js');
      mockTxCreditTransactionFindMany.mockResolvedValue([{ cycle: 0 }, { cycle: 1 }]);

      await chargeForStageWithPriceCasInTx(tx, USER_ID, JOB_ID, 'guided_s2_4', 'guided_s2_4', 'test niche', 3);

      expect(mockCreditTransactionCreate).toHaveBeenCalledWith(
        expect.objectContaining({ data: expect.objectContaining({ stage: 'guided_s2_4', cycle: 2 }) }),
      );
    });
  });
});

describe('chargeForSeedIdeaInTx — numbered seed charges', () => {
  it('charges seed_idea_1 for the first seed, looking the price up under the flat seed_idea stage', async () => {
    const { chargeForSeedIdeaInTx } = await import('../creditService.js');

    const result = await chargeForSeedIdeaInTx(tx, USER_ID, JOB_ID, 1, 'test niche', 2);

    expect(result.cost).toBe(2);
    expect(mockAppSettingsFindUnique).toHaveBeenCalledWith({ where: { key: 'token_cost_seed_idea' } });
    expect(mockCreditTransactionCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({ stage: 'seed_idea_1', amount: -2, relatedJobId: JOB_ID }),
      }),
    );
  });

  it('a second seed on the same job charges seed_idea_2 — no collision with the first', async () => {
    const { chargeForSeedIdeaInTx } = await import('../creditService.js');

    await chargeForSeedIdeaInTx(tx, USER_ID, JOB_ID, 1, 'test niche', 2);
    await chargeForSeedIdeaInTx(tx, USER_ID, JOB_ID, 2, 'test niche', 2);

    const stages = mockCreditTransactionCreate.mock.calls.map((c) => c[0].data.stage);
    expect(stages).toEqual(['seed_idea_1', 'seed_idea_2']);
    // A constant 'seed_idea' ledger stage would have produced the SAME string twice here — which
    // is exactly the P2002 collision (unique on jobId+type+stage+cycle) the numbering exists to
    // avoid.
    expect(new Set(stages).size).toBe(2);
  });

  it('seed_idea_N and regenerate_ideas_N on the same job never share a ledger stage string', async () => {
    const { chargeForSeedIdeaInTx, chargeForRegenerationInTx } = await import('../creditService.js');

    await chargeForSeedIdeaInTx(tx, USER_ID, JOB_ID, 1, 'test niche', 2);
    await chargeForRegenerationInTx(tx, USER_ID, JOB_ID, 1, 'test niche', 2);

    const stages = mockCreditTransactionCreate.mock.calls.map((c) => c[0].data.stage);
    expect(stages).toEqual(['seed_idea_1', 'regenerate_ideas_1']);
    expect(new Set(stages).size).toBe(2);
  });

  it('rejects (PriceChangedError) when the confirmed price no longer matches — mirrors the shared CAS', async () => {
    const { chargeForSeedIdeaInTx, PriceChangedError } = await import('../creditService.js');
    mockAppSettingsFindUnique.mockResolvedValue({ value: '5' });

    await expect(chargeForSeedIdeaInTx(tx, USER_ID, JOB_ID, 1, 'test niche', 2))
      .rejects.toThrow(PriceChangedError);
    expect(mockCreditTransactionCreate).not.toHaveBeenCalled();
  });
});

describe('refundForSeedIdeaStage', () => {
  it('refunds the numbered seed_idea_2 charge, not seed_idea_1', async () => {
    const charge2 = { id: 'c2', amount: -2, stage: 'seed_idea_2', cycle: 0, fromMonthly: 0 };
    mockCreditTransactionFindMany.mockImplementation(async ({ where }: any) =>
      where.type === 'REFUND' ? [] : [charge2],
    );

    const { refundForSeedIdeaStage } = await import('../creditService.js');
    const refund = await refundForSeedIdeaStage(JOB_ID, 2);

    expect(refund).not.toBeNull();
    // The lookup itself is scoped to seed_idea_2 — a seed_idea_1 charge sitting on the same job
    // is never in scope for this call, so it can't accidentally be the one refunded.
    expect(mockCreditTransactionFindMany).toHaveBeenCalledWith(
      expect.objectContaining({ where: expect.objectContaining({ stage: 'seed_idea_2' }) }),
    );
    expect(mockCreditTransactionFindMany).not.toHaveBeenCalledWith(
      expect.objectContaining({ where: expect.objectContaining({ stage: 'seed_idea_1' }) }),
    );
    expect(mockCreditTransactionCreate).toHaveBeenCalledWith(
      expect.objectContaining({ data: expect.objectContaining({ stage: 'seed_idea_2', amount: 2 }) }),
    );
  });

  it('returns null when the seed ordinal was never charged', async () => {
    mockCreditTransactionFindMany.mockResolvedValue([]);

    const { refundForSeedIdeaStage } = await import('../creditService.js');
    const refund = await refundForSeedIdeaStage(JOB_ID, 7);

    expect(refund).toBeNull();
    expect(mockCreditTransactionCreate).not.toHaveBeenCalled();
  });
});

describe('determineFailedStage — seed case', () => {
  it('returns null when the active dispatch is SEED_IDEA (handled via numbered refund, not the flat guess)', async () => {
    const { determineFailedStage } = await import('../creditService.js');
    // AWAITING_SELECTION + no errorStage would otherwise fall through to the conservative
    // 'discovery' default — which the job never charged for a second time.
    expect(determineFailedStage(undefined, 'AWAITING_SELECTION', 'SEED_IDEA')).toBeNull();
  });

  it('unaffected when there is no active SEED_IDEA dispatch (existing behavior preserved)', async () => {
    const { determineFailedStage } = await import('../creditService.js');
    expect(determineFailedStage(undefined, 'AWAITING_SELECTION')).toBe('discovery');
    expect(determineFailedStage(undefined, 'RUNNING')).toBe('discovery');
    expect(determineFailedStage(3, 'RUNNING')).toBe('discovery');
  });
});
