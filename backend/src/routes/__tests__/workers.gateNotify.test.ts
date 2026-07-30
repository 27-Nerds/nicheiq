import { describe, it, expect, vi, beforeEach } from 'vitest';
import express, { Express } from 'express';
import request from 'supertest';

// ============================================
// Mock dependencies (mirrors workers.interactive.test.ts)
// ============================================
const mockJobUpdateMany = vi.fn();
const mockJobFindFirst = vi.fn();
const mockJobFindUnique = vi.fn();
const mockJobUpdate = vi.fn();
const mockUserFindUnique = vi.fn();

// Durable ledger receipts: a same-gate re-arrival (apply_stay round-trip) promotes the
// 'gate_patch_submitted' receipt written by gate-action to 'gate_patch_applied'.
const mockChatMessageFindFirst = vi.fn();
const mockChatMessageUpdate = vi.fn();
const mockChatMessageDelete = vi.fn();
const mockDispatchFindUnique = vi.fn();
const mockDispatchUpdateMany = vi.fn();
const mockDispatchCreate = vi.fn();

vi.mock('../../services/db.js', () => {
  const client: any = {
    job: {
      updateMany: (...args: any[]) => mockJobUpdateMany(...args),
      findFirst: (...args: any[]) => mockJobFindFirst(...args),
      findUnique: (...args: any[]) => mockJobFindUnique(...args),
      update: (...args: any[]) => mockJobUpdate(...args),
    },
    user: {
      findUnique: (...args: any[]) => mockUserFindUnique(...args),
    },
    chatMessage: {
      findFirst: (...args: any[]) => mockChatMessageFindFirst(...args),
      update: (...args: any[]) => mockChatMessageUpdate(...args),
      delete: (...args: any[]) => mockChatMessageDelete(...args),
    },
    // Gate arrival now writes the artifact, promotes the receipt and settles the dispatch in ONE
    // transaction — the promotion used to be a separate call whose failure was swallowed, leaving
    // the artifact changed and its audit row stuck at 'submitted'.
    jobDispatch: {
      findUnique: (...args: any[]) => mockDispatchFindUnique(...args),
      updateMany: (...args: any[]) => mockDispatchUpdateMany(...args),
      create: (...args: any[]) => mockDispatchCreate(...args),
    },
  };
  // Run the callback against the same client, so in-transaction writes hit these same spies.
  client.$transaction = (arg: any) =>
    typeof arg === 'function' ? arg(client) : Promise.all(arg);
  return { prisma: client };
});

vi.mock('../../middleware/auth.js', () => ({
  requireInternalService: (_req: any, _res: any, next: any) => next(),
}));

const mockBroadcastProgress = vi.fn();

vi.mock('../../services/progressBroadcastService.js', () => ({
  broadcastProgress: (...args: any[]) => mockBroadcastProgress(...args),
}));

const mockNotifyGateReached = vi.fn();

vi.mock('../../services/notificationService.js', () => ({
  notifyJobStart: vi.fn(),
  notifyJobComplete: vi.fn(),
  notifyJobError: vi.fn(),
  notifySolutionsReady: vi.fn(),
  notifySelectionReminder: vi.fn(),
  notifyGateReached: (...args: any[]) => mockNotifyGateReached(...args),
}));

vi.mock('../../services/jobService.js', () => ({
  failJob: vi.fn(),
  updateStageProgress: vi.fn(),
  completeJob: vi.fn(),
  getJob: vi.fn(),
  addJobAsset: vi.fn(),
  getJobAsset: vi.fn(),
}));

const mockRegisterWorkerHeartbeat = vi.fn();

vi.mock('../../services/heartbeatService.js', () => ({
  updateJobHeartbeat: vi.fn(),
  registerWorkerHeartbeat: (...args: any[]) => mockRegisterWorkerHeartbeat(...args),
  markWorkerShutdown: vi.fn(),
}));

vi.mock('../../utils/errorTranslator.js', () => ({
  buildErrorDetails: vi.fn().mockReturnValue(null),
}));

vi.mock('../../services/creditService.js', () => ({
  refundChargeInTx: vi.fn(),
  refundForStage: vi.fn(),
  refundForStageInTx: vi.fn(),
  refundForRegenerationStage: vi.fn(),
  isGuidedSegment: vi.fn(),
}));

