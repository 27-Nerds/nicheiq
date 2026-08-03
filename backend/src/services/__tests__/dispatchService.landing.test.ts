import { beforeEach, describe, expect, it, vi } from 'vitest';
import { DispatchKind, DispatchState, JobStatus } from '@prisma/client';

const mockJobUpdateMany = vi.fn();
const mockJobFindUnique = vi.fn();
const mockDispatchUpdateMany = vi.fn();
const mockDispatchFindUnique = vi.fn();
const mockDispatchFindFirst = vi.fn();
const mockJobAssetUpsert = vi.fn();
const mockJobAssetFindUnique = vi.fn();
const mockJobProgressUpdateMany = vi.fn();
const mockRefundChargeInTx = vi.fn();

const tx = {
  job: {
    updateMany: (...args: unknown[]) => mockJobUpdateMany(...args),
    findUnique: (...args: unknown[]) => mockJobFindUnique(...args),
  },
  jobDispatch: {
    updateMany: (...args: unknown[]) => mockDispatchUpdateMany(...args),
    findUnique: (...args: unknown[]) => mockDispatchFindUnique(...args),
    findFirst: (...args: unknown[]) => mockDispatchFindFirst(...args),
  },
  jobAsset: {
    upsert: (...args: unknown[]) => mockJobAssetUpsert(...args),
  },
  jobProgress: {
    updateMany: (...args: unknown[]) => mockJobProgressUpdateMany(...args),
  },
};

vi.mock('../db.js', () => ({
  prisma: {
    job: {
      findUnique: (...args: unknown[]) => mockJobFindUnique(...args),
    },
    jobDispatch: {
      findUnique: (...args: unknown[]) => mockDispatchFindUnique(...args),
    },
    jobAsset: {
      findUnique: (...args: unknown[]) => mockJobAssetFindUnique(...args),
    },
    $transaction: (callback: (client: typeof tx) => unknown) => callback(tx),
  },
}));

vi.mock('../creditService.js', () => ({
  refundChargeInTx: (...args: unknown[]) => mockRefundChargeInTx(...args),
}));

const JOB_ID = 'job-landing-1';
const DISPATCH_ID = 'dispatch-landing-1';
const WORKER_ID = 'worker-1';

beforeEach(() => {
  vi.clearAllMocks();
  mockJobAssetUpsert.mockResolvedValue({});
  mockJobProgressUpdateMany.mockResolvedValue({ count: 1 });
});

