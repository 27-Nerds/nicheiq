import { describe, it, expect, vi, beforeEach } from 'vitest';
import express, { Express } from 'express';
import request from 'supertest';

// ============================================
// Mock dependencies
// ============================================
const mockJobUpdateMany = vi.fn();
const mockJobFindUnique = vi.fn();
const mockJobUpdate = vi.fn();
const mockDispatchFindUnique = vi.fn();
const mockDispatchUpdateMany = vi.fn();
const mockUpdateJobHeartbeat = vi.fn();
const mockStartPaidPoolRecovery = vi.fn();
const mockPreparePaidPoolMutation = vi.fn();
const mockCompletePaidPoolRecovery = vi.fn();
const mockInvalidatePreviewReportCache = vi.fn();

vi.mock('../../services/db.js', () => ({
  prisma: {
    job: {
      updateMany: (...args: any[]) => mockJobUpdateMany(...args),
      findUnique: (...args: any[]) => mockJobFindUnique(...args),
      update: (...args: any[]) => mockJobUpdate(...args),
    },
    jobDispatch: {
      findUnique: (...args: any[]) => mockDispatchFindUnique(...args),
      // claimDispatch (the real dispatchService.js) reaches for this via the same mocked
      // prisma when a test sends a dispatch_id.
      updateMany: (...args: any[]) => mockDispatchUpdateMany(...args),
    },
  },
}));

const mockRegisterWorkerHeartbeat = vi.fn();

vi.mock('../../services/heartbeatService.js', () => ({
  updateJobHeartbeat: (...args: any[]) => mockUpdateJobHeartbeat(...args),
  registerWorkerHeartbeat: (...args: any[]) => mockRegisterWorkerHeartbeat(...args),
  markWorkerShutdown: vi.fn(),
}));

const mockNotifyJobStart = vi.fn();

vi.mock('../../services/notificationService.js', () => ({
  notifyJobStart: (...args: any[]) => mockNotifyJobStart(...args),
  notifyJobComplete: vi.fn(),
  notifyJobError: vi.fn(),
}));

vi.mock('../../middleware/auth.js', () => ({
  requireInternalService: (_req: any, _res: any, next: any) => next(),
}));

vi.mock('../../services/jobService.js', () => ({
  failJob: vi.fn(),
  updateStageProgress: vi.fn(),
  completeJob: vi.fn(),
  getJob: vi.fn(),
  addJobAsset: vi.fn(),
  getJobAsset: vi.fn(),
}));

vi.mock('../../services/paidPoolRecoveryService.js', () => ({
  startPaidPoolRecovery: (...args: any[]) => mockStartPaidPoolRecovery(...args),
  preparePaidPoolMutation: (...args: any[]) => mockPreparePaidPoolMutation(...args),
  completePaidPoolRecovery: (...args: any[]) => mockCompletePaidPoolRecovery(...args),
}));

vi.mock('../../services/assetService.js', () => ({
  invalidatePreviewReportCache: (...args: any[]) => mockInvalidatePreviewReportCache(...args),
}));

vi.mock('../../services/progressBroadcastService.js', () => ({
  broadcastProgress: vi.fn(),
}));

vi.mock('../../utils/errorTranslator.js', () => ({
  buildErrorDetails: vi.fn().mockReturnValue(null),
}));

vi.mock('../../types/job.js', () => ({
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
}));

// ============================================
// Setup Express App
// ============================================
let app: Express;
const jobId = '00000000-0000-0000-0000-000000000001';

beforeEach(async () => {
  vi.clearAllMocks();

  mockRegisterWorkerHeartbeat.mockResolvedValue(undefined);
  mockUpdateJobHeartbeat.mockResolvedValue('updated');
  mockNotifyJobStart.mockResolvedValue(undefined);
  mockStartPaidPoolRecovery.mockResolvedValue('started');
  mockPreparePaidPoolMutation.mockResolvedValue('prepared');
  mockCompletePaidPoolRecovery.mockResolvedValue('completed');

  app = express();
  app.use(express.json());

  const { prisma } = await import('../../services/db.js');
  (prisma as any).$transaction = async (cb: any) => cb({
    job: {
      updateMany: (...args: any[]) => mockJobUpdateMany(...args),
      findUnique: (...args: any[]) => mockJobFindUnique(...args),
    },
    jobDispatch: {
      updateMany: (...args: any[]) => mockDispatchUpdateMany(...args),
      findUnique: (...args: any[]) => mockDispatchFindUnique(...args),
    },
  });

  const { workersRouter } = await import('../workers.js');
  app.use('/api/workers', workersRouter);
});

