import { describe, it, expect, vi, beforeEach } from 'vitest';

// ============================================
// Mock dependencies
// ============================================
const mockUserCreditsFindUnique = vi.fn();
const mockUserCreditsCreate = vi.fn();
const mockUserCreditsUpdate = vi.fn();
const mockJobCreate = vi.fn();
const mockCreditTransactionCreate = vi.fn();
const mockCreditTransactionUpdate = vi.fn();
const mockAppSettingsFindUnique = vi.fn();
const mockPrismaTransaction = vi.fn();
const mockJobFindUnique = vi.fn();
const mockCreditTransactionFindMany = vi.fn();
const mockCreditTransactionFindFirst = vi.fn();

vi.mock('../db.js', () => ({
  prisma: {
    $transaction: (...args: any[]) => mockPrismaTransaction(...args),
    job: {
      findUnique: (...args: any[]) => mockJobFindUnique(...args),
    },
    creditTransaction: {
      findMany: (...args: any[]) => mockCreditTransactionFindMany(...args),
      findFirst: (...args: any[]) => mockCreditTransactionFindFirst(...args),
    },
  },
}));

// ============================================
// Setup
// ============================================
const USER_ID = 'user-123';

beforeEach(() => {
  vi.clearAllMocks();

  // Default: user has enough credits
  const mockTx = {
    userCredits: {
      findUnique: mockUserCreditsFindUnique,
      create: mockUserCreditsCreate,
      update: mockUserCreditsUpdate,
      upsert: vi.fn().mockResolvedValue({}),
    },
    // _chargeForStageImpl now locks the row via `SELECT ... FOR UPDATE`. Derive the locked
    // row from the same findUnique mock so per-test balances still apply (monthly bucket = 0
    // in these tests, so available == balance).
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
    job: {
      create: mockJobCreate,
    },
    creditTransaction: {
      create: mockCreditTransactionCreate,
      update: mockCreditTransactionUpdate,
    },
    appSettings: {
      findUnique: mockAppSettingsFindUnique,
    },
  };

  mockPrismaTransaction.mockImplementation(async (cb: any) => cb(mockTx));

  mockUserCreditsFindUnique.mockResolvedValue({
    userId: USER_ID,
    balance: 50,
    totalPurchased: 100,
    totalUsed: 50,
  });

  mockUserCreditsUpdate.mockResolvedValue({
    userId: USER_ID,
    balance: 45,
    totalPurchased: 100,
    totalUsed: 55,
  });

  mockJobCreate.mockImplementation(async (args: any) => ({
    id: 'job-1',
    ...args.data,
    progress: args.data.progress?.create ?? [],
  }));

  mockCreditTransactionCreate.mockResolvedValue({
    id: 'txn-1',
    userId: USER_ID,
    type: 'JOB_DEDUCTION',
    amount: -5,
    stage: 'discovery',
  });

  mockCreditTransactionUpdate.mockResolvedValue({
    id: 'txn-1',
    relatedJobId: 'job-1',
  });

  // No admin override — use default costs
  mockAppSettingsFindUnique.mockResolvedValue(null);
});