describe('landing auxiliary dispatch lifecycle', () => {
  it('claims QUEUED -> RUNNING without changing the parent Job status', async () => {
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockDispatchUpdateMany.mockResolvedValue({ count: 1 });

    const { startLandingPageDispatch } = await import('../dispatchService.js');
    await expect(startLandingPageDispatch(DISPATCH_ID, WORKER_ID, JOB_ID)).resolves.toBe('started');

    expect(mockJobUpdateMany).toHaveBeenCalledWith({
      where: {
        id: JOB_ID,
        status: JobStatus.COMPLETED,
        landingPageStatus: 'QUEUED',
        activeDispatchId: DISPATCH_ID,
      },
      data: {
        landingPageStatus: 'RUNNING',
        workerId: WORKER_ID,
        lastHeartbeat: expect.any(Date),
      },
    });
    expect(mockDispatchUpdateMany).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({
          id: DISPATCH_ID,
          jobId: JOB_ID,
          kind: DispatchKind.CONTINUE,
          segment: 'landing_page',
        }),
        data: expect.objectContaining({
          state: DispatchState.CLAIMED,
          workerId: WORKER_ID,
        }),
      }),
    );
  });

  it('accepts only a same-worker retry of the already-claimed landing attempt', async () => {
    mockJobUpdateMany.mockResolvedValue({ count: 0 });
    mockJobFindUnique.mockResolvedValue({
      status: JobStatus.COMPLETED,
      landingPageStatus: 'RUNNING',
      activeDispatchId: DISPATCH_ID,
      workerId: WORKER_ID,
    });
    mockDispatchFindUnique.mockResolvedValue({
      jobId: JOB_ID,
      kind: DispatchKind.CONTINUE,
      segment: 'landing_page',
      state: DispatchState.CLAIMED,
      workerId: WORKER_ID,
    });

    const { startLandingPageDispatch } = await import('../dispatchService.js');
    await expect(startLandingPageDispatch(DISPATCH_ID, WORKER_ID, JOB_ID)).resolves.toBe('retry');
    await expect(startLandingPageDispatch(DISPATCH_ID, 'worker-2', JOB_ID)).resolves.toBe(false);
    expect(mockDispatchUpdateMany).not.toHaveBeenCalled();
  });

  it('settles success, publishes the asset, and disarms the Job in one transaction', async () => {
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockDispatchUpdateMany.mockResolvedValue({ count: 1 });

    const { completeLandingPageDispatch } = await import('../dispatchService.js');
    await expect(
      completeLandingPageDispatch(JOB_ID, DISPATCH_ID, 'output/landing.html'),
    ).resolves.toBe(true);

    expect(mockJobUpdateMany).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({
          id: JOB_ID,
          status: JobStatus.COMPLETED,
          activeDispatchId: DISPATCH_ID,
        }),
        data: {
          landingPageStatus: 'COMPLETED',
          activeDispatchId: null,
        },
      }),
    );
    expect(mockDispatchUpdateMany).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({
          id: DISPATCH_ID,
          state: DispatchState.CLAIMED,
          segment: 'landing_page',
        }),
        data: {
          state: DispatchState.COMPLETED,
          settledAt: expect.any(Date),
        },
      }),
    );
    expect(mockJobAssetUpsert).toHaveBeenCalledWith(
      expect.objectContaining({
        create: expect.objectContaining({ filePath: 'output/landing.html' }),
      }),
    );
    expect(mockJobProgressUpdateMany).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({ jobId: JOB_ID, stageNumber: 15 }),
        data: expect.objectContaining({ status: 'COMPLETED', errorMessage: null }),
      }),
    );
  });

  it('refunds the exact paid charge once and terminalizes the failed dispatch', async () => {
    mockDispatchFindFirst.mockResolvedValue({ chargeId: 'charge-landing-1' });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockRefundChargeInTx.mockResolvedValue({ id: 'refund-landing-1', amount: 5 });
    mockDispatchUpdateMany.mockResolvedValue({ count: 1 });

    const { failLandingPageDispatch } = await import('../dispatchService.js');
    await expect(
      failLandingPageDispatch(JOB_ID, DISPATCH_ID, 'template failed'),
    ).resolves.toBe(true);

    expect(mockRefundChargeInTx).toHaveBeenCalledWith(tx, 'charge-landing-1');
    expect(mockDispatchUpdateMany).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({
          id: DISPATCH_ID,
          state: { in: [DispatchState.AUTHORIZED, DispatchState.CLAIMED] },
        }),
        data: expect.objectContaining({
          state: DispatchState.REFUNDED,
          failureKind: 'SYSTEM_FAULT',
          refundTransactionId: 'refund-landing-1',
          refundedAmount: 5,
        }),
      }),
    );
    expect(mockJobProgressUpdateMany).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({ jobId: JOB_ID, stageNumber: 15 }),
        data: expect.objectContaining({
          status: 'FAILED',
          errorMessage: 'template failed',
        }),
      }),
    );
  });

  it('marks a free failed landing attempt FAILED without fabricating a refund', async () => {
    mockDispatchFindFirst.mockResolvedValue({ chargeId: null });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockDispatchUpdateMany.mockResolvedValue({ count: 1 });

    const { failLandingPageDispatch } = await import('../dispatchService.js');
    await expect(failLandingPageDispatch(JOB_ID, DISPATCH_ID)).resolves.toBe(true);

    expect(mockRefundChargeInTx).not.toHaveBeenCalled();
    expect(mockDispatchUpdateMany).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          state: DispatchState.FAILED,
          refundTransactionId: undefined,
          refundedAt: undefined,
          refundedAmount: undefined,
        }),
      }),
    );
  });

  it('keeps an expired-allowance zero reversal FAILED', async () => {
    mockDispatchFindFirst.mockResolvedValue({ chargeId: 'charge-landing-expired' });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockRefundChargeInTx.mockResolvedValue({ id: 'reversal-zero', amount: 0 });
    mockDispatchUpdateMany.mockResolvedValue({ count: 1 });

    const { failLandingPageDispatch } = await import('../dispatchService.js');
    await expect(failLandingPageDispatch(JOB_ID, DISPATCH_ID)).resolves.toBe(true);

    expect(mockDispatchUpdateMany).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          state: DispatchState.FAILED,
          refundTransactionId: 'reversal-zero',
          refundedAt: undefined,
          refundedAmount: 0,
        }),
      }),
    );
  });

  it('a duplicate failure loses the Job CAS and produces no second refund or side effect', async () => {
    mockDispatchFindFirst.mockResolvedValue({ chargeId: 'charge-landing-1' });
    mockJobUpdateMany.mockResolvedValue({ count: 0 });

    const { failLandingPageDispatch } = await import('../dispatchService.js');
    await expect(failLandingPageDispatch(JOB_ID, DISPATCH_ID)).resolves.toBe(false);

    expect(mockRefundChargeInTx).not.toHaveBeenCalled();
    expect(mockDispatchUpdateMany).not.toHaveBeenCalled();
  });

  it('fences monitor recovery to the exact landing heartbeat snapshot it observed', async () => {
    const lastHeartbeat = new Date('2026-07-30T00:00:00.000Z');
    const updatedAt = new Date('2026-07-30T00:00:05.000Z');
    mockDispatchFindFirst.mockResolvedValue({ chargeId: 'charge-landing-1' });
    mockJobUpdateMany.mockResolvedValue({ count: 0 });

    const { failLandingPageDispatch } = await import('../dispatchService.js');
    await expect(
      failLandingPageDispatch(JOB_ID, DISPATCH_ID, 'stale heartbeat', {
        landingPageStatus: 'RUNNING',
        lastHeartbeat,
        updatedAt,
      }),
    ).resolves.toBe(false);

    expect(mockJobUpdateMany).toHaveBeenCalledWith({
      where: {
        id: JOB_ID,
        status: JobStatus.COMPLETED,
        landingPageStatus: 'RUNNING',
        activeDispatchId: DISPATCH_ID,
        lastHeartbeat,
        updatedAt,
      },
      data: {
        landingPageStatus: 'FAILED',
        activeDispatchId: null,
      },
    });
    expect(mockRefundChargeInTx).not.toHaveBeenCalled();
  });
});

