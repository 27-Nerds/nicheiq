import { describe, it, expect, vi, beforeEach } from 'vitest';
import express, { Express } from 'express';
import request from 'supertest';

// ============================================
// E2E happy-path: drives the FULL guided-research status machine across many HTTP
// requests within a single test (gate-reached G1 -> gate-action apply_stay ->
// gate-reached G1 again -> continue -> gate-reached G2 -> continue -> ideas-ready ->
// AWAITING_SELECTION), mounting BOTH jobsRouter (gate-action, the user-facing route)
// and workersRouter (gate-reached/job-started/ideas-ready, the worker-facing routes)
// in one app, same as index.ts does.
//
// Unlike the single-hop unit test files (workers.gateNotify.test.ts,
// jobs.gateAction.test.ts), this needs a STATEFUL mock: each hop's assertions and
// the next hop's behavior depend on what the PREVIOUS hop actually wrote, so the
// Prisma mock is backed by one mutable `jobRow` object instead of a scripted
// `mockResolvedValueOnce` sequence.
// ============================================

const jobId = '00000000-0000-0000-0000-000000000001';
const userId = 'user-123';
const authHeaders = { 'x-user-id': userId };

type JobRow = Record<string, any>;
let jobRow: JobRow;

function resetJobRow() {
  jobRow = {
    id: jobId,
    userId,
    niche: 'consultant invoicing',
    status: 'RUNNING',
    gateStage: null,
    gateArtifact: null,
    gateReachedAt: null,
    gateApplyCount: 0,
    phase1CheckpointPath: null,
    queuedAt: null,
    startedAt: new Date(),
    workerId: null,
    costUsd: 0,
    costSummary: null,
    solutionIdeas: null,
    ideasShownAt: null,
    awaitingSelectionAt: null,
    selectedSolutions: [],
    ideasRegeneratedAt: null,
  };
}

/** Applies a Prisma `data` object onto the store, honoring the update operators
 *  these routes actually use ({ increment } / { decrement }); everything else is a
 *  plain overwrite — a deliberately narrow emulation, not a general Prisma mock. */
function applyData(data: Record<string, any>) {
  for (const [key, value] of Object.entries(data)) {
    if (value && typeof value === 'object' && !(value instanceof Date) && !Array.isArray(value)) {
      if ('increment' in value) {
        jobRow[key] = (jobRow[key] ?? 0) + value.increment;
        continue;
      }
      if ('decrement' in value) {
        jobRow[key] = (jobRow[key] ?? 0) - value.decrement;
        continue;
      }
    }
    jobRow[key] = value;
  }
}

function matchesWhere(where: Record<string, any>): boolean {
  if (where.id !== undefined && where.id !== jobRow.id) return false;
  if (where.userId !== undefined && where.userId !== jobRow.userId) return false;
  if (where.status !== undefined) {
    if (typeof where.status === 'object' && where.status !== null && 'in' in where.status) {
      if (!where.status.in.includes(jobRow.status)) return false;
    } else if (where.status !== jobRow.status) {
      return false;
    }
  }
  if (where.gateStage !== undefined && where.gateStage !== jobRow.gateStage) return false;
  if (
    where.gateReachedAt !== undefined &&
    where.gateReachedAt !== null &&
    typeof where.gateReachedAt === 'object' &&
    'not' in where.gateReachedAt &&
    where.gateReachedAt.not === null &&
    jobRow.gateReachedAt === null
  ) {
    return false;
  }
  return true;
}