// ============================================
// Tests
// ============================================
describe('createJobAndChargeDiscovery', () => {
  it('always creates 15 progress entries (no stage 15 — landing pages are on-demand)', async () => {
    const { createJobAndChargeDiscovery } = await import('../creditService.js');

    await createJobAndChargeDiscovery(USER_ID, 'test niche');

    const jobCreateCall = mockJobCreate.mock.calls[0][0];
    const progressEntries = jobCreateCall.data.progress.create;

    const stageNumbers = progressEntries.map((p: any) => p.stageNumber);
    expect(stageNumbers).not.toContain(15);
    expect(progressEntries).toHaveLength(15);
    expect(jobCreateCall.data.totalStages).toBe(15);
  });

  it('sets generateLandingPage to false', async () => {
    const { createJobAndChargeDiscovery } = await import('../creditService.js');

    await createJobAndChargeDiscovery(USER_ID, 'test niche');

    const jobCreateCall = mockJobCreate.mock.calls[0][0];
    expect(jobCreateCall.data.generateLandingPage).toBe(false);
  });

  it('charges the default discovery cost (5 credits)', async () => {
    const { createJobAndChargeDiscovery } = await import('../creditService.js');

    await createJobAndChargeDiscovery(USER_ID, 'test niche');

    // Should deduct 5 credits
    const updateCall = mockUserCreditsUpdate.mock.calls[0][0];
    expect(updateCall.data.balance.decrement).toBe(5);
    expect(updateCall.data.totalUsed.increment).toBe(5);
  });

  it('uses admin-configured cost when set', async () => {
    mockAppSettingsFindUnique.mockResolvedValue({ value: '3' });

    const { createJobAndChargeDiscovery } = await import('../creditService.js');

    await createJobAndChargeDiscovery(USER_ID, 'test niche');

    const updateCall = mockUserCreditsUpdate.mock.calls[0][0];
    expect(updateCall.data.balance.decrement).toBe(3);
  });

  it('throws InsufficientCreditsError when balance too low', async () => {
    mockUserCreditsFindUnique.mockResolvedValue({
      userId: USER_ID,
      balance: 2,
      totalPurchased: 10,
      totalUsed: 8,
    });

    const { createJobAndChargeDiscovery, InsufficientCreditsError } = await import('../creditService.js');

    await expect(createJobAndChargeDiscovery(USER_ID, 'test niche'))
      .rejects.toThrow(InsufficientCreditsError);
  });

  it('charges with the real job ID (no placeholder update needed)', async () => {
    const { createJobAndChargeDiscovery } = await import('../creditService.js');

    await createJobAndChargeDiscovery(USER_ID, 'test niche');

    // Transaction is created directly with the real job ID
    expect(mockCreditTransactionCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          relatedJobId: 'job-1',
        }),
      })
    );
    // No update needed since we pass the real ID upfront
    expect(mockCreditTransactionUpdate).not.toHaveBeenCalled();
  });
});

