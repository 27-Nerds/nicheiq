import { describe, it, expect, vi, beforeEach } from 'vitest';
import express, { Express } from 'express';
import request from 'supertest';

// ============================================
// Mock dependencies
// ============================================
const mockCreateJobAndChargeDiscoveryInTx = vi.fn();
const mockDeliverDispatchWork = vi.fn();
const mockJobUpdate = vi.fn();
const mockJobDispatchCreate = vi.fn();
const mockPrismaTransaction = vi.fn();
const mockIsEntitledUser = vi.fn();

vi.mock('../../services/db.js', () => {
  const client: any = {
    job: {
      update: (...args: any[]) => mockJobUpdate(...args),
      updateMany: vi.fn(async () => ({ count: 1 })),
    },
    // Job creation now opens a dispatch, so the initial run has an identity a worker callback can
    // be matched against — previously it was the one path with none at all.
    jobDispatch: { create: (...args: any[]) => mockJobDispatchCreate(...args) },
  };
  client.$transaction = (arg: any) => {
    mockPrismaTransaction(arg);
    return typeof arg === 'function' ? arg(client) : Promise.all(arg);
  };
  return { prisma: client };
});

vi.mock('../../services/queueService.js', () => ({
  deliverDispatchWork: (...args: any[]) => mockDeliverDispatchWork(...args),
  enqueueLandingPageJob: vi.fn(),
  enqueuePhase2Job: vi.fn(),
  enqueueRegenerateJob: vi.fn(),
  enqueueContinueFromGateJob: vi.fn(),
  getQueueStats: vi.fn(),
  getQueueLength: vi.fn(),
  removeJobFromQueue: vi.fn(),
}));

vi.mock('../../services/creditService.js', () => ({
  createJobAndChargeDiscoveryInTx: (...args: any[]) => mockCreateJobAndChargeDiscoveryInTx(...args),
  InsufficientCreditsError: class extends Error {
    currentBalance: number;
    required: number;
    constructor(b: number, r: number) {
      super('Insufficient');
      this.currentBalance = b;
      this.required = r;
    }
  },
  PriceChangedError: class extends Error {
    expectedCost: number;
    actualCost: number;
    constructor(expectedCost: number, actualCost: number) {
      super('Price changed');
      this.expectedCost = expectedCost;
      this.actualCost = actualCost;
    }
  },
  refundForStage: vi.fn(),
  refundForRegenerationStage: vi.fn(),
  chargeForStageInTx: vi.fn(),
  chargeForStageWithPriceCasInTx: vi.fn(),
  chargeForRegenerationInTx: vi.fn(),
  chargeForResume: vi.fn(),
  segmentForGateContinue: vi.fn(),
  chargeForSeedIdeaInTx: vi.fn(),
  refundChargeInTx: vi.fn(),
}));

vi.mock('../../services/jobService.js', () => ({
  getJob: vi.fn(),
  updateJobStatus: vi.fn(),
  getJobAsset: vi.fn(),
}));

vi.mock('../../services/catalogService.js', () => ({
  isEntitledUser: (...args: any[]) => mockIsEntitledUser(...args),
}));

