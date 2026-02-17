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

vi.mock('../db.js', () => ({
  prisma: {
    $transaction: (...args: any[]) => mockPrismaTransaction(...args),
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