const mockJobFindFirst = vi.fn(async ({ where }: any) => (matchesWhere(where) ? { ...jobRow } : null));
const mockJobFindUnique = vi.fn(async ({ where, include }: any) => {
  if (where.id !== jobRow.id) return null;
  const row: JobRow = { ...jobRow };
  if (include?.user) row.user = { id: jobRow.userId, email: 'owner@example.com' };
  return row;
});
const mockJobUpdate = vi.fn(async ({ where, data }: any) => {
  if (where.id !== jobRow.id) throw new Error('Record not found');
  applyData(data);
  return { ...jobRow };
});
const mockJobUpdateMany = vi.fn(async ({ where, data }: any) => {
  if (!matchesWhere(where)) return { count: 0 };
  applyData(data);
  return { count: 1 };
});
const mockUserFindUnique = vi.fn(async (_args: any) => ({ email: 'owner@example.com' }));
// Durable ledger receipts (ledgerEvents.ts): apply_stay writes a 'gate_patch_submitted'
// ChatMessage in the flip txn; the same-gate re-arrival promotes it to 'gate_patch_applied'.
const mockChatMessageCreate = vi.fn(async (_args?: any) => ({ id: 'receipt-1' } as any));
const mockChatMessageFindFirst = vi.fn(async (_args?: any) => null as any);
const mockChatMessageUpdate = vi.fn(async (_args?: any) => ({} as any));
const mockChatMessageDelete = vi.fn(async (_args?: any) => ({} as any));
const mockDispatchUpdateMany = vi.fn(async (_args?: any) => ({ count: 1 } as any));
const mockDispatchCreate = vi.fn(async (_args?: any) => ({ id: 'dispatch-test' } as any));

const mockTransaction = vi.fn(async (cb: any) => {
  // Receipt promotion and dispatch settlement now happen INSIDE the arrival transaction — that
  // was the fix: they used to be separate top-level calls whose failure was swallowed, leaving the
  // artifact committed while its audit row still said 'submitted'. So the tx client has to expose
  // everything the real one does, not just the two writes it used to need.
  const tx = {
    job: { updateMany: mockJobUpdateMany, update: mockJobUpdate },
    chatMessage: {
      create: mockChatMessageCreate,
      findFirst: mockChatMessageFindFirst,
      update: mockChatMessageUpdate,
      delete: mockChatMessageDelete,
    },
    jobDispatch: { updateMany: mockDispatchUpdateMany, create: mockDispatchCreate },
  };
  return cb(tx);
});

vi.mock('../../services/db.js', () => ({
  prisma: {
    job: {
      findFirst: (args: any) => mockJobFindFirst(args),
      findUnique: (args: any) => mockJobFindUnique(args),
      update: (args: any) => mockJobUpdate(args),
      updateMany: (args: any) => mockJobUpdateMany(args),
    },
    user: {
      findUnique: (args: any) => mockUserFindUnique(args),
    },
    chatMessage: {
      create: (args: any) => mockChatMessageCreate(args),
      findFirst: (args: any) => mockChatMessageFindFirst(args),
      update: (args: any) => mockChatMessageUpdate(args),
      delete: (args: any) => mockChatMessageDelete(args),
    },
    // Top-level (not tx-scoped): gate-action's enqueue-failure compensation settles the
    // dispatch outside the flip transaction, same as the job/chatMessage revert beside it.
    jobDispatch: {
      updateMany: (args: any) => mockDispatchUpdateMany(args),
    },
    $transaction: (cb: any) => mockTransaction(cb),
  },
}));

