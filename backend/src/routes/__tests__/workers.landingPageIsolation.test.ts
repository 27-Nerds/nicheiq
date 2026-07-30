import { describe, it, expect, vi, beforeEach } from 'vitest';
import express, { Express } from 'express';
import request from 'supertest';

// ============================================
// Mock dependencies
// ============================================
const mockUpdateMany = vi.fn();
const mockJobFindUnique = vi.fn();
const mockJobUpdate = vi.fn();
const mockJobUpdateMany = vi.fn();
const mockJobDispatchFindUnique = vi.fn();
const mockUserFindUnique = vi.fn();

vi.mock('../../services/db.js', () => ({
  prisma: {
    jobProgress: { updateMany: (...args: any[]) => mockUpdateMany(...args) },
    job: {
      findUnique: (...args: any[]) => mockJobFindUnique(...args),
      update: (...args: any[]) => mockJobUpdate(...args),
      updateMany: (...args: any[]) => mockJobUpdateMany(...args),
    },
    jobDispatch: {
      findUnique: (...args: any[]) => mockJobDispatchFindUnique(...args),
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

const mockCompleteLandingPageDispatch = vi.fn();
const mockFailLandingPageDispatch = vi.fn();

vi.mock('../../services/dispatchService.js', () => ({
  dispatchGuard: (dispatchId?: string | null) =>
    dispatchId ? { activeDispatchId: dispatchId } : { activeDispatchId: null },
  diagnoseGuardMiss: vi.fn().mockResolvedValue('status'),
  startDispatchedJob: vi.fn(),
  startLandingPageDispatch: vi.fn(),
  settleDispatch: vi.fn(),
  completeLandingPageDispatch: (...args: any[]) => mockCompleteLandingPageDispatch(...args),
  failLandingPageDispatch: (...args: any[]) => mockFailLandingPageDispatch(...args),
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
  notifySolutionsReady: vi.fn().mockResolvedValue(undefined),
  notifyPhase2Start: vi.fn().mockResolvedValue(undefined),
  notifyRegenerationComplete: vi.fn().mockResolvedValue(undefined),
  notifyLandingPageReady: vi.fn().mockResolvedValue(undefined),
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

const JOB_ID = '00000000-0000-0000-0000-000000000001';
const REPORT_ASSET = { filePath: 'outputs/job-1/report.json' };

beforeEach(async () => {
  vi.clearAllMocks();

  mockFailJob.mockResolvedValue({
    applied: true,
    job: { id: JOB_ID, status: 'FAILED' },
  });
  mockCompleteJob.mockResolvedValue({ id: JOB_ID, status: 'COMPLETED' });
  mockUpdateMany.mockResolvedValue({ count: 1 });
  mockJobUpdate.mockResolvedValue({ id: JOB_ID });
  mockJobUpdateMany.mockResolvedValue({ count: 1 });
  mockJobFindUnique.mockResolvedValue({ status: 'RUNNING' });
  mockJobDispatchFindUnique.mockResolvedValue(null);
  mockUpdateStageProgress.mockResolvedValue({});
  mockCompleteLandingPageDispatch.mockResolvedValue(true);
  mockFailLandingPageDispatch.mockResolvedValue(true);

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
    error_stage: 15,
  };

  it('error_stage=15 + report asset exists → calls completeJob(), not failJob()', async () => {
    mockGetJobAsset.mockResolvedValue(REPORT_ASSET);

    const res = await request(app)
      .post('/api/workers/job-failed')
      .send(baseLandingFailPayload);

    expect(res.status).toBe(200);
    expect(mockCompleteJob).toHaveBeenCalledWith(JOB_ID, REPORT_ASSET.filePath);
    expect(mockFailJob).not.toHaveBeenCalled();
  });

  it('error_stage=15 + report asset exists → does NOT trigger credit refund (failJob not called)', async () => {
    mockGetJobAsset.mockResolvedValue(REPORT_ASSET);

    await request(app)
      .post('/api/workers/job-failed')
      .send(baseLandingFailPayload);

    // failJob triggers auto-refund internally; since it's not called, no refund happens
    expect(mockFailJob).not.toHaveBeenCalled();
  });

  it('error_stage=15 + report asset exists → marks stage 15 as FAILED via updateMany', async () => {
    mockGetJobAsset.mockResolvedValue(REPORT_ASSET);

    await request(app)
      .post('/api/workers/job-failed')
      .send(baseLandingFailPayload);

    expect(mockUpdateMany).toHaveBeenCalledWith({
      where: { jobId: JOB_ID, stageNumber: 15, status: 'RUNNING' },
      data: { status: 'FAILED', errorMessage: baseLandingFailPayload.error_message },
    });
  });

  it('error_stage=15 + report asset exists → sets landingPageStatus=FAILED on job', async () => {
    mockGetJobAsset.mockResolvedValue(REPORT_ASSET);

    await request(app)
      .post('/api/workers/job-failed')
      .send(baseLandingFailPayload);

    expect(mockJobUpdate).toHaveBeenCalledWith({
      where: { id: JOB_ID },
      data: { landingPageStatus: 'FAILED' },
    });
  });

  it('error_stage=15 + report asset exists → broadcasts failure with name=Landing Page Generation', async () => {
    mockGetJobAsset.mockResolvedValue(REPORT_ASSET);

    await request(app)
      .post('/api/workers/job-failed')
      .send(baseLandingFailPayload);

    expect(mockBroadcastProgress).toHaveBeenCalledWith(JOB_ID, {
      stage: 15,
      name: 'Landing Page Generation',
      status: 'failed',
      error: baseLandingFailPayload.error_message,
    });
  });

  it('error_stage=15 + NO report asset → falls through to normal failJob() path', async () => {
    mockGetJobAsset.mockResolvedValue(null);

    const res = await request(app)
      .post('/api/workers/job-failed')
      .send(baseLandingFailPayload);

    expect(res.status).toBe(200);
    expect(mockFailJob).toHaveBeenCalled();
    expect(mockCompleteJob).not.toHaveBeenCalled();
  });

  it('error_stage=6 + report asset exists → still calls failJob() (not stage 15)', async () => {
    mockGetJobAsset.mockResolvedValue(REPORT_ASSET);

    const payload = { ...baseLandingFailPayload, error_stage: 6 };
    const res = await request(app)
      .post('/api/workers/job-failed')
      .send(payload);

    expect(res.status).toBe(200);
    expect(mockFailJob).toHaveBeenCalled();
    expect(mockCompleteJob).not.toHaveBeenCalled();
  });

  it('modern landing failure settles the exact dispatch and keeps the parent Job COMPLETED', async () => {
    const dispatchId = '00000000-0000-4000-8000-000000000015';
    mockJobFindUnique.mockResolvedValue({
      status: 'COMPLETED',
      activeDispatchId: dispatchId,
    });
    mockGetJobAsset.mockResolvedValue(REPORT_ASSET);

    const res = await request(app)
      .post('/api/workers/job-failed')
      .send({ ...baseLandingFailPayload, dispatch_id: dispatchId });

    expect(res.status).toBe(200);
    expect(res.body.status).toBe('COMPLETED');
    expect(mockFailLandingPageDispatch).toHaveBeenCalledWith(
      JOB_ID,
      dispatchId,
      baseLandingFailPayload.error_message,
    );
    expect(mockCompleteJob).not.toHaveBeenCalled();
    expect(mockJobUpdate).not.toHaveBeenCalled();
  });

  it('duplicate modern landing failure is stale and emits no second projection', async () => {
    const dispatchId = '00000000-0000-4000-8000-000000000015';
    mockJobFindUnique.mockResolvedValue({
      status: 'COMPLETED',
      activeDispatchId: dispatchId,
    });
    mockGetJobAsset.mockResolvedValue(REPORT_ASSET);
    mockFailLandingPageDispatch.mockResolvedValue(false);

    const res = await request(app)
      .post('/api/workers/job-failed')
      .send({ ...baseLandingFailPayload, dispatch_id: dispatchId });

    expect(res.body).toMatchObject({ stale: true, shouldCancel: true });
    expect(mockUpdateMany).not.toHaveBeenCalled();
    expect(mockBroadcastProgress).not.toHaveBeenCalled();
  });
});

// ============================================
// Tests: /progress landing page isolation
// ============================================
describe('POST /api/workers/progress — landing page isolation', () => {
  const baseProgressPayload = {
    worker_id: 'worker-1',
    job_id: JOB_ID,
    stage: 15,
    name: 'Landing Page Generation',
    status: 'failed' as const,
    error: 'Landing page template error',
  };

  it('stage=15, status=failed + report asset exists → sets landingPageStatus=FAILED and completeJob()', async () => {
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

  it('stage=15, status=failed + NO report asset → calls failJob() normally', async () => {
    mockGetJobAsset.mockResolvedValue(null);
    mockGetJob.mockResolvedValue({ userId: 'user-1', niche: 'test' });
    mockUserFindUnique.mockResolvedValue(null);

    const res = await request(app)
      .post('/api/workers/progress')
      .send(baseProgressPayload);

    expect(res.status).toBe(200);
    expect(mockFailJob).toHaveBeenCalledWith(
      JOB_ID,
      baseProgressPayload.error,
      15,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
    );
    expect(mockCompleteJob).not.toHaveBeenCalled();
  });

  it('passes progress.dispatch_id into exact whole-job failure settlement', async () => {
    const dispatchId = '00000000-0000-4000-8000-000000000010';
    mockJobFindUnique.mockResolvedValue({ status: 'RUNNING_PHASE2', activeDispatchId: dispatchId });
    mockGetJobAsset.mockResolvedValue(null);
    mockGetJob.mockResolvedValue(null);

    const res = await request(app)
      .post('/api/workers/progress')
      .send({
        worker_id: 'worker-1',
        job_id: JOB_ID,
        stage: 6,
        name: 'SEO & Keyword Strategy',
        status: 'failed',
        error: 'phase 2 failed',
        dispatch_id: dispatchId,
      });

    expect(res.status).toBe(200);
    expect(mockFailJob).toHaveBeenCalledWith(
      JOB_ID,
      'phase 2 failed',
      6,
      undefined,
      undefined,
      undefined,
      undefined,
      dispatchId,
    );
  });

  it('stops progress failure side effects when the settlement CAS reports a stale attempt', async () => {
    const dispatchId = '00000000-0000-4000-8000-000000000010';
    mockJobFindUnique.mockResolvedValue({ status: 'RUNNING_PHASE2', activeDispatchId: dispatchId });
    mockGetJobAsset.mockResolvedValue(null);
    mockFailJob.mockResolvedValue({
      applied: false,
      job: {
        id: JOB_ID,
        status: 'RUNNING_PHASE2',
        activeDispatchId: 'newer-dispatch',
      },
    });

    const res = await request(app)
      .post('/api/workers/progress')
      .send({
        worker_id: 'worker-1',
        job_id: JOB_ID,
        stage: 6,
        name: 'SEO & Keyword Strategy',
        status: 'failed',
        error: 'late failure',
        dispatch_id: dispatchId,
      });

    expect(res.status).toBe(200);
    expect(res.body).toMatchObject({ stale: true, shouldCancel: true });
    expect(mockUpdateStageProgress).not.toHaveBeenCalled();
    expect(mockBroadcastProgress).not.toHaveBeenCalled();
    expect(mockGetJob).not.toHaveBeenCalled();
  });

  it('rejects identityless progress before writing over a modern active dispatch', async () => {
    mockJobFindUnique.mockResolvedValue({
      status: 'RUNNING_PHASE2',
      activeDispatchId: '00000000-0000-4000-8000-000000000010',
    });

    const res = await request(app)
      .post('/api/workers/progress')
      .send({
        worker_id: 'worker-1',
        job_id: JOB_ID,
        stage: 6,
        name: 'SEO & Keyword Strategy',
        status: 'failed',
        error: 'identityless late failure',
      });

    expect(res.status).toBe(200);
    expect(res.body).toMatchObject({ stale: true, shouldCancel: true });
    expect(mockFailJob).not.toHaveBeenCalled();
    expect(mockUpdateStageProgress).not.toHaveBeenCalled();
    expect(mockBroadcastProgress).not.toHaveBeenCalled();
  });

  it('suppresses progress when ownership changes after the advisory read but before the write fence', async () => {
    const dispatchId = '00000000-0000-4000-8000-000000000010';
    mockJobFindUnique.mockResolvedValue({
      status: 'RUNNING_PHASE2',
      activeDispatchId: dispatchId,
    });
    mockUpdateStageProgress.mockResolvedValue(null);

    const res = await request(app)
      .post('/api/workers/progress')
      .send({
        worker_id: 'worker-1',
        job_id: JOB_ID,
        stage: 6,
        name: 'SEO & Keyword Strategy',
        status: 'running',
        dispatch_id: dispatchId,
      });

    expect(res.status).toBe(200);
    expect(res.body).toMatchObject({ stale: true, shouldCancel: true });
    expect(mockUpdateStageProgress).toHaveBeenCalledWith(
      JOB_ID,
      6,
      'RUNNING',
      undefined,
      undefined,
      dispatchId,
    );
    expect(mockBroadcastProgress).not.toHaveBeenCalled();
  });

  it('stage=15, status=running → sets landingPageStatus=RUNNING via CAS updateMany', async () => {
    const runningPayload = {
      worker_id: 'worker-1',
      job_id: JOB_ID,
      stage: 15,
      name: 'Landing Page Generation',
      status: 'running',
    };

    const res = await request(app)
      .post('/api/workers/progress')
      .send(runningPayload);

    expect(res.status).toBe(200);
    expect(mockJobUpdateMany).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({ landingPageStatus: 'RUNNING' }),
      })
    );
  });

  it('stage=15, status=completed + landing_path (no report_path) → adds landing asset, sets COMPLETED via CAS', async () => {
    const completedPayload = {
      worker_id: 'worker-1',
      job_id: JOB_ID,
      stage: 15,
      name: 'Landing Page Generation',
      status: 'completed',
      landing_path: 'outputs/job-1/landing.html',
    };

    mockGetJob.mockResolvedValue({ userId: 'user-1', niche: 'test' });
    mockUserFindUnique.mockResolvedValue({ email: 'test@test.com' });

    const res = await request(app)
      .post('/api/workers/progress')
      .send(completedPayload);

    expect(res.status).toBe(200);
    // Should add the landing page asset
    expect(mockAddJobAsset).toHaveBeenCalledWith(JOB_ID, 'LANDING_PAGE', completedPayload.landing_path);
    // Should set landingPageStatus to COMPLETED via CAS updateMany
    expect(mockJobUpdateMany).toHaveBeenCalledWith(
      expect.objectContaining({
        data: { landingPageStatus: 'COMPLETED' },
      })
    );
  });

  it('modern landing completion settles the dispatch before projecting progress', async () => {
    const dispatchId = '00000000-0000-4000-8000-000000000015';
    const landingPath = 'outputs/job-1/landing.html';
    mockJobFindUnique.mockResolvedValue({
      status: 'COMPLETED',
      activeDispatchId: dispatchId,
    });
    mockJobDispatchFindUnique.mockResolvedValue({
      jobId: JOB_ID,
      kind: 'CONTINUE',
      segment: 'landing_page',
    });
    mockGetJob.mockResolvedValue(null);

    const res = await request(app)
      .post('/api/workers/progress')
      .send({
        worker_id: 'worker-1',
        job_id: JOB_ID,
        dispatch_id: dispatchId,
        stage: 15,
        name: 'Landing Page Generation',
        status: 'completed',
        landing_path: landingPath,
      });

    expect(res.status).toBe(200);
    expect(mockCompleteLandingPageDispatch).toHaveBeenCalledWith(
      JOB_ID,
      dispatchId,
      landingPath,
    );
    expect(mockUpdateStageProgress).not.toHaveBeenCalled();
    expect(mockAddJobAsset).not.toHaveBeenCalled();
    expect(mockJobUpdateMany).not.toHaveBeenCalled();
  });

  it('duplicate modern landing completion is stale and sends no second notification or progress', async () => {
    const dispatchId = '00000000-0000-4000-8000-000000000015';
    mockJobFindUnique.mockResolvedValue({
      status: 'COMPLETED',
      activeDispatchId: dispatchId,
    });
    mockJobDispatchFindUnique.mockResolvedValue({
      jobId: JOB_ID,
      kind: 'CONTINUE',
      segment: 'landing_page',
    });
    mockCompleteLandingPageDispatch.mockResolvedValue(false);

    const res = await request(app)
      .post('/api/workers/progress')
      .send({
        worker_id: 'worker-1',
        job_id: JOB_ID,
        dispatch_id: dispatchId,
        stage: 15,
        name: 'Landing Page Generation',
        status: 'completed',
        landing_path: 'outputs/job-1/landing.html',
      });

    expect(res.body).toMatchObject({ stale: true, shouldCancel: true });
    expect(mockUpdateStageProgress).not.toHaveBeenCalled();
    expect(mockBroadcastProgress).not.toHaveBeenCalled();
  });

  it('modern landing progress failure exact-settles without completing or failing the parent Job', async () => {
    const dispatchId = '00000000-0000-4000-8000-000000000015';
    mockJobFindUnique.mockResolvedValue({
      status: 'COMPLETED',
      activeDispatchId: dispatchId,
    });
    mockGetJobAsset.mockResolvedValue(REPORT_ASSET);

    const res = await request(app)
      .post('/api/workers/progress')
      .send({ ...baseProgressPayload, dispatch_id: dispatchId });

    expect(res.status).toBe(200);
    expect(mockFailLandingPageDispatch).toHaveBeenCalledWith(
      JOB_ID,
      dispatchId,
      baseProgressPayload.error,
    );
    expect(mockFailJob).not.toHaveBeenCalled();
    expect(mockCompleteJob).not.toHaveBeenCalled();
    expect(mockJobUpdate).not.toHaveBeenCalled();
  });

  it('acknowledges the worker intermediate completion until the landing artifact arrives', async () => {
    const dispatchId = '00000000-0000-4000-8000-000000000015';
    mockJobFindUnique.mockResolvedValue({
      status: 'COMPLETED',
      activeDispatchId: dispatchId,
    });
    mockJobDispatchFindUnique.mockResolvedValue({
      jobId: JOB_ID,
      kind: 'CONTINUE',
      segment: 'landing_page',
    });

    const res = await request(app)
      .post('/api/workers/progress')
      .send({
        worker_id: 'worker-1',
        job_id: JOB_ID,
        dispatch_id: dispatchId,
        stage: 15,
        name: 'Landing Page Generation',
        status: 'completed',
      });

    expect(res.status).toBe(200);
    expect(res.body).toMatchObject({ awaitingArtifact: true, shouldCancel: false });
    expect(mockCompleteLandingPageDispatch).not.toHaveBeenCalled();
    expect(mockUpdateStageProgress).not.toHaveBeenCalled();
    expect(mockBroadcastProgress).not.toHaveBeenCalled();
  });

  it('handles the real final worker payload as landing settlement, not whole-job completion', async () => {
    const dispatchId = '00000000-0000-4000-8000-000000000015';
    const landingPath = 'outputs/job-1/landing.html';
    mockJobFindUnique.mockResolvedValue({
      status: 'COMPLETED',
      activeDispatchId: dispatchId,
    });
    mockJobDispatchFindUnique.mockResolvedValue({
      jobId: JOB_ID,
      kind: 'CONTINUE',
      segment: 'landing_page',
    });
    mockGetJob.mockResolvedValue(null);

    const res = await request(app)
      .post('/api/workers/progress')
      .send({
        worker_id: 'worker-1',
        job_id: JOB_ID,
        dispatch_id: dispatchId,
        stage: 15,
        name: 'Completed',
        status: 'completed',
        report_path: REPORT_ASSET.filePath,
        landing_path: landingPath,
      });

    expect(res.status).toBe(200);
    expect(res.body.stale).not.toBe(true);
    expect(mockCompleteLandingPageDispatch).toHaveBeenCalledWith(
      JOB_ID,
      dispatchId,
      landingPath,
    );
    expect(mockCompleteJob).not.toHaveBeenCalled();
  });

  it('refunds a landing dispatch whose final worker callback has no output file', async () => {
    const dispatchId = '00000000-0000-4000-8000-000000000015';
    mockJobFindUnique.mockResolvedValue({
      status: 'COMPLETED',
      activeDispatchId: dispatchId,
    });
    mockJobDispatchFindUnique.mockResolvedValue({
      jobId: JOB_ID,
      kind: 'CONTINUE',
      segment: 'landing_page',
    });

    const res = await request(app)
      .post('/api/workers/progress')
      .send({
        worker_id: 'worker-1',
        job_id: JOB_ID,
        dispatch_id: dispatchId,
        stage: 14,
        name: 'Completed',
        status: 'completed',
        report_path: REPORT_ASSET.filePath,
      });

    expect(res.status).toBe(200);
    expect(res.body).toMatchObject({
      shouldCancel: false,
      landingPageStatus: 'FAILED',
    });
    expect(mockFailLandingPageDispatch).toHaveBeenCalledWith(
      JOB_ID,
      dispatchId,
      'Landing page generation completed without an output file',
    );
    expect(mockCompleteJob).not.toHaveBeenCalled();
    expect(mockBroadcastProgress).toHaveBeenCalledWith(JOB_ID, {
      stage: 15,
      name: 'Landing Page Generation',
      status: 'failed',
      error: 'Landing page generation completed without an output file',
    });
  });
});
