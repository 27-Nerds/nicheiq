import { describe, it, expect, vi, beforeEach } from 'vitest';
import express, { Express } from 'express';
import request from 'supertest';

// ============================================
// Mock dependencies
// ============================================
const mockJobUpdateMany = vi.fn();
const mockJobFindFirst = vi.fn();
const mockJobFindUnique = vi.fn();
const mockJobUpdate = vi.fn();
const mockUserFindUnique = vi.fn();

vi.mock('../../services/db.js', () => ({
  prisma: {
    job: {
      updateMany: (...args: any[]) => mockJobUpdateMany(...args),
      findFirst: (...args: any[]) => mockJobFindFirst(...args),
      findUnique: (...args: any[]) => mockJobFindUnique(...args),
      update: (...args: any[]) => mockJobUpdate(...args),
    },
    user: {
      findUnique: (...args: any[]) => mockUserFindUnique(...args),
    },
  },
}));

vi.mock('../../middleware/auth.js', () => ({
  requireInternalService: (_req: any, _res: any, next: any) => next(),
}));

const mockBroadcastProgress = vi.fn();

vi.mock('../../services/progressBroadcastService.js', () => ({
  broadcastProgress: (...args: any[]) => mockBroadcastProgress(...args),
}));

const mockNotifySolutionsReady = vi.fn();

vi.mock('../../services/notificationService.js', () => ({
  notifyJobStart: vi.fn(),
  notifyJobComplete: vi.fn(),
  notifyJobError: vi.fn(),
  notifySolutionsReady: (...args: any[]) => mockNotifySolutionsReady(...args),
  notifySelectionReminder: vi.fn(),
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
  refundForStage: vi.fn(),
  refundForRegenerationStage: vi.fn(),
}));

