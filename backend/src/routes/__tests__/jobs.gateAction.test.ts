import { describe, it, expect, vi, beforeEach } from 'vitest';
import express, { Express } from 'express';
import request from 'supertest';

// ============================================
// Mock dependencies
// ============================================
const mockJobFindFirst = vi.fn();
// Top-level prisma.job.updateMany — used by the compensating revert (finding 7: conditional
// on status=QUEUED, distinct from the tx-scoped mockJobUpdateMany below).
const mockJobUpdateManyCompensate = vi.fn();
const mockJobUpdateMany = vi.fn();
const mockTransaction = vi.fn();
const mockDispatchCreate = vi.fn();
// Durable ledger receipts (ledgerEvents.ts): apply_stay writes a 'gate_patch_submitted'
// ChatMessage inside the flip transaction, and the compensating revert deletes it.
const mockChatMessageCreate = vi.fn();
const mockChatMessageDelete = vi.fn();
// Enqueue-failure compensation (bug fix): the dispatch must be settled (so it doesn't sit
// AUTHORIZED forever with a live CAS a retry's own charge would collide with) whenever the
// revert actually happened — top-level, since the revert itself is not transaction-scoped.
const mockDispatchUpdateManyCompensate = vi.fn();

vi.mock('../../services/db.js', () => ({
  prisma: {
    job: {
      findFirst: (...args: any[]) => mockJobFindFirst(...args),
      updateMany: (...args: any[]) => mockJobUpdateManyCompensate(...args),
    },
    jobDispatch: {
      updateMany: (...args: any[]) => mockDispatchUpdateManyCompensate(...args),
    },
    chatMessage: {
      delete: (...args: any[]) => mockChatMessageDelete(...args),
    },
    $transaction: (...args: any[]) => mockTransaction(...args),
  },
}));

const mockDeliverDispatchWork = vi.fn();

vi.mock('../../services/queueService.js', () => ({
  enqueueJob: vi.fn(),
  enqueueLandingPageJob: vi.fn(),
  enqueuePhase2Job: vi.fn(),
  enqueueRegenerateJob: vi.fn(),
  enqueueContinueFromGateJob: vi.fn(),
  deliverDispatchWork: (...args: any[]) => mockDeliverDispatchWork(...args),
  getQueueStats: vi.fn(),
  getQueueLength: vi.fn(),
  removeJobFromQueue: vi.fn(),
}));

// Segment-billing mocks (guided-gate charging) — kept as top-level fns so individual
// tests can control cost/segment behavior and assert on charge calls.
const mockChargeForStageInTx = vi.fn();
const mockChargeForStageWithPriceCasInTx = vi.fn();
const mockSegmentForGateContinue = vi.fn();

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

const mockRefundForStage = vi.fn();

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
  PriceChangedError: MockPriceChangedError,
  refundForStage: (...args: any[]) => mockRefundForStage(...args),
  refundForRegenerationStage: vi.fn(),
  chargeForStageInTx: (...args: any[]) => mockChargeForStageInTx(...args),
  chargeForStageWithPriceCasInTx: (...args: any[]) => mockChargeForStageWithPriceCasInTx(...args),
  chargeForRegenerationInTx: vi.fn(),
  chargeForResume: vi.fn(),
  segmentForGateContinue: (...args: any[]) => mockSegmentForGateContinue(...args),
  chargeForSeedIdeaInTx: vi.fn(),
  refundChargeInTx: vi.fn(),
}));

vi.mock('../../services/jobService.js', () => ({
  getJob: vi.fn(),
  updateJobStatus: vi.fn(),
  getJobAsset: vi.fn(),
}));

const mockIsEntitledUser = vi.fn();

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
const jobId = '00000000-0000-0000-0000-000000000001';

