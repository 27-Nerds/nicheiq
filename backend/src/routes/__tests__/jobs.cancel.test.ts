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

vi.mock('../../services/jobService.js', () => ({
  getJob: vi.fn(),
  updateJobStatus: vi.fn(),
  getJobAsset: vi.fn(),
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

  app = express();
  app.use(express.json());

  const { jobsRouter } = await import('../jobs.js');
  app.use('/api/jobs', jobsRouter);
});

// ============================================
// Tests
// ============================================
describe('POST /api/jobs/:jobId/cancel - stage marking', () => {
  const jobId = '00000000-0000-0000-0000-000000000001';

  it('marks running stages as FAILED when cancelling a RUNNING job', async () => {
    mockJobFindFirst.mockResolvedValue({
      id: jobId,
      userId: 'user-123',
      status: 'RUNNING',
    });

    const response = await request(app)
      .post(`/api/jobs/${jobId}/cancel`)
      .set(authHeaders);

    expect(response.status).toBe(200);
    expect(mockUpdateMany).toHaveBeenCalledWith({
      where: { jobId, status: 'RUNNING' },
      data: {
        status: 'FAILED',
        errorMessage: 'Cancelled by user',
      },
    });
  });

  it('sets error message to "Cancelled by user"', async () => {
    mockJobFindFirst.mockResolvedValue({
      id: jobId,
      userId: 'user-123',
      status: 'RUNNING',
    });

    await request(app)
      .post(`/api/jobs/${jobId}/cancel`)
      .set(authHeaders);

    const updateManyCall = mockUpdateMany.mock.calls[0][0];
    expect(updateManyCall.data.errorMessage).toBe('Cancelled by user');
  });

  it('calls updateMany even for QUEUED jobs (no-op, no RUNNING stages)', async () => {
    mockJobFindFirst.mockResolvedValue({
      id: jobId,
      userId: 'user-123',
      status: 'QUEUED',
    });

    await request(app)
      .post(`/api/jobs/${jobId}/cancel`)
      .set(authHeaders);

    // updateMany is called but would match 0 rows for QUEUED jobs
    expect(mockUpdateMany).toHaveBeenCalled();
  });

  it('does not attempt stage update for already finished jobs', async () => {
    mockJobFindFirst.mockResolvedValue({
      id: jobId,
      userId: 'user-123',
      status: 'COMPLETED',
    });

    const response = await request(app)
      .post(`/api/jobs/${jobId}/cancel`)
      .set(authHeaders);

    expect(response.status).toBe(400);
    expect(mockUpdateMany).not.toHaveBeenCalled();
  });
});

describe('POST /api/jobs/:jobId/cancel - post-selection statuses are rejected', () => {
  const jobId = '00000000-0000-0000-0000-000000000001';

  it('rejects cancel from AWAITING_SELECTION', async () => {
    mockJobFindFirst.mockResolvedValue({ id: jobId, userId: 'user-123', status: 'AWAITING_SELECTION' });

    const response = await request(app)
      .post(`/api/jobs/${jobId}/cancel`)
      .set(authHeaders);

    expect(response.status).toBe(400);
    expect(response.body.error).toBe('Cannot cancel job after solution selection');
    expect(mockRefundForStage).not.toHaveBeenCalled();
    expect(mockUpdateMany).not.toHaveBeenCalled();
  });

  it('rejects cancel from REGENERATING', async () => {
    mockJobFindFirst.mockResolvedValue({ id: jobId, userId: 'user-123', status: 'REGENERATING' });

    const response = await request(app)
      .post(`/api/jobs/${jobId}/cancel`)
      .set(authHeaders);

    expect(response.status).toBe(400);
    expect(response.body.error).toBe('Cannot cancel job after solution selection');
    expect(mockRefundForStage).not.toHaveBeenCalled();
    expect(mockUpdateMany).not.toHaveBeenCalled();
  });

  it('rejects cancel from RUNNING_PHASE2', async () => {
    mockJobFindFirst.mockResolvedValue({ id: jobId, userId: 'user-123', status: 'RUNNING_PHASE2' });

    const response = await request(app)
      .post(`/api/jobs/${jobId}/cancel`)
      .set(authHeaders);

    expect(response.status).toBe(400);
    expect(response.body.error).toBe('Cannot cancel job after solution selection');
    expect(mockRefundForStage).not.toHaveBeenCalled();
    expect(mockUpdateMany).not.toHaveBeenCalled();
  });
});