// ============================================
// Cycle-based refund tests
// ============================================
describe('refundForStage — cycle-based matching', () => {
  const JOB_ID = 'job-resume-1';

  function makeCharge(stage: string, cycle: number = 0, amount: number = -5) {
    return {
      id: `charge-${stage}-c${cycle}`,
      userId: USER_ID,
      type: 'JOB_DEDUCTION',
      amount,
      stage,
      cycle,
      relatedJobId: JOB_ID,
      createdAt: new Date('2026-04-10T09:00:00Z'),
    };
  }

  function makeRefund(stage: string, cycle: number = 0, amount: number = 5) {
    return {
      id: `refund-${stage}-c${cycle}`,
      userId: USER_ID,
      type: 'REFUND',
      amount,
      stage,
      cycle,
      relatedJobId: JOB_ID,
      createdAt: new Date('2026-04-10T09:01:00Z'),
    };
  }

  beforeEach(() => {
    mockJobFindUnique.mockResolvedValue({ userId: USER_ID, niche: 'test niche' });
    mockCreditTransactionCreate.mockImplementation(async (args: any) => ({
      id: 'new-refund',
      ...args.data,
    }));
    mockUserCreditsUpdate.mockResolvedValue({
      userId: USER_ID,
      balance: 55,
      totalPurchased: 100,
      totalUsed: 45,
    });
  });

  it('refunds a standard cycle=0 charge normally', async () => {
    const charge = makeCharge('discovery', 0);
    mockCreditTransactionFindMany
      .mockResolvedValueOnce([charge])
      .mockResolvedValueOnce([]);

    const { refundForStage } = await import('../creditService.js');
    const result = await refundForStage(JOB_ID, 'discovery');

    expect(result).not.toBeNull();
    expect(mockCreditTransactionCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          type: 'REFUND',
          stage: 'discovery',
          cycle: 0,
          amount: 5,
        }),
      })
    );
  });

  it('refunds cycle=1 charge when cycle=0 already refunded', async () => {
    mockCreditTransactionFindMany
      .mockResolvedValueOnce([makeCharge('discovery', 1), makeCharge('discovery', 0)])
      .mockResolvedValueOnce([makeRefund('discovery', 0)]);

    const { refundForStage } = await import('../creditService.js');
    const result = await refundForStage(JOB_ID, 'discovery');

    expect(result).not.toBeNull();
    expect(mockCreditTransactionCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          type: 'REFUND',
          stage: 'discovery',
          cycle: 1,
          amount: 5,
        }),
      })
    );
  });

  it('handles multiple resume cycles (0, 1, 2)', async () => {
    mockCreditTransactionFindMany
      .mockResolvedValueOnce([
        makeCharge('discovery', 2),
        makeCharge('discovery', 1),
        makeCharge('discovery', 0),
      ])
      .mockResolvedValueOnce([
        makeRefund('discovery', 0),
        makeRefund('discovery', 1),
      ]);

    const { refundForStage } = await import('../creditService.js');
    const result = await refundForStage(JOB_ID, 'discovery');

    expect(result).not.toBeNull();
    expect(mockCreditTransactionCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          stage: 'discovery',
          cycle: 2,
        }),
      })
    );
  });

  it('returns existing refund when all charges already refunded (idempotency)', async () => {
    const charge = makeCharge('discovery', 0);
    const refund = makeRefund('discovery', 0);

    mockCreditTransactionFindMany
      .mockResolvedValueOnce([charge])
      .mockResolvedValueOnce([refund]);

    const { refundForStage } = await import('../creditService.js');
    const result = await refundForStage(JOB_ID, 'discovery');

    expect(result).toEqual(refund);
    expect(mockCreditTransactionCreate).not.toHaveBeenCalled();
  });

  it('returns null when no charge exists for the stage', async () => {
    mockCreditTransactionFindMany
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([]);

    const { refundForStage } = await import('../creditService.js');
    const result = await refundForStage(JOB_ID, 'discovery');

    expect(result).toBeNull();
    expect(mockCreditTransactionCreate).not.toHaveBeenCalled();
  });

  it('returns null when job has no userId', async () => {
    mockJobFindUnique.mockResolvedValue(null);

    const { refundForStage } = await import('../creditService.js');
    const result = await refundForStage(JOB_ID, 'discovery');

    expect(result).toBeNull();
    expect(mockCreditTransactionFindMany).not.toHaveBeenCalled();
  });

  it('queries only the requested stage (no cross-contamination)', async () => {
    const charge = makeCharge('discovery', 0);
    mockCreditTransactionFindMany
      .mockResolvedValueOnce([charge])
      .mockResolvedValueOnce([]);

    const { refundForStage } = await import('../creditService.js');
    await refundForStage(JOB_ID, 'discovery');

    // Both findMany calls should filter by stage='discovery'
    expect(mockCreditTransactionFindMany).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({ stage: 'discovery' }),
      })
    );
  });

  it('refunds regenerate_ideas_2 at cycle=1 correctly', async () => {
    mockCreditTransactionFindMany
      .mockResolvedValueOnce([
        makeCharge('regenerate_ideas_2', 1, -2),
        makeCharge('regenerate_ideas_2', 0, -2),
      ])
      .mockResolvedValueOnce([makeRefund('regenerate_ideas_2', 0, 2)]);

    const { refundForRegenerationStage } = await import('../creditService.js');
    const result = await refundForRegenerationStage(JOB_ID, 2);

    expect(result).not.toBeNull();
    expect(mockCreditTransactionCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          stage: 'regenerate_ideas_2',
          cycle: 1,
          amount: 2,
        }),
      })
    );
  });

  it('uses human-readable label in refund description', async () => {
    const charge = makeCharge('discovery', 1);
    mockCreditTransactionFindMany
      .mockResolvedValueOnce([charge])
      .mockResolvedValueOnce([]);

    const { refundForStage } = await import('../creditService.js');
    await refundForStage(JOB_ID, 'discovery');

    expect(mockCreditTransactionCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          description: expect.stringContaining('Refund Discovery:'),
        }),
      })
    );
  });
});