beforeEach(async () => {
  vi.clearAllMocks();
  mockJobUpdateMany.mockResolvedValue({ count: 1 });
  mockJobUpdateManyCompensate.mockResolvedValue({ count: 1 });
  mockDispatchUpdateManyCompensate.mockResolvedValue({ count: 1 });
  mockRefundForStage.mockResolvedValue({ amount: 5 });
  mockDeliverDispatchWork.mockResolvedValue(undefined);
  mockIsEntitledUser.mockResolvedValue(true);

  // Default transaction: execute callback with a tx that has job.updateMany, returning
  // whatever the callback returns (the route reads `result.count` off it itself).
  mockChatMessageCreate.mockResolvedValue({ id: 'receipt-1' });
  mockChatMessageDelete.mockResolvedValue({});
  mockSegmentForGateContinue.mockImplementation((gateStage: 1 | 4) =>
    gateStage === 1 ? 'guided_s2_4' : 'guided_s5'
  );
  mockChargeForStageInTx.mockResolvedValue({ cost: 5, transaction: { id: 'txn-1' } });
  mockChargeForStageWithPriceCasInTx.mockResolvedValue({ cost: 5, transaction: { id: 'txn-1' } });
  mockDispatchCreate.mockResolvedValue({ id: 'dispatch-test' });
  mockTransaction.mockImplementation(async (callback: any) => {
    const tx = {
      job: { updateMany: mockJobUpdateMany, update: async () => ({}) },
      jobDispatch: { create: mockDispatchCreate, updateMany: async () => ({ count: 1 }) },
      chatMessage: { create: mockChatMessageCreate },
    };
    return callback(tx);
  });

  app = express();
  app.use(express.json());
  const { jobsRouter } = await import('../jobs.js');
  app.use('/api/jobs', jobsRouter);
});

