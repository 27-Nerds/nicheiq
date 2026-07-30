import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockJobFindUnique = vi.fn();
const mockJobUpdateMany = vi.fn();
const mockDispatchFindUnique = vi.fn();
const mockTransaction = vi.fn();

const mockTxJobUpdateMany = vi.fn();
const mockTxJobFindUnique = vi.fn();
const mockTxDispatchUpdateMany = vi.fn();
const mockTxDispatchUpdate = vi.fn();

const mockRefundChargeInTx = vi.fn();
const mockRefundForStage = vi.fn();
const mockDetermineFailedStage = vi.fn();

const tx = {
  job: {
    updateMany: (...args: any[]) => mockTxJobUpdateMany(...args),
    findUnique: (...args: any[]) => mockTxJobFindUnique(...args),
  },
  jobDispatch: {
    updateMany: (...args: any[]) => mockTxDispatchUpdateMany(...args),
    update: (...args: any[]) => mockTxDispatchUpdate(...args),
  },
};

vi.mock('../db.js', () => ({
  prisma: {
    job: {
      findUnique: (...args: any[]) => mockJobFindUnique(...args),
      updateMany: (...args: any[]) => mockJobUpdateMany(...args),
    },
    jobDispatch: {
      findUnique: (...args: any[]) => mockDispatchFindUnique(...args),
      findFirst: vi.fn(),
    },
    $transaction: (...args: any[]) => mockTransaction(...args),
  },
}));

vi.mock('../creditService.js', () => ({
  determineFailedStage: (...args: any[]) => mockDetermineFailedStage(...args),
  refundChargeInTx: (...args: any[]) => mockRefundChargeInTx(...args),
  refundForStage: (...args: any[]) => mockRefundForStage(...args),
  refundForStageInTx: vi.fn(),
  refundForRegenerationStage: vi.fn(),
  refundForSeedIdeaStage: vi.fn(),
  isGuidedSegment: vi.fn(),
}));

import { failJob } from '../jobService.js';

const JOB = 'job-1';
const MINE = 'dispatch-a';
const OTHER = 'dispatch-b';

beforeEach(() => {
  vi.clearAllMocks();
  mockTransaction.mockImplementation(async (callback: any) => callback(tx));
  mockTxJobUpdateMany.mockResolvedValue({ count: 1 });
  mockTxDispatchUpdateMany.mockResolvedValue({ count: 1 });
  mockTxDispatchUpdate.mockResolvedValue({});
  mockRefundChargeInTx.mockResolvedValue({ id: 'refund-deep', amount: 100 });
  mockDispatchFindUnique.mockResolvedValue({
    id: MINE,
    jobId: JOB,
    chargeId: 'charge-deep',
  });
});