vi.mock('../../types/job.js', async (importOriginal) => {
  const actual = await importOriginal() as any;
  return {
    ...actual,
    PIPELINE_STAGES: [
      { number: 1, name: 'Niche Validation', phase: 1 },
      { number: 2, name: 'Search & Discovery', phase: 1 },
      { number: 3, name: 'Pain Point Analysis', phase: 1 },
      { number: 4, name: 'Audience Mapping', phase: 1 },
      { number: 5, name: 'Solution Pipeline', phase: 1 },
      { number: 5.5, name: 'Competitive Analysis', phase: 2 },
      { number: 6, name: 'SEO & Keyword Strategy', phase: 2 },
      { number: 7, name: 'Pricing Validation', phase: 2 },
      { number: 8, name: 'Traffic Monetization', phase: 2 },
      { number: 9, name: 'Market Sizing', phase: 2 },
      { number: 10, name: 'Solution Refinement', phase: 2 },
      { number: 11, name: 'Trend Analysis', phase: 2 },
      { number: 12, name: 'SEO Score Refinement', phase: 2 },
      { number: 13, name: 'Data Source Research', phase: 2 },
      { number: 14, name: 'Report Generation', phase: 2 },
      { number: 15, name: 'Landing Page Generation', phase: 2 },
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
  mockNotifySolutionsReady.mockResolvedValue(undefined);

  app = express();
  app.use(express.json());

  const { workersRouter } = await import('../workers.js');
  app.use('/api/workers', workersRouter);
});

// ============================================
// Tests
// ============================================
describe('POST /api/workers/ideas-ready', () => {
  const validPayload = {
    worker_id: 'w1',
    job_id: jobId,
    solutions: [{ solution_name: 'Sol1' }],
    checkpoint_path: '/tmp/cp',
    total_to_validate: 3,
  };

  it('transitions RUNNING → AWAITING_SELECTION', async () => {
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockJobFindUnique.mockResolvedValue({ userId: 'user-1', niche: 'test' });
    mockUserFindUnique.mockResolvedValue({ email: 'test@example.com' });

    const response = await request(app)
      .post('/api/workers/ideas-ready')
      .send(validPayload);

    expect(response.status).toBe(200);
    expect(response.body.status).toBe('ok');
    expect(mockJobUpdateMany).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({
          id: jobId,
          status: 'RUNNING',
        }),
        data: expect.objectContaining({
          status: 'AWAITING_SELECTION',
        }),
      })
    );
  });

  it('stores solutionIdeas and checkpointPath', async () => {
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockJobFindUnique.mockResolvedValue({ userId: null, niche: 'test' });

    await request(app)
      .post('/api/workers/ideas-ready')
      .send(validPayload);

    const callArgs = mockJobUpdateMany.mock.calls[0][0];
    expect(callArgs.data.solutionIdeas).toEqual([{ solution_name: 'Sol1' }]);
    expect(callArgs.data.phase1CheckpointPath).toBe('/tmp/cp');
  });

  it('sets ideasShownAt timestamp', async () => {
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockJobFindUnique.mockResolvedValue({ userId: null, niche: 'test' });

    await request(app)
      .post('/api/workers/ideas-ready')
      .send(validPayload);

    const callArgs = mockJobUpdateMany.mock.calls[0][0];
    expect(callArgs.data.ideasShownAt).toBeInstanceOf(Date);
  });

  it('broadcasts progress update', async () => {
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockJobFindUnique.mockResolvedValue({ userId: null, niche: 'test' });

    await request(app)
      .post('/api/workers/ideas-ready')
      .send(validPayload);

    expect(mockBroadcastProgress).toHaveBeenCalledWith(jobId, {
      stage: 5,
      name: 'Solution Pipeline',
      status: 'completed',
    });
  });

  it('calls notifySolutionsReady when user has email', async () => {
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockJobFindUnique.mockResolvedValue({ userId: 'user-1', niche: 'test niche' });
    mockUserFindUnique.mockResolvedValue({ email: 'test@example.com' });

    await request(app)
      .post('/api/workers/ideas-ready')
      .send(validPayload);

    expect(mockNotifySolutionsReady).toHaveBeenCalledWith(
      'user-1',
      'test@example.com',
      jobId,
      'test niche',
      1
    );
  });

  it('still returns 200 even if notification fails', async () => {
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockJobFindUnique.mockResolvedValue({ userId: 'user-1', niche: 'test' });
    mockUserFindUnique.mockResolvedValue({ email: 'test@example.com' });
    mockNotifySolutionsReady.mockRejectedValue(new Error('email failed'));

    const response = await request(app)
      .post('/api/workers/ideas-ready')
      .send(validPayload);

    expect(response.status).toBe(200);
  });

  it('skips notification when job.userId is null', async () => {
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockJobFindUnique.mockResolvedValue({ userId: null, niche: 'test' });

    await request(app)
      .post('/api/workers/ideas-ready')
      .send(validPayload);

    expect(mockNotifySolutionsReady).not.toHaveBeenCalled();
  });

  it('skips notification when user not found', async () => {
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockJobFindUnique.mockResolvedValue({ userId: 'user-1', niche: 'test' });
    mockUserFindUnique.mockResolvedValue(null);

    await request(app)
      .post('/api/workers/ideas-ready')
      .send(validPayload);

    expect(mockNotifySolutionsReady).not.toHaveBeenCalled();
  });

  it('returns 200 idempotent when ideas already delivered (lost response retry)', async () => {
    mockJobUpdateMany.mockResolvedValue({ count: 0 });
    mockJobFindUnique.mockResolvedValue({ status: 'AWAITING_SELECTION', ideasShownAt: new Date() });

    const response = await request(app)
      .post('/api/workers/ideas-ready')
      .send(validPayload);

    expect(response.status).toBe(200);
    expect(response.body.idempotent).toBe(true);
    // first delivery already broadcast/notified — the retry must NOT repeat either
    expect(mockBroadcastProgress).not.toHaveBeenCalled();
  });

  it('returns 404 when job does not exist', async () => {
    mockJobUpdateMany.mockResolvedValue({ count: 0 });
    mockJobFindUnique.mockResolvedValue(null);

    const response = await request(app)
      .post('/api/workers/ideas-ready')
      .send(validPayload);

    expect(response.status).toBe(404);
  });

  it('returns 409 with state for a cancelled job', async () => {
    mockJobUpdateMany.mockResolvedValue({ count: 0 });
    mockJobFindUnique.mockResolvedValue({ status: 'CANCELLED', ideasShownAt: null });

    const response = await request(app)
      .post('/api/workers/ideas-ready')
      .send(validPayload);

    expect(response.status).toBe(409);
    expect(response.body.state).toBe('CANCELLED');
  });

  it('returns 409 with state for a failed job (silent-loss scenario)', async () => {
    mockJobUpdateMany.mockResolvedValue({ count: 0 });
    mockJobFindUnique.mockResolvedValue({ status: 'FAILED', ideasShownAt: null });

    const response = await request(app)
      .post('/api/workers/ideas-ready')
      .send(validPayload);

    expect(response.status).toBe(409);
    expect(response.body.state).toBe('FAILED');
    expect(response.body.error).toContain('FAILED');
  });

  it('returns 400 when a solution is missing solution_name', async () => {
    const response = await request(app)
      .post('/api/workers/ideas-ready')
      .send({ ...validPayload, solutions: [{ name: 'wrong-key' }] });

    expect(response.status).toBe(400);
  });

  // Demotion/backfill worker-boundary contract: the Python worker filters
  // solutionIdeas to VISIBLE ideas only (candidate_status not in demoted/absorbed)
  // before POSTing. The backend must store the payload verbatim — it never
  // re-filters and must not strip the new candidate_status/merged_from fields.
  it('stores solutions verbatim, including candidate_status and merged_from fields, unstripped', async () => {
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockJobFindUnique.mockResolvedValue({ userId: null, niche: 'test' });

    const solutions = [
      { solution_name: 'Sol1', candidate_status: 'active' },
      { solution_name: 'Sol2', candidate_status: 'active', merged_from: ['OldSol'] },
    ];

    await request(app)
      .post('/api/workers/ideas-ready')
      .send({ ...validPayload, solutions });

    const callArgs = mockJobUpdateMany.mock.calls[0][0];
    expect(callArgs.data.solutionIdeas).toEqual(solutions);
  });

  it('returns 400 for an empty solutions array', async () => {
    const response = await request(app)
      .post('/api/workers/ideas-ready')
      .send({ ...validPayload, solutions: [] });

    expect(response.status).toBe(400);
  });

  it('returns 400 for invalid payload (missing job_id)', async () => {
    const response = await request(app)
      .post('/api/workers/ideas-ready')
      .send({ worker_id: 'w1' });

    expect(response.status).toBe(400);
    expect(response.body.error).toBe('Validation error');
  });
});

