import { describe, it, expect, vi, beforeEach } from 'vitest';
import express, { Express } from 'express';
import request from 'supertest';

// ============================================
// Mock dependencies
// ============================================
const mockUpdateMany = vi.fn();
const mockJobFindUnique = vi.fn();
const mockDispatchFindFirst = vi.fn();
const mockUserFindUnique = vi.fn();

vi.mock('../../services/db.js', () => ({
  prisma: {
    jobProgress: { updateMany: (...args: any[]) => mockUpdateMany(...args) },
    job: { findUnique: (...args: any[]) => mockJobFindUnique(...args) },
    jobDispatch: { findFirst: (...args: any[]) => mockDispatchFindFirst(...args) },
    user: { findUnique: (...args: any[]) => mockUserFindUnique(...args) },
  },
}));

const mockFailJob = vi.fn();
const mockCancelRegenerationDispatch = vi.fn();
const mockCancelSeedIdeaDispatch = vi.fn();
const mockFailLandingPageDispatch = vi.fn();

vi.mock('../../services/jobService.js', () => ({
  failJob: (...args: any[]) => mockFailJob(...args),
  cancelRegenerationDispatch: (...args: any[]) => mockCancelRegenerationDispatch(...args),
  cancelSeedIdeaDispatch: (...args: any[]) => mockCancelSeedIdeaDispatch(...args),
  updateStageProgress: vi.fn(),
  completeJob: vi.fn(),
  getJob: vi.fn(),
}));

vi.mock('../../services/dispatchService.js', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../services/dispatchService.js')>();
  return {
    ...actual,
    failLandingPageDispatch: (...args: any[]) => mockFailLandingPageDispatch(...args),
  };
});

const mockBroadcastProgress = vi.fn();

vi.mock('../../services/progressBroadcastService.js', () => ({
  broadcastProgress: (...args: any[]) => mockBroadcastProgress(...args),
}));

vi.mock('../../middleware/auth.js', () => ({
  requireInternalService: (_req: any, _res: any, next: any) => next(),
}));

const mockMarkWorkerShutdown = vi.fn();

vi.mock('../../services/heartbeatService.js', () => ({
  updateJobHeartbeat: vi.fn(),
  registerWorkerHeartbeat: vi.fn(),
  markWorkerShutdown: (...args: any[]) => mockMarkWorkerShutdown(...args),
}));

