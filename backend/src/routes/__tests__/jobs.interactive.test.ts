import { describe, it, expect, vi, beforeEach } from 'vitest';
import express, { Express } from 'express';
import request from 'supertest';

// ============================================
// Mock dependencies
// ============================================
const mockJobFindFirst = vi.fn();
const mockJobUpdate = vi.fn();
const mockJobUpdateMany = vi.fn();
const mockTransaction = vi.fn();
const mockCreditTransactionFindFirst = vi.fn();
const mockUserCreditsFindUnique = vi.fn();

vi.mock('../../services/db.js', () => ({
  prisma: {
    job: {
      findFirst: (...args: any[]) => mockJobFindFirst(...args),
      update: (...args: any[]) => mockJobUpdate(...args),
    },
    creditTransaction: {
      findFirst: (...args: any[]) => mockCreditTransactionFindFirst(...args),
    },
    userCredits: {
      findUnique: (...args: any[]) => mockUserCreditsFindUnique(...args),
    },
    $transaction: (...args: any[]) => mockTransaction(...args),
    discoveryShare: {
      updateMany: vi.fn().mockResolvedValue({ count: 0 }),
    },
  },
}));

const mockEnqueuePhase2Job = vi.fn();
const mockEnqueueRegenerateJob = vi.fn();

vi.mock('../../services/queueService.js', () => ({
  enqueueJob: vi.fn(),
  enqueueLandingPageJob: vi.fn(),
  enqueuePhase2Job: (...args: any[]) => mockEnqueuePhase2Job(...args),
  enqueueRegenerateJob: (...args: any[]) => mockEnqueueRegenerateJob(...args),
  getQueueStats: vi.fn(),
  getQueueLength: vi.fn(),
}));

vi.mock('../../services/creditService.js', () => ({
  createJobAndChargeDiscovery: vi.fn(),
  InsufficientCreditsError: class extends Error {
    currentBalance: number;
    required: number;
    constructor(b: number, r: number) {
      super('Insufficient');
      this.currentBalance = b;
      this.required = r;
    }
  },
  refundForStage: vi.fn(),
  refundForRegenerationStage: vi.fn(),
  chargeForStageInTx: vi.fn().mockResolvedValue({ cost: 15 }),
  chargeForRegenerationInTx: vi.fn().mockResolvedValue({}),
  getStageCost: vi.fn().mockResolvedValue(5),
}));

