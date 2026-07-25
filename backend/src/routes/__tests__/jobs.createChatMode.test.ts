import { describe, it, expect, vi, beforeEach } from 'vitest';
import express, { Express } from 'express';
import request from 'supertest';

// ============================================
// Mock dependencies
// ============================================
const mockCreateJobAndChargeDiscovery = vi.fn();
const mockEnqueueJob = vi.fn();
const mockJobUpdate = vi.fn();
const mockIsEntitledUser = vi.fn();

vi.mock('../../services/db.js', () => {
  const client: any = {
    job: {
      update: (...args: any[]) => mockJobUpdate(...args),
      updateMany: vi.fn(async () => ({ count: 1 })),
    },
    // Job creation now opens a dispatch, so the initial run has an identity a worker callback can
    // be matched against — previously it was the one path with none at all.
    jobDispatch: { create: vi.fn(async () => ({ id: 'dispatch-1' })) },
  };
  client.$transaction = (arg: any) => (typeof arg === 'function' ? arg(client) : Promise.all(arg));
  return { prisma: client };
});

vi.mock('../../services/queueService.js', () => ({
  enqueueJob: (...args: any[]) => mockEnqueueJob(...args),
  enqueueLandingPageJob: vi.fn(),
  enqueuePhase2Job: vi.fn(),
  enqueueRegenerateJob: vi.fn(),
  enqueueContinueFromGateJob: vi.fn(),
  getQueueStats: vi.fn(),
  getQueueLength: vi.fn(),
  removeJobFromQueue: vi.fn(),
}));

vi.mock('../../services/creditService.js', () => ({
  createJobAndChargeDiscovery: (...args: any[]) => mockCreateJobAndChargeDiscovery(...args),
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
  chargeForStageInTx: vi.fn(),
  chargeForRegenerationInTx: vi.fn(),
  chargeForResume: vi.fn(),
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
  mockCreateJobAndChargeDiscovery.mockResolvedValue({ job: { id: 'job-1' } });
  mockEnqueueJob.mockResolvedValue(undefined);
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
    expect(mockCreateJobAndChargeDiscovery).toHaveBeenCalledWith(
      'user-123', validBody.niche, undefined, 'interactive', undefined, undefined, true
    );
    expect(mockEnqueueJob).toHaveBeenCalledWith(
      // Trailing arg: the dispatch opened at creation. The initial run used to be the only path
      // with no identity, so a duplicate delivery could put two workers on the same fresh job.
      'job-1', validBody.niche, 'user-123', undefined, false, 'interactive', undefined, undefined, true, 'dispatch-1'
    );
  });

  it('coerces chatMode to false for a non-entitled user requesting it', async () => {
    mockIsEntitledUser.mockResolvedValue(false);

    const response = await request(app)
      .post('/api/jobs')
      .set(authHeaders)
      .send({ ...validBody, chatMode: true });

    expect(response.status).toBe(201);
    expect(mockCreateJobAndChargeDiscovery).toHaveBeenCalledWith(
      'user-123', validBody.niche, undefined, 'interactive', undefined, undefined, false
    );
    expect(mockEnqueueJob).toHaveBeenCalledWith(
      'job-1', validBody.niche, 'user-123', undefined, false, 'interactive', undefined, undefined, false, 'dispatch-1'
    );
  });

  it('does not call isEntitledUser when chatMode is not requested (skips the entitlement check entirely)', async () => {
    const response = await request(app)
      .post('/api/jobs')
      .set(authHeaders)
      .send(validBody);

    expect(response.status).toBe(201);
    expect(mockIsEntitledUser).not.toHaveBeenCalled();
    expect(mockCreateJobAndChargeDiscovery).toHaveBeenCalledWith(
      'user-123', validBody.niche, undefined, 'interactive', undefined, undefined, false
    );
  });

  it('defaults chatMode to false when omitted', async () => {
    const response = await request(app)
      .post('/api/jobs')
      .set(authHeaders)
      .send(validBody);

    expect(response.status).toBe(201);
    const callArgs = mockCreateJobAndChargeDiscovery.mock.calls[0];
    expect(callArgs[6]).toBe(false);
  });
});