describe('POST /api/jobs/:jobId/gate-action', () => {
  const g2Artifact = {
    type: 'audience_mapping_gate',
    pains: [{ title: 'Pain A', severity: 0.8 }, { title: 'Pain B', severity: 0.5 }],
    segments: [{ segment_name: 'Solo founders' }, { segment_name: 'Agencies' }],
  };

  const makeJob = (overrides: Record<string, any> = {}) => ({
    status: 'AWAITING_GATE',
    gateStage: 1,
    gateArtifact: { type: 'niche_validation', niche_description: 'x' },
    gateApplyCount: 0,
    phase1CheckpointPath: '/cp/path',
    ...overrides,
  });

  // ── Gate-instance guard ──
  describe('gate-instance guard', () => {
    it('returns 404 for wrong user (job not found)', async () => {
      mockJobFindFirst.mockResolvedValue(null);

      const response = await request(app)
        .post(`/api/jobs/${jobId}/gate-action`)
        .set(authHeaders)
        .send({ action: 'continue', gateStage: 1 });

      expect(response.status).toBe(404);
    });

    it('returns 402 when the user is not entitled (subscription lapsed post job-create)', async () => {
      mockJobFindFirst.mockResolvedValue(makeJob());
      mockIsEntitledUser.mockResolvedValue(false);

      const response = await request(app)
        .post(`/api/jobs/${jobId}/gate-action`)
        .set(authHeaders)
        .send({ action: 'continue', gateStage: 1 });

      expect(response.status).toBe(402);
      expect(response.body.code).toBe('NOT_ENTITLED');
      expect(mockJobUpdateMany).not.toHaveBeenCalled();
    });

    it('returns 409 when job is not AWAITING_GATE', async () => {
      mockJobFindFirst.mockResolvedValue(makeJob({ status: 'RUNNING' }));

      const response = await request(app)
        .post(`/api/jobs/${jobId}/gate-action`)
        .set(authHeaders)
        .send({ action: 'continue', gateStage: 1 });

      expect(response.status).toBe(409);
      expect(response.body.status).toBe('RUNNING');
    });

    it('returns 409 when the requested gateStage does not match the job\'s current gate (stale tab)', async () => {
      mockJobFindFirst.mockResolvedValue(makeJob({ gateStage: 4 }));

      const response = await request(app)
        .post(`/api/jobs/${jobId}/gate-action`)
        .set(authHeaders)
        .send({ action: 'continue', gateStage: 1 });

      expect(response.status).toBe(409);
      expect(response.body.gateStage).toBe(4);
    });

    it('returns 409 on optimistic-flip race (updateMany count=0)', async () => {
      mockJobFindFirst.mockResolvedValue(makeJob());
      mockJobUpdateMany.mockResolvedValue({ count: 0 });

      const response = await request(app)
        .post(`/api/jobs/${jobId}/gate-action`)
        .set(authHeaders)
        .send({ action: 'continue', gateStage: 1 });

      expect(response.status).toBe(409);
    });
  });

  // ── action='continue' ──
  describe('action=continue', () => {
    it('flips AWAITING_GATE -> QUEUED and clears gateReachedAt', async () => {
      mockJobFindFirst.mockResolvedValue(makeJob());

      const response = await request(app)
        .post(`/api/jobs/${jobId}/gate-action`)
        .set(authHeaders)
        .send({ action: 'continue', gateStage: 1 });

      expect(response.status).toBe(200);
      expect(response.body.status).toBe('queued');
      const callArgs = mockJobUpdateMany.mock.calls[0][0];
      expect(callArgs.where).toEqual({ id: jobId, status: 'AWAITING_GATE', gateStage: 1 });
      expect(callArgs.data.status).toBe('QUEUED');
      expect(callArgs.data.gateReachedAt).toBeNull();
      expect(callArgs.data.gateApplyCount).toBeUndefined();
    });

    it('persists the exact continue_from_gate payload and delivers its dispatch', async () => {
      mockJobFindFirst.mockResolvedValue(makeJob());

      const response = await request(app)
        .post(`/api/jobs/${jobId}/gate-action`)
        .set(authHeaders)
        .send({ action: 'continue', gateStage: 1 });

      expect(mockDispatchCreate).toHaveBeenCalledWith(
        expect.objectContaining({
          data: expect.objectContaining({
            jobId,
            kind: 'CONTINUE',
            workPayload: expect.objectContaining({
              job_id: jobId,
              checkpoint_path: '/cp/path',
              gate_stage: 1,
              mode: 'continue',
              task_type: 'continue_from_gate',
            }),
          }),
        }),
      );
      expect(mockDeliverDispatchWork).toHaveBeenCalledWith('dispatch-test');
      expect(response.body).toMatchObject({
        operationId: 'dispatch-test',
        deliveryPending: false,
      });
    });

    it('persists an optional validated patch in the immutable work payload', async () => {
      mockJobFindFirst.mockResolvedValue(makeJob());

      const response = await request(app)
        .post(`/api/jobs/${jobId}/gate-action`)
        .set(authHeaders)
        .send({ action: 'continue', gateStage: 1, patch: { niche_description: 'Edited' } });

      expect(response.status).toBe(200);
      expect(mockDispatchCreate).toHaveBeenCalledWith(
        expect.objectContaining({
          data: expect.objectContaining({
            workPayload: expect.objectContaining({
              patch: { niche_description: 'Edited' },
            }),
          }),
        }),
      );
    });

    it('returns 500 when phase1CheckpointPath is missing', async () => {
      mockJobFindFirst.mockResolvedValue(makeJob({ phase1CheckpointPath: null }));

      const response = await request(app)
        .post(`/api/jobs/${jobId}/gate-action`)
        .set(authHeaders)
        .send({ action: 'continue', gateStage: 1 });

      expect(response.status).toBe(500);
    });

    it('keeps the authorized attempt durable when Redis delivery is ambiguous', async () => {
      mockJobFindFirst.mockResolvedValue(makeJob());
      mockDeliverDispatchWork.mockRejectedValue(new Error('Redis unavailable'));

      const response = await request(app)
        .post(`/api/jobs/${jobId}/gate-action`)
        .set(authHeaders)
        .send({ action: 'continue', gateStage: 1 });

      expect(response.status).toBe(200);
      expect(response.body).toMatchObject({
        status: 'queued',
        operationId: 'dispatch-test',
        deliveryPending: true,
      });
      expect(mockJobUpdateManyCompensate).not.toHaveBeenCalled();
      expect(mockDispatchUpdateManyCompensate).not.toHaveBeenCalled();
      expect(mockRefundForStage).not.toHaveBeenCalled();
    });

    it('keeps a priced segment charge linked to the durable dispatch on delivery failure', async () => {
      mockJobFindFirst.mockResolvedValue(makeJob({
        billingModel: 'GUIDED_SEGMENTS_V1',
        niche: 'test niche',
      }));
      mockDeliverDispatchWork.mockRejectedValue(new Error('Redis unavailable'));

      const response = await request(app)
        .post(`/api/jobs/${jobId}/gate-action`)
        .set(authHeaders)
        .send({ action: 'continue', gateStage: 1, expectedCost: 5 });

      expect(response.status).toBe(200);
      expect(mockDispatchCreate).toHaveBeenCalledWith(
        expect.objectContaining({
          data: expect.objectContaining({
            segment: 'guided_s2_4',
            chargeId: 'txn-1',
            state: 'AUTHORIZED',
          }),
        }),
      );
      expect(mockRefundForStage).not.toHaveBeenCalled();
    });
  });

  // ── action='apply_stay' ──
  describe('action=apply_stay', () => {
    it('requires a patch', async () => {
      mockJobFindFirst.mockResolvedValue(makeJob());

      const response = await request(app)
        .post(`/api/jobs/${jobId}/gate-action`)
        .set(authHeaders)
        .send({ action: 'apply_stay', gateStage: 1 });

      expect(response.status).toBe(400);
    });

    it('increments gateApplyCount on the optimistic flip', async () => {
      mockJobFindFirst.mockResolvedValue(makeJob());

      await request(app)
        .post(`/api/jobs/${jobId}/gate-action`)
        .set(authHeaders)
        .send({ action: 'apply_stay', gateStage: 1, patch: { niche_description: 'Edited' } });

      const callArgs = mockJobUpdateMany.mock.calls[0][0];
      expect(callArgs.data.gateApplyCount).toEqual({ increment: 1 });
    });

    it('is capped at 5 applies per gate', async () => {
      mockJobFindFirst.mockResolvedValue(makeJob({ gateApplyCount: 5 }));

      const response = await request(app)
        .post(`/api/jobs/${jobId}/gate-action`)
        .set(authHeaders)
        .send({ action: 'apply_stay', gateStage: 1, patch: { niche_description: 'Edited' } });

      expect(response.status).toBe(400);
      expect(response.body.error).toContain('Maximum gate patch applies');
      expect(mockJobUpdateMany).not.toHaveBeenCalled();
    });

    it('allows the 5th apply (count=4 -> becomes 5)', async () => {
      mockJobFindFirst.mockResolvedValue(makeJob({ gateApplyCount: 4 }));

      const response = await request(app)
        .post(`/api/jobs/${jobId}/gate-action`)
        .set(authHeaders)
        .send({ action: 'apply_stay', gateStage: 1, patch: { niche_description: 'Edited' } });

      expect(response.status).toBe(200);
    });

    it('keeps the apply receipt and increment durable when delivery is pending', async () => {
      mockJobFindFirst.mockResolvedValue(makeJob());
      mockDeliverDispatchWork.mockRejectedValue(new Error('Redis unavailable'));

      const response = await request(app)
        .post(`/api/jobs/${jobId}/gate-action`)
        .set(authHeaders)
        .send({ action: 'apply_stay', gateStage: 1, patch: { niche_description: 'Edited' } });

      expect(response.status).toBe(200);
      expect(response.body.deliveryPending).toBe(true);
      expect(mockJobUpdateManyCompensate).not.toHaveBeenCalled();
      expect(mockChatMessageDelete).not.toHaveBeenCalled();
      expect(mockChatMessageCreate).toHaveBeenCalledTimes(1);
    });
  });

  // ── Zod whitelist + gateArtifact cross-check (G2) ──
  describe('patch validation', () => {
    it('rejects an unknown field in a G1 patch (400)', async () => {
      mockJobFindFirst.mockResolvedValue(makeJob({ gateStage: 1 }));

      const response = await request(app)
        .post(`/api/jobs/${jobId}/gate-action`)
        .set(authHeaders)
        .send({ action: 'continue', gateStage: 1, patch: { anchor_entities: ['hack'] } });

      expect(response.status).toBe(400);
      expect(mockDeliverDispatchWork).not.toHaveBeenCalled();
    });

    it('rejects an invalid segment_emphasis enum value in a G2 patch (400)', async () => {
      mockJobFindFirst.mockResolvedValue(makeJob({ gateStage: 4, gateArtifact: g2Artifact }));

      const response = await request(app)
        .post(`/api/jobs/${jobId}/gate-action`)
        .set(authHeaders)
        .send({
          action: 'continue', gateStage: 4,
          patch: { segment_emphasis: { 'Solo founders': 'medium' } },
        });

      expect(response.status).toBe(400);
    });

    it('accepts a valid G2 patch that references names present in the gateArtifact', async () => {
      mockJobFindFirst.mockResolvedValue(makeJob({ gateStage: 4, gateArtifact: g2Artifact }));

      const response = await request(app)
        .post(`/api/jobs/${jobId}/gate-action`)
        .set(authHeaders)
        .send({
          action: 'continue', gateStage: 4,
          patch: {
            excluded_segments: ['Agencies'],
            pain_scope: { excluded_titles: ['Pain B'], pinned_titles: ['Pain A'] },
          },
        });

      expect(response.status).toBe(200);
    });

    it('cross-check 400s when excluded_segments references a segment not in the gateArtifact', async () => {
      mockJobFindFirst.mockResolvedValue(makeJob({ gateStage: 4, gateArtifact: g2Artifact }));

      const response = await request(app)
        .post(`/api/jobs/${jobId}/gate-action`)
        .set(authHeaders)
        .send({
          action: 'continue', gateStage: 4,
          patch: { excluded_segments: ['Nonexistent Segment'] },
        });

      expect(response.status).toBe(400);
      expect(response.body.error).toContain('unknown segment');
      expect(mockDeliverDispatchWork).not.toHaveBeenCalled();
    });

    it('cross-check 400s when primary_target_segment references a segment not in the gateArtifact', async () => {
      mockJobFindFirst.mockResolvedValue(makeJob({ gateStage: 4, gateArtifact: g2Artifact }));

      const response = await request(app)
        .post(`/api/jobs/${jobId}/gate-action`)
        .set(authHeaders)
        .send({
          action: 'continue', gateStage: 4,
          patch: { primary_target_segment: 'Nonexistent Segment' },
        });

      expect(response.status).toBe(400);
    });

    it('cross-check 400s when pain_scope references a title not in the gateArtifact', async () => {
      mockJobFindFirst.mockResolvedValue(makeJob({ gateStage: 4, gateArtifact: g2Artifact }));

      const response = await request(app)
        .post(`/api/jobs/${jobId}/gate-action`)
        .set(authHeaders)
        .send({
          action: 'continue', gateStage: 4,
          patch: { pain_scope: { excluded_titles: ['No such pain'], pinned_titles: [] } },
        });

      expect(response.status).toBe(400);
      expect(response.body.error).toContain('unknown pain title');
    });

    it('G1 patch cross-check is a no-op (shape-only) even with an artifact present', async () => {
      mockJobFindFirst.mockResolvedValue(makeJob({ gateStage: 1 }));

      const response = await request(app)
        .post(`/api/jobs/${jobId}/gate-action`)
        .set(authHeaders)
        .send({ action: 'continue', gateStage: 1, patch: { niche_description: 'Anything goes here' } });

      expect(response.status).toBe(200);
    });
  });

  // ── Segment billing (guided-gate charging) ──
  describe('segment billing', () => {
    it('a guided Continue at G1 charges the stages-2-4 segment with the confirmed price, via the hardened CAS helper', async () => {
      mockJobFindFirst.mockResolvedValue(makeJob({ billingModel: 'GUIDED_SEGMENTS_V1', niche: 'test niche' }));

      const response = await request(app)
        .post(`/api/jobs/${jobId}/gate-action`)
        .set(authHeaders)
        .send({ action: 'continue', gateStage: 1, expectedCost: 5 });

      expect(response.status).toBe(200);
      // priceStage and ledgerStage are the SAME for guided (no numbering needed — one Continue
      // per gate) — both 'guided_s2_4'. chargeForStageInTx (the un-CASed helper) must NOT be used
      // for this path anymore.
      expect(mockChargeForStageWithPriceCasInTx).toHaveBeenCalledWith(
        expect.anything(), 'user-123', jobId, 'guided_s2_4', 'guided_s2_4', 'test niche', 5,
      );
      expect(mockChargeForStageInTx).not.toHaveBeenCalled();
    });

    // THE MIGRATION TEST — a job created before segment billing is not charged again.
    // This is the test that stops every in-flight customer being billed twice: a job whose
    // billingModel is DISCOVERY_PREPAID_V1 already paid for the whole discovery phase up front,
    // so a Continue at its gate must charge nothing — and needs no expectedCost either, since
    // nothing is being priced.
    it('THE MIGRATION TEST — a job created before segment billing is not charged again', async () => {
      mockJobFindFirst.mockResolvedValue(makeJob({ billingModel: 'DISCOVERY_PREPAID_V1' }));

      const response = await request(app)
        .post(`/api/jobs/${jobId}/gate-action`)
        .set(authHeaders)
        .send({ action: 'continue', gateStage: 1 });

      expect(response.status).toBe(200);
      expect(response.body.status).toBe('queued');
      expect(mockChargeForStageWithPriceCasInTx).not.toHaveBeenCalled();
    });

    // Steering is what the checkpoint is FOR; taxing it would discourage the one behaviour the
    // whole feature exists to enable.
    it('apply_stay is free — no expectedCost required, nothing charged', async () => {
      mockJobFindFirst.mockResolvedValue(makeJob({ billingModel: 'GUIDED_SEGMENTS_V1' }));

      const response = await request(app)
        .post(`/api/jobs/${jobId}/gate-action`)
        .set(authHeaders)
        .send({ action: 'apply_stay', gateStage: 1, patch: { niche_description: 'Edited' } });

      expect(response.status).toBe(200);
      expect(mockChargeForStageWithPriceCasInTx).not.toHaveBeenCalled();
    });

    // The hardened CAS: expectedCost is now REQUIRED for a priced Continue, not merely checked
    // when present. A missing confirmation must 400 before the transaction (and any charge) is
    // ever attempted.
    it('returns 400 when expectedCost is missing for a priced Continue', async () => {
      mockJobFindFirst.mockResolvedValue(makeJob({ billingModel: 'GUIDED_SEGMENTS_V1' }));

      const response = await request(app)
        .post(`/api/jobs/${jobId}/gate-action`)
        .set(authHeaders)
        .send({ action: 'continue', gateStage: 1 });

      expect(response.status).toBe(400);
      expect(mockTransaction).not.toHaveBeenCalled();
      expect(mockChargeForStageWithPriceCasInTx).not.toHaveBeenCalled();
    });

    // A price that changed between the gate rendering and the click: the comparison now happens
    // INSIDE the charging transaction (chargeForStageWithPriceCasInTx), against the price read in
    // that same transaction — not against a price read earlier and separately. Here that's
    // exercised by having the (mocked) CAS helper itself report the drift, exactly as the real
    // implementation would from inside the transaction.
    it('a price that changed under the user is refused, not silently charged — no charge, no status change', async () => {
      mockJobFindFirst.mockResolvedValue(makeJob({ billingModel: 'GUIDED_SEGMENTS_V1' }));
      mockChargeForStageWithPriceCasInTx.mockRejectedValue(new MockPriceChangedError(3, 5));

      const response = await request(app)
        .post(`/api/jobs/${jobId}/gate-action`)
        .set(authHeaders)
        .send({ action: 'continue', gateStage: 1, expectedCost: 3 });

      expect(response.status).toBe(409);
      expect(response.body.code).toBe('PRICE_CHANGED');
      expect(response.body.expectedCost).toBe(3);
      expect(response.body.actualCost).toBe(5);
      // The transaction threw before the flip's job.updateMany ran — no status change either.
      expect(mockJobUpdateMany).not.toHaveBeenCalled();
    });
  });

  it('returns 400 for invalid payload (bad action)', async () => {
    const response = await request(app)
      .post(`/api/jobs/${jobId}/gate-action`)
      .set(authHeaders)
      .send({ action: 'bogus', gateStage: 1 });

    expect(response.status).toBe(400);
  });

  it('returns 401 when unauthenticated', async () => {
    const response = await request(app)
      .post(`/api/jobs/${jobId}/gate-action`)
      .send({ action: 'continue', gateStage: 1 });

    expect(response.status).toBe(401);
  });
});
