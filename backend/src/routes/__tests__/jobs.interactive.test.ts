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

vi.mock('../../services/db.js', () => ({
  prisma: {
    job: {
      findFirst: (...args: any[]) => mockJobFindFirst(...args),
      update: (...args: any[]) => mockJobUpdate(...args),
    },
    $transaction: (...args: any[]) => mockTransaction(...args),
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
  createJobWithCreditDeduction: vi.fn(),
  InsufficientCreditsError: class extends Error {
    currentBalance: number;
    required: number;
    constructor(b: number, r: number) {
      super('Insufficient');
      this.currentBalance = b;
      this.required = r;
    }
  },
  refundCreditsForJob: vi.fn(),
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
    selectedSolution: null,
    phase1CheckpointPath: '/cp/path',
    solutionIdeas: [{ name: 'Sol1' }, { name: 'Sol2' }],
    generateLandingPage: true,
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
      true
    );
  });

  it('passes generateLandingPage flag to enqueuePhase2Job', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob({ generateLandingPage: false }));

    await request(app)
      .post(`/api/jobs/${jobId}/select-solution`)
      .set(authHeaders)
      .send({ solutionNames: ['Sol1'] });

    expect(mockEnqueuePhase2Job).toHaveBeenCalledWith(
      jobId,
      '/cp/path',
      ['Sol1'],
      undefined,
      false
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
      selectedSolution: null,
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
    mockJobFindFirst.mockResolvedValue(makeJob({ selectedSolution: 'AlreadyPicked' }));

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
    phase1CheckpointPath: '/cp/path',
    solutionIdeas: [{ name: 'A' }, { solution_name: 'B' }],
    niche: 'test niche',
    ...overrides,
  });

  it('transitions AWAITING_SELECTION → REGENERATING', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob());

    const response = await request(app)
      .post(`/api/jobs/${jobId}/regenerate-ideas`)
      .set(authHeaders)
      .send({});

    expect(response.status).toBe(200);
    expect(response.body.status).toBe('regenerating');

    const txCallArgs = mockJobUpdateMany.mock.calls[0][0];
    expect(txCallArgs.where.status).toBe('AWAITING_SELECTION');
    expect(txCallArgs.data.status).toBe('REGENERATING');
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

  it('returns 400 when already regenerated', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob({ ideasRegeneratedAt: new Date() }));

    const response = await request(app)
      .post(`/api/jobs/${jobId}/regenerate-ideas`)
      .set(authHeaders)
      .send({});

    expect(response.status).toBe(400);
    expect(response.body.error).toContain('only be regenerated once');
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

  it('canRegenerate is false when ideasRegeneratedAt is set', async () => {
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

    expect(response.body.canRegenerate).toBe(false);
  });

  it('returns 404 for wrong user', async () => {
    mockJobFindFirst.mockResolvedValue(null);

    const response = await request(app)
      .get(`/api/jobs/${jobId}/solutions`)
      .set(authHeaders);

    expect(response.status).toBe(404);
  });
});
