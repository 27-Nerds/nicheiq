/**
 * Billing-history copy: no ledger line may show a raw stage token.
 *
 * `STAGE_LABELS` is exhaustive over `StageName`, so the old `?? stage` fallback beside it could
 * only ever fire for values OUTSIDE that type — and that is most of the ledger: the numbered
 * per-attempt stages (`regenerate_ideas_3`, `seed_idea_2`) the money paths deliberately write,
 * and the operational stages (`admin`, `promo`, `purchase`, `subscription`) plus hand-inserted
 * `repair_bad_refund_<id>` rows that never came from a pipeline run at all. Users' statements
 * read `regenerate_ideas_1: <niche>`.
 *
 * The charge and its refund go through the SAME resolver, so a refund line names exactly the
 * line it reverses — ordinal included.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';

const mockUserCreditsFindUnique = vi.fn();
const mockUserCreditsUpsert = vi.fn();
const mockUserCreditsUpdate = vi.fn();
const mockCreditTransactionCreate = vi.fn();
const mockCreditTransactionFindUnique = vi.fn();
const mockAppSettingsFindUnique = vi.fn();
const mockTxCreditTransactionFindMany = vi.fn();
const mockTxCreditTransactionFindFirst = vi.fn();

vi.mock('../db.js', () => ({
  prisma: {
    job: { findUnique: vi.fn() },
    creditTransaction: { findMany: vi.fn() },
    $transaction: vi.fn(),
  },
}));

const USER_ID = 'user-123';
const JOB_ID = 'job-copy-1';
const NICHE = 'ceramic studio owners';

let tx: any;

/** The description string the ledger row was created with. */
function lastDescription(): string {
  const calls = mockCreditTransactionCreate.mock.calls;
  return calls[calls.length - 1][0].data.description;
}

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
      findUnique: (...args: any[]) => mockCreditTransactionFindUnique(...args),
    },
    appSettings: { findUnique: (...args: any[]) => mockAppSettingsFindUnique(...args) },
    $queryRaw: async () => {
      const c = await mockUserCreditsFindUnique();
      return [
        {
          balance: c?.balance ?? 0,
          monthlyAllowance: c?.monthlyAllowance ?? 0,
          monthlyAllowancePeriodStart: null,
          monthlyAllowancePeriodEnd: null,
        },
      ];
    },
  };

  mockUserCreditsUpsert.mockResolvedValue({});
  mockUserCreditsUpdate.mockResolvedValue({});
  mockUserCreditsFindUnique.mockResolvedValue({ balance: 50, monthlyAllowance: 0 });
  mockTxCreditTransactionFindMany.mockResolvedValue([]);
  mockTxCreditTransactionFindFirst.mockResolvedValue(null);
  mockAppSettingsFindUnique.mockResolvedValue(null);
  mockCreditTransactionCreate.mockImplementation(async (args: any) => ({
    id: `txn-${args.data.stage}`,
    ...args.data,
  }));
});

/** A stored charge row, as refundChargeInTx reads it back. */
function chargeRow(stage: string, overrides: Record<string, unknown> = {}) {
  return {
    id: `charge-${stage}`,
    userId: USER_ID,
    type: 'JOB_DEDUCTION',
    amount: -2,
    stage,
    cycle: 0,
    fromMonthly: 0,
    monthlyPeriodStart: null,
    relatedJobId: JOB_ID,
    reversedBy: null,
    relatedJob: { niche: NICHE },
    ...overrides,
  };
}

