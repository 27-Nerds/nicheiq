import { describe, it, expect, vi, beforeEach } from 'vitest';
import express, { Express } from 'express';
import request from 'supertest';

// These suites exercise route logic, not the decision-tools grant. The grant itself is
// covered in middleware/__tests__/featureAccess.test.ts.
vi.mock('../../middleware/featureAccess.js', () => ({
  requireDecisionToolsAccess: (_req: any, _res: any, next: any) => next(),
}));

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
      // Enqueue compensation is now a GUARDED updateMany scoped to its own dispatch, not an
      // unconditional update() — an ambiguous enqueue error must not stomp a worker that already
      // picked the job up, refund its credit, and wipe its selections.
      updateMany: (...args: any[]) => mockJobUpdateMany(...args),
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

const mockChargeForResume = vi.fn();

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
  chargeForResume: (...args: any[]) => mockChargeForResume(...args),
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

const mockBroadcastProgress = vi.fn();

vi.mock('../../services/progressBroadcastService.js', () => ({
  broadcastProgress: (...args: any[]) => mockBroadcastProgress(...args),
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
const decisionProfile = {
  preset: 'solo_bootstrap',
  weeklyTime: '10_20',
  budget: 'under_1k',
  team: 'solo',
  revenueHorizon: '90_days',
  distributionAdvantages: ['community', 'existing_audience'],
  strengths: 'Domain expertise and direct customer access',
  hardConstraints: 'No regulated data or 24/7 operations',
};
describe('PUT /api/jobs/:jobId/selection-draft', () => {
  const ideas = [
    { solution_name: 'Alpha', idea_id: 'idea-alpha', idea_revision: 2 },
    { solution_name: 'Beta', idea_id: 'idea-beta', idea_revision: 1 },
  ];

  function selectionJob(overrides: Record<string, unknown> = {}) {
    return {
      status: 'AWAITING_SELECTION',
      solutionIdeas: ideas,
      selectionDraft: { schemaVersion: 1, items: [] },
      selectionDraftVersion: 3,
      ...overrides,
    };
  }

  it('persists exact idea revisions without finalizing or dispatching', async () => {
    mockJobFindFirst.mockResolvedValue(selectionJob());

    const response = await request(app)
      .put(`/api/jobs/${jobId}/selection-draft`)
      .set(authHeaders)
      .send({
        expectedVersion: 3,
        items: [{ ideaId: 'idea-alpha', ideaRevision: 2 }],
      });

    expect(response.status).toBe(200);
    expect(response.body.selectionDraft).toEqual({
      version: 4,
      items: [{ ideaId: 'idea-alpha', ideaRevision: 2 }],
    });
    expect(mockJobUpdateMany).toHaveBeenCalledWith({
      where: {
        id: jobId,
        userId: 'user-123',
        status: 'AWAITING_SELECTION',
        selectionDraftVersion: 3,
      },
      data: {
        selectionDraft: {
          schemaVersion: 1,
          items: [{ ideaId: 'idea-alpha', ideaRevision: 2 }],
        },
        selectionDraftVersion: { increment: 1 },
      },
    });
    const updateData = mockJobUpdateMany.mock.calls[0][0].data;
    expect(updateData).not.toHaveProperty('selectedSolutions');
    expect(updateData).not.toHaveProperty('selectedSolutionIds');
    expect(updateData).not.toHaveProperty('status');
    expect(mockEnqueuePhase2Job).not.toHaveBeenCalled();
  });

  it('broadcasts an SSE progress event after a successful save so other tabs refresh', async () => {
    mockJobFindFirst.mockResolvedValue(selectionJob());

    const response = await request(app)
      .put(`/api/jobs/${jobId}/selection-draft`)
      .set(authHeaders)
      .send({
        expectedVersion: 3,
        items: [{ ideaId: 'idea-alpha', ideaRevision: 2 }],
      });

    expect(response.status).toBe(200);
    expect(mockBroadcastProgress).toHaveBeenCalledTimes(1);
    expect(mockBroadcastProgress).toHaveBeenCalledWith(jobId, {
      stage: 0,
      name: 'Selection Draft',
      status: 'completed',
    });
  });

  it('does not broadcast when the save is rejected', async () => {
    mockJobFindFirst
      .mockResolvedValueOnce(selectionJob())
      .mockResolvedValueOnce(selectionJob({ selectionDraftVersion: 4 }));
    mockJobUpdateMany.mockResolvedValueOnce({ count: 0 });

    const response = await request(app)
      .put(`/api/jobs/${jobId}/selection-draft`)
      .set(authHeaders)
      .send({
        expectedVersion: 3,
        items: [{ ideaId: 'idea-alpha', ideaRevision: 2 }],
      });

    expect(response.status).toBe(409);
    expect(mockBroadcastProgress).not.toHaveBeenCalled();
  });

  it('rejects stale revisions before writing the draft', async () => {
    mockJobFindFirst.mockResolvedValue(selectionJob());

    const response = await request(app)
      .put(`/api/jobs/${jobId}/selection-draft`)
      .set(authHeaders)
      .send({
        expectedVersion: 3,
        items: [{ ideaId: 'idea-alpha', ideaRevision: 1 }],
      });

    expect(response.status).toBe(409);
    expect(response.body.code).toBe('SELECTION_DRAFT_STALE_IDEA');
    expect(mockJobUpdateMany).not.toHaveBeenCalled();
  });

  it('returns the latest exact draft after an optimistic concurrency conflict', async () => {
    mockJobFindFirst
      .mockResolvedValueOnce(selectionJob())
      .mockResolvedValueOnce(selectionJob({
        selectionDraftVersion: 4,
        selectionDraft: {
          schemaVersion: 1,
          items: [{ ideaId: 'idea-beta', ideaRevision: 1 }],
        },
      }));
    mockJobUpdateMany.mockResolvedValueOnce({ count: 0 });

    const response = await request(app)
      .put(`/api/jobs/${jobId}/selection-draft`)
      .set(authHeaders)
      .send({
        expectedVersion: 3,
        items: [{ ideaId: 'idea-alpha', ideaRevision: 2 }],
      });

    expect(response.status).toBe(409);
    expect(response.body.code).toBe('SELECTION_DRAFT_CONFLICT');
    expect(response.body.selectionDraft).toEqual({
      version: 4,
      items: [{ ideaId: 'idea-beta', ideaRevision: 1 }],
    });
  });

  it('does not edit a draft after idea selection has ended', async () => {
    mockJobFindFirst.mockResolvedValue(selectionJob({ status: 'QUEUED' }));

    const response = await request(app)
      .put(`/api/jobs/${jobId}/selection-draft`)
      .set(authHeaders)
      .send({ expectedVersion: 3, items: [] });

    expect(response.status).toBe(409);
    expect(response.body.code).toBe('SELECTION_DRAFT_LOCKED');
    expect(response.body.status).toBe('QUEUED');
    expect(mockJobUpdateMany).not.toHaveBeenCalled();
  });
});



beforeEach(async () => {
  vi.clearAllMocks();
  mockJobUpdateMany.mockResolvedValue({ count: 1 });
  mockEnqueuePhase2Job.mockResolvedValue(undefined);
  mockEnqueueRegenerateJob.mockResolvedValue(undefined);

  // Default transaction: execute callback with tx that has job.updateMany
  mockTransaction.mockImplementation(async (callback: any) => {
    const tx = { job: { updateMany: mockJobUpdateMany, update: async () => ({}) }, jobDispatch: { create: async () => ({ id: 'dispatch-test' }), updateMany: async () => ({ count: 1 }) }, };
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
    selectedSolutionIds: [],
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
      'dispatch-test',
    );
  });

  it('accepts stable IDs and resolves the canonical names for the worker', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob({
      solutionIdeas: [
        { name: 'Sol1', idea_id: 'idea_one', idea_revision: 1 },
        { name: 'Sol2', idea_id: 'idea_two', idea_revision: 1 },
      ],
    }));

    const response = await request(app)
      .post(`/api/jobs/${jobId}/select-solution`)
      .set(authHeaders)
      .send({ solutionIds: ['idea_two'] });

    expect(response.status).toBe(200);
    expect(response.body.selectedSolutionIds).toEqual(['idea_two']);
    expect(mockJobUpdateMany).toHaveBeenCalledWith(expect.objectContaining({
      data: expect.objectContaining({
        selectedSolutions: ['Sol2'],
        selectedSolutionIds: ['idea_two'],
      }),
    }));
    expect(mockEnqueuePhase2Job).toHaveBeenCalledWith(
      jobId,
      '/cp/path',
      ['Sol2'],
      undefined,
      'dispatch-test',
    );
  });

  it('rejects an unknown stable ID', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob({
      solutionIdeas: [{ name: 'Sol1', idea_id: 'idea_one', idea_revision: 1 }],
    }));

    const response = await request(app)
      .post(`/api/jobs/${jobId}/select-solution`)
      .set(authHeaders)
      .send({ solutionIds: ['idea_missing'] });

    expect(response.status).toBe(400);
    expect(response.body.missing).toEqual(['idea_missing']);
    expect(mockEnqueuePhase2Job).not.toHaveBeenCalled();
  });

  it('rejects ID and name selections that refer to different ideas', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob({
      solutionIdeas: [
        { name: 'Sol1', idea_id: 'idea_one', idea_revision: 1 },
        { name: 'Sol2', idea_id: 'idea_two', idea_revision: 1 },
      ],
    }));

    const response = await request(app)
      .post(`/api/jobs/${jobId}/select-solution`)
      .set(authHeaders)
      .send({ solutionIds: ['idea_one'], solutionNames: ['Sol2'] });

    expect(response.status).toBe(400);
    expect(response.body.error).toContain('refer to different ideas');
    expect(mockEnqueuePhase2Job).not.toHaveBeenCalled();
  });

  it('rejects duplicate-name identities before charging or enqueueing Phase 2', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob({
      solutionIdeas: [
        { name: 'Signal Desk', idea_id: 'idea_one', idea_revision: 1 },
        { name: '  signal   desk ', idea_id: 'idea_two', idea_revision: 2 },
      ],
    }));

    const response = await request(app)
      .post(`/api/jobs/${jobId}/select-solution`)
      .set(authHeaders)
      .send({ solutionIds: ['idea_one', 'idea_two'] });

    expect(response.status).toBe(409);
    expect(response.body.code).toBe('AMBIGUOUS_PHASE2_SELECTION');
    expect(mockJobUpdateMany).not.toHaveBeenCalled();
    expect(mockEnqueuePhase2Job).not.toHaveBeenCalled();
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

  it('returns a stable conflict when Deep Research was already started', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob({
      status: 'RUNNING_PHASE2',
      selectedSolutions: ['AlreadyPicked'],
    }));

    const response = await request(app)
      .post(`/api/jobs/${jobId}/select-solution`)
      .set(authHeaders)
      .send({ solutionNames: ['Sol1'] });

    expect(response.status).toBe(409);
    expect(response.body).toMatchObject({
      code: 'DEEP_RESEARCH_ALREADY_STARTED',
      status: 'RUNNING_PHASE2',
    });
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

  // Demotion/backfill worker-boundary contract: solutionIdeas as stored is
  // already visible-only (the worker filtered out demoted/absorbed ideas before
  // POSTing). Selection validation only needs to check membership in the stored
  // list — it never needs its own demoted/absorbed filter.
  it('accepts selecting a name present in the stored (visible-only) solutionIdeas', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob({
      solutionIdeas: [
        { name: 'Sol1', candidate_status: 'active' },
        { name: 'Sol2', candidate_status: 'active' },
      ],
    }));

    const response = await request(app)
      .post(`/api/jobs/${jobId}/select-solution`)
      .set(authHeaders)
      .send({ solutionNames: ['Sol1'] });

    expect(response.status).toBe(200);
    expect(response.body.status).toBe('phase2_queued');
  });

  it('rejects a stale demoted idea name that the client held but is absent from stored (visible-only) solutionIdeas', async () => {
    // Stored solutionIdeas represents post-filter state: 'DemotedIdea' was
    // filtered out by the worker before this payload ever reached the backend.
    mockJobFindFirst.mockResolvedValue(makeJob({
      solutionIdeas: [{ name: 'Sol1', candidate_status: 'active' }],
    }));

    const response = await request(app)
      .post(`/api/jobs/${jobId}/select-solution`)
      .set(authHeaders)
      .send({ solutionNames: ['DemotedIdea'] });

    expect(response.status).toBe(400);
    expect(response.body.error).toContain('not found in available ideas');
    expect(response.body.missing).toEqual(['DemotedIdea']);
  });

  it('returns a stable conflict when the job left selection', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob({ status: 'COMPLETED' }));

    const response = await request(app)
      .post(`/api/jobs/${jobId}/select-solution`)
      .set(authHeaders)
      .send({ solutionNames: ['Sol1'] });

    expect(response.status).toBe(409);
    expect(response.body).toMatchObject({
      code: 'DEEP_RESEARCH_NOT_AWAITING_SELECTION',
      status: 'COMPLETED',
    });
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
    expect(response.body.code).toBe('DEEP_RESEARCH_START_CONFLICT');
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
      'test niche',
      undefined, // ideaFocus: not set in this fixture (5th arg added with the idea_focus steer)
      'dispatch-test', // regeneration gets its own dispatch — a stale regen-A failure must not
                       // revert regen-B and refund B's charge
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
    // Compensation is a GUARDED updateMany scoped to this attempt's dispatch — not the old
    // unconditional update(). An enqueue error is ambiguous (the message may have landed and only
    // the ack failed), so an unconditional revert could stomp a REGENERATING worker back to
    // AWAITING_SELECTION and refund a credit for work that is actually running.
    expect(mockJobUpdateMany).toHaveBeenCalledWith({
      where: { id: jobId, status: 'QUEUED', activeDispatchId: 'dispatch-test' },
      data: { status: 'AWAITING_SELECTION', queuedAt: null, activeDispatchId: null },
    });
  });

  it('does NOT refund or revert when the attempt is no longer queued under this dispatch', async () => {
    // The ambiguous-enqueue case: Redis actually accepted the message, a worker picked it up, and
    // only our ack failed. The guarded update matches nothing — and the refund must not fire, or
    // the user gets their credit back for regeneration that is running right now.
    const { refundForRegenerationStage } = await import('../../services/creditService.js');
    mockJobFindFirst.mockResolvedValue(makeJob());
    mockEnqueueRegenerateJob.mockRejectedValue(new Error('ack timeout'));
    mockJobUpdateMany.mockImplementation(async (args: any) =>
      // the flip inside the transaction still succeeds; only the compensating revert misses
      args?.where?.activeDispatchId ? { count: 0 } : { count: 1 },
    );

    const response = await request(app)
      .post(`/api/jobs/${jobId}/regenerate-ideas`)
      .set(authHeaders)
      .send({});

    expect(response.status).toBe(500);
    expect(refundForRegenerationStage).not.toHaveBeenCalled();
  });
});

