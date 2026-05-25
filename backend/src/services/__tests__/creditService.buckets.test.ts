import { describe, it, expect, vi, beforeEach } from 'vitest';

// Verifies the monthly-allowance bucket: monthly-first deduction, expiry gate, the bucket
// split recorded on the ledger, the InsufficientCreditsError breakdown, and resetMonthlyAllowance
// idempotency. Prisma is mocked; the FOR-UPDATE locked row is supplied via the $queryRaw mock.

const txUpsert = vi.fn().mockResolvedValue({});
const txUpdate = vi.fn().mockResolvedValue({});
const txCreate = vi.fn().mockResolvedValue({ id: 'txn' });
const txUpdateMany = vi.fn().mockResolvedValue({ count: 1 });
const txFindUnique = vi.fn();
const appSettingsFindUnique = vi.fn().mockResolvedValue(null);
const prismaTransaction = vi.fn();
let lockedRow: any;

const mockTx = {
  userCredits: { upsert: txUpsert, update: txUpdate, findUnique: txFindUnique, updateMany: txUpdateMany },
  creditTransaction: { create: txCreate },
  appSettings: { findUnique: appSettingsFindUnique },
  $queryRaw: async () => [lockedRow],
};

vi.mock('../db.js', () => ({
  prisma: {
    $transaction: (cb: any) => prismaTransaction(cb),
    appSettings: { findUnique: (...a: any[]) => appSettingsFindUnique(...a) },
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
  txUpsert.mockResolvedValue({});
  txUpdate.mockResolvedValue({});
  txCreate.mockResolvedValue({ id: 'txn' });
  txUpdateMany.mockResolvedValue({ count: 1 });
  appSettingsFindUnique.mockResolvedValue(null); // default stage costs
  prismaTransaction.mockImplementation(async (cb: any) => cb(mockTx));
  lockedRow = { balance: 0, monthlyAllowance: 0, monthlyAllowancePeriodStart: null, monthlyAllowancePeriodEnd: null };
});

const future = () => new Date(Date.now() + 86_400_000);
const past = () => new Date(Date.now() - 86_400_000);

describe('monthly-first deduction', () => {
  it('spends monthly allowance before purchased balance and records the split', async () => {
    const periodStart = new Date('2026-05-01T00:00:00Z');
    lockedRow = { balance: 100, monthlyAllowance: 3, monthlyAllowancePeriodStart: periodStart, monthlyAllowancePeriodEnd: future() };

    const { chargeForStage } = await import('../creditService.js');
    await chargeForStage('u1', 'job1', 'discovery', 'niche'); // discovery cost = 5

    // monthly 3 spent fully (decrement 3), remaining 2 from purchased balance
    const updateData = txUpdate.mock.calls[0][0].data;
    expect(updateData.monthlyAllowance).toEqual({ decrement: 3 });
    expect(updateData.balance).toEqual({ decrement: 2 });
    expect(updateData.totalUsed).toEqual({ increment: 5 });

    const ledger = txCreate.mock.calls[0][0].data;
    expect(ledger.fromMonthly).toBe(3);
    expect(ledger.monthlyPeriodStart).toEqual(periodStart);
    expect(ledger.balanceBefore).toBe(103); // available = 3 + 100
    expect(ledger.balanceAfter).toBe(98);
  });

  it('treats EXPIRED monthly allowance as 0 (not spendable) and zeroes it out', async () => {
    lockedRow = { balance: 100, monthlyAllowance: 50, monthlyAllowancePeriodStart: past(), monthlyAllowancePeriodEnd: past() };

    const { chargeForStage } = await import('../creditService.js');
    await chargeForStage('u1', 'job1', 'discovery', 'niche');

    const updateData = txUpdate.mock.calls[0][0].data;
    expect(updateData.monthlyAllowance).toBe(0); // expired → cleared, not used
    expect(updateData.balance).toEqual({ decrement: 5 }); // full cost from purchased
    const ledger = txCreate.mock.calls[0][0].data;
    expect(ledger.fromMonthly).toBe(0);
    expect(ledger.balanceBefore).toBe(100); // expired monthly excluded from available
  });

  it('throws InsufficientCreditsError with the bucket breakdown when total is short', async () => {
    lockedRow = { balance: 1, monthlyAllowance: 2, monthlyAllowancePeriodStart: new Date(), monthlyAllowancePeriodEnd: future() };

    const { chargeForStage, InsufficientCreditsError } = await import('../creditService.js');
    await expect(chargeForStage('u1', 'job1', 'discovery', 'niche')).rejects.toMatchObject({
      name: 'InsufficientCreditsError',
      currentBalance: 3,
      required: 5,
      monthlyAllowance: 2,
      purchasedBalance: 1,
    });
    expect(InsufficientCreditsError).toBeTruthy();
    expect(txUpdate).not.toHaveBeenCalled();
  });
});

describe('resetMonthlyAllowance', () => {
  it('OVERWRITES monthly allowance and writes a SUBSCRIPTION_GRANT ledger row', async () => {
    txFindUnique.mockResolvedValue({ balance: 10, monthlyAllowance: 4, monthlyAllowancePeriodEnd: future() });
    txUpdateMany.mockResolvedValue({ count: 1 });
    const start = new Date('2026-06-01T00:00:00Z');
    const end = new Date('2026-07-01T00:00:00Z');

    const { resetMonthlyAllowance } = await import('../creditService.js');
    const res = await resetMonthlyAllowance('u1', 50, start, end, 'in_123', 'Monthly');

    expect(res.applied).toBe(true);
    expect(txUpdateMany.mock.calls[0][0].data).toMatchObject({
      monthlyAllowance: 50,
      monthlyAllowancePeriodStart: start,
      monthlyAllowancePeriodEnd: end,
    });
    const ledger = txCreate.mock.calls[0][0].data;
    expect(ledger.type).toBe('SUBSCRIPTION_GRANT');
    expect(ledger.amount).toBe(50);
    expect(ledger.stripeInvoiceId).toBe('in_123');
  });

  it('is a no-op when the cycle was already granted (updateMany matched 0 rows)', async () => {
    txFindUnique.mockResolvedValue({ balance: 10, monthlyAllowance: 50, monthlyAllowancePeriodEnd: future() });
    txUpdateMany.mockResolvedValue({ count: 0 });

    const { resetMonthlyAllowance } = await import('../creditService.js');
    const res = await resetMonthlyAllowance('u1', 50, new Date(), future(), 'in_123', 'Monthly');

    expect(res.applied).toBe(false);
    expect(txCreate).not.toHaveBeenCalled(); // no duplicate grant ledger row
  });
});