vi.mock('../../middleware/auth.js', () => ({
  requireInternalAuth: (req: any, res: any, next: any) => {
    const uid = req.headers['x-user-id'];
    if (uid) {
      req.user = { id: uid };
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

const mockDeliverDispatchWork = vi.fn();
vi.mock('../../services/queueService.js', () => ({
  enqueueJob: vi.fn(),
  enqueueLandingPageJob: vi.fn(),
  enqueuePhase2Job: vi.fn(),
  enqueueRegenerateJob: vi.fn(),
  enqueueContinueFromGateJob: vi.fn(),
  deliverDispatchWork: (...a: any[]) => mockDeliverDispatchWork(...a),
  getQueueStats: vi.fn(),
  getQueueLength: vi.fn(),
  removeJobFromQueue: vi.fn(),
}));

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
  refundForStageInTx: vi.fn(),
  isGuidedSegment: vi.fn(),
}));

const mockIsEntitledUser = vi.fn();
vi.mock('../../services/catalogService.js', () => ({
  isEntitledUser: (...a: any[]) => mockIsEntitledUser(...a),
}));

vi.mock('../../services/jobService.js', () => ({
  getJob: vi.fn(),
  updateJobStatus: vi.fn(),
  getJobAsset: vi.fn(),
  failJob: vi.fn(),
  updateStageProgress: vi.fn(),
  completeJob: vi.fn(),
  addJobAsset: vi.fn(),
}));

const mockBroadcastProgress = vi.fn();
vi.mock('../../services/progressBroadcastService.js', () => ({
  broadcastProgress: (...a: any[]) => mockBroadcastProgress(...a),
}));

const mockNotifyGateReached = vi.fn();
const mockNotifySolutionsReady = vi.fn();
const mockNotifyJobStart = vi.fn();
vi.mock('../../services/notificationService.js', () => ({
  notifyJobStart: (...a: any[]) => mockNotifyJobStart(...a),
  notifyJobComplete: vi.fn(),
  notifyJobError: vi.fn(),
  notifySolutionsReady: (...a: any[]) => mockNotifySolutionsReady(...a),
  notifySelectionReminder: vi.fn(),
  notifyGateReached: (...a: any[]) => mockNotifyGateReached(...a),
  notifyPhase2Start: vi.fn(),
  notifyRegenerationComplete: vi.fn(),
  notifyLandingPageReady: vi.fn(),
}));

const mockRegisterWorkerHeartbeat = vi.fn();
vi.mock('../../services/heartbeatService.js', () => ({
  updateJobHeartbeat: vi.fn(),
  registerWorkerHeartbeat: (...a: any[]) => mockRegisterWorkerHeartbeat(...a),
  markWorkerShutdown: vi.fn(),
}));

vi.mock('../../utils/errorTranslator.js', () => ({
  buildErrorDetails: vi.fn().mockReturnValue(null),
}));

vi.mock('../../types/job.js', async (importOriginal) => {
  const actual = (await importOriginal()) as any;
  return {
    ...actual,
    PIPELINE_STAGES: [
      { number: 1, name: 'Niche Validation', phase: 1 },
      { number: 2, name: 'Search & Discovery', phase: 1 },
      { number: 3, name: 'Pain Point Analysis', phase: 1 },
      { number: 4, name: 'Audience Mapping', phase: 1 },
      { number: 5, name: 'Solution Pipeline', phase: 1 },
    ],
    TOTAL_STAGES: 16,
  };
});

// ============================================
// Setup Express App (both routers, mirroring index.ts's mount paths)
// ============================================
let app: Express;

beforeEach(async () => {
  vi.clearAllMocks();
  resetJobRow();
  mockIsEntitledUser.mockResolvedValue(true);
  mockDeliverDispatchWork.mockResolvedValue(undefined);
  mockRegisterWorkerHeartbeat.mockResolvedValue(undefined);
  mockNotifyGateReached.mockResolvedValue(undefined);
  mockNotifySolutionsReady.mockResolvedValue(undefined);
  mockNotifyJobStart.mockResolvedValue(undefined);

  app = express();
  app.use(express.json());
  const { jobsRouter } = await import('../jobs.js');
  const { workersRouter } = await import('../workers.js');
  app.use('/api/jobs', jobsRouter);
  app.use('/api/workers', workersRouter);
});

describe('Guided research E2E: full gate chain to AWAITING_SELECTION', () => {
  it('G1 reached -> apply_stay -> G1 re-reached -> continue -> G2 reached -> continue -> ideas-ready', async () => {
    // ── Hop 1: worker reports G1 reached (RUNNING -> AWAITING_GATE) ──
    let res = await request(app).post('/api/workers/gate-reached').send({
      worker_id: 'w1',
      job_id: jobId,
      gate_stage: 1,
      checkpoint_path: '/cp/g1-a',
      gate_artifact: { type: 'niche_validation', niche_description: 'consultant invoicing chaos' },
    });
    expect(res.status).toBe(200);
    expect(jobRow.status).toBe('AWAITING_GATE');
    expect(jobRow.gateStage).toBe(1);
    expect(jobRow.gateApplyCount).toBe(0);
    expect(jobRow.phase1CheckpointPath).toBe('/cp/g1-a');

    // ── Hop 2: user applies a G1 patch and stays at the gate ──
    res = await request(app)
      .post(`/api/jobs/${jobId}/gate-action`)
      .set(authHeaders)
      .send({
        action: 'apply_stay',
        gateStage: 1,
        patch: { niche_description: 'Solo consultants managing multiple client invoices' },
      });
    expect(res.status).toBe(200);
    expect(jobRow.status).toBe('QUEUED');
    expect(jobRow.gateApplyCount).toBe(1);
    expect(jobRow.gateReachedAt).toBeNull();
    expect(mockDispatchCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          workPayload: expect.objectContaining({
            job_id: jobId,
            checkpoint_path: '/cp/g1-a',
            gate_stage: 1,
            mode: 'apply_stay',
            patch: { niche_description: 'Solo consultants managing multiple client invoices' },
            task_type: 'continue_from_gate',
          }),
        }),
      }),
    );
    expect(mockDeliverDispatchWork).toHaveBeenCalledWith('dispatch-test');
    // Durable ledger, phase one: the apply is recorded as SUBMITTED (not yet applied —
    // the pipeline hasn't re-derived with it), inside the same transaction as the flip.
    expect(mockChatMessageCreate).toHaveBeenCalledTimes(1);
    const receiptWrite = mockChatMessageCreate.mock.calls[0][0] as any;
    expect(receiptWrite.data.role).toBe('receipt');
    expect(receiptWrite.data.gateStage).toBe(1);
    expect(receiptWrite.data.patchJson.event).toBe('gate_patch_submitted');
    expect(receiptWrite.data.patchJson.rows).toEqual([
      { label: 'Niche description', value: 'Solo consultants managing multiple client invoices' },
    ]);

    // ── Hop 3: worker picks the QUEUED job back up ──
    res = await request(app).post('/api/workers/job-started').send({ worker_id: 'w1', job_id: jobId });
    expect(res.status).toBe(200);
    expect(jobRow.status).toBe('RUNNING');

    // ── Hop 4: worker re-reaches the SAME gate (G1) with a refreshed artifact ──
    // The submitted receipt is now waiting to be promoted.
    mockChatMessageFindFirst.mockResolvedValueOnce({
      id: 'receipt-1',
      patchJson: {
        kind: 'ledger_event',
        version: 1,
        event: 'gate_patch_submitted',
        patch: { niche_description: 'Solo consultants managing multiple client invoices' },
        rows: [{ label: 'Niche description', value: 'Solo consultants managing multiple client invoices' }],
      },
    } as any);
    res = await request(app).post('/api/workers/gate-reached').send({
      worker_id: 'w1',
      job_id: jobId,
      gate_stage: 1,
      checkpoint_path: '/cp/g1-b',
      gate_artifact: {
        type: 'niche_validation',
        niche_description: 'Solo consultants managing multiple client invoices',
      },
    });
    expect(res.status).toBe(200);
    expect(jobRow.status).toBe('AWAITING_GATE');
    expect(jobRow.gateStage).toBe(1);
    // Same-stage re-arrival must NOT reset the apply cap counter.
    expect(jobRow.gateApplyCount).toBe(1);
    // Durable ledger, phase two: the same-gate re-arrival IS the proof the pipeline
    // re-derived with the patch — promote the receipt to APPLIED (this is the row the
    // frontend renders, and the reason an applied change survives a reload).
    expect(mockChatMessageUpdate).toHaveBeenCalledTimes(1);
    const promote = mockChatMessageUpdate.mock.calls[0][0] as any;
    expect(promote.where).toEqual({ id: 'receipt-1' });
    expect(promote.data.patchJson.event).toBe('gate_patch_applied');

    // ── Hop 5: user continues past G1 ──
    res = await request(app)
      .post(`/api/jobs/${jobId}/gate-action`)
      .set(authHeaders)
      .send({ action: 'continue', gateStage: 1 });
    expect(res.status).toBe(200);
    expect(jobRow.status).toBe('QUEUED');
    expect(mockDeliverDispatchWork).toHaveBeenLastCalledWith('dispatch-test');

    // ── Hop 6: worker picks the job back up ──
    res = await request(app).post('/api/workers/job-started').send({ worker_id: 'w1', job_id: jobId });
    expect(res.status).toBe(200);
    expect(jobRow.status).toBe('RUNNING');

    // ── Hop 7: worker reaches G2 (a NEW gate stage — apply cap resets) ──
    res = await request(app).post('/api/workers/gate-reached').send({
      worker_id: 'w1',
      job_id: jobId,
      gate_stage: 4,
      checkpoint_path: '/cp/g2-a',
      gate_artifact: {
        type: 'audience_mapping_gate',
        pains: [{ title: 'Too many disconnected invoice trackers', severity: 0.8 }],
        segments: [{ segment_name: 'Solo consultants' }],
      },
    });
    expect(res.status).toBe(200);
    expect(jobRow.status).toBe('AWAITING_GATE');
    expect(jobRow.gateStage).toBe(4);
    expect(jobRow.gateApplyCount).toBe(0);

    // ── Hop 8: user continues past G2 (no patch) ──
    res = await request(app)
      .post(`/api/jobs/${jobId}/gate-action`)
      .set(authHeaders)
      .send({ action: 'continue', gateStage: 4 });
    expect(res.status).toBe(200);
    expect(jobRow.status).toBe('QUEUED');
    expect(mockDeliverDispatchWork).toHaveBeenLastCalledWith('dispatch-test');

    // ── Hop 9: worker picks the job back up for the final run to Phase 1 completion ──
    res = await request(app).post('/api/workers/job-started').send({ worker_id: 'w1', job_id: jobId });
    expect(res.status).toBe(200);
    expect(jobRow.status).toBe('RUNNING');

    // ── Hop 10: worker reports ideas ready (RUNNING -> AWAITING_SELECTION) ──
    res = await request(app).post('/api/workers/ideas-ready').send({
      worker_id: 'w1',
      job_id: jobId,
      solutions: [{ solution_name: 'Consultant Invoice Hub' }],
      checkpoint_path: '/cp/final',
      total_to_validate: 1,
      cost_summary: { total_cost: 1.23 },
    });
    expect(res.status).toBe(200);
    expect(jobRow.status).toBe('AWAITING_SELECTION');
    expect(jobRow.solutionIdeas).toEqual([
      expect.objectContaining({
        solution_name: 'Consultant Invoice Hub',
        idea_id: expect.stringMatching(/^idea_[a-f0-9]{32}$/),
        idea_revision: 1,
      }),
    ]);
    expect(jobRow.costUsd).toBe(1.23);
    expect(jobRow.ideasShownAt).not.toBeNull();

    // ── Emails/broadcasts fired at each hop, no more/no less ──
    expect(mockNotifyGateReached).toHaveBeenCalledTimes(3);
    expect(mockNotifyGateReached).toHaveBeenNthCalledWith(1, userId, 'owner@example.com', jobId, 'consultant invoicing', 1);
    expect(mockNotifyGateReached).toHaveBeenNthCalledWith(3, userId, 'owner@example.com', jobId, 'consultant invoicing', 4);
    expect(mockNotifyJobStart).toHaveBeenCalledTimes(3);
    expect(mockNotifySolutionsReady).toHaveBeenCalledTimes(1);
    expect(mockNotifySolutionsReady).toHaveBeenCalledWith(userId, 'owner@example.com', jobId, 'consultant invoicing', 1);

    // Exactly ONE receipt across the whole chain: the single apply_stay. A plain
    // `continue` records nothing (nothing changed), and NEW gates don't promote.
    expect(mockChatMessageCreate).toHaveBeenCalledTimes(1);
    expect(mockChatMessageUpdate).toHaveBeenCalledTimes(1);
  });

  it('a redelivered same-gate callback does not double-promote the receipt (idempotent)', async () => {
    jobRow.status = 'RUNNING';
    jobRow.gateStage = 1;
    jobRow.gateApplyCount = 1;
    // The receipt was already promoted by the first delivery — no 'submitted' row left.
    mockChatMessageFindFirst.mockResolvedValue({
      id: 'receipt-1',
      patchJson: { kind: 'ledger_event', version: 1, event: 'gate_patch_applied', patch: {}, rows: [] },
    } as any);

    const res = await request(app).post('/api/workers/gate-reached').send({
      worker_id: 'w1',
      job_id: jobId,
      gate_stage: 1,
      checkpoint_path: '/cp/g1-b',
      gate_artifact: { type: 'niche_validation', niche_description: 'x' },
    });

    expect(res.status).toBe(200);
    expect(mockChatMessageUpdate).not.toHaveBeenCalled();
  });

  it('keeps the receipt and authorized apply durable when Redis delivery is ambiguous', async () => {
    jobRow.status = 'AWAITING_GATE';
    jobRow.gateStage = 1;
    jobRow.gateArtifact = { type: 'niche_validation', niche_description: 'x' };
    jobRow.phase1CheckpointPath = '/cp/g1-a';
    mockChatMessageCreate.mockResolvedValueOnce({ id: 'receipt-1' } as any);
    mockDeliverDispatchWork.mockRejectedValueOnce(new Error('redis down'));

    const res = await request(app)
      .post(`/api/jobs/${jobId}/gate-action`)
      .set(authHeaders)
      .send({ action: 'apply_stay', gateStage: 1, patch: { niche_description: 'never applied' } });

    expect(res.status).toBe(200);
    expect(res.body).toMatchObject({ deliveryPending: true, operationId: 'dispatch-test' });
    expect(mockChatMessageCreate).toHaveBeenCalledTimes(1);
    expect(jobRow.status).toBe('QUEUED');
    expect(mockChatMessageDelete).not.toHaveBeenCalled();
  });
});

