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

// Phase 5.4 — /report-ready now calls extractOrCreateResearchContext after
// asset registration. Mock to keep the route behavior under test.
const mockExtractOrCreate = vi.fn();
vi.mock('../../services/researchContextService.js', () => ({
  extractOrCreateResearchContext: (...args: any[]) => mockExtractOrCreate(...args),
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

const mockNotifyJobComplete = vi.fn().mockResolvedValue(undefined);

vi.mock('../../services/notificationService.js', () => ({
  notifyJobStart: vi.fn(),
  notifyJobComplete: (...args: any[]) => mockNotifyJobComplete(...args),
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

const JOB_ID = '00000000-0000-0000-0000-000000000001';

beforeEach(async () => {
  vi.clearAllMocks();

  mockAddJobAsset.mockResolvedValue({});
  // Default: this is the FIRST delivery (no existing asset). Tests that need
  // to simulate re-delivery override mockGetJobAsset.
  mockGetJobAsset.mockResolvedValue(null);
  mockExtractOrCreate.mockResolvedValue({});

  app = express();
  app.use(express.json());

  const { workersRouter } = await import('../workers.js');
  app.use('/api/workers', workersRouter);
});

// ============================================
// Tests
// ============================================
describe('POST /api/workers/report-ready', () => {
  const validPayload = {
    worker_id: 'worker-1',
    job_id: JOB_ID,
    report_path: 'outputs/job-1/report.json',
  };

  it('happy path: stores report asset, sends notification, broadcasts SSE, returns ok', async () => {
    mockJobFindUnique.mockResolvedValue({ userId: 'user-1', niche: 'test niche' });
    mockUserFindUnique.mockResolvedValue({ email: 'user@example.com' });

    const res = await request(app)
      .post('/api/workers/report-ready')
      .send(validPayload);

    expect(res.status).toBe(200);
    expect(res.body).toEqual({ status: 'ok' });

    // Stores the report asset
    expect(mockAddJobAsset).toHaveBeenCalledWith(JOB_ID, 'REPORT_JSON', validPayload.report_path);
  });

  it('rejects missing worker_id → 400', async () => {
    const res = await request(app)
      .post('/api/workers/report-ready')
      .send({ job_id: JOB_ID, report_path: 'path.json' });

    expect(res.status).toBe(400);
    expect(res.body.error).toBe('Validation error');
  });

  it('rejects missing job_id → 400', async () => {
    const res = await request(app)
      .post('/api/workers/report-ready')
      .send({ worker_id: 'w1', report_path: 'path.json' });

    expect(res.status).toBe(400);
    expect(res.body.error).toBe('Validation error');
  });

  it('rejects missing report_path → 400', async () => {
    const res = await request(app)
      .post('/api/workers/report-ready')
      .send({ worker_id: 'w1', job_id: JOB_ID });

    expect(res.status).toBe(400);
    expect(res.body.error).toBe('Validation error');
  });

  it('calls notifyJobComplete() with correct user email', async () => {
    mockJobFindUnique.mockResolvedValue({ userId: 'user-1', niche: 'test niche' });
    mockUserFindUnique.mockResolvedValue({ email: 'user@example.com' });

    await request(app)
      .post('/api/workers/report-ready')
      .send(validPayload);

    expect(mockNotifyJobComplete).toHaveBeenCalledWith(
      'user-1',
      'user@example.com',
      JOB_ID,
      'test niche'
    );
  });

  it('broadcasts SSE with stage=14, status=completed, report_path', async () => {
    mockJobFindUnique.mockResolvedValue({ userId: 'user-1', niche: 'test niche' });
    mockUserFindUnique.mockResolvedValue({ email: 'user@example.com' });

    await request(app)
      .post('/api/workers/report-ready')
      .send(validPayload);

    expect(mockBroadcastProgress).toHaveBeenCalledWith(JOB_ID, {
      stage: 14,
      name: 'Report Generation',
      status: 'completed',
      report_path: validPayload.report_path,
    });
  });

  it('does not send notification when user has no email', async () => {
    mockJobFindUnique.mockResolvedValue({ userId: 'user-1', niche: 'test niche' });
    mockUserFindUnique.mockResolvedValue({ email: null });

    const res = await request(app)
      .post('/api/workers/report-ready')
      .send(validPayload);

    expect(res.status).toBe(200);
    expect(mockNotifyJobComplete).not.toHaveBeenCalled();
  });

  it('does not send notification when job has no userId', async () => {
    mockJobFindUnique.mockResolvedValue({ userId: null, niche: 'test niche' });

    const res = await request(app)
      .post('/api/workers/report-ready')
      .send(validPayload);

    expect(res.status).toBe(200);
    expect(mockNotifyJobComplete).not.toHaveBeenCalled();
  });

  // Phase 5.4
  it('calls extractOrCreateResearchContext with forceRefreshAll after asset registration', async () => {
    mockJobFindUnique.mockResolvedValue({ userId: 'user-1', niche: 'test niche' });
    mockUserFindUnique.mockResolvedValue({ email: 'user@example.com' });

    await request(app)
      .post('/api/workers/report-ready')
      .send(validPayload);

    expect(mockExtractOrCreate).toHaveBeenCalledWith(JOB_ID, { forceRefreshAll: true });
  });

  it('skips notification email on re-delivery (asset already exists)', async () => {
    mockJobFindUnique.mockResolvedValue({ userId: 'user-1', niche: 'test niche' });
    mockUserFindUnique.mockResolvedValue({ email: 'user@example.com' });
    // Simulate re-delivery: REPORT_JSON asset already exists.
    mockGetJobAsset.mockResolvedValue({ filePath: 'outputs/job-1/report.json' });

    const res = await request(app)
      .post('/api/workers/report-ready')
      .send(validPayload);

    expect(res.status).toBe(200);
    // Asset re-registered (idempotent upsert) but no duplicate email.
    expect(mockAddJobAsset).toHaveBeenCalled();
    expect(mockNotifyJobComplete).not.toHaveBeenCalled();
  });
});
