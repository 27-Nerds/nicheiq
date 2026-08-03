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
const mockJobProgressDeleteMany = vi.fn();
const mockPrismaTransaction = vi.fn();

vi.mock('../../services/db.js', () => ({
  prisma: {
    jobDispatch: { create: async () => ({ id: 'dispatch-test' }), updateMany: async () => ({ count: 1 }) },
    job: {
      findFirst: (...args: any[]) => mockJobFindFirst(...args),
      findUnique: (...args: any[]) => mockJobFindUnique(...args),
      update: (...args: any[]) => mockJobUpdate(...args),
    },
    jobProgress: {
      updateMany: (...args: any[]) => mockUpdateMany(...args),
      create: (...args: any[]) => mockJobProgressCreate(...args),
      deleteMany: (...args: any[]) => mockJobProgressDeleteMany(...args),
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

const mockChargeForStageWithPriceCasInTx = vi.fn();

vi.mock('../../services/creditService.js', () => ({
  createJobAndChargeDiscovery: vi.fn(),
  createJobAndChargeDiscoveryInTx: vi.fn(),
  refundForStage: vi.fn(),
  chargeForStageWithPriceCasInTx: (...args: any[]) => mockChargeForStageWithPriceCasInTx(...args),
  chargeForRegenerationInTx: vi.fn(),
  chargeForResume: vi.fn(),
  segmentForGateContinue: vi.fn(),
  chargeForSeedIdeaInTx: vi.fn(),
  refundChargeInTx: vi.fn(),
  getStageCost: vi.fn().mockResolvedValue(5),
  PriceChangedError: class PriceChangedError extends Error {
    expectedCost: number;
    actualCost: number;
    constructor(expectedCost: number, actualCost: number) {
      super('Price changed');
      this.expectedCost = expectedCost;
      this.actualCost = actualCost;
    }
  },
  InsufficientCreditsError: class InsufficientCreditsError extends Error {
    currentBalance: number;
    required: number;
    constructor(currentBalance: number, required: number) {
      super(`Insufficient credits: have ${currentBalance}, need ${required}`);
      this.name = 'InsufficientCreditsError';
      this.currentBalance = currentBalance;
      this.required = required;
    }
  },
}));

const mockEnqueueJob = vi.fn();
const mockDeliverDispatchWork = vi.fn();
const mockGetQueueStats = vi.fn();
const mockGetQueueLength = vi.fn();

vi.mock('../../services/queueService.js', () => ({
  enqueueJob: (...args: any[]) => mockEnqueueJob(...args),
  deliverDispatchWork: (...args: any[]) => mockDeliverDispatchWork(...args),
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
  mockDeliverDispatchWork.mockResolvedValue(undefined);
  mockChargeForStageWithPriceCasInTx.mockResolvedValue({
    cost: 5,
    transaction: { id: 'charge-landing-1' },
  });
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
        updateMany: vi.fn().mockResolvedValue({ count: 1 }),
        update: vi.fn().mockResolvedValue({ ...job, landingPageStatus: 'QUEUED' }),
      },
      jobProgress: {
        create: vi.fn().mockResolvedValue({}),
        upsert: vi.fn().mockResolvedValue({}),
      },
      // Landing-page generation runs on an already-COMPLETED job that still carries the
      // activeDispatchId of the research run. It needs its OWN attempt, or its callbacks would be
      // matched against a dispatch belonging to a different run.
      jobDispatch: { create: vi.fn().mockResolvedValue({ id: 'dispatch-test' }) },
    };
    mockPrismaTransaction.mockImplementation(async (cb: any) => cb(mockTx));
    return mockTx;
  }

  it('happy path: COMPLETED job + report asset + no landing → enqueues landing job, returns ok', async () => {
    const job = {
      id: JOB_ID,
      userId: USER_ID,
      niche: 'test niche',
      status: JobStatus.COMPLETED,
      landingPageStatus: null,
      assets: [{ assetType: 'REPORT_JSON', filePath: 'outputs/job-1/report.json' }],
      progress: [],
    };

    const mockTx = setupTransaction(job);
    mockGetJobAsset.mockResolvedValue({ filePath: 'outputs/job-1/report.json' });

    const res = await request(app)
      .post(`/api/jobs/${JOB_ID}/generate-landing`)
      .set(validUserHeaders)
      .send({ expectedCost: 5 });

    expect(res.status).toBe(200);
    expect(res.body).toEqual({
      status: 'ok',
      operationId: 'dispatch-test',
      deliveryPending: false,
    });

    // Transaction should have upserted stage 15 progress (supports retry after monitor failure)
    expect(mockTx.jobProgress.upsert).toHaveBeenCalledWith({
      where: { jobId_stageNumber: { jobId: JOB_ID, stageNumber: 15 } },
      create: expect.objectContaining({
        jobId: JOB_ID,
        stageNumber: 15,
        stageName: 'Landing Page Generation',
        status: 'PENDING',
      }),
      update: expect.objectContaining({
        status: 'PENDING',
        errorMessage: null,
      }),
    });

    // Transaction should have updated job with QUEUED status and incremented totalStages
    expect(mockTx.job.updateMany).toHaveBeenCalledWith({
      where: {
        id: JOB_ID,
        userId: USER_ID,
        status: JobStatus.COMPLETED,
        OR: [{ landingPageStatus: null }, { landingPageStatus: 'FAILED' }],
      },
      data: expect.objectContaining({
        generateLandingPage: true,
        landingPageStatus: 'QUEUED',
        totalStages: { increment: 1 },
      }),
    });

    // The charge and its dispatch are written through the same transaction client, and the
    // dispatch points at the exact ledger row that this landing-page attempt paid with.
    expect(mockChargeForStageWithPriceCasInTx).toHaveBeenCalledWith(
      mockTx,
      USER_ID,
      JOB_ID,
      'landing_page',
      'landing_page',
      'test niche',
      5,
    );
    expect(mockTx.jobDispatch.create).toHaveBeenCalledWith({
      data: expect.objectContaining({
        jobId: JOB_ID,
        kind: 'CONTINUE',
        segment: 'landing_page',
        chargeId: 'charge-landing-1',
        workPayload: expect.objectContaining({
          job_id: JOB_ID,
          report_path: 'outputs/job-1/report.json',
          task_type: 'landing_page',
        }),
      }),
      select: { id: true },
    });

    expect(mockDeliverDispatchWork).toHaveBeenCalledWith('dispatch-test');
  });

  it('retries a failed landing attempt on a new ledger cycle without adding stage 15 twice', async () => {
    const job = {
      id: JOB_ID,
      userId: USER_ID,
      niche: 'test niche',
      status: JobStatus.COMPLETED,
      landingPageStatus: 'FAILED',
      assets: [{ assetType: 'REPORT_JSON', filePath: 'outputs/job-1/report.json' }],
      progress: [{ stageNumber: 15, status: 'FAILED' }],
    };
    const mockTx = setupTransaction(job);

    const res = await request(app)
      .post(`/api/jobs/${JOB_ID}/generate-landing`)
      .set(validUserHeaders)
      .send({ expectedCost: 5 });

    expect(res.status).toBe(200);
    expect(mockChargeForStageWithPriceCasInTx).toHaveBeenCalledWith(
      mockTx,
      USER_ID,
      JOB_ID,
      'landing_page',
      'landing_page',
      'test niche',
      5,
    );
    expect(mockTx.job.updateMany).toHaveBeenCalledWith({
      where: {
        id: JOB_ID,
        userId: USER_ID,
        status: JobStatus.COMPLETED,
        OR: [{ landingPageStatus: null }, { landingPageStatus: 'FAILED' }],
      },
      data: {
        generateLandingPage: true,
        landingPageStatus: 'QUEUED',
      },
    });
  });

  it('uses a job CAS so concurrent requests cannot both charge', async () => {
    const job = {
      id: JOB_ID,
      userId: USER_ID,
      niche: 'test niche',
      status: JobStatus.COMPLETED,
      landingPageStatus: null,
      assets: [{ assetType: 'REPORT_JSON', filePath: 'outputs/job-1/report.json' }],
      progress: [],
    };
    const mockTx = setupTransaction(job);
    mockTx.job.updateMany.mockResolvedValueOnce({ count: 0 });

    const res = await request(app)
      .post(`/api/jobs/${JOB_ID}/generate-landing`)
      .set(validUserHeaders)
      .send({ expectedCost: 5 });

    expect(res.status).toBe(409);
    expect(res.body).toEqual({
      error: 'Landing page generation was already started in another request',
      code: 'LANDING_PAGE_START_CONFLICT',
    });
    expect(mockChargeForStageWithPriceCasInTx).not.toHaveBeenCalled();
    expect(mockTx.jobProgress.upsert).not.toHaveBeenCalled();
    expect(mockTx.jobDispatch.create).not.toHaveBeenCalled();
    expect(mockDeliverDispatchWork).not.toHaveBeenCalled();
  });

  it('requires the displayed landing-page price to be confirmed', async () => {
    const res = await request(app)
      .post(`/api/jobs/${JOB_ID}/generate-landing`)
      .set(validUserHeaders)
      .send({});

    expect(res.status).toBe(400);
    expect(res.body.error).toBe('Validation error');
    expect(mockPrismaTransaction).not.toHaveBeenCalled();
    expect(mockChargeForStageWithPriceCasInTx).not.toHaveBeenCalled();
    expect(mockDeliverDispatchWork).not.toHaveBeenCalled();
  });

  it('rolls back when the landing-page price changes before the charge', async () => {
    const { PriceChangedError } = await import('../../services/creditService.js');
    const job = {
      id: JOB_ID,
      userId: USER_ID,
      niche: 'test niche',
      status: JobStatus.COMPLETED,
      landingPageStatus: null,
      assets: [{ assetType: 'REPORT_JSON', filePath: 'outputs/job-1/report.json' }],
      progress: [],
    };
    const mockTx = setupTransaction(job);
    mockChargeForStageWithPriceCasInTx.mockRejectedValueOnce(new PriceChangedError(5, 7));

    const res = await request(app)
      .post(`/api/jobs/${JOB_ID}/generate-landing`)
      .set(validUserHeaders)
      .send({ expectedCost: 5 });

    expect(res.status).toBe(409);
    expect(res.body).toEqual({
      error: 'Landing page price changed; review the updated price before continuing',
      code: 'PRICE_CHANGED',
      expectedCost: 5,
      actualCost: 7,
    });
    expect(mockChargeForStageWithPriceCasInTx).toHaveBeenCalledWith(
      mockTx,
      USER_ID,
      JOB_ID,
      'landing_page',
      'landing_page',
      'test niche',
      5,
    );
    expect(mockTx.jobDispatch.create).not.toHaveBeenCalled();
    expect(mockDeliverDispatchWork).not.toHaveBeenCalled();
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
      .set(validUserHeaders)
      .send({ expectedCost: 5 });

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
      .set(validUserHeaders)
      .send({ expectedCost: 5 });

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
      .set(validUserHeaders)
      .send({ expectedCost: 5 });

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
      .set(validUserHeaders)
      .send({ expectedCost: 5 });

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
      .set(validUserHeaders)
      .send({ expectedCost: 5 });

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
      .set(attackerHeaders)
      .send({ expectedCost: 5 });

    expect(res.status).toBe(404);
    expect(res.body.error).toBe('Job not found');
  });

  it('persists the report path in the durable dispatch work payload', async () => {
    const reportPath = 'outputs/special/report.json';
    const job = {
      id: JOB_ID,
      userId: USER_ID,
      status: JobStatus.COMPLETED,
      landingPageStatus: null,
      assets: [{ assetType: 'REPORT_JSON', filePath: reportPath }],
      progress: [],
    };

    const mockTx = setupTransaction(job);
    mockGetJobAsset.mockResolvedValue({ filePath: reportPath });

    await request(app)
      .post(`/api/jobs/${JOB_ID}/generate-landing`)
      .set(validUserHeaders)
      .send({ expectedCost: 5 });

    expect(mockTx.jobDispatch.create).toHaveBeenCalledWith({
      data: expect.objectContaining({
        workPayload: expect.objectContaining({
          job_id: JOB_ID,
          report_path: reportPath,
          task_type: 'landing_page',
        }),
      }),
      select: { id: true },
    });
    expect(mockDeliverDispatchWork).toHaveBeenCalledWith('dispatch-test');
  });

  it('does not enqueue or compensate when dispatch creation aborts the charge transaction', async () => {
    const { refundForStage } = await import('../../services/creditService.js');
    const job = {
      id: JOB_ID,
      userId: USER_ID,
      niche: 'test niche',
      status: JobStatus.COMPLETED,
      landingPageStatus: null,
      assets: [{ assetType: 'REPORT_JSON', filePath: 'outputs/job-1/report.json' }],
      progress: [],
    };

    const mockTx = setupTransaction(job);
    mockTx.jobDispatch.create.mockRejectedValueOnce(new Error('dispatch write failed'));

    const res = await request(app)
      .post(`/api/jobs/${JOB_ID}/generate-landing`)
      .set(validUserHeaders)
      .send({ expectedCost: 5 });

    expect(res.status).toBe(500);
    expect(mockChargeForStageWithPriceCasInTx).toHaveBeenCalledWith(
      mockTx,
      USER_ID,
      JOB_ID,
      'landing_page',
      'landing_page',
      'test niche',
      5,
    );
    expect(mockDeliverDispatchWork).not.toHaveBeenCalled();
    expect(refundForStage).not.toHaveBeenCalled();
  });

  it('no auth headers → 401', async () => {
    const res = await request(app)
      .post(`/api/jobs/${JOB_ID}/generate-landing`);

    expect(res.status).toBe(401);
  });

  it('keeps the authorized landing attempt durable when Redis delivery is ambiguous', async () => {
    const { refundForStage } = await import('../../services/creditService.js');
    const job = {
      id: JOB_ID,
      userId: USER_ID,
      niche: 'test niche',
      status: JobStatus.COMPLETED,
      landingPageStatus: null,
      assets: [{ assetType: 'REPORT_JSON', filePath: 'outputs/job-1/report.json' }],
      progress: [],
    };

    setupTransaction(job);
    mockGetJobAsset.mockResolvedValue({ filePath: 'outputs/job-1/report.json' });
    mockDeliverDispatchWork.mockRejectedValue(new Error('Redis unavailable'));

    const res = await request(app)
      .post(`/api/jobs/${JOB_ID}/generate-landing`)
      .set(validUserHeaders)
      .send({ expectedCost: 5 });

    expect(res.status).toBe(200);
    expect(res.body).toEqual({
      status: 'ok',
      operationId: 'dispatch-test',
      deliveryPending: true,
    });
    expect(refundForStage).not.toHaveBeenCalled();
  });
});