vi.mock('../../services/jobService.js', () => ({
  getJob: vi.fn(),
  updateJobStatus: vi.fn(),
  getJobAsset: vi.fn(),
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
const authHeaders = { 'x-user-id': 'user-123' };
const jobId = '00000000-0000-0000-0000-000000000001';

beforeEach(async () => {
  vi.clearAllMocks();
  mockJobUpdateMany.mockResolvedValue({ count: 1 });
  mockEnqueuePhase2Job.mockResolvedValue(undefined);
  mockEnqueueRegenerateJob.mockResolvedValue(undefined);

  // Default transaction: execute callback with tx that has job.updateMany
  mockTransaction.mockImplementation(async (callback: any) => {
    const tx = { job: { updateMany: mockJobUpdateMany } };
    return callback(tx);
  });

  app = express();
  app.use(express.json());
  const { jobsRouter } = await import('../jobs.js');
  app.use('/api/jobs', jobsRouter);
});

// ============================================
// Tests
// ============================================
describe('POST /api/jobs/:jobId/select-solution', () => {
  const makeJob = (overrides: Record<string, any> = {}) => ({
    status: 'AWAITING_SELECTION',
    selectedSolutions: [],
    phase1CheckpointPath: '/cp/path',
    solutionIdeas: [{ name: 'Sol1' }, { name: 'Sol2' }],
    niche: 'test niche',
    ...overrides,
  });

  it('enqueues phase 2 during AWAITING_SELECTION', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob());

    const response = await request(app)
      .post(`/api/jobs/${jobId}/select-solution`)
      .set(authHeaders)
      .send({ solutionNames: ['Sol1'] });

    expect(response.status).toBe(200);
    expect(response.body.status).toBe('phase2_queued');
    expect(mockEnqueuePhase2Job).toHaveBeenCalledWith(
      jobId,
      '/cp/path',
      ['Sol1'],
      undefined,
    );
  });

  it('guards against double-selection in transaction', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob());

    await request(app)
      .post(`/api/jobs/${jobId}/select-solution`)
      .set(authHeaders)
      .send({ solutionNames: ['Sol1'] });

    const txCallArgs = mockJobUpdateMany.mock.calls[0][0];
    expect(txCallArgs.where).toEqual(expect.objectContaining({
      selectedSolutions: { equals: [] },
    }));
  });

  it('returns 404 when job not found', async () => {
    mockJobFindFirst.mockResolvedValue(null);

    const response = await request(app)
      .post(`/api/jobs/${jobId}/select-solution`)
      .set(authHeaders)
      .send({ solutionNames: ['Sol1'] });

    expect(response.status).toBe(404);
  });

  it('returns 400 when solution already selected', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob({ selectedSolutions: ['AlreadyPicked'] }));

    const response = await request(app)
      .post(`/api/jobs/${jobId}/select-solution`)
      .set(authHeaders)
      .send({ solutionNames: ['Sol1'] });

    expect(response.status).toBe(400);
    expect(response.body.error).toBe('Solution already selected');
  });

  it('returns 400 when solution name not in solutionIdeas', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob());

    const response = await request(app)
      .post(`/api/jobs/${jobId}/select-solution`)
      .set(authHeaders)
      .send({ solutionNames: ['NonexistentSolution'] });

    expect(response.status).toBe(400);
    expect(response.body.error).toContain('not found in available ideas');
  });

  it('returns 400 when job in wrong status', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob({ status: 'COMPLETED' }));

    const response = await request(app)
      .post(`/api/jobs/${jobId}/select-solution`)
      .set(authHeaders)
      .send({ solutionNames: ['Sol1'] });

    expect(response.status).toBe(400);
    expect(response.body.error).toContain('not in a state');
  });

  it('returns 500 when phase1CheckpointPath is null in AWAITING_SELECTION', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob({ phase1CheckpointPath: null }));

    const response = await request(app)
      .post(`/api/jobs/${jobId}/select-solution`)
      .set(authHeaders)
      .send({ solutionNames: ['Sol1'] });

    expect(response.status).toBe(500);
    expect(response.body.error).toContain('Missing checkpoint path');
  });

  it('returns 409 on concurrent race (updateMany count=0)', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob());
    mockJobUpdateMany.mockResolvedValue({ count: 0 });

    const response = await request(app)
      .post(`/api/jobs/${jobId}/select-solution`)
      .set(authHeaders)
      .send({ solutionNames: ['Sol1'] });

    expect(response.status).toBe(409);
  });

  it('returns 400 for invalid Zod input (missing solutionNames)', async () => {
    const response = await request(app)
      .post(`/api/jobs/${jobId}/select-solution`)
      .set(authHeaders)
      .send({});

    expect(response.status).toBe(400);
    expect(response.body.error).toBe('Validation error');
  });

  it('returns 401 when no auth header', async () => {
    const response = await request(app)
      .post(`/api/jobs/${jobId}/select-solution`)
      .send({ solutionNames: ['Sol1'] });

    expect(response.status).toBe(401);
  });
});

