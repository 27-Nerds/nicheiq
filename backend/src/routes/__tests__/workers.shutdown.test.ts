import { describe, it, expect, vi, beforeEach } from 'vitest';
import express, { Express } from 'express';
import request from 'supertest';

// ============================================
// Mock dependencies
// ============================================
const mockUpdateMany = vi.fn();
const mockJobFindUnique = vi.fn();
const mockUserFindUnique = vi.fn();

vi.mock('../../services/db.js', () => ({
  prisma: {
    jobProgress: { updateMany: (...args: any[]) => mockUpdateMany(...args) },
    job: { findUnique: (...args: any[]) => mockJobFindUnique(...args) },
    user: { findUnique: (...args: any[]) => mockUserFindUnique(...args) },
  },
}));

const mockFailJob = vi.fn();

vi.mock('../../services/jobService.js', () => ({
  failJob: (...args: any[]) => mockFailJob(...args),
  updateStageProgress: vi.fn(),
  completeJob: vi.fn(),
  getJob: vi.fn(),
}));

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
    { number: 1 }, { number: 2 }, { number: 3 }, { number: 4 },
    { number: 5 }, { number: 6 }, { number: 6.5 }, { number: 7 },
    { number: 8 }, { number: 9 }, { number: 10 }, { number: 11 },
  ],
}));

// ============================================
// Setup Express App
// ============================================
let app: Express;

beforeEach(async () => {
  vi.clearAllMocks();

  mockMarkWorkerShutdown.mockResolvedValue(undefined);
  mockFailJob.mockResolvedValue({ id: 'job-1', status: 'FAILED' });
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
      return { id: jobId, status: 'FAILED' };
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
});
