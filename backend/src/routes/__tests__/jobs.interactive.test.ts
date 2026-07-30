import { describe, it, expect, vi, beforeEach } from 'vitest';
import express, { Express } from 'express';
import request from 'supertest';
import { exactSelectionFingerprint } from '../../utils/selectionFingerprint.js';

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
const mockChatMessageCreate = vi.fn();
const mockJobFindUnique = vi.fn();
const mockDispatchFindFirst = vi.fn();
const mockJobDispatchCreate = vi.fn();
const mockChargeForStageWithPriceCasInTx = vi.fn();

vi.mock('../../services/db.js', () => ({
  prisma: {
    job: {
      findFirst: (...args: any[]) => mockJobFindFirst(...args),
      findUnique: (...args: any[]) => mockJobFindUnique(...args),
      update: (...args: any[]) => mockJobUpdate(...args),
      // Enqueue compensation is now a GUARDED updateMany scoped to its own dispatch, not an
      // unconditional update() — an ambiguous enqueue error must not stomp a worker that already
      // picked the job up, refund its credit, and wipe its selections.
      updateMany: (...args: any[]) => mockJobUpdateMany(...args),
    },
    // select-solution replays an existing dispatch for the same clientRequestId before doing
    // any work, so this read happens on every request.
    jobDispatch: {
      findFirst: (...args: any[]) => mockDispatchFindFirst(...args),
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

const mockDeliverDispatchWork = vi.fn();

vi.mock('../../services/queueService.js', () => ({
  enqueueJob: vi.fn(),
  enqueueLandingPageJob: vi.fn(),
  enqueuePhase2Job: (...args: any[]) => mockEnqueuePhase2Job(...args),
  enqueueRegenerateJob: (...args: any[]) => mockEnqueueRegenerateJob(...args),
  enqueueContinueFromGateJob: vi.fn(),
  enqueueSeedIdeaJob: vi.fn(),
  deliverDispatchWork: (...args: any[]) => mockDeliverDispatchWork(...args),
  getQueueStats: vi.fn(),
  getQueueLength: vi.fn(),
}));

const mockChargeForResume = vi.fn();

vi.mock('../../services/creditService.js', () => ({
  createJobAndChargeDiscovery: vi.fn(),
  createJobAndChargeDiscoveryInTx: vi.fn(),
  InsufficientCreditsError: class extends Error {
    currentBalance: number;
    required: number;
    constructor(b: number, r: number) {
      super('Insufficient');
      this.currentBalance = b;
      this.required = r;
    }
  },
  // Every export jobs.ts imports must exist here, including the error CLASSES. A missing one
  // is not a silent no-op: the route's own `catch` does `error instanceof PriceChangedError`,
  // so an absent class throws INSIDE the error handler, no response is ever sent, and the
  // test times out at 5s with the original failure completely hidden.
  PriceChangedError: class extends Error {
    expectedCost: number;
    actualCost: number;
    constructor(e: number, a: number) {
      super('Price changed');
      this.expectedCost = e;
      this.actualCost = a;
    }
  },
  refundForStage: vi.fn(),
  refundForRegenerationStage: vi.fn(),
  refundForSeedIdeaStage: vi.fn(),
  chargeForStageInTx: vi.fn().mockResolvedValue({ cost: 15 }),
  chargeForStageWithPriceCasInTx: (...args: any[]) => mockChargeForStageWithPriceCasInTx(...args),
  chargeForRegenerationInTx: vi.fn().mockResolvedValue({ id: 'charge-regeneration-1' }),
  chargeForSeedIdeaInTx: vi.fn().mockResolvedValue({ id: 'charge-seed-1' }),
  chargeForResume: (...args: any[]) => mockChargeForResume(...args),
  segmentForGateContinue: vi.fn().mockReturnValue('guided_s2'),
  refundChargeInTx: vi.fn(),
  getStageCost: vi.fn().mockResolvedValue(5),
}));

vi.mock('../../services/jobService.js', () => ({
  getJob: vi.fn(),
  updateJobStatus: vi.fn(),
  getJobAsset: vi.fn(),
  cancelJob: vi.fn(),
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
        // titleSnapshot is stamped server-side from the idea at save time, so a later rename
        // or demotion still leaves the shortlist row readable. It is persisted but deliberately
        // not echoed in the response draft above.
        selectionDraft: {
          schemaVersion: 1,
          items: [{ ideaId: 'idea-alpha', ideaRevision: 2, titleSnapshot: 'Alpha' }],
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
  mockDeliverDispatchWork.mockResolvedValue(undefined);
  mockJobDispatchCreate.mockResolvedValue({ id: 'dispatch-test' });
  mockChargeForStageWithPriceCasInTx.mockResolvedValue({
    cost: 15,
    transaction: { id: 'charge-deep-research-1' },
  });
  // No prior dispatch for this clientRequestId — i.e. not an idempotent replay. Both
  // select-solution and regenerate-ideas short-circuit on this read before doing any work.
  mockDispatchFindFirst.mockResolvedValue(null);
  mockJobFindUnique.mockResolvedValue({ selectedSolutionRefs: [] });

  // Default transaction: execute callback with tx that has job.updateMany
  mockTransaction.mockImplementation(async (callback: any) => {
    const tx = {
      job: {
        findFirst: (...args: any[]) => mockJobFindFirst(...args),
        updateMany: mockJobUpdateMany,
        update: async () => ({}),
      },
      jobDispatch: {
        findFirst: (...args: any[]) => mockDispatchFindFirst(...args),
        create: (...args: any[]) => mockJobDispatchCreate(...args),
        updateMany: async () => ({ count: 1 }),
      },
      chatMessage: { create: mockChatMessageCreate },
    };
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
  const defaultIdeas = [
    { name: 'Sol1', idea_id: 'idea_one', idea_revision: 1 },
    { name: 'Sol2', idea_id: 'idea_two', idea_revision: 1 },
  ];
  const defaultRefs = [{ ideaId: 'idea_one', ideaRevision: 1 }];
  const selectPayload = (
    refs = defaultRefs,
    overrides: Record<string, unknown> = {},
  ) => ({
    clientRequestId: '00000000-0000-4000-8000-000000000011',
    expectedCost: 100,
    expectedDraftVersion: 3,
    expectedSelectionFingerprint: exactSelectionFingerprint(refs),
    ...overrides,
  });
  const makeJob = (overrides: Record<string, any> = {}) => ({
    status: 'AWAITING_SELECTION',
    selectedSolutions: [],
    phase1CheckpointPath: '/cp/path',
    solutionIdeas: defaultIdeas,
    selectionDraft: { schemaVersion: 1, items: defaultRefs },
    selectionDraftVersion: 3,
    activeDispatchId: null,
    niche: 'test niche',
    ...overrides,
  });

  it('enqueues phase 2 during AWAITING_SELECTION', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob());

    const response = await request(app)
      .post(`/api/jobs/${jobId}/select-solution`)
      .set(authHeaders)
      .send(selectPayload());

    expect(response.status).toBe(200);
    expect(response.body.status).toBe('phase2_queued');
    expect(mockDeliverDispatchWork).toHaveBeenCalledWith('dispatch-test');
  });

  it('accepts stable IDs and resolves the canonical names for the worker', async () => {
    const selectedRefs = [{ ideaId: 'idea_two', ideaRevision: 1 }];
    mockJobFindFirst.mockResolvedValue(makeJob({
      solutionIdeas: [
        { name: 'Sol1', idea_id: 'idea_one', idea_revision: 1 },
        { name: 'Sol2', idea_id: 'idea_two', idea_revision: 1 },
      ],
      selectionDraft: { schemaVersion: 1, items: selectedRefs },
    }));

    const response = await request(app)
      .post(`/api/jobs/${jobId}/select-solution`)
      .set(authHeaders)
      .send(selectPayload(selectedRefs));

    expect(response.status).toBe(200);
    expect(mockJobUpdateMany).toHaveBeenCalledWith(expect.objectContaining({
      data: expect.objectContaining({
        selectedSolutions: ['Sol2'],
        selectedSolutionIds: ['idea_two'],
      }),
    }));
    expect(mockJobDispatchCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        workPayload: expect.objectContaining({
          selected_solutions: ['Sol2'],
          selected_solution_refs: [
            { idea_id: 'idea_two', idea_revision: 1, solution_name: 'Sol2' },
          ],
          pool_identity_map: [
            { idea_id: 'idea_one', idea_revision: 1, solution_name: 'Sol1' },
            { idea_id: 'idea_two', idea_revision: 1, solution_name: 'Sol2' },
          ],
        }),
      }),
      select: { id: true },
    });
  });

  it('rejects a saved draft whose exact idea revision no longer resolves', async () => {
    const staleRefs = [{ ideaId: 'idea_missing', ideaRevision: 1 }];
    mockJobFindFirst.mockResolvedValue(makeJob({
      solutionIdeas: [{ name: 'Sol1', idea_id: 'idea_one', idea_revision: 1 }],
      selectionDraft: { schemaVersion: 1, items: staleRefs },
    }));

    const response = await request(app)
      .post(`/api/jobs/${jobId}/select-solution`)
      .set(authHeaders)
      .send(selectPayload(staleRefs));

    expect(response.status).toBe(409);
    expect(response.body.code).toBe('STALE_SELECTION_DRAFT');
    expect(mockDeliverDispatchWork).not.toHaveBeenCalled();
  });

  it('rejects a confirmation fingerprint that no longer matches the saved draft', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob());

    const response = await request(app)
      .post(`/api/jobs/${jobId}/select-solution`)
      .set(authHeaders)
      .send(selectPayload(defaultRefs, {
        expectedSelectionFingerprint: exactSelectionFingerprint([
          { ideaId: 'idea_two', ideaRevision: 1 },
        ]),
      }));

    expect(response.status).toBe(409);
    expect(response.body.code).toBe('STALE_SELECTION_DRAFT');
    expect(mockDeliverDispatchWork).not.toHaveBeenCalled();
  });

  it('rejects duplicate-name identities before charging or enqueueing Phase 2', async () => {
    const duplicateRefs = [
      { ideaId: 'idea_one', ideaRevision: 1 },
      { ideaId: 'idea_two', ideaRevision: 2 },
    ];
    mockJobFindFirst.mockResolvedValue(makeJob({
      solutionIdeas: [
        { name: 'Signal Desk', idea_id: 'idea_one', idea_revision: 1 },
        { name: '  signal   desk ', idea_id: 'idea_two', idea_revision: 2 },
      ],
      selectionDraft: { schemaVersion: 1, items: duplicateRefs },
    }));

    const response = await request(app)
      .post(`/api/jobs/${jobId}/select-solution`)
      .set(authHeaders)
      .send(selectPayload(duplicateRefs));

    expect(response.status).toBe(409);
    expect(response.body.code).toBe('AMBIGUOUS_PHASE2_SELECTION');
    expect(mockJobUpdateMany).not.toHaveBeenCalled();
    expect(mockDeliverDispatchWork).not.toHaveBeenCalled();
  });

  it('rejects a selected normalized name that is non-unique anywhere in the full pool', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob({
      solutionIdeas: [
        { name: 'Signal Desk', idea_id: 'idea_one', idea_revision: 1 },
        { name: '  signal   desk ', idea_id: 'idea_two', idea_revision: 2 },
        { name: 'Other Idea', idea_id: 'idea_three', idea_revision: 1 },
      ],
      selectionDraft: {
        schemaVersion: 1,
        items: [{ ideaId: 'idea_one', ideaRevision: 1 }],
      },
    }));

    const response = await request(app)
      .post(`/api/jobs/${jobId}/select-solution`)
      .set(authHeaders)
      .send(selectPayload());

    expect(response.status).toBe(409);
    expect(response.body.code).toBe('AMBIGUOUS_PHASE2_SELECTION');
    expect(mockJobUpdateMany).not.toHaveBeenCalled();
    expect(mockChargeForStageWithPriceCasInTx).not.toHaveBeenCalled();
    expect(mockJobDispatchCreate).not.toHaveBeenCalled();
    expect(mockDeliverDispatchWork).not.toHaveBeenCalled();
  });

  it('guards against double-selection in transaction', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob());

    await request(app)
      .post(`/api/jobs/${jobId}/select-solution`)
      .set(authHeaders)
      .send(selectPayload());

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
      .send(selectPayload());

    expect(response.status).toBe(404);
  });

  it('returns a stable conflict when Deep Research was already started', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob({
      selectedSolutions: ['AlreadyPicked'],
    }));

    const response = await request(app)
      .post(`/api/jobs/${jobId}/select-solution`)
      .set(authHeaders)
      .send(selectPayload());

    expect(response.status).toBe(409);
    expect(response.body.code).toBe('DEEP_RESEARCH_ALREADY_STARTED');
  });

  it('rejects an empty saved shortlist', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob({
      selectionDraft: { schemaVersion: 1, items: [] },
    }));

    const response = await request(app)
      .post(`/api/jobs/${jobId}/select-solution`)
      .set(authHeaders)
      .send(selectPayload());

    expect(response.status).toBe(409);
    expect(response.body.code).toBe('STALE_SELECTION_DRAFT');
  });

  // Demotion/backfill worker-boundary contract: solutionIdeas as stored is
  // already visible-only (the worker filtered out demoted/absorbed ideas before
  // POSTing). Selection validation only needs to check membership in the stored
  // list — it never needs its own demoted/absorbed filter.
  it('accepts selecting a name present in the stored (visible-only) solutionIdeas', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob({
      solutionIdeas: [
        { name: 'Sol1', idea_id: 'idea_one', idea_revision: 1, candidate_status: 'active' },
        { name: 'Sol2', idea_id: 'idea_two', idea_revision: 1, candidate_status: 'active' },
      ],
    }));

    const response = await request(app)
      .post(`/api/jobs/${jobId}/select-solution`)
      .set(authHeaders)
      .send(selectPayload());

    expect(response.status).toBe(200);
    expect(response.body.status).toBe('phase2_queued');
  });

  it('rejects a demoted idea revision that dropped out of the saved shortlist', async () => {
    const demotedRefs = [{ ideaId: 'idea_demoted', ideaRevision: 1 }];
    // Stored solutionIdeas represents post-filter state: 'DemotedIdea' was
    // filtered out by the worker before this payload ever reached the backend.
    mockJobFindFirst.mockResolvedValue(makeJob({
      solutionIdeas: [
        { name: 'Sol1', idea_id: 'idea_one', idea_revision: 1, candidate_status: 'active' },
      ],
      selectionDraft: { schemaVersion: 1, items: demotedRefs },
    }));

    const response = await request(app)
      .post(`/api/jobs/${jobId}/select-solution`)
      .set(authHeaders)
      .send(selectPayload(demotedRefs));

    expect(response.status).toBe(409);
    expect(response.body.code).toBe('STALE_SELECTION_DRAFT');
  });

  it('returns a stable conflict when the job left selection', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob({ status: 'COMPLETED' }));

    const response = await request(app)
      .post(`/api/jobs/${jobId}/select-solution`)
      .set(authHeaders)
      .send(selectPayload());

    expect(response.status).toBe(409);
    expect(response.body.code).toBe('DEEP_RESEARCH_START_CONFLICT');
  });

  it('returns 500 when phase1CheckpointPath is null in AWAITING_SELECTION', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob({ phase1CheckpointPath: null }));

    const response = await request(app)
      .post(`/api/jobs/${jobId}/select-solution`)
      .set(authHeaders)
      .send(selectPayload());

    expect(response.status).toBe(500);
    expect(response.body.error).toContain('Missing checkpoint path');
  });

  it('returns 409 on concurrent race (updateMany count=0)', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob());
    mockJobUpdateMany.mockResolvedValue({ count: 0 });

    const response = await request(app)
      .post(`/api/jobs/${jobId}/select-solution`)
      .set(authHeaders)
      .send(selectPayload());

    expect(response.status).toBe(409);
    expect(response.body.code).toBe('DEEP_RESEARCH_START_CONFLICT');
  });

  it('returns 400 for a missing exact confirmation contract', async () => {
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
      .send(selectPayload());

    expect(response.status).toBe(401);
  });
});