describe('POST /api/jobs/:jobId/regenerate-ideas', () => {
  const makeJob = (overrides: Record<string, any> = {}) => ({
    status: 'AWAITING_SELECTION',
    ideasRegeneratedAt: null,
    regenerationCount: 0,
    phase1CheckpointPath: '/cp/path',
    solutionIdeas: [{ name: 'A' }, { solution_name: 'B' }],
    niche: 'test niche',
    ...overrides,
  });

  it('transitions AWAITING_SELECTION → QUEUED', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob());

    const response = await request(app)
      .post(`/api/jobs/${jobId}/regenerate-ideas`)
      .set(authHeaders)
      .send({});

    expect(response.status).toBe(200);
    expect(response.body.status).toBe('queued');

    const txCallArgs = mockJobUpdateMany.mock.calls[0][0];
    expect(txCallArgs.where.status).toBe('AWAITING_SELECTION');
    expect(txCallArgs.data.status).toBe('QUEUED');
  });

  it('calls enqueueRegenerateJob with correct args', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob());

    await request(app)
      .post(`/api/jobs/${jobId}/regenerate-ideas`)
      .set(authHeaders)
      .send({});

    expect(mockEnqueueRegenerateJob).toHaveBeenCalledWith(
      jobId,
      '/cp/path',
      ['A', 'B'],
      'test niche'
    );
  });

  it('extracts solution names from both s.name and s.solution_name', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob({
      solutionIdeas: [{ name: 'NameA' }, { solution_name: 'NameB' }, { name: 'NameC' }],
    }));

    await request(app)
      .post(`/api/jobs/${jobId}/regenerate-ideas`)
      .set(authHeaders)
      .send({});

    const callArgs = mockEnqueueRegenerateJob.mock.calls[0];
    expect(callArgs[2]).toEqual(['NameA', 'NameB', 'NameC']);
  });

  it('returns 404 for wrong user (job not found)', async () => {
    mockJobFindFirst.mockResolvedValue(null);

    const response = await request(app)
      .post(`/api/jobs/${jobId}/regenerate-ideas`)
      .set(authHeaders)
      .send({});

    expect(response.status).toBe(404);
  });

  it('returns 400 when not in AWAITING_SELECTION', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob({ status: 'RUNNING' }));

    const response = await request(app)
      .post(`/api/jobs/${jobId}/regenerate-ideas`)
      .set(authHeaders)
      .send({});

    expect(response.status).toBe(400);
    expect(response.body.error).toContain('only regenerate ideas when awaiting selection');
  });

  it('returns 400 when max regenerations reached', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob({ regenerationCount: 10 }));

    const response = await request(app)
      .post(`/api/jobs/${jobId}/regenerate-ideas`)
      .set(authHeaders)
      .send({});

    expect(response.status).toBe(400);
    expect(response.body.error).toContain('Maximum regenerations');
  });

  it('allows regeneration when ideasRegeneratedAt is already set (not first regen)', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob({ ideasRegeneratedAt: new Date(), regenerationCount: 1 }));

    const response = await request(app)
      .post(`/api/jobs/${jobId}/regenerate-ideas`)
      .set(authHeaders)
      .send({});

    expect(response.status).toBe(200);
    expect(response.body.status).toBe('queued');
  });

  it('returns 500 when phase1CheckpointPath is null', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob({ phase1CheckpointPath: null }));

    const response = await request(app)
      .post(`/api/jobs/${jobId}/regenerate-ideas`)
      .set(authHeaders)
      .send({});

    expect(response.status).toBe(500);
    expect(response.body.error).toContain('Missing checkpoint path');
  });

  it('returns 409 on concurrent race (updateMany count=0)', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob());
    mockJobUpdateMany.mockResolvedValue({ count: 0 });

    const response = await request(app)
      .post(`/api/jobs/${jobId}/regenerate-ideas`)
      .set(authHeaders)
      .send({});

    expect(response.status).toBe(409);
  });

  it('refunds credits and reverts job when enqueue fails', async () => {
    const { refundForRegenerationStage } = await import('../../services/creditService.js');
    mockJobFindFirst.mockResolvedValue(makeJob());
    mockEnqueueRegenerateJob.mockRejectedValue(new Error('Redis unavailable'));

    const response = await request(app)
      .post(`/api/jobs/${jobId}/regenerate-ideas`)
      .set(authHeaders)
      .send({});

    expect(response.status).toBe(500);
    expect(refundForRegenerationStage).toHaveBeenCalledWith(jobId, 1);
    expect(mockJobUpdate).toHaveBeenCalledWith({
      where: { id: jobId },
      data: { status: 'AWAITING_SELECTION', queuedAt: null },
    });
  });
});

