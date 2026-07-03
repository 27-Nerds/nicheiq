import { describe, it, expect, vi, beforeEach } from 'vitest';
import express, { Express } from 'express';
import request from 'supertest';

// ============================================
// Mock dependencies
// ============================================
const mockJobUpdateMany = vi.fn();
const mockJobFindUnique = vi.fn();
const mockJobUpdate = vi.fn();

vi.mock('../../services/db.js', () => ({
  prisma: {
    job: {
      updateMany: (...args: any[]) => mockJobUpdateMany(...args),
      findUnique: (...args: any[]) => mockJobFindUnique(...args),
      update: (...args: any[]) => mockJobUpdate(...args),
    },
  },
}));

const mockRegisterWorkerHeartbeat = vi.fn();

vi.mock('../../services/heartbeatService.js', () => ({
  updateJobHeartbeat: vi.fn(),
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
  mockNotifyJobStart.mockResolvedValue(undefined);

  app = express();
  app.use(express.json());

  const { workersRouter } = await import('../workers.js');
  app.use('/api/workers', workersRouter);
});

// ============================================
// Tests
// ============================================
describe('POST /api/workers/job-started', () => {
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
    it.each(['FAILED', 'COMPLETED', 'AWAITING_SELECTION'])(
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