// ============================================
// chargeForResume tests
// ============================================
describe('chargeForResume', () => {
  const JOB_ID = 'job-resume-1';

  beforeEach(() => {
    mockJobFindUnique.mockResolvedValue({ userId: USER_ID, niche: 'test niche' });
    mockCreditTransactionCreate.mockImplementation(async (args: any) => ({
      id: 'new-charge',
      ...args.data,
    }));
    mockUserCreditsUpdate.mockResolvedValue({
      userId: USER_ID,
      balance: 45,
      totalPurchased: 100,
      totalUsed: 55,
    });
  });

  it('re-charges at cycle=1 after cycle=0 refund', async () => {
    mockCreditTransactionFindMany
      .mockResolvedValueOnce([{ stage: 'discovery', cycle: 0, amount: -5, createdAt: new Date('2026-04-10T09:00:00Z') }])
      .mockResolvedValueOnce([{ stage: 'discovery', cycle: 0, amount: 5, createdAt: new Date('2026-04-10T09:01:00Z') }]);

    // Mock balance check
    const mockTopLevelUserCredits = vi.fn().mockResolvedValue({ userId: USER_ID, balance: 50 });
    const { prisma: mockPrisma } = await import('../db.js');
    (mockPrisma as any).userCredits = { findUnique: mockTopLevelUserCredits };

    const { chargeForResume } = await import('../creditService.js');
    const result = await chargeForResume(USER_ID, JOB_ID);

    expect(result).toEqual({ charged: true, amount: 5 });
    expect(mockCreditTransactionCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          type: 'JOB_DEDUCTION',
          stage: 'discovery',
          cycle: 1,
          amount: -5,
        }),
      })
    );
  });

  it('skips re-charge when unrefunded charge exists (user already paid)', async () => {
    // Charge at cycle=0, refund at cycle=0, charge at cycle=1 (unrefunded)
    mockCreditTransactionFindMany
      .mockResolvedValueOnce([
        { stage: 'discovery', cycle: 1, amount: -5, createdAt: new Date('2026-04-10T10:00:00Z') },
        { stage: 'discovery', cycle: 0, amount: -5, createdAt: new Date('2026-04-10T09:00:00Z') },
      ])
      .mockResolvedValueOnce([
        { stage: 'discovery', cycle: 0, amount: 5, createdAt: new Date('2026-04-10T09:01:00Z') },
      ]);

    const { chargeForResume } = await import('../creditService.js');
    const result = await chargeForResume(USER_ID, JOB_ID);

    expect(result).toEqual({ charged: false, amount: 0 });
    expect(mockPrismaTransaction).not.toHaveBeenCalled();
  });

  it('skips re-charge when no refund exists', async () => {
    mockCreditTransactionFindMany
      .mockResolvedValueOnce([{ stage: 'discovery', cycle: 0, amount: -5, createdAt: new Date() }])
      .mockResolvedValueOnce([]);

    const { chargeForResume } = await import('../creditService.js');
    const result = await chargeForResume(USER_ID, JOB_ID);

    expect(result).toEqual({ charged: false, amount: 0 });
  });

  it('only re-charges the refunded stage in a multi-stage job', async () => {
    // discovery(c=0) + deep_research(c=0), only deep_research refunded
    mockCreditTransactionFindMany
      .mockResolvedValueOnce([
        { stage: 'discovery', cycle: 0, amount: -5, createdAt: new Date('2026-04-10T09:00:00Z') },
        { stage: 'deep_research', cycle: 0, amount: -15, createdAt: new Date('2026-04-10T10:00:00Z') },
      ])
      .mockResolvedValueOnce([
        { stage: 'deep_research', cycle: 0, amount: 15, createdAt: new Date('2026-04-10T10:01:00Z') },
      ]);

    const mockTopLevelUserCredits = vi.fn().mockResolvedValue({ userId: USER_ID, balance: 50 });
    const { prisma: mockPrisma } = await import('../db.js');
    (mockPrisma as any).userCredits = { findUnique: mockTopLevelUserCredits };

    const { chargeForResume } = await import('../creditService.js');
    const result = await chargeForResume(USER_ID, JOB_ID);

    expect(result).toEqual({ charged: true, amount: 15 });
    expect(mockCreditTransactionCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          stage: 'deep_research',
          cycle: 1,
          amount: -15,
        }),
      })
    );
  });

  it('throws InsufficientCreditsError when balance too low', async () => {
    mockCreditTransactionFindMany
      .mockResolvedValueOnce([{ stage: 'discovery', cycle: 0, amount: -5, createdAt: new Date() }])
      .mockResolvedValueOnce([{ stage: 'discovery', cycle: 0, amount: 5, createdAt: new Date() }]);

    // Resume now routes through _chargeForStageImpl, which checks availability against the
    // FOR-UPDATE-locked row (the tx-level findUnique the $queryRaw mock derives from).
    mockUserCreditsFindUnique.mockResolvedValue({ userId: USER_ID, balance: 2, monthlyAllowance: 0 });

    const { chargeForResume, InsufficientCreditsError } = await import('../creditService.js');

    await expect(chargeForResume(USER_ID, JOB_ID)).rejects.toThrow(InsufficientCreditsError);
  });
});
