/**
 * refundForStage — bucket-aware refund rule.
 *
 * A charge can be SPLIT across two kinds of money: monthly allowance (use-it-or-lose-it,
 * expires at the period end) and purchased balance (real money, never expires). A refund must
 * restore each portion to the bucket it actually came from, not launder one into the other:
 *
 *   monthly portion + SAME unexpired cycle -> back to monthlyAllowance (still expiring)
 *   monthly portion + cycle already ENDED  -> written off, refunded as nothing
 *   purchased portion                      -> always back to balance
 *
 * The old behaviour paid the whole refund into `balance` once the cycle had expired, which
 * turned expiring allowance into permanent purchased credit — exploitable by burning a lapsing
 * allowance at month-end and cancelling the jobs next month to collect credits that never expire.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { CreditTransactionType } from '@prisma/client';

const mockJobFindUnique = vi.fn();
const mockCreditFindMany = vi.fn();
const mockQueryRaw = vi.fn();
const mockUserCreditsUpdate = vi.fn();
const mockCreditTransactionCreate = vi.fn();

vi.mock('../db.js', () => ({
  prisma: {
    job: { findUnique: (a: any) => mockJobFindUnique(a) },
    creditTransaction: { findMany: (a: any) => mockCreditFindMany(a) },
    $transaction: async (fn: any) =>
      fn({
        $queryRaw: (...args: any[]) => mockQueryRaw(...args),
        userCredits: { update: (a: any) => mockUserCreditsUpdate(a) },
        creditTransaction: { create: (a: any) => mockCreditTransactionCreate(a) },
      }),
  },
}));

const JOB = 'job-1';
const USER = 'user-1';

/** The unrefunded charge under test — set per test, read by the findMany mock. */
let charges: Array<Record<string, unknown>> = [];

beforeEach(() => {
  vi.clearAllMocks();
  charges = [];
  mockJobFindUnique.mockResolvedValue({ userId: USER, niche: 'Test Niche' });
  // No refunds recorded yet for this stage — every test starts from a fresh, unrefunded charge.
  mockCreditFindMany.mockImplementation(async (a: any) => {
    if (a.where.type === CreditTransactionType.JOB_DEDUCTION) return charges;
    return [];
  });
  mockUserCreditsUpdate.mockResolvedValue({});
  mockCreditTransactionCreate.mockImplementation(async (a: any) => ({ id: 'refund-1', ...a.data }));
});

describe('refundForStage — bucket rules', () => {
  it('same unexpired cycle: the monthly portion goes back as monthly', async () => {
    const periodStart = new Date('2026-07-01T00:00:00Z');
    const periodEnd = new Date('2026-08-01T00:00:00Z'); // future

    charges = [
      { amount: -5, fromMonthly: 4, monthlyPeriodStart: periodStart, cycle: 0 },
    ];
    mockQueryRaw.mockResolvedValue([
      {
        balance: 10,
        monthlyAllowance: 20,
        monthlyAllowancePeriodStart: periodStart, // same cycle as the charge
        monthlyAllowancePeriodEnd: periodEnd,
      },
    ]);

    const { refundForStage } = await import('../creditService.js');
    const refund = await refundForStage(JOB, 'discovery');

    expect(mockUserCreditsUpdate).toHaveBeenCalledWith(
      expect.objectContaining({
        where: { userId: USER },
        data: expect.objectContaining({
          monthlyAllowance: { increment: 4 },
          balance: { increment: 1 },
          totalUsed: { decrement: 5 },
        }),
      }),
    );
    expect(refund?.amount).toBe(5);
    expect(refund?.type).toBe(CreditTransactionType.REFUND);
  });

  it('expired cycle: the monthly portion is written off, the purchased portion is not (anti-laundering rule)', async () => {
    // This is the exploit path the rule closes: an expired monthly portion must NOT fall through
    // into `balance`, where it would become permanent purchased credit.
    const chargePeriodStart = new Date('2026-06-01T00:00:00Z'); // the cycle the charge was made in
    const currentPeriodStart = new Date('2026-07-01T00:00:00Z'); // that cycle has since rolled over
    const currentPeriodEnd = new Date('2026-08-01T00:00:00Z');

    charges = [
      { amount: -5, fromMonthly: 4, monthlyPeriodStart: chargePeriodStart, cycle: 0 },
    ];
    mockQueryRaw.mockResolvedValue([
      {
        balance: 10,
        monthlyAllowance: 20,
        monthlyAllowancePeriodStart: currentPeriodStart, // rolled over — different cycle
        monthlyAllowancePeriodEnd: currentPeriodEnd,
      },
    ]);

    const { refundForStage } = await import('../creditService.js');
    const refund = await refundForStage(JOB, 'discovery');

    expect(mockUserCreditsUpdate).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          monthlyAllowance: { increment: 0 },
          balance: { increment: 1 }, // ONLY the purchased portion — not the full 5
          totalUsed: { decrement: 1 },
        }),
      }),
    );
    expect(refund?.amount).toBe(1);
  });

  it('a fully-purchased charge is refunded in full regardless of cycle', async () => {
    const oldPeriodStart = new Date('2026-06-01T00:00:00Z');
    const currentPeriodStart = new Date('2026-07-01T00:00:00Z');
    const currentPeriodEnd = new Date('2026-08-01T00:00:00Z');

    charges = [
      { amount: -5, fromMonthly: 0, monthlyPeriodStart: null, cycle: 0 },
    ];
    mockQueryRaw.mockResolvedValue([
      {
        balance: 10,
        monthlyAllowance: 20,
        monthlyAllowancePeriodStart: currentPeriodStart,
        monthlyAllowancePeriodEnd: currentPeriodEnd,
      },
    ]);
    void oldPeriodStart;

    const { refundForStage } = await import('../creditService.js');
    const refund = await refundForStage(JOB, 'discovery');

    expect(mockUserCreditsUpdate).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          monthlyAllowance: { increment: 0 },
          balance: { increment: 5 },
          totalUsed: { decrement: 5 },
        }),
      }),
    );
    expect(refund?.amount).toBe(5);
  });

  it('a fully-monthly charge on an expired cycle refunds nothing', async () => {
    const chargePeriodStart = new Date('2026-06-01T00:00:00Z');
    const currentPeriodStart = new Date('2026-07-01T00:00:00Z'); // rolled over
    const currentPeriodEnd = new Date('2026-08-01T00:00:00Z');

    charges = [
      { amount: -5, fromMonthly: 5, monthlyPeriodStart: chargePeriodStart, cycle: 0 },
    ];
    mockQueryRaw.mockResolvedValue([
      {
        balance: 10,
        monthlyAllowance: 20,
        monthlyAllowancePeriodStart: currentPeriodStart,
        monthlyAllowancePeriodEnd: currentPeriodEnd,
      },
    ]);

    const { refundForStage } = await import('../creditService.js');
    const refund = await refundForStage(JOB, 'discovery');

    expect(mockUserCreditsUpdate).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          monthlyAllowance: { increment: 0 },
          balance: { increment: 0 },
          totalUsed: { decrement: 0 },
        }),
      }),
    );
    expect(refund?.amount).toBe(0);
  });
});