describe('deep-research report publication', () => {
  const REPORT_PATH = 'output/report.json';
  const FINGERPRINT = 'report-fingerprint';
  const SNAPSHOT = { schemaVersion: 1, reportPath: REPORT_PATH };

  it('publishes the asset and settles Job + dispatch atomically', async () => {
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockDispatchUpdateMany.mockResolvedValue({ count: 1 });

    const { publishDeepResearchReport } = await import('../dispatchService.js');
    await expect(
      publishDeepResearchReport(
        JOB_ID,
        DISPATCH_ID,
        REPORT_PATH,
        SNAPSHOT,
        FINGERPRINT,
        { selectedSolution: 'Winner' },
      ),
    ).resolves.toBe('published');

    expect(mockJobUpdateMany).toHaveBeenCalledWith({
      where: {
        id: JOB_ID,
        status: JobStatus.RUNNING_PHASE2,
        activeDispatchId: DISPATCH_ID,
      },
      data: {
        selectedSolution: 'Winner',
        status: JobStatus.COMPLETED,
        completedAt: expect.any(Date),
        progressPercent: 100,
        activeDispatchId: null,
      },
    });
    expect(mockDispatchUpdateMany).toHaveBeenCalledWith({
      where: {
        id: DISPATCH_ID,
        jobId: JOB_ID,
        kind: DispatchKind.DEEP_RESEARCH,
        state: DispatchState.CLAIMED,
        OR: [
          { resultFingerprint: null },
          { resultFingerprint: FINGERPRINT },
        ],
      },
      data: {
        state: DispatchState.COMPLETED,
        settledAt: expect.any(Date),
        resultSnapshot: SNAPSHOT,
        resultFingerprint: FINGERPRINT,
      },
    });
    expect(mockJobAssetUpsert).toHaveBeenCalledWith(
      expect.objectContaining({
        create: expect.objectContaining({ filePath: REPORT_PATH }),
      }),
    );
  });

  it('loses cleanly when failure wins the Job row first', async () => {
    mockJobUpdateMany.mockResolvedValue({ count: 0 });
    mockJobFindUnique.mockResolvedValue({
      status: JobStatus.FAILED,
      activeDispatchId: null,
    });
    mockDispatchFindUnique.mockResolvedValue({
      jobId: JOB_ID,
      kind: DispatchKind.DEEP_RESEARCH,
      state: DispatchState.REFUNDED,
      resultFingerprint: null,
    });
    mockJobAssetFindUnique.mockResolvedValue(null);

    const { publishDeepResearchReport } = await import('../dispatchService.js');
    await expect(
      publishDeepResearchReport(
        JOB_ID,
        DISPATCH_ID,
        REPORT_PATH,
        SNAPSHOT,
        FINGERPRINT,
        {},
      ),
    ).resolves.toBe('stale');

    expect(mockDispatchUpdateMany).not.toHaveBeenCalled();
    expect(mockJobAssetUpsert).not.toHaveBeenCalled();
  });

  it('recognizes only the exact already-published result as idempotent', async () => {
    mockJobUpdateMany.mockResolvedValue({ count: 0 });
    mockJobFindUnique.mockResolvedValue({
      status: JobStatus.COMPLETED,
      activeDispatchId: null,
    });
    mockDispatchFindUnique.mockResolvedValue({
      jobId: JOB_ID,
      kind: DispatchKind.DEEP_RESEARCH,
      state: DispatchState.COMPLETED,
      resultFingerprint: FINGERPRINT,
    });
    mockJobAssetFindUnique.mockResolvedValue({ filePath: REPORT_PATH });

    const { publishDeepResearchReport } = await import('../dispatchService.js');
    await expect(
      publishDeepResearchReport(
        JOB_ID,
        DISPATCH_ID,
        REPORT_PATH,
        SNAPSHOT,
        FINGERPRINT,
        {},
      ),
    ).resolves.toBe('idempotent');
  });
});