// The analyst gate is now hasAnalystAccess = isEntitledUser || the chatAnalystAccess
// grant. These suites drive the entitlement half, so the existing mock stands in for
// the whole gate. Decision tools default ON here so the pre-existing prompt/tool
// assertions keep describing the full-feature owner; the off case has its own tests.
const mockHasDecisionToolsAccess = vi.fn().mockResolvedValue(true);
vi.mock('../../services/featureAccess.js', () => ({
  hasAnalystAccess: (...args: any[]) => mockIsEntitledUser(...args),
  hasDecisionToolsAccess: (...args: any[]) => mockHasDecisionToolsAccess(...args),
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

beforeEach(async () => {
  vi.clearAllMocks();
  mockCreateJobAndChargeDiscoveryInTx.mockImplementation(async (...args: any[]) => ({
    job: { id: 'job-1' },
    transaction: {
      id: 'charge-initial-1',
      stage: args[7] ? 'guided_s1' : 'discovery',
    },
  }));
  mockJobDispatchCreate.mockResolvedValue({ id: 'dispatch-1' });
  mockDeliverDispatchWork.mockResolvedValue(undefined);
  mockJobUpdate.mockResolvedValue({});

  app = express();
  app.use(express.json());
  const { jobsRouter } = await import('../jobs.js');
  app.use('/api/jobs', jobsRouter);
});

describe('POST /api/jobs — chatMode entitlement coercion', () => {
  const validBody = { niche: 'A niche description long enough to pass validation' };

  it('passes chatMode=true through for an entitled user', async () => {
    mockIsEntitledUser.mockResolvedValue(true);

    const response = await request(app)
      .post('/api/jobs')
      .set(authHeaders)
      .send({ ...validBody, chatMode: true });

    expect(response.status).toBe(201);
    expect(mockIsEntitledUser).toHaveBeenCalledWith('user-123');
    expect(mockCreateJobAndChargeDiscoveryInTx).toHaveBeenCalledWith(
      expect.objectContaining({ jobDispatch: expect.any(Object) }),
      'user-123', validBody.niche, undefined, 'interactive', undefined, undefined, true
    );
    expect(mockJobDispatchCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        jobId: 'job-1',
        kind: 'CONTINUE',
        segment: 'guided_s1',
        chargeId: 'charge-initial-1',
        workPayload: expect.objectContaining({
          job_id: 'job-1',
          niche: validBody.niche,
          chat_mode: true,
        }),
      }),
      select: { id: true },
    });
    expect(mockJobUpdate).toHaveBeenCalledWith({
      where: { id: 'job-1' },
      data: { status: 'QUEUED', queuedAt: expect.any(Date) },
    });
    expect(mockPrismaTransaction).toHaveBeenCalledTimes(1);
    expect(mockDeliverDispatchWork).toHaveBeenCalledWith('dispatch-1');
  });

  it('coerces chatMode to false for a non-entitled user requesting it', async () => {
    mockIsEntitledUser.mockResolvedValue(false);

    const response = await request(app)
      .post('/api/jobs')
      .set(authHeaders)
      .send({ ...validBody, chatMode: true });

    expect(response.status).toBe(201);
    expect(mockCreateJobAndChargeDiscoveryInTx).toHaveBeenCalledWith(
      expect.objectContaining({ jobDispatch: expect.any(Object) }),
      'user-123', validBody.niche, undefined, 'interactive', undefined, undefined, false
    );
    expect(mockDeliverDispatchWork).toHaveBeenCalledWith('dispatch-1');
  });

  it('does not call isEntitledUser when chatMode is not requested (skips the entitlement check entirely)', async () => {
    const response = await request(app)
      .post('/api/jobs')
      .set(authHeaders)
      .send(validBody);

    expect(response.status).toBe(201);
    expect(mockIsEntitledUser).not.toHaveBeenCalled();
    expect(mockCreateJobAndChargeDiscoveryInTx).toHaveBeenCalledWith(
      expect.objectContaining({ jobDispatch: expect.any(Object) }),
      'user-123', validBody.niche, undefined, 'interactive', undefined, undefined, false
    );
  });

  it('defaults chatMode to false when omitted', async () => {
    const response = await request(app)
      .post('/api/jobs')
      .set(authHeaders)
      .send(validBody);

    expect(response.status).toBe(201);
    const callArgs = mockCreateJobAndChargeDiscoveryInTx.mock.calls[0];
    expect(callArgs[7]).toBe(false);
  });

  it('does not enqueue when dispatch authorization fails inside the creation transaction', async () => {
    mockJobDispatchCreate.mockRejectedValueOnce(new Error('dispatch write failed'));

    const response = await request(app)
      .post('/api/jobs')
      .set(authHeaders)
      .send(validBody);

    expect(response.status).toBe(500);
    expect(mockPrismaTransaction).toHaveBeenCalledTimes(1);
    expect(mockCreateJobAndChargeDiscoveryInTx).toHaveBeenCalledOnce();
    expect(mockDeliverDispatchWork).not.toHaveBeenCalled();
    expect(mockJobUpdate).not.toHaveBeenCalled();
  });

  it('keeps the authorized queued attempt durable when Redis delivery is ambiguous', async () => {
    mockDeliverDispatchWork.mockRejectedValueOnce(new Error('redis timeout'));

    const response = await request(app)
      .post('/api/jobs')
      .set(authHeaders)
      .send(validBody);

    expect(response.status).toBe(201);
    expect(response.body).toMatchObject({
      status: 'queued',
      operationId: 'dispatch-1',
      deliveryPending: true,
    });
    expect(mockJobDispatchCreate).toHaveBeenCalledOnce();
    expect(mockJobUpdate).toHaveBeenCalledWith({
      where: { id: 'job-1' },
      data: { status: 'QUEUED', queuedAt: expect.any(Date) },
    });
  });
});