// ============================================
// Tests
// ============================================
describe('POST /api/workers/heartbeat', () => {
  it('passes the exact dispatch identity to heartbeat ownership validation', async () => {
    const dispatchId = '00000000-0000-4000-8000-000000000010';
    mockJobFindUnique.mockResolvedValue({ status: 'RUNNING' });

    const response = await request(app)
      .post('/api/workers/heartbeat')
      .send({
        worker_id: 'worker-1',
        job_id: jobId,
        dispatch_id: dispatchId,
      });

    expect(response.status).toBe(200);
    expect(response.body.shouldCancel).toBe(false);
    expect(mockUpdateJobHeartbeat).toHaveBeenCalledWith(jobId, 'worker-1', dispatchId);
    expect(mockRegisterWorkerHeartbeat).toHaveBeenCalledWith(
      'worker-1',
      jobId,
      undefined,
      undefined,
    );
  });

  it('tells a stale worker to stop and does not register it against the current job', async () => {
    const staleDispatchId = '00000000-0000-4000-8000-000000000010';
    mockUpdateJobHeartbeat.mockResolvedValue('stale');

    const response = await request(app)
      .post('/api/workers/heartbeat')
      .send({
        worker_id: 'worker-old',
        job_id: jobId,
        dispatch_id: staleDispatchId,
      });

    expect(response.status).toBe(200);
    expect(response.body).toMatchObject({
      status: 'ok',
      stale: true,
      shouldCancel: true,
    });
    expect(mockJobFindUnique).not.toHaveBeenCalled();
    expect(mockRegisterWorkerHeartbeat).toHaveBeenCalledWith(
      'worker-old',
      null,
      undefined,
      undefined,
    );
  });
});

