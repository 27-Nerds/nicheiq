/**
 * POST /api/jobs/:jobId/seed-idea (plans/eager-meandering-feather.md Phase 5) — "generate an
 * idea from your own idea" at selection chat. Mirrors jobs.gateAction.test.ts's mocking shape:
 * dispatchService.js is NOT mocked — openDispatch/settleDispatch run for REAL against the `tx`
 * this file controls, so a passing test here also proves the real dispatch plumbing wires up.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import express, { Express } from 'express';
import request from 'supertest';
import { candidateSnapshotSha256 } from '../../utils/ideaIdentity.js';

const mockJobFindFirst = vi.fn();
// tx-scoped job.updateMany — used by the seedIdeaCount+status flip AND (on the compensation
// path) both the revert itself and settleDispatch's internal CAS-disarm update.
const mockJobUpdateMany = vi.fn();
const mockJobUpdate = vi.fn();
const mockDispatchCreate = vi.fn();
const mockDispatchUpdate = vi.fn();
const mockDispatchUpdateMany = vi.fn();
const mockChatMessageCreate = vi.fn();
const mockChatMessageDelete = vi.fn();
const mockChatMessageFindFirst = vi.fn();
const mockChatMessageFindMany = vi.fn();
const mockTransaction = vi.fn();
const mockParseCurrentFounderFit = vi.fn();

vi.mock('../../services/db.js', () => ({
  prisma: {
    job: { findFirst: (...a: any[]) => mockJobFindFirst(...a) },
    chatMessage: {
      delete: (...a: any[]) => mockChatMessageDelete(...a),
      findFirst: (...a: any[]) => mockChatMessageFindFirst(...a),
      findMany: (...a: any[]) => mockChatMessageFindMany(...a),
    },
    $transaction: (...a: any[]) => mockTransaction(...a),
  },
}));

vi.mock('../../services/founderFitService.js', () => ({
  parseCurrentFounderFitArtifact: (...a: any[]) => mockParseCurrentFounderFit(...a),
}));

const mockDeliverDispatchWork = vi.fn();

vi.mock('../../services/queueService.js', () => ({
  enqueueJob: vi.fn(),
  enqueueLandingPageJob: vi.fn(),
  enqueuePhase2Job: vi.fn(),
  enqueueRegenerateJob: vi.fn(),
  enqueueContinueFromGateJob: vi.fn(),
  enqueueSeedIdeaJob: vi.fn(),
  deliverDispatchWork: (...a: any[]) => mockDeliverDispatchWork(...a),
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
  createJobAndChargeDiscoveryInTx: vi.fn(),
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
  refundChargeInTx: vi.fn(),
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

// The analyst gate is now hasAnalystAccess = isEntitledUser || the chatAnalystAccess
// grant. These suites drive the entitlement half, so the existing mock stands in for
// the whole gate. Decision tools default ON here so the pre-existing prompt/tool
// assertions keep describing the full-feature owner; the off case has its own tests.
const mockHasDecisionToolsAccess = vi.fn().mockResolvedValue(true);
vi.mock('../../services/featureAccess.js', () => ({
  hasAnalystAccess: (...a: any[]) => mockIsEntitledUser(...a),
  hasDecisionToolsAccess: (...a: any[]) => mockHasDecisionToolsAccess(...a),
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
  solutionIdeas: [],
  ...overrides,
});

beforeEach(async () => {
  vi.clearAllMocks();
  mockIsEntitledUser.mockResolvedValue(true);
  mockDeliverDispatchWork.mockResolvedValue(undefined);
  mockChargeForSeedIdeaInTx.mockResolvedValue({ cost: 2, transaction: { id: 'txn-seed-1' } });
  mockRefundForSeedIdeaStage.mockResolvedValue({ amount: -2 });
  mockJobUpdateMany.mockResolvedValue({ count: 1 });
  mockJobUpdate.mockResolvedValue({});
  mockDispatchCreate.mockResolvedValue({ id: 'dispatch-seed-1' });
  mockDispatchUpdate.mockResolvedValue({});
  mockDispatchUpdateMany.mockResolvedValue({ count: 1 });
  mockChatMessageCreate.mockResolvedValue({ id: 'receipt-1' });
  mockChatMessageDelete.mockResolvedValue({});
  mockChatMessageFindMany.mockResolvedValue([]);
  mockParseCurrentFounderFit.mockReturnValue(null);

  const tx = {
    job: { updateMany: (...a: any[]) => mockJobUpdateMany(...a), update: (...a: any[]) => mockJobUpdate(...a) },
    jobDispatch: {
      create: (...a: any[]) => mockDispatchCreate(...a),
      update: (...a: any[]) => mockDispatchUpdate(...a),
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

  it('reloads a stored synthesis proposal and enqueues a server-derived seed brief', async () => {
    const parent = {
      idea_id: 'idea-parent',
      idea_revision: 2,
      solution_name: 'Broad monitor',
    };
    mockJobFindFirst.mockResolvedValue(makeJob({ solutionIdeas: [parent] }));
    mockChatMessageFindFirst.mockResolvedValue({
      patchJson: {
        kind: 'idea_synthesis',
        operation: 'narrow',
        proposedTitle: 'Focused monitor',
        proposedBrief: 'Monitor one workflow for agencies.',
        changeSummary: 'Narrows the buyer and use case.',
        rationale: 'The source is broad.',
        parents: [{
          ideaId: 'idea-parent',
          ideaRevision: 2,
          solutionName: 'Broad monitor',
          contribution: 'Keep the alerting mechanism.',
        }],
        evidence: {
          sourceAnchors: [{
            ideaId: 'idea-parent',
            ideaRevision: 2,
            candidateSnapshotSha256: candidateSnapshotSha256(parent),
            pain: 'Missed workflow changes',
          }],
          requiresValidation: ['Validate agency demand.'],
        },
        newAssumptions: [],
        evaluation: {
          version: 1,
          conceptSetId: '22222222-2222-2222-2222-222222222222',
          optionId: 'O11111111111',
          inputFingerprint: 'f'.repeat(64),
          changedAxes: [{
            axis: 'scope',
            from: 'All workflows',
            to: 'One agency workflow',
            reason: 'Keep the evaluation exact.',
          }],
          assumptions: [{
            assumptionId: 'A1111111111',
            type: 'demand',
            statement: 'Agencies need this workflow.',
            whyDecisionChanging: 'Demand determines viability.',
            consequenceIfFalse: 'Do not build it.',
          }],
          retainedEvidence: ['The source pain remains relevant.'],
          evidenceToRecheck: ['Validate agency demand.'],
          disqualifiers: ['No agency commits.'],
          suggestedTest: {
            assumptionId: 'A1111111111',
            hypothesis: 'Agencies will request access.',
            method: 'CTA_CLICK',
            evidenceSignal: 'SMALL_COMMITMENT',
            audience: 'Agency operators',
            artifact: 'Concept page with request-access CTA',
            primaryMetric: 'Qualified CTA conversion',
            passThreshold: 'At least 15 percent',
            failThreshold: 'Below 5 percent',
            measurementWindow: 'Thirty days',
          },
        },
      },
    });

    const response = await request(app)
      .post(`/api/jobs/${jobId}/seed-idea`)
      .set(authHeaders)
      .send({
        kind: 'idea_synthesis',
        sourceMessageId: 'msg-synthesis',
        expectedCost: 2,
      });

    expect(response.status).toBe(200);
    expect(mockDispatchUpdate).toHaveBeenCalledWith({
      where: { id: 'dispatch-seed-1' },
      data: {
        workPayload: expect.objectContaining({
          job_id: jobId,
          checkpoint_path: '/cp/path',
          niche: 'test niche',
          seed_text: expect.stringContaining('Focused monitor'),
          pain_ref: 'Missed workflow changes',
          tool_ref: null,
          task_type: 'seed_idea',
          synthesis_evaluation: expect.objectContaining({
            evaluation_id: 'dispatch-seed-1',
            dispatch_id: 'dispatch-seed-1',
            source_message_id: 'msg-synthesis',
            proposal: expect.objectContaining({
              proposedTitle: 'Focused monitor',
              evaluation: expect.objectContaining({
                conceptSetId: '22222222-2222-2222-2222-222222222222',
                disqualifiers: ['No agency commits.'],
              }),
            }),
          }),
        }),
      },
    });
    expect(mockDeliverDispatchWork).toHaveBeenCalledWith('dispatch-seed-1');
    expect(response.body).toMatchObject({
      evaluationId: 'dispatch-seed-1',
      dispatchId: 'dispatch-seed-1',
      sourceMessageId: 'msg-synthesis',
      proposedTitle: 'Focused monitor',
    });
  });

  it('rejects a combined synthesis before charging when either source revision is stale', async () => {
    const alerts = {
      idea_id: 'idea-alerts',
      idea_revision: 2,
      solution_name: 'Change monitor',
    };
    const briefing = {
      idea_id: 'idea-briefing',
      idea_revision: 5,
      solution_name: 'Briefing desk',
    };
    mockJobFindFirst.mockResolvedValue(makeJob({ solutionIdeas: [alerts, briefing] }));
    mockChatMessageFindFirst.mockResolvedValue({
      patchJson: {
        kind: 'idea_synthesis',
        operation: 'combine',
        proposedTitle: 'Agency signal desk',
        proposedBrief: 'Combines alerts with client briefings.',
        changeSummary: 'Joins two adjacent workflows.',
        rationale: 'The same buyer may own both jobs.',
        parents: [
          {
            ideaId: 'idea-alerts',
            ideaRevision: 2,
            solutionName: 'Change monitor',
            contribution: 'Keep alerts.',
          },
          {
            ideaId: 'idea-briefing',
            ideaRevision: 4,
            solutionName: 'Briefing desk',
            contribution: 'Keep summaries.',
          },
        ],
        evidence: {
          sourceAnchors: [
            {
              ideaId: 'idea-alerts',
              ideaRevision: 2,
              candidateSnapshotSha256: candidateSnapshotSha256(alerts),
            },
            {
              ideaId: 'idea-briefing',
              ideaRevision: 4,
              candidateSnapshotSha256: candidateSnapshotSha256(briefing),
            },
          ],
          requiresValidation: ['Validate that one buyer owns both workflows.'],
        },
        newAssumptions: ['One buyer needs both capabilities.'],
      },
    });

    const response = await request(app)
      .post(`/api/jobs/${jobId}/seed-idea`)
      .set(authHeaders)
      .send({
        kind: 'idea_synthesis',
        sourceMessageId: 'msg-synthesis',
        expectedCost: 2,
      });

    expect(response.status).toBe(409);
    expect(response.body.code).toBe('STALE_SYNTHESIS_SOURCE');
    expect(mockChargeForSeedIdeaInTx).not.toHaveBeenCalled();
  });

  it('rejects a founder-fit reshape before charging when its profile fingerprint is stale', async () => {
    const parent = {
      idea_id: 'idea-parent',
      idea_revision: 2,
      solution_name: 'Signal Desk',
    };
    mockJobFindFirst.mockResolvedValue(makeJob({
      solutionIdeas: [parent],
      selectionDecisionProfile: { weeklyTime: 'under_10' },
      selectionFounderFit: { inputFingerprint: 'f'.repeat(64) },
    }));
    mockChatMessageFindFirst.mockResolvedValue({
      patchJson: {
        kind: 'idea_synthesis',
        operation: 'narrow',
        proposedTitle: 'Weekly Signal Brief',
        proposedBrief: 'One weekly review for a single workflow.',
        changeSummary: 'Removes continuous monitoring.',
        rationale: 'Designed around the time conflict.',
        parents: [{
          ideaId: 'idea-parent',
          ideaRevision: 2,
          solutionName: 'Signal Desk',
          contribution: 'Keep signal interpretation.',
        }],
        evidence: {
          sourceAnchors: [{
            ideaId: 'idea-parent',
            ideaRevision: 2,
            candidateSnapshotSha256: candidateSnapshotSha256(parent),
          }],
          requiresValidation: ['Recheck demand for weekly review.'],
          founderFitRef: {
            inputFingerprint: 'f'.repeat(64),
            ideaId: 'idea-parent',
            ideaRevision: 2,
            verdict: 'needs_reshape',
            conflicts: [{
              dimension: 'time',
              summary: 'The build exceeds available time.',
              profileFields: ['weeklyTime'],
              ideaFields: ['estimated_development_time'],
            }],
          },
        },
        newAssumptions: ['A weekly cadence is useful.'],
      },
    });

    const response = await request(app)
      .post(`/api/jobs/${jobId}/seed-idea`)
      .set(authHeaders)
      .send({
        kind: 'idea_synthesis',
        sourceMessageId: 'msg-fit-reshape',
        expectedCost: 2,
      });

    expect(response.status).toBe(409);
    expect(response.body.code).toBe('STALE_FOUNDER_FIT_RESHAPE');
    expect(mockChargeForSeedIdeaInTx).not.toHaveBeenCalled();
  });

  it('returns the prior settlement for one proposal without a second charge', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob());
    mockChatMessageFindMany.mockResolvedValue([{
      patchJson: {
        kind: 'ledger_event',
        event: 'seed_settled',
        sourceMessageId: 'msg-already-evaluated',
        outcome: 'accepted',
      },
    }]);

    const response = await request(app)
      .post(`/api/jobs/${jobId}/seed-idea`)
      .set(authHeaders)
      .send({
        ...validBody,
        sourceMessageId: 'msg-already-evaluated',
      });

    expect(response.status).toBe(200);
    expect(response.body).toMatchObject({ status: 'settled', outcome: 'accepted' });
    expect(mockChargeForSeedIdeaInTx).not.toHaveBeenCalled();
    expect(mockDeliverDispatchWork).not.toHaveBeenCalled();
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

    expect(mockDispatchUpdate).toHaveBeenCalledWith({
      where: { id: 'dispatch-seed-1' },
      data: {
        workPayload: expect.objectContaining({
          job_id: jobId,
          checkpoint_path: '/cp/path',
          niche: 'test niche',
          seed_text: 'A tool that does X for Y',
          pain_ref: 'Pain A',
          tool_ref: 'Spreadsheets',
          synthesis_evaluation: null,
          task_type: 'seed_idea',
        }),
      },
    });
    expect(mockDeliverDispatchWork).toHaveBeenCalledWith('dispatch-seed-1');
    expect(response.body).toMatchObject({
      operationId: 'dispatch-seed-1',
      deliveryPending: false,
    });
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

  it('returns 409 when concurrent admission hits the unique charge constraint', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob());
    mockTransaction.mockRejectedValue({ code: 'P2002' });

    const response = await request(app)
      .post(`/api/jobs/${jobId}/seed-idea`)
      .set(authHeaders)
      .send(validBody);

    expect(response.status).toBe(409);
    expect(response.body.error).toBe('Seed idea already in progress (duplicate charge)');
    expect(mockDeliverDispatchWork).not.toHaveBeenCalled();
  });

  it('keeps the charged dispatch and receipt durable when Redis delivery is ambiguous', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob());
    mockDeliverDispatchWork.mockRejectedValue(new Error('Redis unavailable'));

    const response = await request(app)
      .post(`/api/jobs/${jobId}/seed-idea`)
      .set(authHeaders)
      .send(validBody);

    expect(response.status).toBe(200);
    expect(response.body).toMatchObject({
      status: 'queued',
      operationId: 'dispatch-seed-1',
      deliveryPending: true,
    });
    expect(mockJobUpdateMany).toHaveBeenCalledTimes(1);
    expect(mockDispatchUpdateMany).not.toHaveBeenCalled();
    expect(mockRefundForSeedIdeaStage).not.toHaveBeenCalled();
    expect(mockChatMessageDelete).not.toHaveBeenCalled();
  });

  it('does not attempt delivery when persisting the immutable work payload fails', async () => {
    mockJobFindFirst.mockResolvedValue(makeJob());
    mockDispatchUpdate.mockRejectedValue(new Error('database unavailable'));

    const response = await request(app)
      .post(`/api/jobs/${jobId}/seed-idea`)
      .set(authHeaders)
      .send(validBody);

    expect(response.status).toBe(500);
    expect(mockDeliverDispatchWork).not.toHaveBeenCalled();
  });
});
