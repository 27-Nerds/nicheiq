import { describe, expect, it, vi } from 'vitest';

const mockJobFindUnique = vi.fn();

vi.mock('../db.js', () => ({
  prisma: {
    job: {
      findUnique: (...args: any[]) => mockJobFindUnique(...args),
    },
  },
}));

vi.mock('../creditService.js', () => ({
  determineFailedStage: vi.fn(),
  refundChargeInTx: vi.fn(),
  refundForStage: vi.fn(),
  refundForStageInTx: vi.fn(),
  refundForRegenerationStage: vi.fn(),
  refundForSeedIdeaStage: vi.fn(),
  isGuidedSegment: vi.fn(),
}));

vi.mock('../queueService.js', () => ({
  removeJobFromQueue: vi.fn(),
}));

vi.mock('../dispatchService.js', () => ({
  settleDispatch: vi.fn(),
}));

describe('getJob refund projection', () => {
  it('loads refund amounts so reload-stable responses reflect actual restored credits', async () => {
    mockJobFindUnique.mockResolvedValue(null);

    const { getJob } = await import('../jobService.js');
    await getJob('job-1');

    expect(mockJobFindUnique).toHaveBeenCalledWith({
      where: { id: 'job-1' },
      include: {
        progress: {
          orderBy: { stageNumber: 'asc' },
        },
        assets: true,
        creditTransactions: {
          where: { type: 'REFUND' },
          select: {
            id: true,
            amount: true,
          },
        },
        dispatches: {
          orderBy: { createdAt: 'desc' },
          take: 1,
          select: {
            id: true,
            kind: true,
            state: true,
            refundedAmount: true,
            refundTransaction: {
              select: { amount: true },
            },
          },
        },
      },
    });
  });
});
