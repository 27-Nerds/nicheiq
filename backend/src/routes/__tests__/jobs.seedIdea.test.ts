/**
 * POST /api/jobs/:jobId/seed-idea (plans/eager-meandering-feather.md Phase 5) — "generate an
 * idea from your own idea" at selection chat. Mirrors jobs.gateAction.test.ts's mocking shape:
 * dispatchService.js is NOT mocked — openDispatch/settleDispatch run for REAL against the `tx`
 * this file controls, so a passing test here also proves the real dispatch plumbing wires up.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import express, { Express } from 'express';
import request from 'supertest';

const mockJobFindFirst = vi.fn();
// tx-scoped job.updateMany — used by the seedIdeaCount+status flip AND (on the compensation
// path) both the revert itself and settleDispatch's internal CAS-disarm update.
const mockJobUpdateMany = vi.fn();
const mockJobUpdate = vi.fn();
const mockDispatchCreate = vi.fn();
const mockDispatchUpdateMany = vi.fn();
const mockChatMessageCreate = vi.fn();
const mockChatMessageDelete = vi.fn();
const mockTransaction = vi.fn();

vi.mock('../../services/db.js', () => ({
  prisma: {
    job: { findFirst: (...a: any[]) => mockJobFindFirst(...a) },
    chatMessage: { delete: (...a: any[]) => mockChatMessageDelete(...a) },
    $transaction: (...a: any[]) => mockTransaction(...a),
  },
}));

const mockEnqueueSeedIdeaJob = vi.fn();

vi.mock('../../services/queueService.js', () => ({
  enqueueJob: vi.fn(),
  enqueueLandingPageJob: vi.fn(),
  enqueuePhase2Job: vi.fn(),
  enqueueRegenerateJob: vi.fn(),
  enqueueContinueFromGateJob: vi.fn(),
  enqueueSeedIdeaJob: (...a: any[]) => mockEnqueueSeedIdeaJob(...a),
  getQueueStats: vi.fn(),
  getQueueLength: vi.fn(),
}));

const mockChargeForSeedIdeaInTx = vi.fn();
const mockRefundForSeedIdeaStage = vi.fn();

class MockInsufficientCreditsError extends Error {
  currentBalance: number;
  required: number;
  constructor(balance: number, required: number) {
    super('Insufficient credits');
    this.name = 'InsufficientCreditsError';
    this.currentBalance = balance;
    this.required = required;
  }
}

class MockPriceChangedError extends Error {
  expectedCost: number;
  actualCost: number;
  constructor(expectedCost: number, actualCost: number) {
    super('Price changed');
    this.name = 'PriceChangedError';
    this.expectedCost = expectedCost;
    this.actualCost = actualCost;
  }
}

vi.mock('../../services/creditService.js', () => ({
  createJobAndChargeDiscovery: vi.fn(),
  InsufficientCreditsError: MockInsufficientCreditsError,
  PriceChangedError: MockPriceChangedError,
  refundForStage: vi.fn(),
  chargeForStageInTx: vi.fn(),
  chargeForStageWithPriceCasInTx: vi.fn(),
  chargeForRegenerationInTx: vi.fn(),
  refundForRegenerationStage: vi.fn(),
  chargeForResume: vi.fn(),
  segmentForGateContinue: vi.fn(),
  chargeForSeedIdeaInTx: (...a: any[]) => mockChargeForSeedIdeaInTx(...a),
  refundForSeedIdeaStage: (...a: any[]) => mockRefundForSeedIdeaStage(...a),
}));

vi.mock('../../services/jobService.js', () => ({
  getJob: vi.fn(),
  getJobAsset: vi.fn(),
  cancelJob: vi.fn(),
}));

const mockIsEntitledUser = vi.fn();

vi.mock('../../services/catalogService.js', () => ({
  isEntitledUser: (...a: any[]) => mockIsEntitledUser(...a),
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

let app: Express;
const authHeaders = { 'x-user-id': 'user-123' };
const jobId = '00000000-0000-0000-0000-000000000001';

const makeJob = (overrides: Record<string, any> = {}) => ({
  status: 'AWAITING_SELECTION',
  seedIdeaCount: 0,
  phase1CheckpointPath: '/cp/path',
  niche: 'test niche',
  ...overrides,
});

beforeEach(async () => {
  vi.clearAllMocks();
  mockIsEntitledUser.mockResolvedValue(true);
  mockEnqueueSeedIdeaJob.mockResolvedValue(undefined);
  mockChargeForSeedIdeaInTx.mockResolvedValue({ cost: 2, transaction: { id: 'txn-seed-1' } });
  mockRefundForSeedIdeaStage.mockResolvedValue({ amount: -2 });
  mockJobUpdateMany.mockResolvedValue({ count: 1 });
  mockJobUpdate.mockResolvedValue({});
  mockDispatchCreate.mockResolvedValue({ id: 'dispatch-seed-1' });
  mockDispatchUpdateMany.mockResolvedValue({ count: 1 });
  mockChatMessageCreate.mockResolvedValue({ id: 'receipt-1' });
  mockChatMessageDelete.mockResolvedValue({});

  const tx = {
    job: { updateMany: (...a: any[]) => mockJobUpdateMany(...a), update: (...a: any[]) => mockJobUpdate(...a) },
    jobDispatch: {
      create: (...a: any[]) => mockDispatchCreate(...a),
      updateMany: (...a: any[]) => mockDispatchUpdateMany(...a),
    },
    chatMessage: { create: (...a: any[]) => mockChatMessageCreate(...a) },
  };
  mockTransaction.mockImplementation(async (cb: any) => cb(tx));

  app = express();
  app.use(express.json());
  const { jobsRouter } = await import('../jobs.js');
  app.use('/api/jobs', jobsRouter);
});

const validBody = {
  free_text: 'A tool that does X for Y',
  pain_ref: 'Pain A',
  tool_ref: 'Spreadsheets',
  sourceMessageId: 'msg-abc',
  expectedCost: 2,
};

describe('POST /api/jobs/:jobId/seed-idea', () => {
  it('returns 404 for a job the user does not own / that does not exist', async () => {
    mockJobFindFirst.mockResolvedValue(null);

    const response = await request(app)
      .post(`/api/jobs/${jobId}/seed-idea`)
      .set(authHeaders)
      .send(validBody);

    expect(response.status).toBe(404);
  });

  it('returns 402 when the user is not entitled', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob());
    mockIsEntitledUser.mockResolvedValue(false);

    const response = await request(app)
      .post(`/api/jobs/${jobId}/seed-idea`)
      .set(authHeaders)
      .send(validBody);

    expect(response.status).toBe(402);
    expect(response.body.code).toBe('NOT_ENTITLED');
    expect(mockChargeForSeedIdeaInTx).not.toHaveBeenCalled();
  });

  it('returns 400 when expectedCost is missing', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob());
    const { expectedCost, ...withoutCost } = validBody;

    const response = await request(app)
      .post(`/api/jobs/${jobId}/seed-idea`)
      .set(authHeaders)
      .send(withoutCost);

    expect(response.status).toBe(400);
    expect(mockChargeForSeedIdeaInTx).not.toHaveBeenCalled();
  });

  it('returns 400 when sourceMessageId is missing (card identity is required, not optional)', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob());
    const { sourceMessageId, ...withoutSourceId } = validBody;

    const response = await request(app)
      .post(`/api/jobs/${jobId}/seed-idea`)
      .set(authHeaders)
      .send(withoutSourceId);

    expect(response.status).toBe(400);
  });

  it('returns 400 when the job is not AWAITING_SELECTION', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob({ status: 'RUNNING' }));

    const response = await request(app)
      .post(`/api/jobs/${jobId}/seed-idea`)
      .set(authHeaders)
      .send(validBody);

    expect(response.status).toBe(400);
    expect(response.body.status).toBe('RUNNING');
  });

  it('returns 500 when phase1CheckpointPath is missing', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob({ phase1CheckpointPath: null }));

    const response = await request(app)
      .post(`/api/jobs/${jobId}/seed-idea`)
      .set(authHeaders)
      .send(validBody);

    expect(response.status).toBe(500);
  });

  it('returns 402 with balance/required on insufficient credits, no dispatch opened', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob());
    mockChargeForSeedIdeaInTx.mockRejectedValue(new MockInsufficientCreditsError(1, 2));

    const response = await request(app)
      .post(`/api/jobs/${jobId}/seed-idea`)
      .set(authHeaders)
      .send(validBody);

    expect(response.status).toBe(402);
    expect(response.body).toEqual(
      expect.objectContaining({ code: 'INSUFFICIENT_CREDITS', balance: 1, required: 2 }),
    );
    expect(mockDispatchCreate).not.toHaveBeenCalled();
  });

  it('returns 409 PRICE_CHANGED on a mid-flight reprice — nothing charged, no dispatch opened', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob());
    mockChargeForSeedIdeaInTx.mockRejectedValue(new MockPriceChangedError(2, 5));

    const response = await request(app)
      .post(`/api/jobs/${jobId}/seed-idea`)
      .set(authHeaders)
      .send(validBody);

    expect(response.status).toBe(409);
    expect(response.body).toEqual(
      expect.objectContaining({ code: 'PRICE_CHANGED', expectedCost: 2, actualCost: 5 }),
    );
    expect(mockDispatchCreate).not.toHaveBeenCalled();
  });

  it('happy path: charges seed_idea_1, flips to QUEUED, opens a SEED_IDEA dispatch, writes the seed_submitted receipt, and enqueues', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob());

    const response = await request(app)
      .post(`/api/jobs/${jobId}/seed-idea`)
      .set(authHeaders)
      .send(validBody);

    expect(response.status).toBe(200);
    expect(mockChargeForSeedIdeaInTx).toHaveBeenCalledWith(
      expect.anything(), 'user-123', jobId, 1, 'test niche', 2,
    );

    const flipArgs = mockJobUpdateMany.mock.calls[0][0];
    expect(flipArgs.where).toEqual({ id: jobId, status: 'AWAITING_SELECTION', seedIdeaCount: 0 });
    expect(flipArgs.data).toEqual(
      expect.objectContaining({ status: 'QUEUED', seedIdeaCount: 1 }),
    );

    expect(mockDispatchCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          jobId, kind: 'SEED_IDEA', chargeId: 'txn-seed-1', seedOrdinal: 1, sourceMessageId: 'msg-abc',
        }),
      }),
    );

    expect(mockChatMessageCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          jobId, gateStage: 5, role: 'receipt',
          patchJson: expect.objectContaining({
            kind: 'ledger_event', event: 'seed_submitted', sourceMessageId: 'msg-abc',
          }),
        }),
      }),
    );

    expect(mockEnqueueSeedIdeaJob).toHaveBeenCalledWith(
      jobId, '/cp/path', 'test niche', 'A tool that does X for Y', 'Pain A', 'Spreadsheets', 'dispatch-seed-1',
    );
  });

  it('a second seed on the same job charges seed_idea_2 (ordinal derived from seedIdeaCount)', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob({ seedIdeaCount: 1 }));

    await request(app)
      .post(`/api/jobs/${jobId}/seed-idea`)
      .set(authHeaders)
      .send(validBody);

    expect(mockChargeForSeedIdeaInTx).toHaveBeenCalledWith(
      expect.anything(), 'user-123', jobId, 2, 'test niche', 2,
    );
  });

  it('returns 409 CONFLICT when the optimistic seedIdeaCount lock loses the race', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob());
    mockJobUpdateMany.mockResolvedValue({ count: 0 });

    const response = await request(app)
      .post(`/api/jobs/${jobId}/seed-idea`)
      .set(authHeaders)
      .send(validBody);

    expect(response.status).toBe(409);
  });

  it('on enqueue failure: reverts to AWAITING_SELECTION, settles the dispatch FAILED, refunds seed_idea_1, and retracts the seed_submitted receipt', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob());
    mockEnqueueSeedIdeaJob.mockRejectedValue(new Error('Redis unavailable'));

    const response = await request(app)
      .post(`/api/jobs/${jobId}/seed-idea`)
      .set(authHeaders)
      .send(validBody);

    expect(response.status).toBe(500);

    // The compensating revert (second $transaction call) reverted status and settled the
    // dispatch — settleDispatch's own CAS-disarm update reuses the same tx.job.updateMany mock,
    // so we assert on the REVERT call specifically (data.status === AWAITING_SELECTION).
    const revertCall = mockJobUpdateMany.mock.calls.find(
      (c: any[]) => c[0].data?.status === 'AWAITING_SELECTION',
    );
    expect(revertCall).toBeTruthy();
    expect(revertCall![0].where).toEqual({ id: jobId, status: 'QUEUED', activeDispatchId: 'dispatch-seed-1' });

    expect(mockDispatchUpdateMany).toHaveBeenCalledWith(
      expect.objectContaining({
        where: { id: 'dispatch-seed-1' },
        data: expect.objectContaining({ state: 'FAILED' }),
      }),
    );
    expect(mockRefundForSeedIdeaStage).toHaveBeenCalledWith(jobId, 1);
    expect(mockChatMessageDelete).toHaveBeenCalledWith({ where: { id: 'receipt-1' } });
  });

  it('skips refund/retraction when the enqueue-failure revert no longer matches (a worker already claimed it)', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob());
    mockEnqueueSeedIdeaJob.mockRejectedValue(new Error('Redis unavailable'));
    // First call (the main flip) must succeed with count 1; only the SECOND call (compensating
    // revert) should report a lost race.
    mockJobUpdateMany
      .mockResolvedValueOnce({ count: 1 })
      .mockResolvedValue({ count: 0 });

    const response = await request(app)
      .post(`/api/jobs/${jobId}/seed-idea`)
      .set(authHeaders)
      .send(validBody);

    expect(response.status).toBe(500);
    expect(mockRefundForSeedIdeaStage).not.toHaveBeenCalled();
    expect(mockChatMessageDelete).not.toHaveBeenCalled();
  });
});