describe('failJob — dispatch-scoped settlement', () => {
  it.each(['DISCOVERY_PREPAID_V1', 'GUIDED_SEGMENTS_V1'])(
    'reverses the exact Deep Research charge for an early stage-5 failure (%s)',
    async (billingModel) => {
      mockJobFindUnique.mockResolvedValue({
        status: 'RUNNING_PHASE2',
        regenerationCount: 0,
        activeDispatchId: MINE,
      });
      mockTxJobFindUnique.mockResolvedValue({
        id: JOB,
        status: 'FAILED',
        billingModel,
        activeDispatchId: null,
      });

      const result = await failJob(
        JOB,
        'Phase-2 selection resolution failed',
        5,
        undefined,
        undefined,
        'SYSTEM_FAULT',
        undefined,
        MINE,
      );

      expect(result).toMatchObject({
        applied: true,
        job: { status: 'FAILED', activeDispatchId: null },
      });
      expect(mockTxJobUpdateMany).toHaveBeenCalledWith({
        where: {
          id: JOB,
          status: {
            in: [
              'PENDING',
              'QUEUED',
              'RUNNING',
              'AWAITING_SELECTION',
              'AWAITING_GATE',
              'REGENERATING',
              'RUNNING_PHASE2',
            ],
          },
          activeDispatchId: MINE,
        },
        data: expect.objectContaining({
          status: 'FAILED',
          errorStage: 5,
          activeDispatchId: null,
        }),
      });
      expect(mockTxDispatchUpdateMany).toHaveBeenCalledWith({
        where: {
          id: MINE,
          jobId: JOB,
          state: { in: ['AUTHORIZED', 'CLAIMED'] },
        },
        data: {
          state: 'FAILED',
          failureKind: 'SYSTEM_FAULT',
          settledAt: expect.any(Date),
        },
      });
      expect(mockRefundChargeInTx).toHaveBeenCalledWith(tx, 'charge-deep');
      expect(mockTxDispatchUpdate).toHaveBeenCalledWith({
        where: { id: MINE },
        data: {
          state: 'REFUNDED',
          refundTransactionId: 'refund-deep',
          refundedAt: expect.any(Date),
          refundedAmount: 100,
        },
      });
      expect(mockRefundForStage).not.toHaveBeenCalled();
      expect(mockDetermineFailedStage).not.toHaveBeenCalled();
    },
  );

  it('does not let delayed failure A terminate or refund active attempt B', async () => {
    mockJobFindUnique
      .mockResolvedValueOnce({
        status: 'RUNNING_PHASE2',
        regenerationCount: 0,
        activeDispatchId: OTHER,
      })
      .mockResolvedValueOnce({
        id: JOB,
        status: 'RUNNING_PHASE2',
        activeDispatchId: OTHER,
      });
    mockTxJobUpdateMany.mockResolvedValue({ count: 0 });

    const result = await failJob(
      JOB,
      'late failure from A',
      6,
      undefined,
      undefined,
      undefined,
      undefined,
      MINE,
    );

    expect(result).toMatchObject({
      applied: false,
      job: { status: 'RUNNING_PHASE2', activeDispatchId: OTHER },
    });
    expect(mockTxJobUpdateMany).toHaveBeenCalledWith(
      expect.objectContaining({ where: expect.objectContaining({ activeDispatchId: MINE }) }),
    );
    expect(mockTxDispatchUpdateMany).not.toHaveBeenCalled();
    expect(mockRefundChargeInTx).not.toHaveBeenCalled();
    expect(mockRefundForStage).not.toHaveBeenCalled();
  });

  it('loses stale-heartbeat recovery when the worker refreshed after the monitor read', async () => {
    const observedHeartbeat = new Date('2026-07-30T00:00:00.000Z');
    mockJobFindUnique
      .mockResolvedValueOnce({
        status: 'RUNNING_PHASE2',
        regenerationCount: 0,
        activeDispatchId: MINE,
      })
      .mockResolvedValueOnce({
        id: JOB,
        status: 'RUNNING_PHASE2',
        activeDispatchId: MINE,
      });
    mockTxJobUpdateMany.mockResolvedValue({ count: 0 });

    const result = await failJob(
      JOB,
      'stale heartbeat',
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      MINE,
      { status: 'RUNNING_PHASE2' as any, lastHeartbeat: observedHeartbeat },
    );

    expect(result.applied).toBe(false);
    expect(mockTxJobUpdateMany).toHaveBeenCalledWith(
      expect.objectContaining({
        where: {
          id: JOB,
          status: 'RUNNING_PHASE2',
          activeDispatchId: MINE,
          lastHeartbeat: observedHeartbeat,
        },
      }),
    );
    expect(mockTxDispatchUpdateMany).not.toHaveBeenCalled();
    expect(mockRefundChargeInTx).not.toHaveBeenCalled();
  });

  it('treats a duplicate callback after settlement as idempotent', async () => {
    mockJobFindUnique
      .mockResolvedValueOnce({ id: JOB, status: 'FAILED', activeDispatchId: null })
      .mockResolvedValueOnce({ id: JOB, status: 'FAILED', activeDispatchId: null });

    const result = await failJob(
      JOB,
      'duplicate',
      5,
      undefined,
      undefined,
      undefined,
      undefined,
      MINE,
    );

    expect(result).toMatchObject({
      applied: false,
      job: { status: 'FAILED' },
    });
    expect(mockTransaction).not.toHaveBeenCalled();
    expect(mockRefundChargeInTx).not.toHaveBeenCalled();
    expect(mockRefundForStage).not.toHaveBeenCalled();
  });

  it('allows stage inference only when both callback and Job are genuinely legacy', async () => {
    mockJobFindUnique
      .mockResolvedValueOnce({
        status: 'RUNNING',
        regenerationCount: 0,
        activeDispatchId: null,
      })
      .mockResolvedValueOnce({
        id: JOB,
        status: 'FAILED',
        billingModel: 'DISCOVERY_PREPAID_V1',
      });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockDetermineFailedStage.mockReturnValue('discovery');
    mockRefundForStage.mockResolvedValue({ amount: 99 });

    await failJob(JOB, 'legacy failure', 5);

    expect(mockJobUpdateMany).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({ activeDispatchId: null }),
      }),
    );
    expect(mockDetermineFailedStage).toHaveBeenCalledWith(5, 'RUNNING');
    expect(mockRefundForStage).toHaveBeenCalledWith(JOB, 'discovery');
    expect(mockRefundChargeInTx).not.toHaveBeenCalled();
  });
});
