import { describe, it, expect, vi, beforeEach } from 'vitest';
import express, { Express } from 'express';
import request from 'supertest';

// ============================================
// Mock dependencies
// ============================================
const mockUpdateMany = vi.fn();
const mockJobFindUnique = vi.fn();
const mockJobUpdate = vi.fn();
const mockUserFindUnique = vi.fn();

vi.mock('../../services/db.js', () => ({
  prisma: {
    jobProgress: { updateMany: (...args: any[]) => mockUpdateMany(...args) },
    job: {
      findUnique: (...args: any[]) => mockJobFindUnique(...args),
      update: (...args: any[]) => mockJobUpdate(...args),
    },
    user: { findUnique: (...args: any[]) => mockUserFindUnique(...args) },
  },
}));

const mockFailJob = vi.fn();
const mockUpdateStageProgress = vi.fn();
const mockCompleteJob = vi.fn();
const mockGetJob = vi.fn();
const mockGetJobAsset = vi.fn();
const mockAddJobAsset = vi.fn();

vi.mock('../../services/jobService.js', () => ({
  failJob: (...args: any[]) => mockFailJob(...args),
  updateStageProgress: (...args: any[]) => mockUpdateStageProgress(...args),
  completeJob: (...args: any[]) => mockCompleteJob(...args),
  getJob: (...args: any[]) => mockGetJob(...args),
  getJobAsset: (...args: any[]) => mockGetJobAsset(...args),
  addJobAsset: (...args: any[]) => mockAddJobAsset(...args),
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

const JOB_ID = '00000000-0000-0000-0000-000000000001';
const REPORT_ASSET = { filePath: 'outputs/job-1/report.json' };

beforeEach(async () => {
  vi.clearAllMocks();

  mockFailJob.mockResolvedValue({ id: JOB_ID, status: 'FAILED' });
  mockCompleteJob.mockResolvedValue({ id: JOB_ID, status: 'COMPLETED' });
  mockUpdateMany.mockResolvedValue({ count: 1 });
  mockJobUpdate.mockResolvedValue({ id: JOB_ID });
  mockJobFindUnique.mockResolvedValue({ status: 'RUNNING' });
  mockUpdateStageProgress.mockResolvedValue({});

  app = express();
  app.use(express.json());

  const { workersRouter } = await import('../workers.js');
  app.use('/api/workers', workersRouter);
});

// ============================================
// Tests: /job-failed landing page isolation
// ============================================
describe('POST /api/workers/job-failed — landing page isolation', () => {
  const baseLandingFailPayload = {
    worker_id: 'worker-1',
    job_id: JOB_ID,
    error_message: 'Landing page generation failed: template error',
    error_stage: 11,
  };

  it('error_stage=11 + report asset exists → calls completeJob(), not failJob()', async () => {
    mockGetJobAsset.mockResolvedValue(REPORT_ASSET);

    const res = await request(app)
      .post('/api/workers/job-failed')
      .send(baseLandingFailPayload);

    expect(res.status).toBe(200);
    expect(mockCompleteJob).toHaveBeenCalledWith(JOB_ID, REPORT_ASSET.filePath);
    expect(mockFailJob).not.toHaveBeenCalled();
  });

  it('error_stage=11 + report asset exists → does NOT trigger credit refund (failJob not called)', async () => {
    mockGetJobAsset.mockResolvedValue(REPORT_ASSET);

    await request(app)
      .post('/api/workers/job-failed')
      .send(baseLandingFailPayload);

    // failJob triggers auto-refund internally; since it's not called, no refund happens
    expect(mockFailJob).not.toHaveBeenCalled();
  });

  it('error_stage=11 + report asset exists → marks stage 11 as FAILED via updateMany', async () => {
    mockGetJobAsset.mockResolvedValue(REPORT_ASSET);

    await request(app)
      .post('/api/workers/job-failed')
      .send(baseLandingFailPayload);

    expect(mockUpdateMany).toHaveBeenCalledWith({
      where: { jobId: JOB_ID, stageNumber: 11, status: 'RUNNING' },
      data: { status: 'FAILED', errorMessage: baseLandingFailPayload.error_message },
    });
  });

  it('error_stage=11 + report asset exists → sets landingPageStatus=FAILED on job', async () => {
    mockGetJobAsset.mockResolvedValue(REPORT_ASSET);

    await request(app)
      .post('/api/workers/job-failed')
      .send(baseLandingFailPayload);

    expect(mockJobUpdate).toHaveBeenCalledWith({
      where: { id: JOB_ID },
      data: { landingPageStatus: 'FAILED' },
    });
  });

  it('error_stage=11 + report asset exists → broadcasts failure with name=Landing Page Generation', async () => {
    mockGetJobAsset.mockResolvedValue(REPORT_ASSET);

    await request(app)
      .post('/api/workers/job-failed')
      .send(baseLandingFailPayload);

    expect(mockBroadcastProgress).toHaveBeenCalledWith(JOB_ID, {
      stage: 11,
      name: 'Landing Page Generation',
      status: 'failed',
      error: baseLandingFailPayload.error_message,
    });
  });

  it('error_stage=11 + NO report asset → falls through to normal failJob() path', async () => {
    mockGetJobAsset.mockResolvedValue(null);

    const res = await request(app)
      .post('/api/workers/job-failed')
      .send(baseLandingFailPayload);

    expect(res.status).toBe(200);
    expect(mockFailJob).toHaveBeenCalled();
    expect(mockCompleteJob).not.toHaveBeenCalled();
  });

  it('error_stage=6 + report asset exists → still calls failJob() (not stage 11)', async () => {
    mockGetJobAsset.mockResolvedValue(REPORT_ASSET);

    const payload = { ...baseLandingFailPayload, error_stage: 6 };
    const res = await request(app)
      .post('/api/workers/job-failed')
      .send(payload);

    expect(res.status).toBe(200);
    expect(mockFailJob).toHaveBeenCalled();
    expect(mockCompleteJob).not.toHaveBeenCalled();
  });
});

// ============================================
// Tests: /progress landing page isolation
// ============================================
describe('POST /api/workers/progress — landing page isolation', () => {
  const baseProgressPayload = {
    worker_id: 'worker-1',
    job_id: JOB_ID,
    stage: 11,
    name: 'Landing Page Generation',
    status: 'failed' as const,
    error: 'Landing page template error',
  };

  it('stage=11, status=failed + report asset exists → sets landingPageStatus=FAILED and completeJob()', async () => {
    mockGetJobAsset.mockResolvedValue(REPORT_ASSET);

    const res = await request(app)
      .post('/api/workers/progress')
      .send(baseProgressPayload);

    expect(res.status).toBe(200);
    // Should update landingPageStatus to FAILED
    expect(mockJobUpdate).toHaveBeenCalledWith(
      expect.objectContaining({
        where: { id: JOB_ID },
        data: { landingPageStatus: 'FAILED' },
      })
    );
    // Should complete the job with the report path
    expect(mockCompleteJob).toHaveBeenCalledWith(JOB_ID, REPORT_ASSET.filePath);
    // Should NOT fail the whole job
    expect(mockFailJob).not.toHaveBeenCalled();
  });

  it('stage=11, status=failed + NO report asset → calls failJob() normally', async () => {
    mockGetJobAsset.mockResolvedValue(null);
    mockGetJob.mockResolvedValue({ userId: 'user-1', niche: 'test' });
    mockUserFindUnique.mockResolvedValue(null);

    const res = await request(app)
      .post('/api/workers/progress')
      .send(baseProgressPayload);

    expect(res.status).toBe(200);
    expect(mockFailJob).toHaveBeenCalledWith(JOB_ID, baseProgressPayload.error, 11);
    expect(mockCompleteJob).not.toHaveBeenCalled();
  });

  it('stage=11, status=running → sets landingPageStatus=RUNNING', async () => {
    const runningPayload = {
      worker_id: 'worker-1',
      job_id: JOB_ID,
      stage: 11,
      name: 'Landing Page Generation',
      status: 'running',
    };

    const res = await request(app)
      .post('/api/workers/progress')
      .send(runningPayload);

    expect(res.status).toBe(200);
    expect(mockJobUpdate).toHaveBeenCalledWith(
      expect.objectContaining({
        where: { id: JOB_ID },
        data: { landingPageStatus: 'RUNNING' },
      })
    );
  });

  it('stage=11, status=completed + landing_path (no report_path) → adds landing asset, sets COMPLETED', async () => {
    const completedPayload = {
      worker_id: 'worker-1',
      job_id: JOB_ID,
      stage: 11,
      name: 'Landing Page Generation',
      status: 'completed',
      landing_path: 'outputs/job-1/landing.html',
    };

    const res = await request(app)
      .post('/api/workers/progress')
      .send(completedPayload);

    expect(res.status).toBe(200);
    // Should add the landing page asset
    expect(mockAddJobAsset).toHaveBeenCalledWith(JOB_ID, 'LANDING_PAGE', completedPayload.landing_path);
    // Should set landingPageStatus to COMPLETED
    expect(mockJobUpdate).toHaveBeenCalledWith(
      expect.objectContaining({
        where: { id: JOB_ID },
        data: { landingPageStatus: 'COMPLETED' },
      })
    );
  });
});
