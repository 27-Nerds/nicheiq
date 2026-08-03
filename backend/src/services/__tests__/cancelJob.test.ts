/**
 * cancelJob — the single cancellation path, and the CAS that keeps it single.
 *
 * Before this, cancel and failJob each did read-status-then-write-unconditionally. Whichever wrote
 * LAST won the terminal status — but BOTH issued a refund. So a job could be settled twice, and
 * the same user action could have two different prices depending on which write landed second.
 *
 * There were also two cancel routes with two different state machines: POST timestamped the job,
 * pulled it from the queue and failed its RUNNING progress rows; DELETE did none of that. Same
 * intent, different behaviour — which becomes a billing bug the moment cancellation owes money.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';

const mockJobFindUnique = vi.fn();
const mockJobUpdateMany = vi.fn();
const mockProgressUpdateMany = vi.fn(async (_a?: any) => ({ count: 0 }) as any);
const mockDispatchFindMany = vi.fn(async (_a?: any) => [] as any);
const mockDispatchFindUnique = vi.fn(async (_a?: any) => null as any);
const mockDispatchFindFirst = vi.fn(async (_a?: any) => null as any);
const mockDispatchUpdateMany = vi.fn(async (_a?: any) => ({ count: 0 }) as any);
const mockChatMessageCreate = vi.fn(async (_a?: any) => ({ id: 'receipt-1' }) as any);
const mockRefundForStage = vi.fn();
const mockRefundForSeedIdeaStage = vi.fn();
const mockRefundChargeInTx = vi.fn();
const mockRemoveFromQueue = vi.fn(async (_a?: any) => {});

// $transaction just invokes the callback with the same mocked prisma — none of these tests
// exercise real transactional isolation, only that the right calls happen in the right order.
const mockPrismaTransaction = vi.fn(async (cb: any) => cb(prismaMock));

const prismaMock = {
  job: {
    findUnique: (a: any) => mockJobFindUnique(a),
    updateMany: (a: any) => mockJobUpdateMany(a),
    update: vi.fn(),
  },
  jobProgress: { updateMany: (a: any) => mockProgressUpdateMany(a) },
  jobDispatch: {
    findMany: (a: any) => mockDispatchFindMany(a),
    findUnique: (a: any) => mockDispatchFindUnique(a),
    findFirst: (a: any) => mockDispatchFindFirst(a),
    updateMany: (a: any) => mockDispatchUpdateMany(a),
  },
  chatMessage: { create: (a: any) => mockChatMessageCreate(a) },
  $transaction: (cb: any) => mockPrismaTransaction(cb),
};

vi.mock('../db.js', () => ({ prisma: prismaMock }));
vi.mock('../creditService.js', () => ({
  refundForStage: (a: any, b: any) => mockRefundForStage(a, b),
  refundForStageInTx: (_tx: any, a: any, b: any) => mockRefundForStage(a, b),
  refundChargeInTx: (tx: any, chargeId: any) => mockRefundChargeInTx(tx, chargeId),
  refundForRegenerationStage: vi.fn(),
  refundForSeedIdeaStage: (a: any, b: any) => mockRefundForSeedIdeaStage(a, b),
  determineFailedStage: vi.fn(() => 'discovery'),
  // Real-shape stand-in (not just a bare vi.fn()) — cancelJob/failJob's guided-billing branches
  // call this to validate a dispatch's `segment` before trusting it as a refund stage name.
  isGuidedSegment: (stage: string) => ['guided_s1', 'guided_s2_4', 'guided_s5'].includes(stage),
}));
vi.mock('../queueService.js', () => ({
  removeJobFromQueue: (a: any) => mockRemoveFromQueue(a),
}));

const JOB = 'job-1';

beforeEach(() => {
  vi.clearAllMocks();
  mockRefundForStage.mockResolvedValue({ amount: 5 });
  mockRefundForSeedIdeaStage.mockResolvedValue({ amount: 2 });
  mockRefundChargeInTx.mockResolvedValue(null);
  mockProgressUpdateMany.mockResolvedValue({ count: 0 });
  mockDispatchFindMany.mockResolvedValue([]);
  mockDispatchFindUnique.mockResolvedValue(null);
  mockDispatchFindFirst.mockResolvedValue(null);
  mockDispatchUpdateMany.mockResolvedValue({ count: 1 });
  mockChatMessageCreate.mockResolvedValue({ id: 'receipt-1' });
  mockPrismaTransaction.mockImplementation(async (cb: any) => cb(prismaMock));
});

describe('cancelJob', () => {
  it('cancels a RUNNING job: one terminal write, refund, progress failed, dispatch disarmed', async () => {
    // Same object shape answers both the initial status read and the later billing-model read —
    // cancelJob only ever asks for the field it needs, so the extra field on the other call is inert.
    mockJobFindUnique.mockResolvedValue({ status: 'RUNNING', billingModel: 'DISCOVERY_PREPAID_V1' });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });

    const { cancelJob } = await import('../jobService.js');
    const outcome = await cancelJob(JOB);

    expect(outcome).toEqual({ cancelled: true, creditRefunded: 5 });

    // The terminal write is a CAS, not an unconditional update by id.
    expect(mockJobUpdateMany).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({
          id: JOB,
          status: { in: ['PENDING', 'QUEUED', 'RUNNING', 'AWAITING_GATE'] },
        }),
        // Disarming the dispatch is what stops a worker still running this job from dragging it
        // back to life with a late (but matching) callback.
        data: expect.objectContaining({ status: 'CANCELLED', activeDispatchId: null }),
      }),
    );
    // Behaviour that used to exist only on the POST route now happens for BOTH verbs.
    expect(mockProgressUpdateMany).toHaveBeenCalled();
    expect(mockDispatchUpdateMany).toHaveBeenCalled();
  });

  it('does NOT refund when a concurrent failure already claimed the terminal state', async () => {
    // The race. We read RUNNING, but a failJob won the CAS in between — so our updateMany matches
    // nothing. The job is settled; paying out again would refund the same job twice.
    mockJobFindUnique
      .mockResolvedValueOnce({ status: 'RUNNING' }) // our initial read
      .mockResolvedValueOnce({ status: 'FAILED' }); // re-read after losing the CAS
    mockJobUpdateMany.mockResolvedValue({ count: 0 });

    const { cancelJob } = await import('../jobService.js');
    const outcome = await cancelJob(JOB);

    expect(outcome).toEqual({ cancelled: false, reason: 'not_cancellable', status: 'FAILED' });
    expect(mockRefundForStage).not.toHaveBeenCalled();
    expect(mockProgressUpdateMany).not.toHaveBeenCalled();
  });

  it('pulls a QUEUED job out of the queue, but does not try to for a RUNNING one', async () => {
    mockJobFindUnique.mockResolvedValue({ status: 'QUEUED', billingModel: 'DISCOVERY_PREPAID_V1' });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });

    const { cancelJob } = await import('../jobService.js');
    await cancelJob(JOB);
    expect(mockRemoveFromQueue).toHaveBeenCalledWith(JOB);

    vi.clearAllMocks();
    mockRefundForStage.mockResolvedValue({ amount: 5 });
    mockProgressUpdateMany.mockResolvedValue({ count: 0 });
    mockDispatchFindMany.mockResolvedValue([]);
    mockDispatchUpdateMany.mockResolvedValue({ count: 0 });
    mockJobFindUnique.mockResolvedValue({ status: 'RUNNING', billingModel: 'DISCOVERY_PREPAID_V1' });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });

    await cancelJob(JOB);
    expect(mockRemoveFromQueue).not.toHaveBeenCalled();
  });

  it('refuses a job that is past the point of cancelling, without touching credits', async () => {
    mockJobFindUnique.mockResolvedValue({ status: 'AWAITING_SELECTION' });

    const { cancelJob } = await import('../jobService.js');
    const outcome = await cancelJob(JOB);

    expect(outcome).toEqual({
      cancelled: false,
      reason: 'not_cancellable',
      status: 'AWAITING_SELECTION',
    });
    expect(mockJobUpdateMany).not.toHaveBeenCalled();
    expect(mockRefundForStage).not.toHaveBeenCalled();
  });

  it('rolls cancellation back when the exact refund fails, then lets the same request retry once', async () => {
    mockJobFindUnique.mockResolvedValue({
      status: 'RUNNING',
      activeDispatchId: 'dispatch-1',
      billingModel: 'DISCOVERY_PREPAID_V1',
    });
    mockDispatchFindUnique.mockResolvedValue({
      id: 'dispatch-1',
      kind: 'CONTINUE',
      chargeId: 'charge-1',
    });
    mockDispatchFindMany.mockResolvedValue([{
      id: 'dispatch-1',
      state: 'CLAIMED',
      segment: 'discovery',
      chargeId: 'charge-1',
      kind: 'CONTINUE',
      gateStage: null,
    }]);
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockRefundChargeInTx
      .mockRejectedValueOnce(new Error('ledger unavailable'))
      .mockResolvedValueOnce({ id: 'refund-1', amount: 5 });

    const { cancelJob } = await import('../jobService.js');
    await expect(cancelJob(JOB)).rejects.toThrow('ledger unavailable');
    const outcome = await cancelJob(JOB);
    mockJobFindUnique.mockResolvedValueOnce({
      status: 'CANCELLED',
      activeDispatchId: null,
    });
    const duplicate = await cancelJob(JOB);

    expect(outcome).toEqual({ cancelled: true, creditRefunded: 5 });
    expect(duplicate).toEqual({
      cancelled: false,
      reason: 'not_cancellable',
      status: 'CANCELLED',
    });
    expect(mockRefundChargeInTx).toHaveBeenCalledTimes(2);
    expect(mockRefundChargeInTx).toHaveBeenLastCalledWith(prismaMock, 'charge-1');
  });

  it('returns not_found for a job that does not exist', async () => {
    mockJobFindUnique.mockResolvedValue(null);

    const { cancelJob } = await import('../jobService.js');
    expect(await cancelJob(JOB)).toEqual({ cancelled: false, reason: 'not_found' });
    expect(mockJobUpdateMany).not.toHaveBeenCalled();
  });

  it('keeps a zero-amount whole-job reversal FAILED instead of claiming a refund', async () => {
    mockJobFindUnique.mockResolvedValue({
      status: 'RUNNING',
      activeDispatchId: 'dispatch-1',
      billingModel: 'DISCOVERY_PREPAID_V1',
    });
    mockDispatchFindUnique.mockResolvedValue({
      id: 'dispatch-1',
      kind: 'CONTINUE',
      chargeId: 'charge-1',
    });
    mockDispatchFindMany.mockResolvedValue([{
      id: 'dispatch-1',
      state: 'CLAIMED',
      segment: 'discovery',
      chargeId: 'charge-1',
      kind: 'CONTINUE',
      gateStage: null,
    }]);
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockRefundChargeInTx.mockResolvedValue({ id: 'reversal-zero', amount: 0 });

    const { cancelJob } = await import('../jobService.js');
    const outcome = await cancelJob(JOB);

    expect(outcome).toEqual({ cancelled: true, creditRefunded: 0 });
    expect(mockDispatchUpdateMany).toHaveBeenCalledWith({
      where: {
        id: 'dispatch-1',
        state: { in: ['AUTHORIZED', 'CLAIMED'] },
      },
      data: expect.objectContaining({
        state: 'FAILED',
        refundTransactionId: 'reversal-zero',
        refundedAmount: 0,
      }),
    });
    expect(mockDispatchUpdateMany).not.toHaveBeenCalledWith(
      expect.objectContaining({ data: expect.objectContaining({ state: 'REFUNDED' }) }),
    );
  });
});

describe('cancelJob — SEED_IDEA op-scoped cancellation (plan: eager-meandering-feather.md Phase 5)', () => {
  it('refunds a modern seed dispatch by its exact charge inside the parent-state transaction', async () => {
    mockJobFindUnique.mockResolvedValueOnce({ status: 'QUEUED', activeDispatchId: 'dispatch-1' });
    mockDispatchFindUnique.mockResolvedValueOnce({
      id: 'dispatch-1',
      kind: 'SEED_IDEA',
      state: 'AUTHORIZED',
      seedOrdinal: 2,
      sourceMessageId: 'msg-1',
      chargeId: 'charge-seed-2',
    });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockRefundChargeInTx.mockResolvedValue({
      id: 'refund-seed-2',
      amount: 2,
    });

    const { cancelJob } = await import('../jobService.js');
    const outcome = await cancelJob(JOB);

    expect(outcome).toEqual({ cancelled: true, creditRefunded: 2 });
    expect(mockRefundChargeInTx).toHaveBeenCalledWith(prismaMock, 'charge-seed-2');
    expect(mockRefundForStage).not.toHaveBeenCalled();
    expect(mockDispatchUpdateMany).toHaveBeenCalledWith({
      where: { id: 'dispatch-1', state: 'FAILED' },
      data: expect.objectContaining({
        state: 'REFUNDED',
        refundTransactionId: 'refund-seed-2',
        refundedAmount: 2,
      }),
    });
  });

  it('keeps a zero-amount seed reversal FAILED instead of claiming it was refunded', async () => {
    mockJobFindUnique.mockResolvedValueOnce({ status: 'QUEUED', activeDispatchId: 'dispatch-1' });
    mockDispatchFindUnique.mockResolvedValueOnce({
      id: 'dispatch-1',
      kind: 'SEED_IDEA',
      state: 'AUTHORIZED',
      seedOrdinal: 2,
      sourceMessageId: 'msg-1',
      chargeId: 'charge-seed-2',
    });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockRefundChargeInTx.mockResolvedValue({ id: 'reversal-zero', amount: 0 });

    const { cancelJob } = await import('../jobService.js');
    const outcome = await cancelJob(JOB);

    expect(outcome).toEqual({ cancelled: true, creditRefunded: 0 });
    expect(mockDispatchUpdateMany).not.toHaveBeenCalledWith(
      expect.objectContaining({ data: expect.objectContaining({ state: 'REFUNDED' }) }),
    );
    expect(mockChatMessageCreate).toHaveBeenCalledWith(expect.objectContaining({
      data: expect.objectContaining({
        patchJson: expect.objectContaining({ outcome: 'cancelled' }),
      }),
    }));
  });

  it('settles only the seed dispatch, restores AWAITING_SELECTION, refunds seed_idea_N, and writes a terminal seed_settled receipt — never the whole-job CANCELLED path', async () => {
    mockJobFindUnique.mockResolvedValueOnce({ status: 'QUEUED', activeDispatchId: 'dispatch-1' });
    mockDispatchFindUnique.mockResolvedValueOnce({
      id: 'dispatch-1', kind: 'SEED_IDEA', state: 'AUTHORIZED', seedOrdinal: 2, sourceMessageId: 'msg-1',
    });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockRefundForStage.mockResolvedValue({ id: 'refund-seed-2', amount: 2 });

    const { cancelJob } = await import('../jobService.js');
    const outcome = await cancelJob(JOB);

    expect(outcome).toEqual({ cancelled: true, creditRefunded: 2 });
    expect(mockJobUpdateMany).toHaveBeenCalledTimes(1);
    expect(mockJobUpdateMany).toHaveBeenCalledWith({
      where: { id: JOB, status: 'QUEUED', activeDispatchId: 'dispatch-1' },
      data: { status: 'AWAITING_SELECTION', activeDispatchId: null },
    });
    expect(mockRefundForStage).toHaveBeenCalledWith(JOB, 'seed_idea_2');
    // Never the whole-job cancellation write — the parent research job must survive.
    expect(mockJobUpdateMany).not.toHaveBeenCalledWith(
      expect.objectContaining({ data: expect.objectContaining({ status: 'CANCELLED' }) }),
    );
    expect(mockRemoveFromQueue).toHaveBeenCalledWith(JOB);

    // The bug this guards: without this receipt, the durable 'seed_submitted' row (written by
    // POST /:jobId/seed-idea) stays 'pending' forever, which pins the frontend's
    // hasPendingSeed lock open and permanently disables confirm-selection/regenerate/chat on
    // this job. The terminal 'seed_settled' row must be written, keyed to the same
    // sourceMessageId, with outcome 'refunded'.
    expect(mockChatMessageCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        jobId: JOB,
        gateStage: 5,
        role: 'receipt',
        patchJson: expect.objectContaining({
          kind: 'ledger_event',
          event: 'seed_settled',
          sourceMessageId: 'msg-1',
          outcome: 'refunded',
        }),
      }),
    });
  });

  it('does not throw when the dispatch has no sourceMessageId — settles and refunds, but skips the receipt', async () => {
    mockJobFindUnique.mockResolvedValueOnce({ status: 'QUEUED', activeDispatchId: 'dispatch-1' });
    mockDispatchFindUnique.mockResolvedValueOnce({
      id: 'dispatch-1', kind: 'SEED_IDEA', state: 'AUTHORIZED', seedOrdinal: 3, sourceMessageId: null,
    });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockRefundForStage.mockResolvedValue({ id: 'refund-seed-3', amount: 2 });

    const { cancelJob } = await import('../jobService.js');
    const outcome = await cancelJob(JOB);

    expect(outcome).toEqual({ cancelled: true, creditRefunded: 2 });
    expect(mockRefundForStage).toHaveBeenCalledWith(JOB, 'seed_idea_3');
    expect(mockChatMessageCreate).not.toHaveBeenCalled();
  });

  it('pulls a QUEUED seed op out of the redis queue', async () => {
    mockJobFindUnique.mockResolvedValueOnce({ status: 'QUEUED', activeDispatchId: 'dispatch-1' });
    mockDispatchFindUnique.mockResolvedValueOnce({ id: 'dispatch-1', kind: 'SEED_IDEA', state: 'AUTHORIZED', seedOrdinal: 1 });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });

    const { cancelJob } = await import('../jobService.js');
    await cancelJob(JOB);

    expect(mockRemoveFromQueue).toHaveBeenCalledWith(JOB);
  });

  it('reports not_cancellable without refunding when the dispatch was already settled by something else', async () => {
    mockJobFindUnique
      .mockResolvedValueOnce({ status: 'QUEUED', activeDispatchId: 'dispatch-1' })
      .mockResolvedValueOnce({ status: 'AWAITING_SELECTION' }); // re-read after losing the CAS
    mockDispatchFindUnique.mockResolvedValueOnce({ id: 'dispatch-1', kind: 'SEED_IDEA', state: 'AUTHORIZED', seedOrdinal: 1 });
    mockJobUpdateMany.mockResolvedValue({ count: 0 });

    const { cancelJob } = await import('../jobService.js');
    const outcome = await cancelJob(JOB);

    expect(outcome).toEqual({ cancelled: false, reason: 'not_cancellable', status: 'AWAITING_SELECTION' });
    expect(mockRefundForSeedIdeaStage).not.toHaveBeenCalled();
  });

  it('does not cancel or refund a seed after a worker has claimed it', async () => {
    mockJobFindUnique.mockResolvedValueOnce({
      status: 'RUNNING',
      activeDispatchId: 'dispatch-1',
    });
    mockDispatchFindUnique.mockResolvedValueOnce({
      id: 'dispatch-1',
      kind: 'SEED_IDEA',
      state: 'CLAIMED',
      seedOrdinal: 1,
      sourceMessageId: 'msg-1',
      chargeId: 'charge-1',
    });

    const { cancelJob } = await import('../jobService.js');
    const outcome = await cancelJob(JOB);

    expect(outcome).toEqual({
      cancelled: false,
      reason: 'not_cancellable',
      status: 'RUNNING',
    });
    expect(mockJobUpdateMany).not.toHaveBeenCalled();
    expect(mockRefundChargeInTx).not.toHaveBeenCalled();
    expect(mockRefundForSeedIdeaStage).not.toHaveBeenCalled();
  });

  it('a non-seed active dispatch falls through to the normal whole-job cancellation', async () => {
    mockJobFindUnique.mockResolvedValue({
      status: 'RUNNING', activeDispatchId: 'dispatch-1', billingModel: 'DISCOVERY_PREPAID_V1',
    });
    mockDispatchFindUnique.mockResolvedValueOnce({ id: 'dispatch-1', kind: 'CONTINUE', seedOrdinal: null });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });

    const { cancelJob } = await import('../jobService.js');
    const outcome = await cancelJob(JOB);

    expect(outcome).toEqual({ cancelled: true, creditRefunded: 5 });
    expect(mockJobUpdateMany).toHaveBeenCalledWith(
      expect.objectContaining({ data: expect.objectContaining({ status: 'CANCELLED' }) }),
    );
    expect(mockRefundForSeedIdeaStage).not.toHaveBeenCalled();
  });
});

// Money-loss fix: the guided-billing refund loop only ever looked dispatches up BY SEGMENT —
// but two dispatches are opened with no segment at all (jobs.ts: the job-creation dispatch that
// buys guided_s1, and the post-select-solution dispatch that buys deep_research). Cancelling
// while either sits AUTHORIZED silently lost the charge. The fix falls back to naming the
// implicit stage from Job.selectedSolutions, mirroring how the DISCOVERY_PREPAID_V1 branch
// already refunds by stage name rather than by dispatch linkage.
describe('cancelJob — GUIDED_SEGMENTS_V1 falls back to stage-name refund for no-segment dispatches', () => {
  it('refunds guided_s1 for the job-creation dispatch (no solution selected yet)', async () => {
    mockJobFindUnique.mockResolvedValue({
      status: 'QUEUED', billingModel: 'GUIDED_SEGMENTS_V1', selectedSolutions: [],
    });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockDispatchFindMany.mockResolvedValue([
      { id: 'dispatch-create', state: 'AUTHORIZED', segment: null, chargeId: null, kind: 'CONTINUE', gateStage: null },
    ]);
    mockRefundForStage.mockResolvedValue({ amount: 1 });

    const { cancelJob } = await import('../jobService.js');
    const outcome = await cancelJob(JOB);

    expect(outcome).toEqual({ cancelled: true, creditRefunded: 1 });
    expect(mockRefundForStage).toHaveBeenCalledWith(JOB, 'guided_s1');
    expect(mockDispatchUpdateMany).toHaveBeenCalledWith({
      where: {
        id: 'dispatch-create',
        state: { in: ['AUTHORIZED', 'CLAIMED'] },
      },
      data: expect.objectContaining({ state: 'REFUNDED' }),
    });
  });

  it('refunds deep_research for the post-select-solution dispatch (a solution IS selected)', async () => {
    mockJobFindUnique.mockResolvedValue({
      status: 'QUEUED', billingModel: 'GUIDED_SEGMENTS_V1', selectedSolutions: ['Some Idea'],
    });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockDispatchFindMany.mockResolvedValue([
      { id: 'dispatch-phase2', state: 'AUTHORIZED', segment: null, chargeId: null, kind: 'CONTINUE', gateStage: null },
    ]);
    mockRefundForStage.mockResolvedValue({ amount: 15 });

    const { cancelJob } = await import('../jobService.js');
    const outcome = await cancelJob(JOB);

    expect(outcome).toEqual({ cancelled: true, creditRefunded: 15 });
    expect(mockRefundForStage).toHaveBeenCalledWith(JOB, 'deep_research');
  });

  it('still refunds a segment-carrying dispatch by its own segment (regression check)', async () => {
    mockJobFindUnique.mockResolvedValue({
      status: 'AWAITING_GATE', billingModel: 'GUIDED_SEGMENTS_V1', selectedSolutions: [],
    });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockDispatchFindMany.mockResolvedValue([
      { id: 'dispatch-gate', state: 'AUTHORIZED', segment: 'guided_s2_4', chargeId: 'txn-1', kind: 'CONTINUE', gateStage: 1 },
    ]);
    mockRefundChargeInTx.mockResolvedValue({ id: 'refund-gate', amount: 3 });

    const { cancelJob } = await import('../jobService.js');
    const outcome = await cancelJob(JOB);

    expect(outcome).toEqual({ cancelled: true, creditRefunded: 3 });
    expect(mockRefundChargeInTx).toHaveBeenCalledWith(prismaMock, 'txn-1');
    expect(mockRefundForStage).not.toHaveBeenCalled();
  });

  it('does not refund a free apply_stay dispatch (no segment, but gateStage is set — not one of the two implicit charges)', async () => {
    mockJobFindUnique.mockResolvedValue({
      status: 'AWAITING_GATE', billingModel: 'GUIDED_SEGMENTS_V1', selectedSolutions: [],
    });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockDispatchFindMany.mockResolvedValue([
      { id: 'dispatch-apply', state: 'AUTHORIZED', segment: null, chargeId: null, kind: 'APPLY_STAY', gateStage: 1 },
    ]);

    const { cancelJob } = await import('../jobService.js');
    const outcome = await cancelJob(JOB);

    expect(outcome).toEqual({ cancelled: true, creditRefunded: 0 });
    expect(mockRefundForStage).not.toHaveBeenCalled();
  });
});

describe('failJob loses the same race cleanly', () => {
  it('does not overwrite a CANCELLED job, and does not refund on top of it', async () => {
    // The other half of the race. failJob used to read the status and then write FAILED with an
    // unconditional update() — so a cancel that landed in between was silently overwritten AND
    // double-refunded. Its terminal write is now a CAS over the valid pre-fail statuses, so a job
    // that has already been cancelled matches nothing.
    mockJobFindUnique
      .mockResolvedValueOnce({ status: 'RUNNING', regenerationCount: 0 }) // initial read
      .mockResolvedValueOnce({ status: 'CANCELLED' }); // re-read after losing the CAS
    mockJobUpdateMany.mockResolvedValue({ count: 0 });

    const { failJob } = await import('../jobService.js');
    const result = await failJob('job-1', 'worker crashed');

    expect(result).toEqual({ applied: false, job: { status: 'CANCELLED' } });
    expect(mockRefundForStage).not.toHaveBeenCalled();
  });

  it('still fails and refunds a job nobody else has settled', async () => {
    mockJobFindUnique
      .mockResolvedValueOnce({ status: 'RUNNING', regenerationCount: 0 })
      .mockResolvedValueOnce({ id: 'job-1', status: 'FAILED' });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });

    const { failJob } = await import('../jobService.js');
    await failJob('job-1', 'boom', 3);

    expect(mockJobUpdateMany).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({ id: 'job-1', status: { in: expect.any(Array) } }),
        data: expect.objectContaining({ status: 'FAILED', activeDispatchId: null }),
      }),
    );
    expect(mockRefundForStage).toHaveBeenCalled();
  });

  it('does not let an identityless callback fail or refund a modern active dispatch', async () => {
    const { determineFailedStage } = await import('../creditService.js');
    mockJobFindUnique
      .mockResolvedValueOnce({ status: 'RUNNING', regenerationCount: 0, activeDispatchId: 'dispatch-1' })
      .mockResolvedValueOnce({ id: 'job-1', status: 'RUNNING', activeDispatchId: 'dispatch-1' });

    const { failJob } = await import('../jobService.js');
    const result = await failJob('job-1', 'boom', 3);

    expect(result).toMatchObject({
      applied: false,
      job: { status: 'RUNNING', activeDispatchId: 'dispatch-1' },
    });
    expect(mockJobUpdateMany).not.toHaveBeenCalled();
    expect(determineFailedStage).not.toHaveBeenCalled();
    expect(mockRefundForStage).not.toHaveBeenCalled();
  });
});

// Money-loss fix: failJob's guided branch used to look up the in-flight dispatch with
// `segment: { not: null }` — which is exactly the filter that made it find NOTHING for the two
// dispatches opened with no segment (job-creation's guided_s1 charge, and the post-select-solution
// deep_research charge). It early-returned before ever refunding anything. The fix drops that
// filter and falls back to naming the implicit stage from Job.selectedSolutions, mirroring
// cancelJob's guided branch.
describe('failJob — GUIDED_SEGMENTS_V1 falls back to stage-name refund for no-segment dispatches', () => {
  it('refunds guided_s1 when stage-1 fails (no solution selected yet)', async () => {
    mockJobFindUnique
      .mockResolvedValueOnce({ status: 'RUNNING', regenerationCount: 0, activeDispatchId: null })
      .mockResolvedValueOnce({ id: 'job-1', status: 'FAILED', billingModel: 'GUIDED_SEGMENTS_V1', selectedSolutions: [] });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockDispatchFindFirst.mockResolvedValue({
      id: 'dispatch-create', segment: null, chargeId: null, kind: 'CONTINUE', gateStage: null,
    });
    mockRefundForStage.mockResolvedValue({ amount: 1 });

    const { failJob } = await import('../jobService.js');
    await failJob('job-1', 'stage 1 crashed', 1);

    expect(mockRefundForStage).toHaveBeenCalledWith('job-1', 'guided_s1');
    expect(mockDispatchUpdateMany).toHaveBeenCalledWith({
      where: { id: 'dispatch-create' },
      data: { state: 'REFUNDED', settledAt: expect.any(Date) },
    });
  });

  it('refunds deep_research when phase 2 fails (a solution IS selected)', async () => {
    mockJobFindUnique
      .mockResolvedValueOnce({ status: 'RUNNING_PHASE2', regenerationCount: 0, activeDispatchId: null })
      .mockResolvedValueOnce({
        id: 'job-1', status: 'FAILED', billingModel: 'GUIDED_SEGMENTS_V1', selectedSolutions: ['Some Idea'],
      });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockDispatchFindFirst.mockResolvedValue({
      id: 'dispatch-phase2', segment: null, chargeId: null, kind: 'CONTINUE', gateStage: null,
    });
    mockRefundForStage.mockResolvedValue({ amount: 15 });

    const { failJob } = await import('../jobService.js');
    await failJob('job-1', 'phase 2 crashed', 15);

    expect(mockRefundForStage).toHaveBeenCalledWith('job-1', 'deep_research');
  });

  it('still refunds a segment-carrying dispatch by its own segment (regression check)', async () => {
    mockJobFindUnique
      .mockResolvedValueOnce({ status: 'AWAITING_GATE', regenerationCount: 0, activeDispatchId: null })
      .mockResolvedValueOnce({ id: 'job-1', status: 'FAILED', billingModel: 'GUIDED_SEGMENTS_V1', selectedSolutions: [] });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockDispatchFindFirst.mockResolvedValue({
      id: 'dispatch-gate', segment: 'guided_s2_4', chargeId: 'txn-1', kind: 'CONTINUE', gateStage: 1,
    });
    mockRefundForStage.mockResolvedValue({ amount: 3 });

    const { failJob } = await import('../jobService.js');
    await failJob('job-1', 'gate continuation crashed');

    expect(mockRefundForStage).toHaveBeenCalledWith('job-1', 'guided_s2_4');
  });

  it('keeps a legacy guided dispatch FAILED when its allowance reversal restores zero', async () => {
    mockJobFindUnique
      .mockResolvedValueOnce({ status: 'RUNNING', regenerationCount: 0, activeDispatchId: null })
      .mockResolvedValueOnce({
        id: 'job-1',
        status: 'FAILED',
        billingModel: 'GUIDED_SEGMENTS_V1',
        selectedSolutions: [],
      });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockDispatchFindFirst.mockResolvedValue({
      id: 'dispatch-create',
      segment: null,
      chargeId: null,
      kind: 'CONTINUE',
      gateStage: null,
    });
    mockRefundForStage.mockResolvedValue({ id: 'reversal-zero', amount: 0 });

    const { failJob } = await import('../jobService.js');
    await failJob('job-1', 'stage 1 crashed', 1);

    expect(mockDispatchUpdateMany).toHaveBeenCalledWith({
      where: { id: 'dispatch-create' },
      data: { state: 'FAILED', settledAt: expect.any(Date) },
    });
  });

  it('does not refund when there is no open dispatch at all', async () => {
    mockJobFindUnique
      .mockResolvedValueOnce({ status: 'RUNNING', regenerationCount: 0, activeDispatchId: null })
      .mockResolvedValueOnce({ id: 'job-1', status: 'FAILED', billingModel: 'GUIDED_SEGMENTS_V1', selectedSolutions: [] });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockDispatchFindFirst.mockResolvedValue(null);

    const { failJob } = await import('../jobService.js');
    await failJob('job-1', 'crashed with nothing in flight');

    expect(mockRefundForStage).not.toHaveBeenCalled();
  });
});
