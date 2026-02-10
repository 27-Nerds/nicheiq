import { describe, it, expect, vi, beforeEach } from 'vitest';
import express, { Express } from 'express';
import request from 'supertest';
import { JobStatus } from '@prisma/client';

// ============================================
// Mock dependencies
// ============================================
const mockJobFindFirst = vi.fn();
const mockJobFindUnique = vi.fn();
const mockJobUpdate = vi.fn();
const mockUpdateMany = vi.fn();
const mockJobProgressCreate = vi.fn();
const mockPrismaTransaction = vi.fn();

vi.mock('../../services/db.js', () => ({
  prisma: {
    job: {
      findFirst: (...args: any[]) => mockJobFindFirst(...args),
      findUnique: (...args: any[]) => mockJobFindUnique(...args),
      update: (...args: any[]) => mockJobUpdate(...args),
    },
    jobProgress: {
      updateMany: (...args: any[]) => mockUpdateMany(...args),
      create: (...args: any[]) => mockJobProgressCreate(...args),
    },
    $transaction: (...args: any[]) => mockPrismaTransaction(...args),
  },
}));

const mockGetJob = vi.fn();
const mockGetJobAsset = vi.fn();
const mockUpdateJobStatus = vi.fn();

vi.mock('../../services/jobService.js', () => ({
  getJob: (...args: any[]) => mockGetJob(...args),
  updateJobStatus: (...args: any[]) => mockUpdateJobStatus(...args),
  getJobAsset: (...args: any[]) => mockGetJobAsset(...args),
}));

const mockCreateJobWithCreditDeduction = vi.fn();
const mockRefundCreditsForJob = vi.fn();

vi.mock('../../services/creditService.js', () => ({
  createJobWithCreditDeduction: (...args: any[]) => mockCreateJobWithCreditDeduction(...args),
  refundCreditsForJob: (...args: any[]) => mockRefundCreditsForJob(...args),
  InsufficientCreditsError: class InsufficientCreditsError extends Error {
    currentBalance: number;
    required: number;
    constructor(currentBalance: number, required: number) {
      super(`Insufficient credits: have ${currentBalance}, need ${required}`);
      this.currentBalance = currentBalance;
      this.required = required;
    }
  },
}));

const mockEnqueueJob = vi.fn();
const mockEnqueueLandingPageJob = vi.fn();
const mockGetQueueStats = vi.fn();
const mockGetQueueLength = vi.fn();

vi.mock('../../services/queueService.js', () => ({
  enqueueJob: (...args: any[]) => mockEnqueueJob(...args),
  enqueueLandingPageJob: (...args: any[]) => mockEnqueueLandingPageJob(...args),
  enqueuePhase2Job: vi.fn(),
  enqueueRegenerateJob: vi.fn(),
  getQueueStats: (...args: any[]) => mockGetQueueStats(...args),
  getQueueLength: (...args: any[]) => mockGetQueueLength(...args),
}));

// ============================================
// Auth mocks
// ============================================
const TEST_SERVICE_SECRET = 'test-internal-secret';

vi.mock('../../middleware/auth.js', () => ({
  requireInternalAuth: (req: any, res: any, next: any) => {
    if (req.headers['x-internal-service'] !== TEST_SERVICE_SECRET) {
      return res.status(401).json({ error: 'Authentication required' });
    }
    const userId = req.headers['x-user-id'];
    if (!userId) {
      return res.status(401).json({ error: 'Authentication required' });
    }
    req.user = {
      id: userId,
      email: req.headers['x-user-email'],
      role: req.headers['x-user-role'],
    };
    next();
  },
  requireInternalService: (req: any, res: any, next: any) => {
    if (req.headers['x-internal-service'] !== TEST_SERVICE_SECRET) {
      return res.status(401).json({ error: 'Unauthorized' });
    }
    next();
  },
  verifyOwnership: (req: any, resourceUserId: string) => {
    return req.user?.id === resourceUserId;
  },
  AuthenticatedRequest: {},
}));

vi.mock('../../middleware/rateLimit.js', () => ({
  jobCreationLimiter: (_req: any, _res: any, next: any) => next(),
}));

const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