describe('POST /api/jobs/:jobId/regenerate-ideas', () => {
  const regeneratePayload = (overrides: Record<string, unknown> = {}) => ({
    clientRequestId: '00000000-0000-4000-8000-000000000012',
    expectedCost: 25,
    idea_focus: 'auto',
    ...overrides,
  });
  const makeJob = (overrides: Record<string, any> = {}) => ({
    status: 'AWAITING_SELECTION',
    ideasRegeneratedAt: null,
    regenerationCount: 0,
    ideaBatchCompletedCount: 0,
    activeDispatchId: null,
    phase1CheckpointPath: '/cp/path',
    solutionIdeas: [
      { name: 'A', idea_id: 'idea_a', idea_revision: 1 },
      { solution_name: 'B', idea_id: 'idea_b', idea_revision: 1 },
    ],
    niche: 'test niche',
    ...overrides,
  });

  it('transitions AWAITING_SELECTION → QUEUED', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob());

    const response = await request(app)
      .post(`/api/jobs/${jobId}/regenerate-ideas`)
      .set(authHeaders)
      .send(regeneratePayload());

    expect(response.status).toBe(200);
    expect(response.body.status).toBe('queued');
    expect(response.body).toMatchObject({
      operationId: 'dispatch-test',
      batchOrdinal: 1,
      focus: 'auto',
    });
    expect(mockChatMessageCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        role: 'receipt',
        operationId: 'regeneration:dispatch-test:submitted',
        patchJson: expect.objectContaining({
          event: 'regeneration_submitted',
          operationId: 'dispatch-test',
        }),
      }),
    });

    const txCallArgs = mockJobUpdateMany.mock.calls[0][0];
    expect(txCallArgs.where.status).toBe('AWAITING_SELECTION');
    expect(txCallArgs.data.status).toBe('QUEUED');
  });

  it('stores the exact batch work payload and delivers its durable dispatch', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob());

    await request(app)
      .post(`/api/jobs/${jobId}/regenerate-ideas`)
      .set(authHeaders)
      .send(regeneratePayload());

    expect(mockJobDispatchCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        kind: 'REGENERATE',
        batchOrdinal: 1,
        workPayload: expect.objectContaining({
          checkpoint_path: '/cp/path',
          existing_solution_names: ['A', 'B'],
          niche: 'test niche',
          idea_focus: 'auto',
          batch_ordinal: 1,
          pool_identity_map: [
            { idea_id: 'idea_a', idea_revision: 1, solution_name: 'A' },
            { idea_id: 'idea_b', idea_revision: 1, solution_name: 'B' },
          ],
        }),
      }),
      select: { id: true },
    });
    expect(mockDeliverDispatchWork).toHaveBeenCalledWith('dispatch-test');
  });

  it('extracts solution names from both s.name and s.solution_name', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob({
      solutionIdeas: [{ name: 'NameA' }, { solution_name: 'NameB' }, { name: 'NameC' }],
    }));

    await request(app)
      .post(`/api/jobs/${jobId}/regenerate-ideas`)
      .set(authHeaders)
      .send(regeneratePayload());

    const createArgs = mockJobDispatchCreate.mock.calls[0][0];
    expect(createArgs.data.workPayload.existing_solution_names).toEqual([
      'NameA',
      'NameB',
      'NameC',
    ]);
  });

  it('returns 404 for wrong user (job not found)', async () => {
    mockJobFindFirst.mockResolvedValue(null);

    const response = await request(app)
      .post(`/api/jobs/${jobId}/regenerate-ideas`)
      .set(authHeaders)
      .send(regeneratePayload());

    expect(response.status).toBe(404);
  });

  it('returns 400 when not in AWAITING_SELECTION', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob({ status: 'RUNNING' }));

    const response = await request(app)
      .post(`/api/jobs/${jobId}/regenerate-ideas`)
      .set(authHeaders)
      .send(regeneratePayload());

    expect(response.status).toBe(400);
    expect(response.body.error).toContain('only add another idea batch while awaiting selection');
  });

  it('returns 400 when max regenerations reached', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob({ ideaBatchCompletedCount: 10 }));

    const response = await request(app)
      .post(`/api/jobs/${jobId}/regenerate-ideas`)
      .set(authHeaders)
      .send(regeneratePayload());

    expect(response.status).toBe(400);
    expect(response.body.error).toContain('Maximum additional idea batches');
  });

  it('allows regeneration when ideasRegeneratedAt is already set (not first regen)', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob({ ideasRegeneratedAt: new Date(), regenerationCount: 1 }));

    const response = await request(app)
      .post(`/api/jobs/${jobId}/regenerate-ideas`)
      .set(authHeaders)
      .send(regeneratePayload());

    expect(response.status).toBe(200);
    expect(response.body.status).toBe('queued');
  });

  it('returns 500 when phase1CheckpointPath is null', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob({ phase1CheckpointPath: null }));

    const response = await request(app)
      .post(`/api/jobs/${jobId}/regenerate-ideas`)
      .set(authHeaders)
      .send(regeneratePayload());

    expect(response.status).toBe(500);
    expect(response.body.error).toContain('Missing checkpoint path');
  });

  it('returns 409 on concurrent race (updateMany count=0)', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob());
    mockJobUpdateMany.mockResolvedValue({ count: 0 });

    const response = await request(app)
      .post(`/api/jobs/${jobId}/regenerate-ideas`)
      .set(authHeaders)
      .send(regeneratePayload());

    expect(response.status).toBe(409);
  });

  it('keeps an authorized dispatch for outbox retry when immediate delivery fails', async () => {
    const { refundForRegenerationStage } = await import('../../services/creditService.js');
    mockJobFindFirst.mockResolvedValue(makeJob());
    mockDeliverDispatchWork.mockRejectedValue(new Error('Redis unavailable'));

    const response = await request(app)
      .post(`/api/jobs/${jobId}/regenerate-ideas`)
      .set(authHeaders)
      .send(regeneratePayload());

    expect(response.status).toBe(200);
    expect(response.body).toMatchObject({
      operationId: 'dispatch-test',
      deliveryPending: true,
    });
    expect(refundForRegenerationStage).not.toHaveBeenCalled();
    expect(mockJobUpdateMany).toHaveBeenCalledTimes(1);
  });

  it('replays the existing operation for a repeated clientRequestId', async () => {
    mockDispatchFindFirst.mockResolvedValue({
      id: 'dispatch-existing',
      state: 'AUTHORIZED',
      batchOrdinal: 2,
    });

    const response = await request(app)
      .post(`/api/jobs/${jobId}/regenerate-ideas`)
      .set(authHeaders)
      .send(regeneratePayload());

    expect(response.status).toBe(200);
    expect(response.body).toMatchObject({
      operationId: 'dispatch-existing',
      operationState: 'AUTHORIZED',
      batchOrdinal: 2,
      idempotent: true,
    });
    expect(mockJobFindFirst).not.toHaveBeenCalled();
    expect(mockJobDispatchCreate).not.toHaveBeenCalled();
    expect(mockDeliverDispatchWork).not.toHaveBeenCalled();
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
      selectionDraft: {
        version: 0,
        items: [],
        selectionFingerprint: exactSelectionFingerprint([]),
      },
      activeOperation: null,
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
  it('reopens a failed Phase-2 job at selection without charging or dispatching', async () => {
    const savedDraft = {
      schemaVersion: 1,
      items: [{ ideaId: 'idea_one', ideaRevision: 1, titleSnapshot: 'Sol1' }],
    };
    mockJobFindFirst.mockResolvedValue({
      id: jobId,
      userId: 'user-123',
      status: 'FAILED',
      niche: 'test niche',
      jobMode: 'interactive',
      phase1CheckpointPath: '/cp/path',
      selectedSolution: 'Sol1',
      selectedSolutions: ['Sol1'],
      selectedSolutionIds: ['idea_one'],
      selectedSolutionRefs: [{ ideaId: 'idea_one', ideaRevision: 1, snapshotSha256: 'a'.repeat(64) }],
      selectionRationale: 'Best fit',
      selectionDraft: savedDraft,
      selectionDraftVersion: 3,
      activeDispatchId: null,
      errorMessage: 'Worker failed',
      errorStage: 6,
      errorCode: 'SYSTEM_ERROR',
      errorDetails: { userMessage: 'Worker failed' },
    });

    const response = await request(app)
      .post(`/api/jobs/${jobId}/resume`)
      .set(authHeaders)
      .send({});

    expect(response.status).toBe(200);
    expect(response.body).toEqual(expect.objectContaining({
      status: 'AWAITING_SELECTION',
      creditCharged: 0,
      requiresSelectionConfirmation: true,
    }));
    expect(mockJobUpdateMany).toHaveBeenCalledWith({
      where: {
        id: jobId,
        userId: 'user-123',
        status: 'FAILED',
        activeDispatchId: null,
      },
      data: expect.objectContaining({
        status: 'AWAITING_SELECTION',
        selectedSolution: null,
        selectedSolutions: [],
        selectedSolutionIds: [],
        selectionRationale: null,
        errorMessage: null,
        errorStage: null,
        errorCode: null,
      }),
    });
    const resetData = mockJobUpdateMany.mock.calls[0][0].data;
    expect(resetData).toHaveProperty('selectedSolutionRefs');
    expect(resetData).toHaveProperty('errorDetails');
    expect(resetData).not.toHaveProperty('selectionDraft');
    expect(resetData).not.toHaveProperty('selectionDraftVersion');
    expect(mockChargeForResume).not.toHaveBeenCalled();
    expect(mockJobDispatchCreate).not.toHaveBeenCalled();
    expect(mockDeliverDispatchWork).not.toHaveBeenCalled();
  });

  it('atomically re-charges, flips, and opens a tracked dispatch for a legacy discovery resume', async () => {
    mockJobFindFirst.mockResolvedValue({
      id: jobId,
      userId: 'user-123',
      status: 'FAILED',
      niche: 'test niche',
      jobMode: 'interactive',
      entryMode: 'discovery',
      ideaFocus: 'novelty',
      allowedProjectTypes: ['micro_saas'],
      chatMode: false,
      phase1CheckpointPath: null,
      selectedSolutions: [],
      activeDispatchId: null,
    });

    mockChargeForResume.mockResolvedValue({
      charged: true,
      amount: 5,
      transaction: { id: 'resume-charge-1', stage: 'discovery' },
    });

    const response = await request(app)
      .post(`/api/jobs/${jobId}/resume`)
      .set(authHeaders)
      .send({});

    expect(response.status).toBe(200);
    expect(response.body.status).toBe('queued');
    expect(response.body.creditCharged).toBe(5);
    expect(mockJobUpdateMany).toHaveBeenCalledWith(expect.objectContaining({
      where: {
        id: jobId,
        userId: 'user-123',
        status: 'FAILED',
        activeDispatchId: null,
      },
      data: expect.objectContaining({ status: 'QUEUED' }),
    }));
    expect(mockChargeForResume).toHaveBeenCalledWith(
      'user-123',
      jobId,
      expect.any(Object),
    );
    expect(mockJobDispatchCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        kind: 'CONTINUE',
        segment: 'discovery',
        chargeId: 'resume-charge-1',
        workPayload: expect.objectContaining({
          job_id: jobId,
          niche: 'test niche',
          user_id: 'user-123',
          allowed_project_types: ['micro_saas'],
          resume: true,
          job_mode: 'interactive',
          entry_mode: 'discovery',
          idea_focus: 'novelty',
          chat_mode: false,
        }),
      }),
      select: { id: true },
    });
    expect(mockDeliverDispatchWork).toHaveBeenCalledWith('dispatch-test');
  });

  it('retries failed catalog Deep Research from its immutable seed payload', async () => {
    mockJobFindFirst.mockResolvedValue({
      id: jobId,
      userId: 'user-123',
      status: 'FAILED',
      niche: 'catalog niche',
      jobMode: 'interactive',
      entryMode: 'deep_idea',
      selectedSolutions: ['Catalog idea'],
      selectedSolutionIds: [],
      selectedSolutionRefs: null,
      phase1CheckpointPath: null,
      activeDispatchId: null,
    });
    mockDispatchFindFirst.mockResolvedValue({
      workPayload: {
        job_id: jobId,
        task_type: 'catalog_deep_research',
        idea_seed: { solution_name: 'Catalog idea' },
        niche: 'catalog niche',
        user_id: 'user-123',
        created_at: '2026-01-01T00:00:00.000Z',
      },
    });
    mockChargeForStageWithPriceCasInTx.mockResolvedValue({
      cost: 100,
      transaction: { id: 'resume-charge-2', stage: 'deep_research' },
    });

    const response = await request(app)
      .post(`/api/jobs/${jobId}/resume`)
      .set(authHeaders)
      .send({ expectedCost: 100 });

    expect(response.status).toBe(200);
    expect(response.body).toEqual(expect.objectContaining({
      status: 'queued',
      creditCharged: 100,
      operationId: 'dispatch-test',
    }));
    expect(mockDispatchFindFirst).toHaveBeenCalledWith({
      where: { jobId, kind: 'DEEP_RESEARCH' },
      orderBy: { createdAt: 'desc' },
      select: { workPayload: true },
    });
    expect(mockChargeForStageWithPriceCasInTx).toHaveBeenCalledWith(
      expect.any(Object),
      'user-123',
      jobId,
      'deep_research',
      'deep_research',
      'catalog niche',
      100,
    );
    expect(mockChargeForResume).not.toHaveBeenCalled();
    expect(mockJobDispatchCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        kind: 'DEEP_RESEARCH',
        segment: 'deep_research',
        chargeId: 'resume-charge-2',
        workPayload: expect.objectContaining({
          job_id: jobId,
          task_type: 'catalog_deep_research',
          idea_seed: { solution_name: 'Catalog idea' },
          niche: 'catalog niche',
          user_id: 'user-123',
        }),
      }),
      select: { id: true },
    });
    expect(mockDeliverDispatchWork).toHaveBeenCalledWith('dispatch-test');
  });

  it('does not charge or queue a catalog retry when the original seed payload is missing', async () => {
    mockJobFindFirst.mockResolvedValue({
      id: jobId,
      userId: 'user-123',
      status: 'FAILED',
      niche: 'catalog niche',
      jobMode: 'interactive',
      entryMode: 'deep_idea',
      selectedSolutions: ['Catalog idea'],
      selectedSolutionIds: [],
      selectedSolutionRefs: null,
      phase1CheckpointPath: null,
      activeDispatchId: null,
    });
    mockDispatchFindFirst.mockResolvedValue({ workPayload: null });

    const response = await request(app)
      .post(`/api/jobs/${jobId}/resume`)
      .set(authHeaders)
      .send({ expectedCost: 100 });

    expect(response.status).toBe(409);
    expect(response.body.code).toBe('RESUME_CATALOG_PAYLOAD_MISSING');
    expect(mockChargeForResume).not.toHaveBeenCalled();
    expect(mockJobDispatchCreate).not.toHaveBeenCalled();
    expect(mockDeliverDispatchWork).not.toHaveBeenCalled();
  });

  it('requires an explicit current-price confirmation for a catalog retry', async () => {
    mockJobFindFirst.mockResolvedValue({
      id: jobId,
      userId: 'user-123',
      status: 'FAILED',
      niche: 'catalog niche',
      jobMode: 'interactive',
      entryMode: 'deep_idea',
      selectedSolutions: ['Catalog idea'],
      selectedSolutionIds: [],
      selectedSolutionRefs: null,
      phase1CheckpointPath: null,
      activeDispatchId: null,
    });

    const response = await request(app)
      .post(`/api/jobs/${jobId}/resume`)
      .set(authHeaders)
      .send({});

    expect(response.status).toBe(400);
    expect(response.body.code).toBe('EXPECTED_COST_REQUIRED');
    expect(mockDispatchFindFirst).not.toHaveBeenCalled();
    expect(mockChargeForResume).not.toHaveBeenCalled();
    expect(mockChargeForStageWithPriceCasInTx).not.toHaveBeenCalled();
    expect(mockJobDispatchCreate).not.toHaveBeenCalled();
  });

  it('does not charge or open a dispatch when the legacy resume CAS loses a race', async () => {
    mockJobFindFirst.mockResolvedValue({
      id: jobId,
      userId: 'user-123',
      status: 'FAILED',
      niche: 'test niche',
      selectedSolutions: [],
      activeDispatchId: null,
    });
    mockJobUpdateMany.mockResolvedValue({ count: 0 });

    const response = await request(app)
      .post(`/api/jobs/${jobId}/resume`)
      .set(authHeaders)
      .send({});

    expect(response.status).toBe(409);
    expect(response.body.code).toBe('RESUME_CONFLICT');
    expect(mockChargeForResume).not.toHaveBeenCalled();
    expect(mockJobDispatchCreate).not.toHaveBeenCalled();
    expect(mockDeliverDispatchWork).not.toHaveBeenCalled();
  });

  it('returns 402 when balance insufficient for resume re-charge', async () => {
    mockJobFindFirst.mockResolvedValue({
      id: jobId,
      userId: 'user-123',
      status: 'FAILED',
      niche: 'test niche',
      selectedSolutions: [],
      activeDispatchId: null,
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
    expect(mockJobDispatchCreate).not.toHaveBeenCalled();
    expect(mockDeliverDispatchWork).not.toHaveBeenCalled();
  });
});