vi.mock('../../types/job.js', async (importOriginal) => {
  const actual = (await importOriginal()) as any;
  return {
    ...actual,
    PIPELINE_STAGES: [
      { number: 1, name: 'Niche Validation', phase: 1 },
      { number: 2, name: 'Search & Discovery', phase: 1 },
      { number: 3, name: 'Pain Point Analysis', phase: 1 },
      { number: 4, name: 'Audience Mapping', phase: 1 },
      { number: 5, name: 'Solution Pipeline', phase: 1 },
    ],
    TOTAL_STAGES: 16,
  };
});

// ============================================
// Setup Express App
// ============================================
let app: Express;
const jobId = '00000000-0000-0000-0000-000000000001';

beforeEach(async () => {
  vi.clearAllMocks();
  mockNotifyGateReached.mockResolvedValue(undefined);

  app = express();
  app.use(express.json());

  const { workersRouter } = await import('../workers.js');
  app.use('/api/workers', workersRouter);
});

// ============================================
// POST /api/workers/gate-reached
// ============================================
describe('POST /api/workers/gate-reached', () => {
  const validPayload = {
    worker_id: 'w1',
    job_id: jobId,
    gate_stage: 1,
    checkpoint_path: '/tmp/checkpoint-g1',
    gate_artifact: { type: 'niche_validation', niche_description: 'x' },
  };

  it('transitions RUNNING -> AWAITING_GATE and stamps gateStage/gateArtifact/gateReachedAt', async () => {
    mockJobFindUnique
      .mockResolvedValueOnce({ gateStage: null }) // pre-row read (isNewGate check)
      .mockResolvedValueOnce({ userId: 'user-1', niche: 'test' }); // post-update email lookup
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockUserFindUnique.mockResolvedValue({ email: 'test@example.com' });

    const response = await request(app).post('/api/workers/gate-reached').send(validPayload);

    expect(response.status).toBe(200);
    expect(response.body.status).toBe('ok');
    expect(mockJobUpdateMany).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({ id: jobId, status: { in: ['RUNNING', 'QUEUED'] } }),
        data: expect.objectContaining({
          status: 'AWAITING_GATE',
          gateStage: 1,
          gateArtifact: validPayload.gate_artifact,
        }),
      })
    );
  });

  it('resets gateApplyCount to 0 on arrival at a NEW gate stage', async () => {
    mockJobFindUnique
      .mockResolvedValueOnce({ gateStage: 1 }) // was at G1
      .mockResolvedValueOnce({ userId: null, niche: 'test' });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });

    await request(app)
      .post('/api/workers/gate-reached')
      .send({ ...validPayload, gate_stage: 4 }); // now arriving at G2

    const callArgs = mockJobUpdateMany.mock.calls[0][0];
    expect(callArgs.data.gateApplyCount).toBe(0);
  });

  it('does NOT reset gateApplyCount on a same-stage re-arrival (apply_stay round-trip)', async () => {
    mockJobFindUnique
      .mockResolvedValueOnce({ gateStage: 1 }) // already at G1
      .mockResolvedValueOnce({ userId: null, niche: 'test' });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });

    await request(app).post('/api/workers/gate-reached').send(validPayload); // gate_stage: 1 again

    const callArgs = mockJobUpdateMany.mock.calls[0][0];
    expect(callArgs.data.gateApplyCount).toBeUndefined();
  });

  it('accepts a QUEUED job (apply_stay round-trip) as well as RUNNING', async () => {
    mockJobFindUnique
      .mockResolvedValueOnce({ gateStage: 1 })
      .mockResolvedValueOnce({ userId: null, niche: 'test' });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });

    const response = await request(app).post('/api/workers/gate-reached').send(validPayload);

    expect(response.status).toBe(200);
    expect(mockJobUpdateMany.mock.calls[0][0].where.status).toEqual({ in: ['RUNNING', 'QUEUED'] });
  });

  it('broadcasts progress and sends the gate-reached email', async () => {
    mockJobFindUnique
      .mockResolvedValueOnce({ gateStage: null })
      .mockResolvedValueOnce({ userId: 'user-1', niche: 'test niche' });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockUserFindUnique.mockResolvedValue({ email: 'test@example.com' });

    await request(app).post('/api/workers/gate-reached').send(validPayload);

    expect(mockBroadcastProgress).toHaveBeenCalledWith(jobId, {
      stage: 1,
      name: 'Niche Validation',
      status: 'completed',
    });
    expect(mockNotifyGateReached).toHaveBeenCalledWith(
      'user-1', 'test@example.com', jobId, 'test niche', 1
    );
  });

  it('returns 200 idempotent on a lost-response retry (same gate, already AWAITING_GATE)', async () => {
    mockJobUpdateMany.mockResolvedValue({ count: 0 });
    mockJobFindUnique.mockResolvedValue({
      status: 'AWAITING_GATE', gateStage: 1, gateReachedAt: new Date(),
    });

    const response = await request(app).post('/api/workers/gate-reached').send(validPayload);

    expect(response.status).toBe(200);
    expect(response.body.idempotent).toBe(true);
    expect(mockBroadcastProgress).not.toHaveBeenCalled();
  });

  it('returns 200 quietly for a CANCELLED job (nothing to deliver to)', async () => {
    mockJobUpdateMany.mockResolvedValue({ count: 0 });
    mockJobFindUnique.mockResolvedValue({ status: 'CANCELLED', gateStage: null, gateReachedAt: null });

    const response = await request(app).post('/api/workers/gate-reached').send(validPayload);

    expect(response.status).toBe(200);
    expect(response.body.idempotent).toBeUndefined();
  });

  it('returns 404 when job does not exist', async () => {
    mockJobUpdateMany.mockResolvedValue({ count: 0 });
    mockJobFindUnique.mockResolvedValue(null);

    const response = await request(app).post('/api/workers/gate-reached').send(validPayload);

    expect(response.status).toBe(404);
  });

  it('returns 409 for a genuinely conflicting state', async () => {
    mockJobUpdateMany.mockResolvedValue({ count: 0 });
    mockJobFindUnique.mockResolvedValue({ status: 'FAILED', gateStage: null, gateReachedAt: null });

    const response = await request(app).post('/api/workers/gate-reached').send(validPayload);

    expect(response.status).toBe(409);
    expect(response.body.state).toBe('FAILED');
  });

  it('returns 400 for invalid payload (bad gate_stage)', async () => {
    const response = await request(app)
      .post('/api/workers/gate-reached')
      .send({ ...validPayload, gate_stage: 2 });

    expect(response.status).toBe(400);
  });

  it('finding 9 (REGRESSION, top-3): rejects a stale/regressed gate_stage as a no-op '
    + '(a delayed retry of a PREVIOUS gate must not rewind a job already at a LATER gate)', async () => {
    mockJobFindUnique.mockResolvedValueOnce({ gateStage: 4 }); // job already progressed to G2

    const response = await request(app)
      .post('/api/workers/gate-reached')
      .send({ ...validPayload, gate_stage: 1 }); // stale retry of the G1 notification

    expect(response.status).toBe(200);
    expect(response.body.stale).toBe(true);
    expect(mockJobUpdateMany).not.toHaveBeenCalled();
    expect(mockBroadcastProgress).not.toHaveBeenCalled();
  });

  it('finding 9: a same-stage re-arrival (apply_stay round-trip) is NOT treated as stale', async () => {
    mockJobFindUnique
      .mockResolvedValueOnce({ gateStage: 1 })
      .mockResolvedValueOnce({ userId: null, niche: 'test' });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });

    const response = await request(app).post('/api/workers/gate-reached').send(validPayload); // gate_stage: 1

    expect(response.status).toBe(200);
    expect(mockJobUpdateMany).toHaveBeenCalled();
  });

  it('persists real cost_summary spend onto the job', async () => {
    mockJobFindUnique
      .mockResolvedValueOnce({ gateStage: null })
      .mockResolvedValueOnce({ userId: null, niche: 'test' });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });

    await request(app)
      .post('/api/workers/gate-reached')
      .send({ ...validPayload, cost_summary: { total_cost: 0.42 } });

    const callArgs = mockJobUpdateMany.mock.calls[0][0];
    expect(callArgs.data.costUsd).toBe(0.42);
  });
});

