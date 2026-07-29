import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockJobUpdateMany = vi.fn();
const mockJobFindUnique = vi.fn();
const mockDispatchUpdateMany = vi.fn();
const mockDispatchUpdate = vi.fn();
const mockReceiptUpsert = vi.fn();
const mockReceiptUpdate = vi.fn();
const mockRefundForRegenerationStage = vi.fn();
const mockRefundChargeInTx = vi.fn();

const transactionClient = {
  job: {
    updateMany: (...args: any[]) => mockJobUpdateMany(...args),
    findUnique: (...args: any[]) => mockJobFindUnique(...args),
  },
  jobDispatch: {
    updateMany: (...args: any[]) => mockDispatchUpdateMany(...args),
    update: (...args: any[]) => mockDispatchUpdate(...args),
  },
  chatMessage: {
    upsert: (...args: any[]) => mockReceiptUpsert(...args),
    update: (...args: any[]) => mockReceiptUpdate(...args),
  },
};

vi.mock('../db.js', () => ({
  prisma: {
    job: {
      findUnique: (...args: any[]) => mockJobFindUnique(...args),
    },
    $transaction: async (callback: any) => callback(transactionClient),
  },
}));

vi.mock('../creditService.js', () => ({
  determineFailedStage: vi.fn(),
  refundForStage: vi.fn(),
  refundForRegenerationStage: (...args: any[]) => mockRefundForRegenerationStage(...args),
  refundChargeInTx: (...args: any[]) => mockRefundChargeInTx(...args),
  refundForSeedIdeaStage: vi.fn(),
  isGuidedSegment: vi.fn(),
}));

import { cancelRegenerationDispatch } from '../jobService.js';

describe('cancelRegenerationDispatch', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    // Only consulted for the settled receipt's display ordinal when the dispatch segment
    // carries none; a numbered segment always wins over it.
    mockJobFindUnique.mockResolvedValue({ regenerationCount: 4, status: 'REGENERATING' });
    mockDispatchUpdateMany.mockResolvedValue({ count: 1 });
    mockDispatchUpdate.mockResolvedValue({});
    mockReceiptUpsert.mockResolvedValue({});
    mockReceiptUpdate.mockResolvedValue({});
    mockRefundForRegenerationStage.mockResolvedValue({ amount: 3 });
    mockRefundChargeInTx.mockResolvedValue(null);
  });

  it('refunds the dispatch-linked charge and records the exact reversal', async () => {
    mockRefundChargeInTx.mockResolvedValue({ id: 'refund-1', amount: 3 });

    const result = await cancelRegenerationDispatch(
      'job-1',
      { id: 'dispatch-7', segment: 'regenerate_ideas_7', chargeId: 'charge-7' },
      'REGENERATING' as any,
      'SYSTEM_FAULT',
    );

    expect(result).toEqual({ cancelled: true, creditRefunded: 3 });
    expect(mockRefundChargeInTx).toHaveBeenCalledWith(transactionClient, 'charge-7');
    expect(mockRefundForRegenerationStage).not.toHaveBeenCalled();
    expect(mockDispatchUpdate).toHaveBeenCalledWith({
      where: { id: 'dispatch-7' },
      data: expect.objectContaining({
        state: 'REFUNDED',
        refundTransactionId: 'refund-1',
        refundedAmount: 3,
      }),
    });
  });

  it('refunds the exact numbered segment owned by the failed dispatch', async () => {
    const result = await cancelRegenerationDispatch(
      'job-1',
      { id: 'dispatch-7', segment: 'regenerate_ideas_7' },
      'REGENERATING' as any,
      'SYSTEM_FAULT',
    );

    expect(result).toEqual({ cancelled: true, creditRefunded: 3 });
    expect(mockRefundForRegenerationStage).toHaveBeenCalledOnce();
    expect(mockRefundForRegenerationStage).toHaveBeenCalledWith('job-1', 7);
    expect(mockReceiptUpdate).toHaveBeenCalledWith({
      where: { operationId: 'regeneration:dispatch-7:settled' },
      data: expect.objectContaining({
        patchJson: expect.objectContaining({
          event: 'regeneration_settled',
          operationId: 'dispatch-7',
          batch: expect.objectContaining({
            ordinal: 7,
            outcome: 'refunded',
            refunded: true,
          }),
        }),
      }),
    });
  });

  it('still writes the settled receipt when the segment carries no ordinal', async () => {
    // The settled receipt is the only thing that clears the client's pending-batch state,
    // and that state gates every pool mutation. Skipping it for an unnumbered (pre-batch-
    // numbering) dispatch would lock the workbench permanently.
    const result = await cancelRegenerationDispatch(
      'job-1',
      { id: 'dispatch-9', segment: null },
      'REGENERATING' as any,
      'SYSTEM_FAULT',
    );

    expect(result).toEqual({ cancelled: true, creditRefunded: 0 });
    // No numbered segment means no identifiable charge, so nothing is refunded...
    expect(mockRefundForRegenerationStage).not.toHaveBeenCalled();
    // ...but the operation is still settled, falling back to the job's batch counter.
    expect(mockReceiptUpsert).toHaveBeenCalledWith(expect.objectContaining({
      where: { operationId: 'regeneration:dispatch-9:settled' },
      create: expect.objectContaining({
        patchJson: expect.objectContaining({
          event: 'regeneration_settled',
          operationId: 'dispatch-9',
          batch: expect.objectContaining({ ordinal: 4, outcome: 'failed', refunded: false }),
        }),
      }),
    }));
  });
});
