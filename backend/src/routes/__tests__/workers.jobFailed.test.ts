import { describe, it, expect, vi, beforeEach } from 'vitest';
import express, { Express } from 'express';
import request from 'supertest';

// ============================================
// Mock dependencies
// ============================================
const mockUpdateMany = vi.fn();
const mockJobFindUnique = vi.fn();

vi.mock('../../services/db.js', () => ({
  prisma: {
    jobProgress: { updateMany: (...args: any[]) => mockUpdateMany(...args) },
    job: { findUnique: (...args: any[]) => mockJobFindUnique(...args) },
  },
}));

const mockFailJob = vi.fn();
const mockUpdateStageProgress = vi.fn();
const mockCompleteJob = vi.fn();
const mockGetJob = vi.fn();

vi.mock('../../services/jobService.js', () => ({
  failJob: (...args: any[]) => mockFailJob(...args),
  updateStageProgress: (...args: any[]) => mockUpdateStageProgress(...args),
  completeJob: (...args: any[]) => mockCompleteJob(...args),
  getJob: (...args: any[]) => mockGetJob(...args),
}));

const mockBroadcastProgress = vi.fn();

vi.mock('../../services/progressBroadcastService.js', () => ({
  broadcastProgress: (...args: any[]) => mockBroadcastProgress(...args),
}));

vi.mock('../../middleware/auth.js', () => ({
  requireInternalService: (_req: any, _res: any, next: any) => next(),
}));

vi.mock('../../services/heartbeatService.js', () => ({
  updateJobHeartbeat: vi.fn(),
  registerWorkerHeartbeat: vi.fn(),
  markWorkerShutdown: vi.fn(),
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

  mockFailJob.mockResolvedValue({ id: 'job-1', status: 'FAILED' });
  mockUpdateMany.mockResolvedValue({ count: 1 });

  app = express();
  app.use(express.json());

  const { workersRouter } = await import('../workers.js');
  app.use('/api/workers', workersRouter);
});

// ============================================
// Tests
// ============================================
describe('POST /api/workers/job-failed - stage marking', () => {
  const validPayload = {
    worker_id: 'worker-1',
    job_id: '00000000-0000-0000-0000-000000000001',
    error_message: 'Stage 6 failed: API rate limit exceeded',
    error_stage: 6,
  };

  it('marks running stages as FAILED when job fails with error_stage', async () => {
    const response = await request(app)
      .post('/api/workers/job-failed')
      .send(validPayload);

    expect(response.status).toBe(200);
    expect(mockUpdateMany).toHaveBeenCalledWith({
      where: { jobId: validPayload.job_id, status: 'RUNNING' },
      data: {
        status: 'FAILED',
        errorMessage: validPayload.error_message,
      },
    });
  });

  it('marks running stages when error_stage is not provided', async () => {
    const payload = {
      worker_id: 'worker-1',
      job_id: '00000000-0000-0000-0000-000000000001',
      error_message: 'Unexpected error',
    };

    await request(app)
      .post('/api/workers/job-failed')
      .send(payload);

    expect(mockUpdateMany).toHaveBeenCalledWith({
      where: { jobId: payload.job_id, status: 'RUNNING' },
      data: {
        status: 'FAILED',
        errorMessage: payload.error_message,
      },
    });
  });

  it('uses updateMany to handle parallel stages (6 and 6.5)', async () => {
    // updateMany targets all RUNNING stages, not just one
    mockUpdateMany.mockResolvedValue({ count: 2 });

    const response = await request(app)
      .post('/api/workers/job-failed')
      .send(validPayload);

    expect(response.status).toBe(200);
    // Verify it uses updateMany (not findFirst + update)
    expect(mockUpdateMany).toHaveBeenCalledTimes(1);
    expect(mockUpdateMany).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({ status: 'RUNNING' }),
      })
    );
  });

  it('stage update happens before broadcastProgress', async () => {
    const callOrder: string[] = [];
    mockFailJob.mockImplementation(async () => {
      callOrder.push('failJob');
      return { id: 'job-1', status: 'FAILED' };
    });
    mockUpdateMany.mockImplementation(async () => {
      callOrder.push('updateMany');
      return { count: 1 };
    });
    mockBroadcastProgress.mockImplementation(() => {
      callOrder.push('broadcastProgress');
    });

    await request(app)
      .post('/api/workers/job-failed')
      .send(validPayload);

    expect(callOrder).toEqual(['failJob', 'updateMany', 'broadcastProgress']);
  });

  it('stage update failure does not break endpoint', async () => {
    mockUpdateMany.mockRejectedValue(new Error('DB connection lost'));

    const response = await request(app)
      .post('/api/workers/job-failed')
      .send(validPayload);

    // Endpoint still returns 200 with job status
    expect(response.status).toBe(200);
    expect(response.body.success).toBe(true);
  });

  it('quality gate stop also marks stages as FAILED', async () => {
    const payload = {
      worker_id: 'worker-1',
      job_id: '00000000-0000-0000-0000-000000000001',
      error_message: 'Insufficient data quality',
      error_stage: 5,
      stop_reason: 'INSUFFICIENT_DATA',
      stop_reason_details: { qualityTier: 'low' },
    };

    await request(app)
      .post('/api/workers/job-failed')
      .send(payload);

    expect(mockUpdateMany).toHaveBeenCalledWith({
      where: { jobId: payload.job_id, status: 'RUNNING' },
      data: {
        status: 'FAILED',
        errorMessage: payload.error_message,
      },
    });
  });

  it('does not set completedAt in updateMany data', async () => {
    await request(app)
      .post('/api/workers/job-failed')
      .send(validPayload);

    const updateManyCall = mockUpdateMany.mock.calls[0][0];
    expect(updateManyCall.data).not.toHaveProperty('completedAt');
  });
});
