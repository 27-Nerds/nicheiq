import { describe, it, expect, vi, beforeEach } from 'vitest';
import express, { Express } from 'express';
import request from 'supertest';

// ============================================
// Mock dependencies
// ============================================
const mockJobFindFirst = vi.fn();
const mockJobUpdate = vi.fn();
const mockUpdateMany = vi.fn();

vi.mock('../../services/db.js', () => ({
  prisma: {
    job: {
      findFirst: (...args: any[]) => mockJobFindFirst(...args),
      update: (...args: any[]) => mockJobUpdate(...args),
    },
    jobProgress: {
      updateMany: (...args: any[]) => mockUpdateMany(...args),
    },
  },
}));

const mockCancelJob = vi.fn();

vi.mock('../../services/jobService.js', () => ({
  getJob: vi.fn(),
  updateJobStatus: vi.fn(),
  getJobAsset: vi.fn(),
  cancelJob: (...args: any[]) => mockCancelJob(...args),
}));

const mockRefundForStage = vi.fn();

vi.mock('../../services/creditService.js', () => ({
  createJobAndChargeDiscovery: vi.fn(),
  InsufficientCreditsError: class InsufficientCreditsError extends Error {
    currentBalance: number;
    required: number;
    constructor(balance: number, required: number) {
      super('Insufficient credits');
      this.currentBalance = balance;
      this.required = required;
    }
  },
  refundForStage: (...args: any[]) => mockRefundForStage(...args),
  chargeForStageInTx: vi.fn(),
  getStageCost: vi.fn().mockResolvedValue(5),
}));

vi.mock('../../services/queueService.js', () => ({
  enqueueJob: vi.fn(),
  enqueueLandingPageJob: vi.fn(),
  enqueuePhase2Job: vi.fn(),
  enqueueRegenerateJob: vi.fn(),
  getQueueStats: vi.fn(),
  getQueueLength: vi.fn(),
  removeJobFromQueue: vi.fn(),
}));

vi.mock('../../middleware/auth.js', () => ({
  requireInternalAuth: (req: any, res: any, next: any) => {
    const userId = req.headers['x-user-id'];
    if (userId) {
      req.user = { id: userId };
      return next();
    }
    res.status(401).json({ error: 'Unauthorized' });
  },
  requireInternalService: (_req: any, _res: any, next: any) => next(),
  verifyOwnership: () => true,
  AuthenticatedRequest: {},
}));

vi.mock('../../middleware/rateLimit.js', () => ({
  jobCreationLimiter: (_req: any, _res: any, next: any) => next(),
}));

vi.mock('../../config.js', () => ({
  CONFIG: { baseUrl: 'http://localhost:3001' },
}));

vi.mock('../../utils/jobFormatter.js', () => ({
  formatJobResponse: vi.fn(),
}));

vi.mock('../../utils/assetPath.js', () => ({
  resolveAssetPath: vi.fn(),
}));

vi.mock('../../middleware/validation.js', () => ({
  validateJobId: (_req: any, _res: any, next: any) => next(),
}));

// ============================================
// Setup Express App
// ============================================
let app: Express;

const authHeaders = {
  'x-user-id': 'user-123',
};

beforeEach(async () => {
  vi.clearAllMocks();

  mockJobUpdate.mockResolvedValue({ id: 'job-1', status: 'CANCELLED' });
  mockUpdateMany.mockResolvedValue({ count: 1 });
  mockRefundForStage.mockResolvedValue({ id: 'refund-1', amount: 5 });
  mockCancelJob.mockResolvedValue({ cancelled: true, creditRefunded: 0 });

  app = express();
  app.use(express.json());

  const { jobsRouter } = await import('../jobs.js');
  app.use('/api/jobs', jobsRouter);
});

