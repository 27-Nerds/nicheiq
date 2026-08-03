import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockJobUpdateMany = vi.fn();
const mockJobFindUnique = vi.fn();
const mockDispatchFindUnique = vi.fn();
const mockDispatchUpdateMany = vi.fn();
const mockDispatchUpdate = vi.fn();
const mockChatCreate = vi.fn();
const mockChatUpsert = vi.fn();
const mockRefundChargeInTx = vi.fn();

vi.mock('../db.js', () => {
  const tx: any = {
    job: {
      updateMany: (...a: any[]) => mockJobUpdateMany(...a),
      findUnique: (...a: any[]) => mockJobFindUnique(...a),
    },
    jobDispatch: {
      findUnique: (...a: any[]) => mockDispatchFindUnique(...a),
      updateMany: (...a: any[]) => mockDispatchUpdateMany(...a),
      update: (...a: any[]) => mockDispatchUpdate(...a),
    },
    chatMessage: {
      create: (...a: any[]) => mockChatCreate(...a),
      upsert: (...a: any[]) => mockChatUpsert(...a),
    },
  };
  return {
    prisma: {
      ...tx,
      $transaction: (fn: any) => fn(tx),
    },
  };
});

vi.mock('../creditService.js', () => ({
  refundChargeInTx: (...a: any[]) => mockRefundChargeInTx(...a),
}));

beforeEach(() => {
  vi.clearAllMocks();
  mockJobUpdateMany.mockResolvedValue({ count: 1 });
  mockDispatchUpdateMany.mockResolvedValue({ count: 1 });
  mockDispatchUpdate.mockResolvedValue({});
  mockChatCreate.mockResolvedValue({});
  mockChatUpsert.mockResolvedValue({});
});

describe('paid pool durable recovery', () => {
  it('rolls back stale unprepared settlement when prepare registration won the race', async () => {
    mockDispatchFindUnique.mockResolvedValue({
      jobId: 'job-1',
      kind: 'SEED_IDEA',
      state: 'CLAIMED',
      workerId: 'worker-1',
      recoveryPreparedAt: new Date(),
      chargeId: 'charge-1',
    });

    const { failUnpreparedPaidPoolMutation } = await import('../paidPoolRecoveryService.js');
    const applied = await failUnpreparedPaidPoolMutation('job-1', 'dispatch-1', {
      status: 'RUNNING' as any,
      workerId: 'worker-1',
      lastHeartbeat: new Date(0),
    });

    expect(applied).toBe(false);
    expect(mockDispatchUpdateMany).not.toHaveBeenCalled();
    expect(mockRefundChargeInTx).not.toHaveBeenCalled();
  });

  it('does not claim a zero-dollar reversal as a user refund', async () => {
    mockDispatchFindUnique.mockResolvedValue({
      jobId: 'job-1',
      kind: 'SEED_IDEA',
      state: 'RECOVERING',
      workerId: 'recovery-worker',
      recoveryToken: '22222222-2222-4222-8222-222222222222',
      chargeId: 'charge-1',
      sourceMessageId: 'message-1',
      seedOrdinal: 1,
      segment: null,
      batchOrdinal: null,
    });
    mockRefundChargeInTx.mockResolvedValue({ id: 'reversal-1', amount: 0 });

    const { completePaidPoolRecovery } = await import('../paidPoolRecoveryService.js');
    const outcome = await completePaidPoolRecovery({
      jobId: 'job-1',
      dispatchId: 'dispatch-1',
      recoveryToken: '22222222-2222-4222-8222-222222222222',
      workerId: 'recovery-worker',
    });

    expect(outcome).toBe('completed');
    expect(mockDispatchUpdateMany).toHaveBeenCalledWith(expect.objectContaining({
      data: expect.objectContaining({
        state: 'FAILED',
        refundTransactionId: undefined,
        refundedAt: undefined,
        refundedAmount: undefined,
      }),
    }));
    expect(mockChatCreate).toHaveBeenCalledWith(expect.objectContaining({
      data: expect.objectContaining({
        patchJson: expect.objectContaining({ outcome: 'failed' }),
      }),
    }));
  });
});
