/**
 * POST /api/workers/seed-complete and /api/workers/seed-failed (plans/eager-meandering-
 * feather.md Phase 5) — the settlement side of the user-seed pipeline. Mirrors
 * workers.gateNotify.test.ts's single-shared-client mocking shape (top-level AND tx-scoped
 * calls hit the same spies), so dispatchGuard/settleDispatch run for REAL against them.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import express, { Express } from 'express';
import request from 'supertest';

const mockJobFindFirst = vi.fn();
const mockJobFindUnique = vi.fn();
const mockJobUpdateMany = vi.fn();
const mockDispatchFindUnique = vi.fn();
const mockDispatchUpdateMany = vi.fn();
const mockChatMessageCreate = vi.fn();

vi.mock('../../services/db.js', () => {
  const client: any = {
    job: {
      findFirst: (...a: any[]) => mockJobFindFirst(...a),
      findUnique: (...a: any[]) => mockJobFindUnique(...a),
      updateMany: (...a: any[]) => mockJobUpdateMany(...a),
    },
    jobDispatch: {
      findUnique: (...a: any[]) => mockDispatchFindUnique(...a),
      updateMany: (...a: any[]) => mockDispatchUpdateMany(...a),
    },
    chatMessage: {
      create: (...a: any[]) => mockChatMessageCreate(...a),
    },
  };
  client.$transaction = (arg: any) => (typeof arg === 'function' ? arg(client) : Promise.all(arg));
  return { prisma: client };
});

vi.mock('../../middleware/auth.js', () => ({
  requireInternalService: (_req: any, _res: any, next: any) => next(),
}));

const mockBroadcastProgress = vi.fn();

vi.mock('../../services/progressBroadcastService.js', () => ({
  broadcastProgress: (...a: any[]) => mockBroadcastProgress(...a),
}));

vi.mock('../../services/notificationService.js', () => ({
  notifyJobStart: vi.fn(),
  notifyJobComplete: vi.fn(),
  notifyJobError: vi.fn(),
  notifySolutionsReady: vi.fn(),
  notifyGateReached: vi.fn(),
  notifyPhase2Start: vi.fn(),
  notifyRegenerationComplete: vi.fn(),
  notifyLandingPageReady: vi.fn(),
}));

vi.mock('../../services/jobService.js', () => ({
  failJob: vi.fn(),
  updateStageProgress: vi.fn(),
  completeJob: vi.fn(),
  getJob: vi.fn(),
  addJobAsset: vi.fn(),
  getJobAsset: vi.fn(),
}));

const mockInvalidatePreviewReportCache = vi.fn();

vi.mock('../../services/assetService.js', () => ({
  invalidatePreviewReportCache: (...a: any[]) => mockInvalidatePreviewReportCache(...a),
}));

const mockRegisterWorkerHeartbeat = vi.fn();

vi.mock('../../services/heartbeatService.js', () => ({
  updateJobHeartbeat: vi.fn(),
  registerWorkerHeartbeat: (...a: any[]) => mockRegisterWorkerHeartbeat(...a),
  markWorkerShutdown: vi.fn(),
}));

vi.mock('../../utils/errorTranslator.js', () => ({
  buildErrorDetails: vi.fn().mockReturnValue(null),
}));

const mockRefundForSeedIdeaStage = vi.fn();

vi.mock('../../services/creditService.js', () => ({
  refundForStage: vi.fn(),
  refundForRegenerationStage: vi.fn(),
  refundForSeedIdeaStage: (...a: any[]) => mockRefundForSeedIdeaStage(...a),
  isGuidedSegment: vi.fn(),
}));

vi.mock('../../types/job.js', async (importOriginal) => {
  const actual = (await importOriginal()) as any;
  return {
    ...actual,
    PIPELINE_STAGES: [
      { number: 1, name: 'Niche Validation', phase: 1 },
      { number: 5, name: 'Solution Pipeline', phase: 1 },
    ],
    TOTAL_STAGES: 16,
  };
});

let app: Express;
const jobId = '00000000-0000-0000-0000-000000000001';
const dispatchId = '11111111-1111-1111-1111-111111111111';

beforeEach(async () => {
  vi.clearAllMocks();
  mockRefundForSeedIdeaStage.mockResolvedValue({ amount: -2 });
  mockChatMessageCreate.mockResolvedValue({ id: 'settled-receipt-1' });

  app = express();
  app.use(express.json());
  const { workersRouter } = await import('../workers.js');
  app.use('/api/workers', workersRouter);
});

describe('POST /api/workers/seed-complete', () => {
  const validPayload = {
    worker_id: 'w1',
    job_id: jobId,
    idea: { solution_name: 'Seed Idea' },
    outcome: 'accepted',
    dispatch_id: dispatchId,
  };

  it('merges the idea into the pool, flips to AWAITING_SELECTION, and settles the dispatch COMPLETED', async () => {
    mockJobFindFirst.mockResolvedValue({ solutionIdeas: [{ solution_name: 'Existing' }], costUsd: 0 });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockDispatchUpdateMany.mockResolvedValue({ count: 1 });

    const response = await request(app).post('/api/workers/seed-complete').send(validPayload);

    expect(response.status).toBe(200);
    expect(mockJobUpdateMany).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({ id: jobId, activeDispatchId: dispatchId }),
        data: expect.objectContaining({
          status: 'AWAITING_SELECTION',
          solutionIdeas: [{ solution_name: 'Existing' }, { solution_name: 'Seed Idea' }],
        }),
      }),
    );
    // The dispatch settlement — same CAS predicate settleDispatch always uses.
    expect(mockDispatchUpdateMany).toHaveBeenCalledWith(
      expect.objectContaining({ where: { id: dispatchId }, data: expect.objectContaining({ state: 'COMPLETED' }) }),
    );
  });

  it('writes a seed_settled receipt keyed on the dispatch sourceMessageId, carrying the outcome', async () => {
    mockJobFindFirst.mockResolvedValue({ solutionIdeas: [], costUsd: 0 });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockDispatchUpdateMany.mockResolvedValue({ count: 1 });
    mockDispatchFindUnique.mockResolvedValue({ sourceMessageId: 'msg-abc' });

    await request(app).post('/api/workers/seed-complete').send({ ...validPayload, outcome: 'demoted' });

    expect(mockDispatchFindUnique).toHaveBeenCalledWith({
      where: { id: dispatchId },
      select: { sourceMessageId: true },
    });
    expect(mockChatMessageCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          jobId, gateStage: 5, role: 'receipt',
          patchJson: expect.objectContaining({
            idea: { solution_name: 'Seed Idea' },
            kind: 'ledger_event', event: 'seed_settled', sourceMessageId: 'msg-abc', outcome: 'demoted',
          }),
        }),
      }),
    );
  });

  it('skips the receipt write (but still settles) when the dispatch has no sourceMessageId', async () => {
    mockJobFindFirst.mockResolvedValue({ solutionIdeas: [], costUsd: 0 });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockDispatchUpdateMany.mockResolvedValue({ count: 1 });
    mockDispatchFindUnique.mockResolvedValue({ sourceMessageId: null });

    const response = await request(app).post('/api/workers/seed-complete').send(validPayload);

    expect(response.status).toBe(200);
    expect(mockChatMessageCreate).not.toHaveBeenCalledWith(
      expect.objectContaining({ data: expect.objectContaining({ role: 'receipt' }) }),
    );
    expect(mockChatMessageCreate).toHaveBeenCalledWith(
      expect.objectContaining({ data: expect.objectContaining({ origin: 'mutation_followup' }) }),
    );
  });

  it('rejects a stale/superseded dispatch id — CAS matches nothing, job untouched', async () => {
    // The tx-scoped findFirst (guarded by dispatchGuard) matches nothing because the job has
    // moved on to a different attempt.
    mockJobFindFirst.mockResolvedValue(null);
    mockJobFindUnique.mockResolvedValue({ status: 'AWAITING_SELECTION', activeDispatchId: 'a-newer-dispatch' });

    const response = await request(app).post('/api/workers/seed-complete').send(validPayload);

    expect(response.status).toBe(200);
    expect(response.body.stale).toBe(true);
    expect(mockJobUpdateMany).not.toHaveBeenCalled();
    expect(mockDispatchUpdateMany).not.toHaveBeenCalled();
  });

  it('reports idempotent success on a lost-response retry of the SAME (already-completed) dispatch', async () => {
    mockJobFindFirst.mockResolvedValue(null);
    mockJobFindUnique.mockResolvedValue({ status: 'AWAITING_SELECTION', activeDispatchId: null });
    mockDispatchFindUnique.mockResolvedValue({ state: 'COMPLETED' });

    const response = await request(app).post('/api/workers/seed-complete').send(validPayload);

    expect(response.status).toBe(200);
    expect(response.body.idempotent).toBe(true);
  });

  it('returns 409 when the job is in some other unexpected state', async () => {
    mockJobFindFirst.mockResolvedValue(null);
    mockJobFindUnique.mockResolvedValue({ status: 'FAILED', activeDispatchId: dispatchId });

    const response = await request(app).post('/api/workers/seed-complete').send(validPayload);

    expect(response.status).toBe(409);
  });

  it('does NOT append a demoted seed to solutionIdeas — it must not enter the selectable pool', async () => {
    mockJobFindFirst.mockResolvedValue({ solutionIdeas: [{ solution_name: 'Existing' }], costUsd: 0 });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockDispatchUpdateMany.mockResolvedValue({ count: 1 });

    const response = await request(app)
      .post('/api/workers/seed-complete')
      .send({ ...validPayload, outcome: 'demoted' });

    expect(response.status).toBe(200);
    expect(mockJobUpdateMany).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          status: 'AWAITING_SELECTION',
          solutionIdeas: [{ solution_name: 'Existing' }],
        }),
      }),
    );
  });

  it('invalidates the cached preview report so the re-materialized ruled-out record is served next read', async () => {
    mockJobFindFirst.mockResolvedValue({ solutionIdeas: [], costUsd: 0 });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockDispatchUpdateMany.mockResolvedValue({ count: 1 });

    await request(app).post('/api/workers/seed-complete').send({ ...validPayload, outcome: 'demoted' });

    expect(mockInvalidatePreviewReportCache).toHaveBeenCalledWith(jobId);
  });
});

describe('POST /api/workers/seed-failed', () => {
  const validPayload = {
    worker_id: 'w1',
    job_id: jobId,
    error_message: 'birth produced nothing',
    dispatch_id: dispatchId,
  };

  it('reverts QUEUED/RUNNING -> AWAITING_SELECTION, settles the dispatch FAILED, and refunds seed_idea_N', async () => {
    mockDispatchFindUnique.mockResolvedValue({ seedOrdinal: 3, sourceMessageId: 'msg-xyz' });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockDispatchUpdateMany.mockResolvedValue({ count: 1 });

    const response = await request(app).post('/api/workers/seed-failed').send(validPayload);

    expect(response.status).toBe(200);
    expect(mockJobUpdateMany).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({ id: jobId, activeDispatchId: dispatchId }),
        data: { status: 'AWAITING_SELECTION' },
      }),
    );
    expect(mockDispatchUpdateMany).toHaveBeenCalledWith(
      expect.objectContaining({ where: { id: dispatchId }, data: expect.objectContaining({ state: 'FAILED' }) }),
    );
    expect(mockRefundForSeedIdeaStage).toHaveBeenCalledWith(jobId, 3);
    // Promoted FAILED -> REFUNDED once the credit is actually back — a SEPARATE call from the
    // settleDispatch one above (mirrors /gate-failed's own two-step settle).
    expect(mockDispatchUpdateMany).toHaveBeenCalledWith({
      where: { id: dispatchId },
      data: { state: 'REFUNDED' },
    });
  });

  it('does not promote to REFUNDED when there is nothing to refund (no charge existed for this ordinal)', async () => {
    mockDispatchFindUnique.mockResolvedValue({ seedOrdinal: 3, sourceMessageId: 'msg-xyz' });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockDispatchUpdateMany.mockResolvedValue({ count: 1 });
    mockRefundForSeedIdeaStage.mockResolvedValue(null);

    await request(app).post('/api/workers/seed-failed').send(validPayload);

    expect(mockDispatchUpdateMany).not.toHaveBeenCalledWith(
      expect.objectContaining({ data: { state: 'REFUNDED' } }),
    );
  });

  it('writes a seed_settled receipt with outcome=failed keyed on the dispatch sourceMessageId', async () => {
    mockDispatchFindUnique.mockResolvedValue({ seedOrdinal: 1, sourceMessageId: 'msg-xyz' });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockDispatchUpdateMany.mockResolvedValue({ count: 1 });

    await request(app).post('/api/workers/seed-failed').send(validPayload);

    expect(mockChatMessageCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          jobId, gateStage: 5, role: 'receipt',
          patchJson: expect.objectContaining({
            kind: 'ledger_event', event: 'seed_settled', sourceMessageId: 'msg-xyz', outcome: 'failed',
          }),
        }),
      }),
    );
  });

  it('never refunds a stale/superseded dispatch id', async () => {
    // The dispatch row itself (fetched up front, real jobDispatch.findUnique).
    mockDispatchFindUnique.mockResolvedValue({ seedOrdinal: 1, sourceMessageId: 'msg-xyz' });
    mockJobUpdateMany.mockResolvedValue({ count: 0 }); // CAS misses — superseded
    // Post-mortem read of the JOB (not the dispatch) to diagnose the miss.
    mockJobFindUnique.mockResolvedValue({ status: 'AWAITING_SELECTION', activeDispatchId: 'a-newer-dispatch' });

    const response = await request(app).post('/api/workers/seed-failed').send(validPayload);

    expect(response.status).toBe(200);
    expect(response.body.stale).toBe(true);
    expect(mockRefundForSeedIdeaStage).not.toHaveBeenCalled();
  });

  it('a lost-response retry after the dispatch already settled never refunds twice', async () => {
    // settleDispatch nulls activeDispatchId on success, so a retry naming the NOW-settled
    // dispatch id reads back as a mismatch (same "stale" classification gate-failed's
    // identical pre-existing check produces for this exact scenario) — harmless either way,
    // since BOTH branches return 200 without touching credits again.
    mockDispatchFindUnique.mockResolvedValue({ seedOrdinal: 1, sourceMessageId: 'msg-xyz' });
    mockJobFindUnique.mockResolvedValue({ status: 'AWAITING_SELECTION', activeDispatchId: null });
    mockJobUpdateMany.mockResolvedValue({ count: 0 });

    const response = await request(app).post('/api/workers/seed-failed').send(validPayload);

    expect(response.status).toBe(200);
    expect(mockRefundForSeedIdeaStage).not.toHaveBeenCalled();
  });
});