describe('POST /api/workers/regeneration-complete', () => {
  const validPayload = {
    worker_id: 'w1',
    job_id: jobId,
    solutions: [{ name: 'New1' }],
  };

  it('merges new solutions with existing', async () => {
    mockJobFindFirst.mockResolvedValue({ solutionIdeas: [{ name: 'Old1' }] });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });

    const response = await request(app)
      .post('/api/workers/regeneration-complete')
      .send(validPayload);

    expect(response.status).toBe(200);
    const callArgs = mockJobUpdateMany.mock.calls[0][0];
    expect(callArgs.data.solutionIdeas).toEqual([{ name: 'Old1' }, { name: 'New1' }]);
  });

  it('handles null existing solutionIdeas', async () => {
    mockJobFindFirst.mockResolvedValue({ solutionIdeas: null });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });

    const response = await request(app)
      .post('/api/workers/regeneration-complete')
      .send(validPayload);

    expect(response.status).toBe(200);
    const callArgs = mockJobUpdateMany.mock.calls[0][0];
    expect(callArgs.data.solutionIdeas).toEqual([{ name: 'New1' }]);
  });

  it('transitions REGENERATING/QUEUED → AWAITING_SELECTION', async () => {
    mockJobFindFirst.mockResolvedValue({ solutionIdeas: [] });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });

    await request(app)
      .post('/api/workers/regeneration-complete')
      .send(validPayload);

    const callArgs = mockJobUpdateMany.mock.calls[0][0];
    expect(callArgs.where.status).toEqual({ in: ['REGENERATING', 'QUEUED'] });
    expect(callArgs.where.ideasRegeneratedAt).toEqual({ not: null });
    expect(callArgs.data.status).toBe('AWAITING_SELECTION');
  });

  it('broadcasts progress update', async () => {
    mockJobFindFirst.mockResolvedValue({ solutionIdeas: [] });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });

    await request(app)
      .post('/api/workers/regeneration-complete')
      .send(validPayload);

    expect(mockBroadcastProgress).toHaveBeenCalledWith(jobId, {
      stage: 5,
      name: 'Solution Pipeline',
      status: 'completed',
    });
  });

  it('returns 409 when not in REGENERATING state (findFirst null)', async () => {
    mockJobFindFirst.mockResolvedValue(null);

    const response = await request(app)
      .post('/api/workers/regeneration-complete')
      .send(validPayload);

    expect(response.status).toBe(409);
    expect(response.body.error).toBe('Job not in REGENERATING state');
  });

  it('returns 409 on race condition (updateMany count=0)', async () => {
    mockJobFindFirst.mockResolvedValue({ solutionIdeas: [] });
    mockJobUpdateMany.mockResolvedValue({ count: 0 });

    const response = await request(app)
      .post('/api/workers/regeneration-complete')
      .send(validPayload);

    expect(response.status).toBe(409);
    expect(response.body.error).toBe('Job state changed during regeneration');
  });

  it('returns 400 for invalid payload', async () => {
    const response = await request(app)
      .post('/api/workers/regeneration-complete')
      .send({ worker_id: 'w1' });

    expect(response.status).toBe(400);
    expect(response.body.error).toBe('Validation error');
  });

  // Demotion/backfill worker-boundary contract (mirrors ideas-ready): the worker
  // pre-filters to visible-only solutions before POSTing, so the backend must
  // append them verbatim without stripping candidate_status/merged_from.
  it('appends worker-sent solutions verbatim, including candidate_status field, unstripped', async () => {
    mockJobFindFirst.mockResolvedValue({ solutionIdeas: [{ name: 'Old1', candidate_status: 'active' }] });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });

    const newSolutions = [{ name: 'New1', candidate_status: 'active', merged_from: ['Old2'] }];

    await request(app)
      .post('/api/workers/regeneration-complete')
      .send({ ...validPayload, solutions: newSolutions });

    const callArgs = mockJobUpdateMany.mock.calls[0][0];
    expect(callArgs.data.solutionIdeas).toEqual([
      { name: 'Old1', candidate_status: 'active' },
      { name: 'New1', candidate_status: 'active', merged_from: ['Old2'] },
    ]);
  });

  // Zero-visible regenerate case: every regenerated idea got demoted/absorbed
  // again, so the worker sends an empty solutions array. This must be accepted
  // (not rejected as "invalid"), leaving existing stored solutions untouched.
  it('accepts an empty solutions array (zero-visible regenerate case) without error', async () => {
    mockJobFindFirst.mockResolvedValue({ solutionIdeas: [{ name: 'Old1' }] });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });

    const response = await request(app)
      .post('/api/workers/regeneration-complete')
      .send({ ...validPayload, solutions: [] });

    expect(response.status).toBe(200);
    const callArgs = mockJobUpdateMany.mock.calls[0][0];
    expect(callArgs.data.solutionIdeas).toEqual([{ name: 'Old1' }]);
  });

  // Cost tracking (regeneration gap fix): unlike report-ready (which OVERWRITES costUsd with
  // the run's cumulative total), regeneration ADDS spend to an already-settled job, so costUsd
  // must ACCUMULATE onto whatever was already persisted.
  it('accumulates costUsd onto an existing value when cost_summary is present', async () => {
    mockJobFindFirst.mockResolvedValue({ solutionIdeas: [{ name: 'Old1' }], costUsd: 2.5 });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });

    const cost_summary = { total_cost: 0.75, total_tokens: 1000 };

    await request(app)
      .post('/api/workers/regeneration-complete')
      .send({ ...validPayload, cost_summary });

    const callArgs = mockJobUpdateMany.mock.calls[0][0];
    expect(callArgs.data.costUsd).toBeCloseTo(3.25);
    expect(callArgs.data.costSummary).toEqual(cost_summary);
  });

  it('accumulates onto a null existing costUsd as if it were zero', async () => {
    mockJobFindFirst.mockResolvedValue({ solutionIdeas: [], costUsd: null });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });

    const cost_summary = { total_cost: 1.2 };

    await request(app)
      .post('/api/workers/regeneration-complete')
      .send({ ...validPayload, cost_summary });

    const callArgs = mockJobUpdateMany.mock.calls[0][0];
    expect(callArgs.data.costUsd).toBeCloseTo(1.2);
  });

  it('leaves costUsd unchanged when cost_summary is absent', async () => {
    mockJobFindFirst.mockResolvedValue({ solutionIdeas: [], costUsd: 5 });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });

    await request(app)
      .post('/api/workers/regeneration-complete')
      .send(validPayload);

    const callArgs = mockJobUpdateMany.mock.calls[0][0];
    expect(callArgs.data.costUsd).toBeUndefined();
    expect(callArgs.data.costSummary).toBeUndefined();
  });

  it('leaves costUsd unchanged when cost_summary.total_cost is 0', async () => {
    mockJobFindFirst.mockResolvedValue({ solutionIdeas: [], costUsd: 5 });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });

    await request(app)
      .post('/api/workers/regeneration-complete')
      .send({ ...validPayload, cost_summary: { total_cost: 0 } });

    const callArgs = mockJobUpdateMany.mock.calls[0][0];
    expect(callArgs.data.costUsd).toBeUndefined();
  });
});