describe('GET /api/jobs/:jobId/solutions', () => {
  it('returns solution data', async () => {
    mockJobFindFirst.mockResolvedValue({
      solutionIdeas: [{ name: 'Sol1' }],
      selectedSolution: 'Sol1',
      selectedSolutions: ['Sol1'],
      selectionRationale: 'best fit',
      ideasRegeneratedAt: null,
      status: 'AWAITING_SELECTION',
    });

    const response = await request(app)
      .get(`/api/jobs/${jobId}/solutions`)
      .set(authHeaders);

    expect(response.status).toBe(200);
    expect(response.body).toEqual({
      solutionIdeas: [{ name: 'Sol1' }],
      selectedSolution: 'Sol1',
      selectedSolutions: ['Sol1'],
      selectionRationale: 'best fit',
      canRegenerate: true,
      status: 'AWAITING_SELECTION',
    });
  });

  it('canRegenerate is true when ideasRegeneratedAt is null', async () => {
    mockJobFindFirst.mockResolvedValue({
      solutionIdeas: [],
      selectedSolution: null,
      selectedSolutions: [],
      selectionRationale: null,
      ideasRegeneratedAt: null,
      status: 'AWAITING_SELECTION',
    });

    const response = await request(app)
      .get(`/api/jobs/${jobId}/solutions`)
      .set(authHeaders);

    expect(response.body.canRegenerate).toBe(true);
  });

  it('canRegenerate is always true even when ideasRegeneratedAt is set', async () => {
    mockJobFindFirst.mockResolvedValue({
      solutionIdeas: [],
      selectedSolution: null,
      selectedSolutions: [],
      selectionRationale: null,
      ideasRegeneratedAt: new Date(),
      status: 'AWAITING_SELECTION',
    });

    const response = await request(app)
      .get(`/api/jobs/${jobId}/solutions`)
      .set(authHeaders);

    expect(response.body.canRegenerate).toBe(true);
  });

  it('returns 404 for wrong user', async () => {
    mockJobFindFirst.mockResolvedValue(null);

    const response = await request(app)
      .get(`/api/jobs/${jobId}/solutions`)
      .set(authHeaders);

    expect(response.status).toBe(404);
  });
});

describe('POST /api/jobs/:jobId/resume', () => {
  it('creates JOB_DEDUCTION with resume_ stage prefix instead of deleting refund', async () => {
    // Job is FAILED with a refund transaction
    mockJobFindFirst.mockResolvedValue({
      id: jobId,
      userId: 'user-123',
      status: 'FAILED',
      niche: 'test niche',
    });

    mockCreditTransactionFindFirst.mockResolvedValue({
      id: 'refund-tx-1',
      amount: 5,
      stage: 'discovery',
    });

    mockUserCreditsFindUnique.mockResolvedValue({
      userId: 'user-123',
      balance: 10,
    });

    // Transaction mock: execute callback with tx that has userCredits + creditTransaction
    const mockTxUserCreditsFind = vi.fn().mockResolvedValue({ userId: 'user-123', balance: 10 });
    const mockTxUserCreditsUpdate = vi.fn().mockResolvedValue({ userId: 'user-123', balance: 5 });
    const mockTxCreditTransactionCreate = vi.fn().mockResolvedValue({});
    const mockTxCreditTransactionDelete = vi.fn();

    mockTransaction.mockImplementation(async (callback: any) => {
      const tx = {
        userCredits: {
          findUnique: mockTxUserCreditsFind,
          update: mockTxUserCreditsUpdate,
        },
        creditTransaction: {
          create: mockTxCreditTransactionCreate,
          delete: mockTxCreditTransactionDelete,
        },
        job: { updateMany: mockJobUpdateMany },
      };
      return callback(tx);
    });

    mockJobUpdate.mockResolvedValue({});

    const response = await request(app)
      .post(`/api/jobs/${jobId}/resume`)
      .set(authHeaders)
      .send({});

    expect(response.status).toBe(200);

    // Should NOT delete the refund transaction
    expect(mockTxCreditTransactionDelete).not.toHaveBeenCalled();

    // Should create a new JOB_DEDUCTION with resume_ prefix
    expect(mockTxCreditTransactionCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        userId: 'user-123',
        type: 'JOB_DEDUCTION',
        amount: -5,
        balanceBefore: 10,
        balanceAfter: 5,
        relatedJobId: jobId,
        stage: 'resume_discovery',
        description: 'Resume: re-charge discovery',
      }),
    });

    // Should decrement balance
    expect(mockTxUserCreditsUpdate).toHaveBeenCalledWith({
      where: { userId: 'user-123' },
      data: {
        balance: { decrement: 5 },
        totalUsed: { increment: 5 },
      },
    });
  });

  it('returns 402 when balance insufficient for resume re-charge', async () => {
    mockJobFindFirst.mockResolvedValue({
      id: jobId,
      userId: 'user-123',
      status: 'FAILED',
      niche: 'test niche',
    });

    mockCreditTransactionFindFirst.mockResolvedValue({
      id: 'refund-tx-1',
      amount: 5,
      stage: 'discovery',
    });

    // Balance is too low
    mockUserCreditsFindUnique.mockResolvedValue({
      userId: 'user-123',
      balance: 3,
    });

    const response = await request(app)
      .post(`/api/jobs/${jobId}/resume`)
      .set(authHeaders)
      .send({});

    expect(response.status).toBe(402);
    expect(response.body.code).toBe('INSUFFICIENT_CREDITS');
  });
});
