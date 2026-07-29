/**
 * DispatchKind.SEED_IDEA round-trip through the generic dispatch machinery
 * (openDispatch / claimDispatch / dispatchGuard / settleDispatch).
 *
 * The whole point of reusing JobDispatch for seeds (plans/eager-meandering-feather.md, P3
 * reconciliation) instead of inventing a parallel operation identity is that the admission/claim/
 * settle skeleton needs ZERO seed-specific code — these tests pin that a SEED_IDEA dispatch behaves
 * exactly like every other kind already proven by workers.dispatch.test.ts, plus the two new
 * linkage columns (seedOrdinal, sourceMessageId) round-trip correctly.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { DispatchKind, DispatchState } from '@prisma/client';

const mockDispatchCreate = vi.fn();
const mockDispatchUpdateMany = vi.fn();
const mockDispatchFindUnique = vi.fn();
const mockDispatchFindFirst = vi.fn();
const mockDispatchUpdate = vi.fn();
const mockJobUpdate = vi.fn();
const mockJobUpdateMany = vi.fn();
const mockJobFindUnique = vi.fn();
const mockRefundChargeInTx = vi.fn();

const transactionClient = {
  jobDispatch: {
    findFirst: (...args: any[]) => mockDispatchFindFirst(...args),
    updateMany: (...args: any[]) => mockDispatchUpdateMany(...args),
    update: (...args: any[]) => mockDispatchUpdate(...args),
  },
  job: {
    updateMany: (...args: any[]) => mockJobUpdateMany(...args),
  },
};

vi.mock('../db.js', () => ({
  prisma: {
    jobDispatch: {
      create: (...args: any[]) => mockDispatchCreate(...args),
      updateMany: (...args: any[]) => mockDispatchUpdateMany(...args),
      findUnique: (...args: any[]) => mockDispatchFindUnique(...args),
    },
    job: {
      update: (...args: any[]) => mockJobUpdate(...args),
      updateMany: (...args: any[]) => mockJobUpdateMany(...args),
      findUnique: (...args: any[]) => mockJobFindUnique(...args),
    },
    $transaction: (callback: (client: typeof transactionClient) => unknown) =>
      callback(transactionClient),
  },
}));

vi.mock('../creditService.js', () => ({
  refundChargeInTx: (...args: any[]) => mockRefundChargeInTx(...args),
}));

const JOB_ID = 'job-seed-1';
const MINE = 'dispatch-mine';
const THEIRS = 'dispatch-theirs';
const WORKER = 'worker-seed-1';

// A minimal stand-in for Prisma.TransactionClient — openDispatch only touches jobDispatch.create
// and job.update, both of which are mocked above and reused as the "tx" client.
let tx: any;

beforeEach(() => {
  vi.clearAllMocks();
  tx = {
    jobDispatch: { create: mockDispatchCreate },
    job: { update: mockJobUpdate },
  };
  mockDispatchUpdate.mockResolvedValue({});
  mockRefundChargeInTx.mockResolvedValue(null);
});

describe('DispatchKind.SEED_IDEA — open/claim/guard/settle round-trip', () => {
  it('opens a SEED_IDEA dispatch carrying the seed ordinal + source message id, and arms the CAS', async () => {
    mockDispatchCreate.mockResolvedValue({ id: MINE });
    mockJobUpdate.mockResolvedValue({});

    const { openDispatch } = await import('../dispatchService.js');
    const dispatchId = await openDispatch(tx, {
      jobId: JOB_ID,
      kind: DispatchKind.SEED_IDEA,
      segment: null,
      chargeId: 'txn-seed-1',
      seedOrdinal: 1,
      sourceMessageId: 'msg-abc',
    });

    expect(dispatchId).toBe(MINE);
    expect(mockDispatchCreate).toHaveBeenCalledWith({
      data: {
        jobId: JOB_ID,
        kind: DispatchKind.SEED_IDEA,
        gateStage: null,
        segment: null,
        chargeId: 'txn-seed-1',
        seedOrdinal: 1,
        sourceMessageId: 'msg-abc',
        clientRequestId: null,
        requestSnapshot: undefined,
        requestFingerprint: null,
        workPayload: undefined,
        batchOrdinal: null,
        state: DispatchState.AUTHORIZED,
      },
      select: { id: true },
    });
    // The CAS predicate is armed the moment the transaction (here, the mocked tx) commits.
    expect(mockJobUpdate).toHaveBeenCalledWith({
      where: { id: JOB_ID },
      data: { activeDispatchId: MINE },
    });
  });

  it('defaults seedOrdinal/sourceMessageId to null when omitted (every non-seed kind)', async () => {
    mockDispatchCreate.mockResolvedValue({ id: MINE });
    mockJobUpdate.mockResolvedValue({});

    const { openDispatch } = await import('../dispatchService.js');
    await openDispatch(tx, { jobId: JOB_ID, kind: DispatchKind.CONTINUE });

    expect(mockDispatchCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({ seedOrdinal: null, sourceMessageId: null }),
      }),
    );
  });

  it('claims a SEED_IDEA dispatch exactly like any other kind (AUTHORIZED -> CLAIMED)', async () => {
    mockDispatchUpdateMany.mockResolvedValue({ count: 1 });

    const { claimDispatch } = await import('../dispatchService.js');
    const claimed = await claimDispatch(MINE, WORKER);

    expect(claimed).toBe(true);
    expect(mockDispatchUpdateMany).toHaveBeenCalledWith({
      where: {
        id: MINE,
        OR: [{ state: DispatchState.AUTHORIZED }, { state: DispatchState.CLAIMED, workerId: WORKER }],
      },
      data: { state: DispatchState.CLAIMED, workerId: WORKER, claimedAt: expect.any(Date) },
    });
  });

  it('a second worker cannot steal a claimed SEED_IDEA dispatch', async () => {
    // Guard predicate matches nothing for a DIFFERENT worker on an already-CLAIMED row.
    mockDispatchUpdateMany.mockResolvedValue({ count: 0 });

    const { claimDispatch } = await import('../dispatchService.js');
    const claimed = await claimDispatch(MINE, 'worker-intruder');

    expect(claimed).toBe(false);
  });

  it('dispatchGuard builds the same CAS fragment for a SEED_IDEA dispatch id as any other', async () => {
    // The guard itself is kind-agnostic by design — it operates purely on Job.activeDispatchId.
    // This pins that a seed dispatch id is not special-cased into leaking through.
    const { dispatchGuard } = await import('../dispatchService.js');
    expect(dispatchGuard(MINE)).toEqual({ activeDispatchId: MINE });
    expect(dispatchGuard(undefined)).toEqual({ activeDispatchId: null });
  });

  it('settleDispatch terminates a SEED_IDEA dispatch and disarms the CAS on the job', async () => {
    mockDispatchUpdateMany.mockResolvedValue({ count: 1 });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });

    // settleDispatch's tx-shaped param only needs jobDispatch/job.updateMany.
    const txForSettle = { jobDispatch: { updateMany: mockDispatchUpdateMany }, job: { updateMany: mockJobUpdateMany } };
    const { settleDispatch } = await import('../dispatchService.js');
    await settleDispatch(txForSettle as any, MINE, DispatchState.COMPLETED);

    expect(mockDispatchUpdateMany).toHaveBeenCalledWith({
      where: { id: MINE },
      data: { state: DispatchState.COMPLETED, failureKind: undefined, settledAt: expect.any(Date) },
    });
    expect(mockJobUpdateMany).toHaveBeenCalledWith({
      where: { activeDispatchId: MINE },
      data: { activeDispatchId: null },
    });
  });

  it('a stale/duplicate seed-complete (superseded dispatch id) is rejected — CAS matches nothing', async () => {
    // The job has moved on to a NEWER attempt (THEIRS); a callback naming the old dispatch (MINE)
    // must guard-miss, exactly as workers.dispatch.test.ts proves for gate-reached/ideas-ready.
    mockJobUpdateMany.mockResolvedValue({ count: 0 });
    mockJobFindUnique.mockResolvedValue({
      status: 'AWAITING_SELECTION',
      activeDispatchId: THEIRS,
    });

    const { diagnoseGuardMiss } = await import('../dispatchService.js');
    const reason = await diagnoseGuardMiss(JOB_ID, MINE, ['AWAITING_SELECTION' as any]);

    expect(reason).toBe('stale_dispatch');
  });

  it('cancels and refunds only an unclaimed queued selection dispatch', async () => {
    mockDispatchFindFirst.mockResolvedValue({
      id: MINE,
      kind: DispatchKind.DEEP_RESEARCH,
      state: DispatchState.AUTHORIZED,
      chargeId: 'charge-1',
    });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockDispatchUpdateMany.mockResolvedValue({ count: 1 });
    mockRefundChargeInTx.mockResolvedValue({ id: 'refund-1', amount: 5 });

    const { cancelAuthorizedSelectionDispatch } = await import('../dispatchService.js');
    const result = await cancelAuthorizedSelectionDispatch(JOB_ID, MINE);

    expect(result).toBe('cancelled');
    expect(mockJobUpdateMany).toHaveBeenCalledWith(expect.objectContaining({
      where: expect.objectContaining({
        id: JOB_ID,
        status: 'QUEUED',
        activeDispatchId: MINE,
      }),
    }));
    expect(mockDispatchUpdateMany).toHaveBeenCalledWith(expect.objectContaining({
      where: { id: MINE, state: DispatchState.AUTHORIZED },
      data: expect.objectContaining({ state: DispatchState.CANCELLED }),
    }));
    expect(mockRefundChargeInTx).toHaveBeenCalledWith(transactionClient, 'charge-1');
    expect(mockDispatchUpdate).toHaveBeenCalledWith({
      where: { id: MINE },
      data: expect.objectContaining({
        refundTransactionId: 'refund-1',
        refundedAmount: 5,
      }),
    });
  });
});