describe('GET /api/jobs/:jobId/solutions', () => {
  it('returns solution data', async () => {
    mockJobFindFirst.mockResolvedValue({
      solutionIdeas: [{ name: 'Sol1', idea_id: 'idea_persisted', idea_revision: 1 }],
      selectedSolution: 'Sol1',
      selectedSolutions: ['Sol1'],
      selectedSolutionIds: ['idea_persisted'],
      selectionRationale: 'best fit',
      selectionDecisionProfile: decisionProfile,
      selectionDraft: null,
      selectionDraftVersion: 0,
      ideasRegeneratedAt: null,
      status: 'AWAITING_SELECTION',
    });

    const response = await request(app)
      .get(`/api/jobs/${jobId}/solutions`)
      .set(authHeaders);

    expect(response.status).toBe(200);
    expect(response.body).toEqual({
      solutionIdeas: [{
        name: 'Sol1',
        idea_id: 'idea_persisted',
        idea_revision: 1,
      }],
      selectedSolution: 'Sol1',
      selectedSolutions: ['Sol1'],
      selectedSolutionIds: ['idea_persisted'],
      selectionRationale: 'best fit',
      selectionDecisionProfile: decisionProfile,
      selectionDraft: { version: 0, items: [] },
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

describe('PUT /api/jobs/:jobId/decision-profile', () => {
  it('persists owner constraints without touching research scores', async () => {
    mockJobFindFirst.mockResolvedValue({ status: 'AWAITING_SELECTION' });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });

    const response = await request(app)
      .put(`/api/jobs/${jobId}/decision-profile`)
      .set(authHeaders)
      .send(decisionProfile);

    expect(response.status).toBe(200);
    expect(response.body.selectionDecisionProfile).toEqual(decisionProfile);
    expect(mockJobUpdateMany).toHaveBeenCalledWith(
      expect.objectContaining({
        where: { id: jobId, userId: 'user-123', status: 'AWAITING_SELECTION' },
        data: expect.objectContaining({
          selectionDecisionProfile: decisionProfile,
          selectionFounderFit: expect.anything(),
        }),
      }),
    );
  });

  it('rejects malformed or unknown constraints before reading the job', async () => {
    const response = await request(app)
      .put(`/api/jobs/${jobId}/decision-profile`)
      .set(authHeaders)
      .send({ ...decisionProfile, team: 'army' });

    expect(response.status).toBe(400);
    expect(mockJobFindFirst).not.toHaveBeenCalled();
  });

  it('is not editable after the selection stage', async () => {
    mockJobFindFirst.mockResolvedValue({ status: 'COMPLETED' });
    const response = await request(app)
      .put(`/api/jobs/${jobId}/decision-profile`)
      .set(authHeaders)
      .send(decisionProfile);

    expect(response.status).toBe(409);
    expect(mockJobUpdateMany).not.toHaveBeenCalled();
  });
});

describe('POST /api/jobs/:jobId/resume', () => {
  it('re-charges credits via chargeForResume and returns creditCharged', async () => {
    mockJobFindFirst.mockResolvedValue({
      id: jobId,
      userId: 'user-123',
      status: 'FAILED',
      niche: 'test niche',
    });

    mockChargeForResume.mockResolvedValue({ charged: true, amount: 5 });
    mockJobUpdate.mockResolvedValue({});

    const response = await request(app)
      .post(`/api/jobs/${jobId}/resume`)
      .set(authHeaders)
      .send({});

    expect(response.status).toBe(200);
    expect(mockChargeForResume).toHaveBeenCalledWith('user-123', jobId);
    expect(response.body.creditCharged).toBe(5);
  });

  it('resumes without charging when chargeForResume returns charged=false', async () => {
    mockJobFindFirst.mockResolvedValue({
      id: jobId,
      userId: 'user-123',
      status: 'FAILED',
      niche: 'test niche',
    });

    mockChargeForResume.mockResolvedValue({ charged: false, amount: 0 });
    mockJobUpdate.mockResolvedValue({});

    const response = await request(app)
      .post(`/api/jobs/${jobId}/resume`)
      .set(authHeaders)
      .send({});

    expect(response.status).toBe(200);
    expect(response.body.creditCharged).toBe(0);
  });

  it('returns 402 when balance insufficient for resume re-charge', async () => {
    mockJobFindFirst.mockResolvedValue({
      id: jobId,
      userId: 'user-123',
      status: 'FAILED',
      niche: 'test niche',
    });

    const { InsufficientCreditsError } = await import('../../services/creditService.js');
    mockChargeForResume.mockRejectedValue(new InsufficientCreditsError(3, 5));

    const response = await request(app)
      .post(`/api/jobs/${jobId}/resume`)
      .set(authHeaders)
      .send({});

    expect(response.status).toBe(402);
    expect(response.body.code).toBe('INSUFFICIENT_CREDITS');
    expect(response.body.balance).toBe(3);
    expect(response.body.required).toBe(5);
  });
});