describe('POST /api/workers/job-started', () => {
  it('claims only the exact RECOVERING generation token', async () => {
    const dispatchId = '00000000-0000-4000-8000-000000000010';
    const recoveryToken = '00000000-0000-4000-8000-000000000020';
    mockJobFindUnique.mockResolvedValue({
      selectedSolutions: [],
      ideasRegeneratedAt: null,
    });
    mockDispatchFindUnique.mockResolvedValue({
      kind: 'SEED_IDEA',
      segment: null,
      state: 'RECOVERING',
      recoveryToken,
    });

    const response = await request(app)
      .post('/api/workers/job-started')
      .send({
        worker_id: 'recovery-worker',
        job_id: jobId,
        dispatch_id: dispatchId,
        recovery_token: recoveryToken,
      });

    expect(response.status).toBe(200);
    expect(response.body.shouldCancel).toBe(false);
    expect(mockStartPaidPoolRecovery).toHaveBeenCalledWith({
      jobId,
      dispatchId,
      recoveryToken,
      workerId: 'recovery-worker',
    });
    expect(mockJobUpdateMany).not.toHaveBeenCalled();
    expect(mockDispatchUpdateMany).not.toHaveBeenCalled();
    expect(mockRegisterWorkerHeartbeat).toHaveBeenCalledWith('recovery-worker', jobId);
  });

  describe('cancellation handling', () => {
    it('returns shouldCancel: true when job is already CANCELLED', async () => {
      // Simulate: job was cancelled while in queue, so updateMany finds no rows to update
      mockJobUpdateMany.mockResolvedValue({ count: 0 });
      mockJobFindUnique.mockResolvedValue({ status: 'CANCELLED' });

      const response = await request(app)
        .post('/api/workers/job-started')
        .send({ worker_id: 'worker-1', job_id: jobId });

      expect(response.status).toBe(200);
      expect(response.body.shouldCancel).toBe(true);
      expect(response.body.status).toBe('ok');
    });

    it('returns shouldCancel: false and updates status when job is QUEUED', async () => {
      mockJobUpdateMany.mockResolvedValue({ count: 1 });
      mockJobFindUnique
        .mockResolvedValueOnce({ selectedSolutions: [], ideasRegeneratedAt: null })
        .mockResolvedValueOnce({
          id: jobId,
          niche: 'test niche',
          userId: 'user-1',
          user: { id: 'user-1', email: 'test@example.com' },
        });

      const response = await request(app)
        .post('/api/workers/job-started')
        .send({ worker_id: 'worker-1', job_id: jobId });

      expect(response.status).toBe(200);
      expect(response.body.shouldCancel).toBe(false);
      expect(mockJobUpdateMany).toHaveBeenCalledWith({
        where: {
          id: jobId,
          status: { in: ['QUEUED', 'PENDING'] },
          // This worker sent no dispatch id, so it may only start a job that has no active
          // dispatch. That is the narrow legacy path — NOT a bypass. A worker that omits the id
          // for a job which HAS an active dispatch is a stale worker, and must not start it.
          activeDispatchId: null,
        },
        data: expect.objectContaining({
          status: 'RUNNING',
          workerId: 'worker-1',
        }),
      });
    });

    it('does not update status to RUNNING when job is CANCELLED (atomic check)', async () => {
      // Simulate race: job was cancelled between queue pickup and job-started call
      mockJobUpdateMany.mockResolvedValue({ count: 0 });
      mockJobFindUnique.mockResolvedValue({ status: 'CANCELLED' });

      await request(app)
        .post('/api/workers/job-started')
        .send({ worker_id: 'worker-1', job_id: jobId });

      // Verify no unconditional update to RUNNING happened
      expect(mockJobUpdate).not.toHaveBeenCalled();
      // updateMany was called but should not have matched cancelled job
      expect(mockJobUpdateMany).toHaveBeenCalledTimes(1);
    });

    it('handles already RUNNING job gracefully (duplicate call)', async () => {
      // Job already RUNNING - updateMany finds no match
      mockJobUpdateMany.mockResolvedValue({ count: 0 });
      mockJobFindUnique.mockResolvedValue({ status: 'RUNNING' });

      const response = await request(app)
        .post('/api/workers/job-started')
        .send({ worker_id: 'worker-1', job_id: jobId });

      expect(response.status).toBe(200);
      expect(response.body.shouldCancel).toBe(false);
    });

    // Infra review round 2: a stale-requeued job whose heartbeat monitor already marked it
    // FAILED (and refunded it) must NOT be blessed to run again.
    it.each(['FAILED', 'COMPLETED', 'AWAITING_SELECTION', 'AWAITING_GATE'])(
      'returns shouldCancel: true for terminal/settled state %s',
      async (status) => {
        mockJobUpdateMany.mockResolvedValue({ count: 0 });
        mockJobFindUnique.mockResolvedValue({ status });

        const response = await request(app)
          .post('/api/workers/job-started')
          .send({ worker_id: 'worker-1', job_id: jobId });

        expect(response.status).toBe(200);
        expect(response.body.shouldCancel).toBe(true);
      },
    );

    it('returns shouldCancel: true when job does not exist', async () => {
      mockJobUpdateMany.mockResolvedValue({ count: 0 });
      mockJobFindUnique.mockResolvedValue(null);

      const response = await request(app)
        .post('/api/workers/job-started')
        .send({ worker_id: 'worker-1', job_id: jobId });

      expect(response.status).toBe(200);
      expect(response.body.shouldCancel).toBe(true);
    });
  });

  describe('normal operation', () => {
    it('registers worker heartbeat on successful start', async () => {
      mockJobUpdateMany.mockResolvedValue({ count: 1 });
      mockJobFindUnique.mockResolvedValue({
        id: jobId,
        niche: 'test niche',
        userId: null,
        user: null,
      });

      await request(app)
        .post('/api/workers/job-started')
        .send({ worker_id: 'worker-1', job_id: jobId });

      expect(mockRegisterWorkerHeartbeat).toHaveBeenCalledWith('worker-1', jobId);
    });

    it('sends job start notification when user has email', async () => {
      mockJobUpdateMany.mockResolvedValue({ count: 1 });
      mockJobFindUnique.mockResolvedValue({
        id: jobId,
        niche: 'test niche',
        userId: 'user-1',
        user: { id: 'user-1', email: 'test@example.com' },
      });

      await request(app)
        .post('/api/workers/job-started')
        .send({ worker_id: 'worker-1', job_id: jobId });

      expect(mockNotifyJobStart).toHaveBeenCalledWith(
        'user-1',
        'test@example.com',
        jobId,
        'test niche'
      );
    });

    it('does not send notification when job was not started (count: 0, not cancelled)', async () => {
      mockJobUpdateMany.mockResolvedValue({ count: 0 });
      mockJobFindUnique.mockResolvedValue({ status: 'RUNNING' }); // Already running

      await request(app)
        .post('/api/workers/job-started')
        .send({ worker_id: 'worker-1', job_id: jobId });

      expect(mockNotifyJobStart).not.toHaveBeenCalled();
    });
  });

  describe('regeneration detection', () => {
    it('transitions QUEUED → REGENERATING when ideasRegeneratedAt is set and no selectedSolution', async () => {
      mockJobUpdateMany.mockResolvedValue({ count: 1 });
      mockJobFindUnique
        .mockResolvedValueOnce({ selectedSolutions: [], ideasRegeneratedAt: new Date() })
        .mockResolvedValueOnce({ id: jobId, niche: 'test', userId: null, user: null });

      await request(app)
        .post('/api/workers/job-started')
        .send({ worker_id: 'worker-1', job_id: jobId });

      expect(mockJobUpdateMany).toHaveBeenCalledWith({
        where: {
          id: jobId,
          status: { in: ['QUEUED', 'PENDING'] },
          // No dispatch id sent -> may only start a job with no active dispatch (legacy path).
          activeDispatchId: null,
        },
        data: expect.objectContaining({
          status: 'REGENERATING',
          workerId: 'worker-1',
        }),
      });
    });

    it('transitions QUEUED → RUNNING_PHASE2 when selectedSolutions is set', async () => {
      mockJobUpdateMany.mockResolvedValue({ count: 1 });
      mockJobFindUnique
        .mockResolvedValueOnce({ selectedSolutions: ['Sol A'], ideasRegeneratedAt: null })
        .mockResolvedValueOnce({ id: jobId, niche: 'test', userId: null, user: null });

      await request(app)
        .post('/api/workers/job-started')
        .send({ worker_id: 'worker-1', job_id: jobId });

      expect(mockJobUpdateMany).toHaveBeenCalledWith({
        where: {
          id: jobId,
          status: { in: ['QUEUED', 'PENDING'] },
          // No dispatch id sent -> may only start a job with no active dispatch (legacy path).
          activeDispatchId: null,
        },
        data: expect.objectContaining({
          status: 'RUNNING_PHASE2',
          workerId: 'worker-1',
        }),
      });
    });

    it('does not treat as regeneration when selectedSolutions is non-empty (phase-2)', async () => {
      // Has ideasRegeneratedAt but also selectedSolutions — this is a phase-2 job after regen
      mockJobUpdateMany.mockResolvedValue({ count: 1 });
      mockJobFindUnique
        .mockResolvedValueOnce({ selectedSolutions: ['Sol A'], ideasRegeneratedAt: new Date() })
        .mockResolvedValueOnce({ id: jobId, niche: 'test', userId: null, user: null });

      await request(app)
        .post('/api/workers/job-started')
        .send({ worker_id: 'worker-1', job_id: jobId });

      expect(mockJobUpdateMany).toHaveBeenCalledWith(
        expect.objectContaining({
          data: expect.objectContaining({
            status: 'RUNNING_PHASE2',
          }),
        })
      );
    });

    it('a SEED_IDEA dispatch takes precedence: RUNNING, not REGENERATING, even when ideasRegeneratedAt is set from an earlier regeneration this run', async () => {
      // ideasRegeneratedAt is a run-level marker that never clears — a seed submitted on a job
      // that regenerated earlier this run would otherwise satisfy the isRegenerate heuristic
      // (ideasRegeneratedAt != null && !hasSelections is true for a seed op too) and get
      // mislabelled REGENERATING. The dispatch kind must win.
      const dispatchId = '00000000-0000-0000-0000-0000000000aa';
      mockJobUpdateMany.mockResolvedValue({ count: 1 });
      mockDispatchUpdateMany.mockResolvedValue({ count: 1 }); // claimDispatch succeeds
      mockDispatchFindUnique.mockResolvedValue({ kind: 'SEED_IDEA' });
      mockJobFindUnique
        .mockResolvedValueOnce({ selectedSolutions: [], ideasRegeneratedAt: new Date() })
        .mockResolvedValueOnce({ id: jobId, niche: 'test', userId: null, user: null });

      await request(app)
        .post('/api/workers/job-started')
        .send({ worker_id: 'worker-1', job_id: jobId, dispatch_id: dispatchId });

      expect(mockDispatchFindUnique).toHaveBeenCalledWith({
        where: { id: dispatchId },
        select: { kind: true, segment: true, state: true, recoveryToken: true },
      });
      expect(mockJobUpdateMany).toHaveBeenCalledWith(
        expect.objectContaining({
          data: expect.objectContaining({ status: 'RUNNING' }),
        })
      );
    });

    it('claims a landing dispatch while preserving the parent Job as COMPLETED', async () => {
      const dispatchId = '00000000-0000-0000-0000-0000000000ac';
      mockJobUpdateMany.mockResolvedValue({ count: 1 });
      mockDispatchUpdateMany.mockResolvedValue({ count: 1 });
      mockDispatchFindUnique.mockResolvedValue({
        kind: 'CONTINUE',
        segment: 'landing_page',
      });
      mockJobFindUnique
        .mockResolvedValueOnce({ selectedSolutions: [], ideasRegeneratedAt: null })
        .mockResolvedValueOnce(null);

      const res = await request(app)
        .post('/api/workers/job-started')
        .send({ worker_id: 'worker-1', job_id: jobId, dispatch_id: dispatchId });

      expect(res.status).toBe(200);
      expect(res.body.shouldCancel).toBe(false);
      expect(mockJobUpdateMany).toHaveBeenCalledWith({
        where: {
          id: jobId,
          status: 'COMPLETED',
          landingPageStatus: 'QUEUED',
          activeDispatchId: dispatchId,
        },
        data: {
          landingPageStatus: 'RUNNING',
          workerId: 'worker-1',
          lastHeartbeat: expect.any(Date),
        },
      });
      expect(mockDispatchUpdateMany).toHaveBeenCalledWith(
        expect.objectContaining({
          where: expect.objectContaining({
            id: dispatchId,
            jobId,
            segment: 'landing_page',
            OR: expect.arrayContaining([{ state: 'AUTHORIZED' }]),
          }),
          data: expect.objectContaining({ state: 'CLAIMED', workerId: 'worker-1' }),
        }),
      );
      expect(mockNotifyJobStart).not.toHaveBeenCalled();
    });

    describe('atomic dispatched start', () => {
      const dispatchId = '00000000-0000-0000-0000-0000000000bb';

      it('updates the Job before claiming the Dispatch', async () => {
        mockJobUpdateMany.mockResolvedValue({ count: 1 });
        mockDispatchUpdateMany.mockResolvedValue({ count: 1 });
        mockDispatchFindUnique.mockResolvedValue({ kind: 'CONTINUE' });
        mockJobFindUnique
          .mockResolvedValueOnce({ selectedSolutions: [], ideasRegeneratedAt: null })
          .mockResolvedValueOnce({ id: jobId, niche: 'test', userId: null, user: null });

        const response = await request(app)
          .post('/api/workers/job-started')
          .send({ worker_id: 'worker-1', job_id: jobId, dispatch_id: dispatchId });

        expect(response.body.shouldCancel).toBe(false);
        expect(mockJobUpdateMany.mock.invocationCallOrder[0])
          .toBeLessThan(mockDispatchUpdateMany.mock.invocationCallOrder[0]);
        expect(mockDispatchUpdateMany).toHaveBeenCalledWith({
          where: {
            id: dispatchId,
            jobId,
            OR: [
              { state: 'AUTHORIZED' },
              { state: 'CLAIMED', workerId: 'worker-1' },
            ],
          },
          data: {
            state: 'CLAIMED',
            workerId: 'worker-1',
            claimedAt: expect.any(Date),
          },
        });
      });

      it('rejects the worker when the dispatch claim loses after the Job CAS', async () => {
        mockJobUpdateMany.mockResolvedValue({ count: 1 });
        mockDispatchUpdateMany.mockResolvedValue({ count: 0 });
        mockDispatchFindUnique.mockResolvedValue({ kind: 'CONTINUE' });
        mockJobFindUnique.mockResolvedValue({ selectedSolutions: [], ideasRegeneratedAt: null });

        const response = await request(app)
          .post('/api/workers/job-started')
          .send({ worker_id: 'worker-1', job_id: jobId, dispatch_id: dispatchId });

        expect(response.body).toMatchObject({ shouldCancel: true, stale: true });
        expect(mockRegisterWorkerHeartbeat).not.toHaveBeenCalled();
      });

      it('accepts a committed retry only for the worker that owns the claim', async () => {
        mockJobUpdateMany.mockResolvedValue({ count: 0 });
        mockDispatchFindUnique
          .mockResolvedValueOnce({ kind: 'CONTINUE' })
          .mockResolvedValueOnce({ jobId, state: 'CLAIMED', workerId: 'worker-1' });
        mockJobFindUnique
          .mockResolvedValueOnce({ selectedSolutions: [], ideasRegeneratedAt: null })
          .mockResolvedValueOnce({ status: 'RUNNING', activeDispatchId: dispatchId, workerId: 'worker-1' })
          .mockResolvedValueOnce({ status: 'RUNNING', activeDispatchId: dispatchId })
          .mockResolvedValueOnce({ status: 'RUNNING' });

        const response = await request(app)
          .post('/api/workers/job-started')
          .send({ worker_id: 'worker-1', job_id: jobId, dispatch_id: dispatchId });

        expect(response.body.shouldCancel).toBe(false);
        expect(mockRegisterWorkerHeartbeat).toHaveBeenCalledWith('worker-1', jobId);
        expect(mockDispatchUpdateMany).not.toHaveBeenCalled();
      });

      it('rejects a second worker after another worker committed the start', async () => {
        mockJobUpdateMany.mockResolvedValue({ count: 0 });
        mockDispatchFindUnique
          .mockResolvedValueOnce({ kind: 'CONTINUE' })
          .mockResolvedValueOnce({ jobId, state: 'CLAIMED', workerId: 'worker-1' });
        mockJobFindUnique
          .mockResolvedValueOnce({ selectedSolutions: [], ideasRegeneratedAt: null })
          .mockResolvedValueOnce({ status: 'RUNNING', activeDispatchId: dispatchId, workerId: 'worker-1' });

        const response = await request(app)
          .post('/api/workers/job-started')
          .send({ worker_id: 'worker-2', job_id: jobId, dispatch_id: dispatchId });

        expect(response.body).toMatchObject({ shouldCancel: true, stale: true });
        expect(mockRegisterWorkerHeartbeat).not.toHaveBeenCalled();
      });
    });

  });

  describe('validation', () => {
    it('returns 400 for invalid job_id format', async () => {
      const response = await request(app)
        .post('/api/workers/job-started')
        .send({ worker_id: 'worker-1', job_id: 'not-a-uuid' });

      expect(response.status).toBe(400);
      expect(response.body.error).toBe('Validation error');
    });

    it('returns 400 for missing worker_id', async () => {
      const response = await request(app)
        .post('/api/workers/job-started')
        .send({ job_id: jobId });

      expect(response.status).toBe(400);
      expect(response.body.error).toBe('Validation error');
    });
  });
});

describe('POST /api/workers/paid-pool-recovery-complete', () => {
  it('invalidates restored preview data before releasing the recovery worker', async () => {
    const dispatchId = '00000000-0000-4000-8000-000000000010';
    const recoveryToken = '00000000-0000-4000-8000-000000000020';

    const response = await request(app)
      .post('/api/workers/paid-pool-recovery-complete')
      .send({
        worker_id: 'recovery-worker',
        job_id: jobId,
        dispatch_id: dispatchId,
        recovery_token: recoveryToken,
      });

    expect(response.status).toBe(200);
    expect(response.body).toEqual({ status: 'ok', idempotent: false });
    expect(mockCompletePaidPoolRecovery).toHaveBeenCalledWith({
      jobId,
      dispatchId,
      recoveryToken,
      workerId: 'recovery-worker',
    });
    expect(mockInvalidatePreviewReportCache).toHaveBeenCalledWith(jobId);
    expect(mockRegisterWorkerHeartbeat).toHaveBeenCalledWith('recovery-worker', null);
  });
});