// ============================================
// Tests
// ============================================
describe('POST /api/jobs/:jobId/cancel - delegates to cancelJob service', () => {
  const jobId = '00000000-0000-0000-0000-000000000001';

  it('calls cancelJob with the jobId after the ownership check passes', async () => {
    mockJobFindFirst.mockResolvedValue({ id: jobId, userId: 'user-123', status: 'RUNNING' });

    await request(app)
      .post(`/api/jobs/${jobId}/cancel`)
      .set(authHeaders);

    expect(mockCancelJob).toHaveBeenCalledWith(jobId);
  });

  it('maps {cancelled: true, creditRefunded > 0} to 200 with the refund message', async () => {
    mockJobFindFirst.mockResolvedValue({ id: jobId, userId: 'user-123', status: 'RUNNING' });
    mockCancelJob.mockResolvedValue({ cancelled: true, creditRefunded: 5 });

    const response = await request(app)
      .post(`/api/jobs/${jobId}/cancel`)
      .set(authHeaders);

    expect(response.status).toBe(200);
    expect(response.body).toEqual({
      status: 'cancelled',
      message: 'Job cancelled and credit refunded',
      creditRefunded: 5,
    });
  });

  it('maps {cancelled: true, creditRefunded: 0} to 200 without the refund message', async () => {
    mockJobFindFirst.mockResolvedValue({ id: jobId, userId: 'user-123', status: 'QUEUED' });
    mockCancelJob.mockResolvedValue({ cancelled: true, creditRefunded: 0 });

    const response = await request(app)
      .post(`/api/jobs/${jobId}/cancel`)
      .set(authHeaders);

    expect(response.status).toBe(200);
    expect(response.body).toEqual({
      status: 'cancelled',
      message: 'Job cancelled',
      creditRefunded: 0,
    });
  });

  it('maps {cancelled: false, reason: "not_found"} to 404', async () => {
    mockJobFindFirst.mockResolvedValue({ id: jobId, userId: 'user-123', status: 'RUNNING' });
    mockCancelJob.mockResolvedValue({ cancelled: false, reason: 'not_found' });

    const response = await request(app)
      .post(`/api/jobs/${jobId}/cancel`)
      .set(authHeaders);

    expect(response.status).toBe(404);
    expect(response.body.error).toBe('Job not found');
  });

  it('maps {cancelled: false, reason: "not_cancellable", status: COMPLETED} to 400 "Job already finished"', async () => {
    mockJobFindFirst.mockResolvedValue({ id: jobId, userId: 'user-123', status: 'COMPLETED' });
    mockCancelJob.mockResolvedValue({ cancelled: false, reason: 'not_cancellable', status: 'COMPLETED' });

    const response = await request(app)
      .post(`/api/jobs/${jobId}/cancel`)
      .set(authHeaders);

    expect(response.status).toBe(400);
    expect(response.body.error).toBe('Job already finished');
    expect(response.body.status).toBe('COMPLETED');
  });
});

describe('POST /api/jobs/:jobId/cancel - post-selection statuses are rejected', () => {
  const jobId = '00000000-0000-0000-0000-000000000001';

  it('rejects cancel from AWAITING_SELECTION', async () => {
    mockJobFindFirst.mockResolvedValue({ id: jobId, userId: 'user-123', status: 'AWAITING_SELECTION' });
    mockCancelJob.mockResolvedValue({ cancelled: false, reason: 'not_cancellable', status: 'AWAITING_SELECTION' });

    const response = await request(app)
      .post(`/api/jobs/${jobId}/cancel`)
      .set(authHeaders);

    expect(response.status).toBe(400);
    expect(response.body.error).toBe('Cannot cancel job after solution selection');
  });

  it('rejects cancel from REGENERATING', async () => {
    mockJobFindFirst.mockResolvedValue({ id: jobId, userId: 'user-123', status: 'REGENERATING' });
    mockCancelJob.mockResolvedValue({ cancelled: false, reason: 'not_cancellable', status: 'REGENERATING' });

    const response = await request(app)
      .post(`/api/jobs/${jobId}/cancel`)
      .set(authHeaders);

    expect(response.status).toBe(400);
    expect(response.body.error).toBe('Cannot cancel job after solution selection');
  });

  it('rejects cancel from RUNNING_PHASE2', async () => {
    mockJobFindFirst.mockResolvedValue({ id: jobId, userId: 'user-123', status: 'RUNNING_PHASE2' });
    mockCancelJob.mockResolvedValue({ cancelled: false, reason: 'not_cancellable', status: 'RUNNING_PHASE2' });

    const response = await request(app)
      .post(`/api/jobs/${jobId}/cancel`)
      .set(authHeaders);

    expect(response.status).toBe(400);
    expect(response.body.error).toBe('Cannot cancel job after solution selection');
  });
});

// Phase B (DR A1/Codex 12): AWAITING_GATE (guided mode's G1/G2 stage gates) sits strictly
// BEFORE Stage 5 the same way PENDING/QUEUED/RUNNING do — symmetric with those, NOT with
// AWAITING_SELECTION (which the block above intentionally keeps non-cancellable).
describe('POST /api/jobs/:jobId/cancel - AWAITING_GATE is cancellable with discovery refund', () => {
  const jobId = '00000000-0000-0000-0000-000000000001';

  it('cancels a job AWAITING_GATE and refunds the discovery credit', async () => {
    mockJobFindFirst.mockResolvedValue({ id: jobId, userId: 'user-123', status: 'AWAITING_GATE' });
    mockCancelJob.mockResolvedValue({ cancelled: true, creditRefunded: 5 });

    const response = await request(app)
      .post(`/api/jobs/${jobId}/cancel`)
      .set(authHeaders);

    expect(response.status).toBe(200);
    expect(response.body.status).toBe('cancelled');
    expect(response.body.creditRefunded).toBe(5);
    expect(mockCancelJob).toHaveBeenCalledWith(jobId);
  });
});
