import { describe, it, expect, vi, beforeEach } from 'vitest';

// ============================================
// Mock dependencies
// ============================================
const mockUserCreditsFindUnique = vi.fn();
const mockUserCreditsCreate = vi.fn();
const mockUserCreditsUpdate = vi.fn();
const mockJobCreate = vi.fn();
const mockCreditTransactionCreate = vi.fn();
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
    },
  };

  mockPrismaTransaction.mockImplementation(async (cb: any) => cb(mockTx));

  mockUserCreditsFindUnique.mockResolvedValue({
    userId: USER_ID,
    balance: 10,
    totalPurchased: 20,
    totalUsed: 10,
  });

  mockUserCreditsUpdate.mockResolvedValue({
    userId: USER_ID,
    balance: 9,
    totalPurchased: 20,
    totalUsed: 11,
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
    amount: -1,
  });
});

// ============================================
// Tests
// ============================================
describe('createJobWithCreditDeduction — conditional stage 11', () => {
  it('generateLandingPage=true → creates 16 progress entries (includes stage 11)', async () => {
    const { createJobWithCreditDeduction } = await import('../creditService.js');

    await createJobWithCreditDeduction(USER_ID, 'test niche', 1, undefined, true);

    const jobCreateCall = mockJobCreate.mock.calls[0][0];
    const progressEntries = jobCreateCall.data.progress.create;

    // Should include stage 11
    const stageNumbers = progressEntries.map((p: any) => p.stageNumber);
    expect(stageNumbers).toContain(11);
    expect(progressEntries).toHaveLength(16);
    expect(jobCreateCall.data.totalStages).toBe(16);
  });

  it('generateLandingPage=false → creates 15 progress entries (no stage 11)', async () => {
    const { createJobWithCreditDeduction } = await import('../creditService.js');

    await createJobWithCreditDeduction(USER_ID, 'test niche', 1, undefined, false);

    const jobCreateCall = mockJobCreate.mock.calls[0][0];
    const progressEntries = jobCreateCall.data.progress.create;

    // Should NOT include stage 11
    const stageNumbers = progressEntries.map((p: any) => p.stageNumber);
    expect(stageNumbers).not.toContain(11);
    expect(progressEntries).toHaveLength(15);
    expect(jobCreateCall.data.totalStages).toBe(15);
  });

  it('generateLandingPage=undefined → defaults to true (16 stages)', async () => {
    const { createJobWithCreditDeduction } = await import('../creditService.js');

    await createJobWithCreditDeduction(USER_ID, 'test niche', 1, undefined, undefined);

    const jobCreateCall = mockJobCreate.mock.calls[0][0];
    const progressEntries = jobCreateCall.data.progress.create;

    const stageNumbers = progressEntries.map((p: any) => p.stageNumber);
    expect(stageNumbers).toContain(11);
    expect(progressEntries).toHaveLength(16);
    expect(jobCreateCall.data.totalStages).toBe(16);
  });

  it('job.create progress array contains stageNumber: 11 only when landing page enabled', async () => {
    const { createJobWithCreditDeduction } = await import('../creditService.js');

    // With landing page
    await createJobWithCreditDeduction(USER_ID, 'niche with landing', 1, undefined, true);
    const withLanding = mockJobCreate.mock.calls[0][0].data.progress.create;
    expect(withLanding.some((p: any) => p.stageNumber === 11)).toBe(true);

    mockJobCreate.mockClear();

    // Without landing page
    await createJobWithCreditDeduction(USER_ID, 'niche without landing', 1, undefined, false);
    const withoutLanding = mockJobCreate.mock.calls[0][0].data.progress.create;
    expect(withoutLanding.some((p: any) => p.stageNumber === 11)).toBe(false);
  });

  it('generateLandingPage sets the generateLandingPage flag on job data', async () => {
    const { createJobWithCreditDeduction } = await import('../creditService.js');

    await createJobWithCreditDeduction(USER_ID, 'test niche', 1, undefined, false);

    const jobCreateCall = mockJobCreate.mock.calls[0][0];
    expect(jobCreateCall.data.generateLandingPage).toBe(false);
  });
});