// ============================================
// POST /api/workers/gate-failed
// ============================================
describe('POST /api/workers/gate-failed', () => {
  const validPayload = {
    worker_id: 'w1',
    job_id: jobId,
    gate_stage: 1,
    error_message: 'Invalid gate patch: unknown field',
  };

  it('reverts QUEUED -> AWAITING_GATE, guarding on gateStage and re-stamping gateReachedAt', async () => {
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockJobFindUnique.mockResolvedValue({ gateStage: 1 });
    mockRegisterWorkerHeartbeat.mockResolvedValue(undefined);

    const response = await request(app).post('/api/workers/gate-failed').send(validPayload);

    expect(response.status).toBe(200);
    // Codex review finding 8 (BLOCKER): the OLD predicate (status=QUEUED AND gateReachedAt
    // NOT NULL) could never match — the accepted gate-action always clears gateReachedAt on
    // the flip to QUEUED, and /job-started further flips QUEUED -> RUNNING before
    // continue_from_gate even starts. The fixed predicate guards on gateStage instead and
    // accepts QUEUED or RUNNING, re-stamping gateReachedAt on the revert (finding 13 coordination).
    expect(mockJobUpdateMany).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({
          id: jobId, status: { in: ['QUEUED', 'RUNNING'] }, gateStage: 1,
        }),
        data: expect.objectContaining({ status: 'AWAITING_GATE', gateReachedAt: expect.any(Date) }),
      })
    );
  });

  it('finding 8: also reverts a RUNNING job (continue_from_gate failed after /job-started)', async () => {
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockJobFindUnique.mockResolvedValue({ gateStage: 1 });

    const response = await request(app).post('/api/workers/gate-failed').send(validPayload);

    expect(response.status).toBe(200);
    expect(mockJobUpdateMany.mock.calls[0][0].where.status).toEqual({ in: ['QUEUED', 'RUNNING'] });
  });

  it('clears worker heartbeat', async () => {
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockJobFindUnique.mockResolvedValue({ gateStage: 1 });

    await request(app).post('/api/workers/gate-failed').send(validPayload);

    expect(mockRegisterWorkerHeartbeat).toHaveBeenCalledWith('w1', null);
  });

  it('broadcasts progress with the (unchanged) gate stage', async () => {
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockJobFindUnique.mockResolvedValue({ gateStage: 4 });

    await request(app).post('/api/workers/gate-failed').send({ ...validPayload, gate_stage: 4 });

    expect(mockBroadcastProgress).toHaveBeenCalledWith(jobId, {
      stage: 4, name: 'Gate', status: 'completed',
    });
  });

  it('returns 409 when job not in QUEUED/RUNNING state (never reached a gate)', async () => {
    mockJobUpdateMany.mockResolvedValue({ count: 0 });
    mockJobFindUnique.mockResolvedValue({ status: 'PENDING', gateStage: null });

    const response = await request(app).post('/api/workers/gate-failed').send(validPayload);

    expect(response.status).toBe(409);
  });

  it('finding 10 (AMEND): retry against an already-settled AWAITING_GATE (same gateStage) '
    + 'returns 200 idempotent instead of a spurious 409', async () => {
    mockJobUpdateMany.mockResolvedValue({ count: 0 }); // an earlier attempt already reverted it
    mockJobFindUnique.mockResolvedValue({ status: 'AWAITING_GATE', gateStage: 1 });

    const response = await request(app).post('/api/workers/gate-failed').send(validPayload);

    expect(response.status).toBe(200);
    expect(response.body.idempotent).toBe(true);
  });

  it('finding 10: a settled AWAITING_GATE at a DIFFERENT gateStage still 409s', async () => {
    mockJobUpdateMany.mockResolvedValue({ count: 0 });
    mockJobFindUnique.mockResolvedValue({ status: 'AWAITING_GATE', gateStage: 4 });

    const response = await request(app).post('/api/workers/gate-failed').send(validPayload); // gate_stage: 1

    expect(response.status).toBe(409);
  });

  it('accepts a null gate_stage (unexpected pre-gate-stamp failure)', async () => {
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockJobFindUnique.mockResolvedValue({ gateStage: null });

    const response = await request(app)
      .post('/api/workers/gate-failed')
      .send({ ...validPayload, gate_stage: null });

    expect(response.status).toBe(200);
  });

  it('returns 400 for invalid payload (missing required fields)', async () => {
    const response = await request(app).post('/api/workers/gate-failed').send({ worker_id: 'w1' });

    expect(response.status).toBe(400);
    expect(response.body.error).toBe('Validation error');
  });
});