describe('POST /api/workers/regeneration-failed', () => {
  const validPayload = {
    worker_id: 'w1',
    job_id: jobId,
    error_message: 'LLM rate limit exceeded',
  };

  it('reverts REGENERATING/QUEUED → AWAITING_SELECTION', async () => {
    mockJobFindUnique.mockResolvedValue({ regenerationCount: 1 });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockRegisterWorkerHeartbeat.mockResolvedValue(undefined);

    const response = await request(app)
      .post('/api/workers/regeneration-failed')
      .send(validPayload);

    expect(response.status).toBe(200);
    expect(response.body.status).toBe('ok');
    expect(mockJobUpdateMany).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({
          id: jobId,
          status: { in: ['REGENERATING', 'QUEUED'] },
          ideasRegeneratedAt: { not: null },
        }),
        data: expect.objectContaining({
          status: 'AWAITING_SELECTION',
        }),
      })
    );
  });

  it('clears worker heartbeat', async () => {
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockRegisterWorkerHeartbeat.mockResolvedValue(undefined);

    await request(app)
      .post('/api/workers/regeneration-failed')
      .send(validPayload);

    expect(mockRegisterWorkerHeartbeat).toHaveBeenCalledWith('w1', null);
  });

  it('broadcasts progress update', async () => {
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockRegisterWorkerHeartbeat.mockResolvedValue(undefined);

    await request(app)
      .post('/api/workers/regeneration-failed')
      .send(validPayload);

    expect(mockBroadcastProgress).toHaveBeenCalledWith(jobId, {
      stage: 5,
      name: 'Solution Pipeline',
      status: 'completed',
    });
  });

  it('returns 409 when job not in REGENERATING/QUEUED state', async () => {
    mockJobUpdateMany.mockResolvedValue({ count: 0 });

    const response = await request(app)
      .post('/api/workers/regeneration-failed')
      .send(validPayload);

    expect(response.status).toBe(409);
    expect(response.body.error).toBe('Job not in REGENERATING state');
  });

  it('returns 400 for invalid payload (missing required fields)', async () => {
    const response = await request(app)
      .post('/api/workers/regeneration-failed')
      .send({ worker_id: 'w1' });

    expect(response.status).toBe(400);
    expect(response.body.error).toBe('Validation error');
  });
});