vi.mock('../../middleware/validation.js', () => ({
  validateJobId: (req: any, res: any, next: any) => {
    const { jobId } = req.params;
    if (!jobId || !UUID_REGEX.test(jobId)) {
      return res.status(400).json({ error: 'Invalid job ID format' });
    }
    next();
  },
}));

vi.mock('../../config.js', () => ({
  CONFIG: { baseUrl: 'http://localhost:3001' },
}));

vi.mock('../../utils/jobFormatter.js', () => ({
  formatJobResponse: (job: any) => job,
}));

vi.mock('fs', () => ({
  existsSync: vi.fn().mockReturnValue(true),
  createReadStream: vi.fn(),
  statSync: vi.fn().mockReturnValue({ size: 100 }),
}));

vi.mock('../../utils/assetPath.js', () => ({
  resolveAssetPath: (p: string) => p,
}));

// ============================================
// Setup Express App
// ============================================
let app: Express;

const JOB_ID = '00000000-0000-0000-0000-000000000001';
const USER_ID = 'user-123';

const validUserHeaders = {
  'x-user-id': USER_ID,
  'x-internal-service': TEST_SERVICE_SECRET,
};

const attackerHeaders = {
  'x-user-id': 'attacker-456',
  'x-internal-service': TEST_SERVICE_SECRET,
};

beforeEach(async () => {
  vi.clearAllMocks();

  app = express();
  app.use(express.json());

  const { jobsRouter } = await import('../jobs.js');
  app.use('/api/jobs', jobsRouter);

  mockGetQueueLength.mockResolvedValue(0);
  mockGetQueueStats.mockResolvedValue({ position: 1, aheadCount: 0, totalQueued: 1 });
  mockEnqueueLandingPageJob.mockResolvedValue(undefined);
});