vi.mock('../../services/notificationService.js', () => ({
  notifyJobStart: vi.fn(),
  notifyJobComplete: vi.fn(),
  notifyJobError: vi.fn().mockResolvedValue(undefined),
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

beforeEach(async () => {
  vi.clearAllMocks();

  mockMarkWorkerShutdown.mockResolvedValue(undefined);
  mockFailJob.mockResolvedValue({
    applied: true,
    job: { id: 'job-1', status: 'FAILED' },
  });
  mockCancelRegenerationDispatch.mockResolvedValue({ cancelled: true, creditRefunded: 3 });
  mockCancelSeedIdeaDispatch.mockResolvedValue({ cancelled: true, creditRefunded: 2 });
  mockFailLandingPageDispatch.mockResolvedValue(true);
  mockDispatchFindFirst.mockResolvedValue(null);
  mockUpdateMany.mockResolvedValue({ count: 1 });
  mockUserFindUnique.mockResolvedValue(null);

  app = express();
  app.use(express.json());

  const { workersRouter } = await import('../workers.js');
  app.use('/api/workers', workersRouter);
});

// ============================================
// Tests
// ============================================
describe('POST /api/workers/shutdown - stage marking', () => {
  it('marks running stages when worker shuts down with active RUNNING job', async () => {
    const jobId = '00000000-0000-0000-0000-000000000001';
    mockJobFindUnique.mockResolvedValue({
      status: 'RUNNING',
      niche: 'test niche',
      userId: 'user-1',
    });

    const response = await request(app)
      .post('/api/workers/shutdown')
      .send({
        worker_id: 'worker-1',
        job_id: jobId,
        reason: 'SIGTERM',
      });

    expect(response.status).toBe(200);
    expect(mockUpdateMany).toHaveBeenCalledWith({
      where: { jobId, status: 'RUNNING' },
      data: {
        status: 'FAILED',
        errorMessage: expect.stringContaining('Worker shutdown'),
      },
    });
  });

  it('broadcasts progress after stage update', async () => {
    const jobId = '00000000-0000-0000-0000-000000000001';
    mockJobFindUnique.mockResolvedValue({
      status: 'RUNNING',
      niche: 'test niche',
      userId: null,
    });

    const callOrder: string[] = [];
    mockFailJob.mockImplementation(async () => {
      callOrder.push('failJob');
      return { applied: true, job: { id: jobId, status: 'FAILED' } };
    });
    mockUpdateMany.mockImplementation(async () => {
      callOrder.push('updateMany');
      return { count: 1 };
    });
    mockBroadcastProgress.mockImplementation(() => {
      callOrder.push('broadcastProgress');
    });

    await request(app)
      .post('/api/workers/shutdown')
      .send({
        worker_id: 'worker-1',
        job_id: jobId,
        reason: 'SIGTERM',
      });

    expect(callOrder).toEqual(['failJob', 'updateMany', 'broadcastProgress']);
  });

  it('does not attempt stage update when no active job', async () => {
    await request(app)
      .post('/api/workers/shutdown')
      .send({
        worker_id: 'worker-1',
        reason: 'graceful shutdown',
      });

    expect(mockUpdateMany).not.toHaveBeenCalled();
    expect(mockFailJob).not.toHaveBeenCalled();
  });

  it('does not attempt stage update when job is not RUNNING', async () => {
    mockJobFindUnique.mockResolvedValue({
      status: 'COMPLETED',
      niche: 'test niche',
      userId: null,
    });

    await request(app)
      .post('/api/workers/shutdown')
      .send({
        worker_id: 'worker-1',
        job_id: '00000000-0000-0000-0000-000000000001',
        reason: 'SIGTERM',
      });

    expect(mockUpdateMany).not.toHaveBeenCalled();
    expect(mockFailJob).not.toHaveBeenCalled();
  });

  it('passes a Phase-2 shutdown dispatch identity into exact failure settlement', async () => {
    const jobId = '00000000-0000-0000-0000-000000000001';
    const dispatchId = '00000000-0000-4000-8000-000000000010';
    mockJobFindUnique.mockResolvedValue({
      status: 'RUNNING_PHASE2',
      niche: 'test niche',
      userId: null,
      activeDispatchId: dispatchId,
    });

    await request(app)
      .post('/api/workers/shutdown')
      .send({
        worker_id: 'worker-1',
        job_id: jobId,
        reason: 'SIGTERM',
        dispatch_id: dispatchId,
      });

    expect(mockFailJob).toHaveBeenCalledWith(
      jobId,
      expect.stringContaining('Worker shutdown'),
      undefined,
      undefined,
      undefined,
      'WORKER_CRASH',
      undefined,
      dispatchId,
    );
  });

  it('settles a regeneration shutdown without failing the parent selection job', async () => {
    const jobId = '00000000-0000-0000-0000-000000000001';
    const dispatchId = '00000000-0000-4000-8000-000000000010';
    mockJobFindUnique.mockResolvedValue({
      status: 'REGENERATING',
      niche: 'test niche',
      userId: null,
      activeDispatchId: dispatchId,
    });
    mockDispatchFindFirst.mockResolvedValue({
      id: dispatchId,
      kind: 'REGENERATE',
      segment: 'regenerate_ideas_2',
      chargeId: 'charge-regen-2',
      seedOrdinal: null,
      sourceMessageId: null,
    });

    const response = await request(app)
      .post('/api/workers/shutdown')
      .send({
        worker_id: 'worker-1',
        job_id: jobId,
        reason: 'SIGTERM',
        dispatch_id: dispatchId,
      });

    expect(response.status).toBe(200);
    expect(response.body.stale).toBeUndefined();
    expect(mockCancelRegenerationDispatch).toHaveBeenCalledWith(
      jobId,
      {
        id: dispatchId,
        segment: 'regenerate_ideas_2',
        chargeId: 'charge-regen-2',
      },
      'REGENERATING',
      'WORKER_CRASH',
    );
    expect(mockFailJob).not.toHaveBeenCalled();
    expect(mockUpdateMany).not.toHaveBeenCalled();
    expect(mockBroadcastProgress).not.toHaveBeenCalled();
  });

  it('settles a seed shutdown without failing the parent selection job', async () => {
    const jobId = '00000000-0000-0000-0000-000000000001';
    const dispatchId = '00000000-0000-4000-8000-000000000010';
    mockJobFindUnique.mockResolvedValue({
      status: 'RUNNING',
      niche: 'test niche',
      userId: null,
      activeDispatchId: dispatchId,
    });
    mockDispatchFindFirst.mockResolvedValue({
      id: dispatchId,
      kind: 'SEED_IDEA',
      segment: null,
      chargeId: 'charge-seed-3',
      seedOrdinal: 3,
      sourceMessageId: 'message-3',
    });

    const response = await request(app)
      .post('/api/workers/shutdown')
      .send({
        worker_id: 'worker-1',
        job_id: jobId,
        reason: 'SIGTERM',
        dispatch_id: dispatchId,
      });

    expect(response.status).toBe(200);
    expect(response.body.stale).toBeUndefined();
    expect(mockCancelSeedIdeaDispatch).toHaveBeenCalledWith(
      jobId,
      {
        id: dispatchId,
        seedOrdinal: 3,
        sourceMessageId: 'message-3',
        chargeId: 'charge-seed-3',
      },
      'RUNNING',
      'WORKER_CRASH',
    );
    expect(mockFailJob).not.toHaveBeenCalled();
    expect(mockUpdateMany).not.toHaveBeenCalled();
    expect(mockBroadcastProgress).not.toHaveBeenCalled();
  });

  it('settles an active landing shutdown without failing the completed parent job', async () => {
    const jobId = '00000000-0000-0000-0000-000000000001';
    const dispatchId = '00000000-0000-4000-8000-000000000010';
    mockJobFindUnique.mockResolvedValue({
      status: 'COMPLETED',
      niche: 'test niche',
      userId: null,
      activeDispatchId: dispatchId,
      landingPageStatus: 'RUNNING',
    });
    mockDispatchFindFirst.mockResolvedValue({
      id: dispatchId,
      kind: 'CONTINUE',
      segment: 'landing_page',
      chargeId: 'charge-landing',
      seedOrdinal: null,
      sourceMessageId: null,
    });

    const response = await request(app)
      .post('/api/workers/shutdown')
      .send({
        worker_id: 'worker-1',
        job_id: jobId,
        reason: 'SIGTERM',
        dispatch_id: dispatchId,
      });

    expect(response.status).toBe(200);
    expect(response.body.stale).toBeUndefined();
    expect(mockFailLandingPageDispatch).toHaveBeenCalledWith(
      jobId,
      dispatchId,
      'Worker shutdown during landing page generation: SIGTERM.',
    );
    expect(mockFailJob).not.toHaveBeenCalled();
    expect(mockUpdateMany).not.toHaveBeenCalled();
    expect(mockBroadcastProgress).toHaveBeenCalledWith(jobId, {
      stage: 15,
      name: 'Landing Page Generation',
      status: 'failed',
      error: expect.stringContaining('Worker shutdown during landing page generation'),
    });
  });

  it('treats a duplicate regeneration shutdown as stale without failing the parent', async () => {
    const jobId = '00000000-0000-0000-0000-000000000001';
    const dispatchId = '00000000-0000-4000-8000-000000000010';
    mockJobFindUnique.mockResolvedValue({
      status: 'REGENERATING',
      niche: 'test niche',
      userId: null,
      activeDispatchId: dispatchId,
    });
    mockDispatchFindFirst.mockResolvedValue({
      id: dispatchId,
      kind: 'REGENERATE',
      segment: 'regenerate_ideas_2',
      chargeId: 'charge-regen-2',
      seedOrdinal: null,
      sourceMessageId: null,
    });
    mockCancelRegenerationDispatch.mockResolvedValue({
      cancelled: false,
      reason: 'not_cancellable',
      status: 'AWAITING_SELECTION',
    });

    const response = await request(app)
      .post('/api/workers/shutdown')
      .send({
        worker_id: 'worker-1',
        job_id: jobId,
        reason: 'SIGTERM',
        dispatch_id: dispatchId,
      });

    expect(response.status).toBe(200);
    expect(response.body.stale).toBe(true);
    expect(mockFailJob).not.toHaveBeenCalled();
    expect(mockUpdateMany).not.toHaveBeenCalled();
    expect(mockBroadcastProgress).not.toHaveBeenCalled();
  });

  it('does not mark progress or broadcast when shutdown settlement is stale', async () => {
    const dispatchId = '00000000-0000-4000-8000-000000000010';
    mockJobFindUnique.mockResolvedValue({
      status: 'RUNNING',
      niche: 'test niche',
      userId: null,
      activeDispatchId: dispatchId,
    });
    mockFailJob.mockResolvedValue({
      applied: false,
      job: {
        id: 'job-1',
        status: 'RUNNING',
        activeDispatchId: 'newer-dispatch',
      },
    });

    const response = await request(app)
      .post('/api/workers/shutdown')
      .send({
        worker_id: 'worker-1',
        job_id: '00000000-0000-0000-0000-000000000001',
        reason: 'SIGTERM',
        dispatch_id: dispatchId,
      });

    expect(response.status).toBe(200);
    expect(response.body.stale).toBe(true);
    expect(mockFailJob).toHaveBeenCalled();
    expect(mockUpdateMany).not.toHaveBeenCalled();
    expect(mockBroadcastProgress).not.toHaveBeenCalled();
  });

  it('does not let identityless shutdown terminate a modern active dispatch', async () => {
    mockJobFindUnique.mockResolvedValue({
      status: 'RUNNING',
      niche: 'test niche',
      userId: null,
      activeDispatchId: '00000000-0000-4000-8000-000000000010',
    });

    const response = await request(app)
      .post('/api/workers/shutdown')
      .send({
        worker_id: 'worker-1',
        job_id: '00000000-0000-0000-0000-000000000001',
        reason: 'SIGTERM',
      });

    expect(response.status).toBe(200);
    expect(response.body.stale).toBe(true);
    expect(mockFailJob).not.toHaveBeenCalled();
    expect(mockUpdateMany).not.toHaveBeenCalled();
    expect(mockBroadcastProgress).not.toHaveBeenCalled();
  });
});