describe('stageDisplayLabel', () => {
  it('labels the base stage of a numbered per-attempt stage and keeps the ordinal', async () => {
    const { stageDisplayLabel } = await import('../creditService.js');

    expect(stageDisplayLabel('regenerate_ideas_1')).toBe('Add Another Idea Batch (#1)');
    expect(stageDisplayLabel('regenerate_ideas_9')).toBe('Add Another Idea Batch (#9)');
    expect(stageDisplayLabel('seed_idea_2')).toBe('Generate From Your Idea (#2)');
  });

  it('does not mistake a guided segment for a numbered stage', async () => {
    const { stageDisplayLabel } = await import('../creditService.js');

    expect(stageDisplayLabel('guided_s1')).toBe('Niche validation');
    expect(stageDisplayLabel('guided_s5')).toBe('Idea generation');
  });

  it('gives the operational stages real copy', async () => {
    const { stageDisplayLabel } = await import('../creditService.js');

    expect(stageDisplayLabel('admin')).toBe('Account adjustment');
    expect(stageDisplayLabel('promo')).toBe('Promo code');
    expect(stageDisplayLabel('purchase')).toBe('Credit purchase');
    expect(stageDisplayLabel('subscription')).toBe('Subscription credits');
  });

  it('never shows the internal handle of a hand-inserted repair row', async () => {
    const { stageDisplayLabel } = await import('../creditService.js');

    const label = stageDisplayLabel('repair_bad_refund_72c5cc0a');
    expect(label).toBe('Billing correction');
    expect(label).not.toContain('72c5cc0a');
  });

  it('humanizes an unclassifiable value instead of echoing the token', async () => {
    const { stageDisplayLabel } = await import('../creditService.js');

    expect(stageDisplayLabel('some_future_stage')).toBe('Some future stage');
    expect(stageDisplayLabel('')).toBe('Credit adjustment');
    expect(stageDisplayLabel(null)).toBe('Credit adjustment');
  });
});

describe('ledger descriptions — charge and refund read as one pair', () => {
  it('writes human copy for a numbered regeneration charge', async () => {
    const { chargeForRegenerationInTx } = await import('../creditService.js');

    await chargeForRegenerationInTx(tx, USER_ID, JOB_ID, 3, NICHE, 2);

    expect(lastDescription()).toBe(`Add Another Idea Batch (#3): ${NICHE}`);
    expect(lastDescription()).not.toContain('regenerate_ideas');
  });

  it('refunds a numbered regeneration under the exact wording of the charge', async () => {
    const { chargeForRegenerationInTx, refundChargeInTx } = await import('../creditService.js');

    await chargeForRegenerationInTx(tx, USER_ID, JOB_ID, 3, NICHE, 2);
    const chargeCopy = lastDescription();

    mockCreditTransactionFindUnique.mockResolvedValue(chargeRow('regenerate_ideas_3'));
    await refundChargeInTx(tx, 'charge-regenerate_ideas_3');

    expect(lastDescription()).toBe(`Refund ${chargeCopy}`);
    expect(lastDescription()).not.toContain('regenerate_ideas');
  });

  it('writes human copy for a numbered seed charge and its refund', async () => {
    const { chargeForSeedIdeaInTx, refundChargeInTx } = await import('../creditService.js');

    await chargeForSeedIdeaInTx(tx, USER_ID, JOB_ID, 2, NICHE, 2);
    expect(lastDescription()).toBe(`Generate From Your Idea (#2): ${NICHE}`);

    mockCreditTransactionFindUnique.mockResolvedValue(chargeRow('seed_idea_2'));
    await refundChargeInTx(tx, 'charge-seed_idea_2');

    expect(lastDescription()).toBe(`Refund Generate From Your Idea (#2): ${NICHE}`);
    expect(lastDescription()).not.toContain('seed_idea');
  });

  it('never leaves an operational stage token on a refund line', async () => {
    const { refundChargeInTx } = await import('../creditService.js');

    mockCreditTransactionFindUnique.mockResolvedValue(chargeRow('admin'));
    await refundChargeInTx(tx, 'charge-admin');
    expect(lastDescription()).toBe(`Refund Account adjustment: ${NICHE}`);

    mockCreditTransactionFindUnique.mockResolvedValue(chargeRow('promo', { id: 'charge-promo' }));
    await refundChargeInTx(tx, 'charge-promo');
    expect(lastDescription()).toBe(`Refund Promo code: ${NICHE}`);
  });

  it('names the stage in the resume re-charge line', async () => {
    const { chargeForStageInTx } = await import('../creditService.js');

    await chargeForStageInTx(tx, USER_ID, JOB_ID, 'deep_research', NICHE);

    expect(lastDescription()).toBe(`Deep Research: ${NICHE}`);
  });
});