// ============================================
// Tests
// ============================================
describe('POST /api/jobs/:jobId/generate-landing', () => {
  // Helper: set up a successful transaction mock
  function setupTransaction(job: any) {
    const mockTx = {
      job: {
        findFirst: vi.fn().mockResolvedValue(job),
        update: vi.fn().mockResolvedValue({ ...job, landingPageStatus: 'QUEUED' }),
      },
      jobProgress: {
        create: vi.fn().mockResolvedValue({}),
      },
    };
    mockPrismaTransaction.mockImplementation(async (cb: any) => cb(mockTx));
    return mockTx;
  }

  it('happy path: COMPLETED job + report asset + no landing → enqueues landing job, returns ok', async () => {
    const job = {
      id: JOB_ID,
      userId: USER_ID,
      status: JobStatus.COMPLETED,
      landingPageStatus: null,
      assets: [{ assetType: 'REPORT_JSON', filePath: 'outputs/job-1/report.json' }],
      progress: [],
    };

    const mockTx = setupTransaction(job);
    mockGetJobAsset.mockResolvedValue({ filePath: 'outputs/job-1/report.json' });

    const res = await request(app)
      .post(`/api/jobs/${JOB_ID}/generate-landing`)
      .set(validUserHeaders);

    expect(res.status).toBe(200);
    expect(res.body).toEqual({ status: 'ok' });

    // Transaction should have created stage 11 progress
    expect(mockTx.jobProgress.create).toHaveBeenCalledWith({
      data: expect.objectContaining({
        jobId: JOB_ID,
        stageNumber: 11,
        stageName: 'Landing Page Generation',
        status: 'PENDING',
      }),
    });

    // Transaction should have updated job with QUEUED status and incremented totalStages
    expect(mockTx.job.update).toHaveBeenCalledWith({
      where: { id: JOB_ID },
      data: expect.objectContaining({
        generateLandingPage: true,
        landingPageStatus: 'QUEUED',
        totalStages: { increment: 1 },
      }),
    });

    // Should enqueue landing page job with correct report path
    expect(mockEnqueueLandingPageJob).toHaveBeenCalledWith(JOB_ID, 'outputs/job-1/report.json');
  });

  it('rejects non-COMPLETED job → 400', async () => {
    const job = {
      id: JOB_ID,
      userId: USER_ID,
      status: JobStatus.RUNNING,
      landingPageStatus: null,
      assets: [{ assetType: 'REPORT_JSON', filePath: 'outputs/job-1/report.json' }],
      progress: [],
    };

    setupTransaction(job);

    const res = await request(app)
      .post(`/api/jobs/${JOB_ID}/generate-landing`)
      .set(validUserHeaders);

    expect(res.status).toBe(400);
    expect(res.body.error).toMatch(/must be completed/i);
  });

  it('rejects when landing page asset already exists → 400', async () => {
    const job = {
      id: JOB_ID,
      userId: USER_ID,
      status: JobStatus.COMPLETED,
      landingPageStatus: 'COMPLETED',
      assets: [
        { assetType: 'REPORT_JSON', filePath: 'outputs/job-1/report.json' },
        { assetType: 'LANDING_PAGE', filePath: 'outputs/job-1/landing.html' },
      ],
      progress: [],
    };

    setupTransaction(job);

    const res = await request(app)
      .post(`/api/jobs/${JOB_ID}/generate-landing`)
      .set(validUserHeaders);

    expect(res.status).toBe(400);
    expect(res.body.error).toMatch(/already exists/i);
  });

  it('rejects when landingPageStatus is QUEUED (double-click guard) → 400', async () => {
    const job = {
      id: JOB_ID,
      userId: USER_ID,
      status: JobStatus.COMPLETED,
      landingPageStatus: 'QUEUED',
      assets: [{ assetType: 'REPORT_JSON', filePath: 'outputs/job-1/report.json' }],
      progress: [],
    };

    setupTransaction(job);

    const res = await request(app)
      .post(`/api/jobs/${JOB_ID}/generate-landing`)
      .set(validUserHeaders);

    expect(res.status).toBe(400);
    expect(res.body.error).toMatch(/already exists|being generated/i);
  });

  it('rejects when landingPageStatus is RUNNING (double-click guard) → 400', async () => {
    const job = {
      id: JOB_ID,
      userId: USER_ID,
      status: JobStatus.COMPLETED,
      landingPageStatus: 'RUNNING',
      assets: [{ assetType: 'REPORT_JSON', filePath: 'outputs/job-1/report.json' }],
      progress: [],
    };

    setupTransaction(job);

    const res = await request(app)
      .post(`/api/jobs/${JOB_ID}/generate-landing`)
      .set(validUserHeaders);

    expect(res.status).toBe(400);
    expect(res.body.error).toMatch(/already exists|being generated/i);
  });

  it('rejects when no report asset → 400', async () => {
    const job = {
      id: JOB_ID,
      userId: USER_ID,
      status: JobStatus.COMPLETED,
      landingPageStatus: null,
      assets: [], // No report
      progress: [],
    };

    setupTransaction(job);

    const res = await request(app)
      .post(`/api/jobs/${JOB_ID}/generate-landing`)
      .set(validUserHeaders);

    expect(res.status).toBe(400);
    expect(res.body.error).toMatch(/report not found/i);
  });

  it('404 when job not found (wrong user / IDOR)', async () => {
    // Transaction returns null for the job (user ID mismatch in findFirst)
    mockPrismaTransaction.mockImplementation(async (cb: any) => {
      const mockTx = {
        job: {
          findFirst: vi.fn().mockResolvedValue(null),
          update: vi.fn(),
        },
        jobProgress: { create: vi.fn() },
      };
      return cb(mockTx);
    });

    const res = await request(app)
      .post(`/api/jobs/${JOB_ID}/generate-landing`)
      .set(attackerHeaders);

    expect(res.status).toBe(404);
    expect(res.body.error).toBe('Job not found');
  });

  it('calls enqueueLandingPageJob with correct jobId and report filePath', async () => {
    const reportPath = 'outputs/special/report.json';
    const job = {
      id: JOB_ID,
      userId: USER_ID,
      status: JobStatus.COMPLETED,
      landingPageStatus: null,
      assets: [{ assetType: 'REPORT_JSON', filePath: reportPath }],
      progress: [],
    };

    setupTransaction(job);
    mockGetJobAsset.mockResolvedValue({ filePath: reportPath });

    await request(app)
      .post(`/api/jobs/${JOB_ID}/generate-landing`)
      .set(validUserHeaders);

    expect(mockEnqueueLandingPageJob).toHaveBeenCalledWith(JOB_ID, reportPath);
  });

  it('no auth headers → 401', async () => {
    const res = await request(app)
      .post(`/api/jobs/${JOB_ID}/generate-landing`);

    expect(res.status).toBe(401);
  });
});