// Non-entitled matrix (plan Phase C): gate-action 402 is asserted here since it's
// the new check added alongside this E2E test (also covered in isolation in
// jobs.gateAction.test.ts). The other two matrix cases already had dedicated
// coverage before this task and are not duplicated here:
//   - job-create chatMode coercion -> jobs.createChatMode.test.ts (4 cases)
//   - chat route 402 -> chat.test.ts's G3 baseline suite
describe('Guided research non-entitled matrix', () => {
  it('gate-action 402s a non-entitled user even mid-gate (subscription lapsed after job creation)', async () => {
    jobRow.status = 'AWAITING_GATE';
    jobRow.gateStage = 1;
    jobRow.gateArtifact = { type: 'niche_validation', niche_description: 'x' };
    jobRow.phase1CheckpointPath = '/cp/g1-a';
    mockIsEntitledUser.mockResolvedValue(false);

    const res = await request(app)
      .post(`/api/jobs/${jobId}/gate-action`)
      .set(authHeaders)
      .send({ action: 'continue', gateStage: 1 });

    expect(res.status).toBe(402);
    expect(res.body.code).toBe('NOT_ENTITLED');
    expect(jobRow.status).toBe('AWAITING_GATE'); // never flipped to QUEUED
    expect(mockDeliverDispatchWork).not.toHaveBeenCalled();
  });
});
