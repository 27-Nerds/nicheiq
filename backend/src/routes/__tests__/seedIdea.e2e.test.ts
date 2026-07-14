import { describe, it, expect, vi, beforeEach } from 'vitest';
import express, { Express } from 'express';
import request from 'supertest';
import { randomUUID } from 'crypto';

// ============================================
// E2E: the FULL user-seed lifecycle (plans/eager-meandering-feather.md Phase 5/9)
// — chat proposes a seed -> POST /:jobId/seed-idea (charge + dispatch + receipt) -> worker
// claims it (/job-started) -> worker settles it (/seed-complete accepted|demoted, /seed-failed,
// or the user cancels it) — mounting BOTH jobsRouter and workersRouter in one app, same as
// gates.e2e.test.ts does for the guided-gate chain.
//
// Like gates.e2e.test.ts, this needs a STATEFUL mock: each hop's assertions and the next hop's
// behavior depend on what the PREVIOUS hop actually wrote, so job/dispatch state is backed by
// mutable `jobRow`/`dispatchRow` objects rather than a scripted `mockResolvedValueOnce` sequence.
//
// dispatchService.js and jobService.js are NOT mocked — openDispatch/claimDispatch/settleDispatch/
// dispatchGuard and cancelJob/cancelSeedIdeaDispatch all run for REAL against the state this file
// controls (mirrors jobs.seedIdea.test.ts's "dispatchService is real" comment, extended to
// jobService so the CANCEL hop exercises the real op-scoped cancellation branch too). Only
// creditService's charge/refund functions and the queue are stubbed — a seed's *pricing/ledger
// arithmetic* already has its own dedicated unit coverage (creditService.seedIdea.test.ts).
//
// HONEST GAP (do not read past this without noting it): a demoted seed does NOT enter
// Job.solutionIdeas at all (workers.ts's seed-complete only appends when
// `outcome === 'accepted'`) — settlement instead drops this process's in-memory preview-report
// cache (`invalidatePreviewReportCache`) so the NEXT read re-parses the worker's re-materialized
// asset. The demoted-path test below can only prove the pool stays untouched and the
// seed_settled receipt carries outcome='demoted'. It does NOT and CANNOT prove the "Examined &
// ruled out" panel renders a badged entry, because that finding (`reason`, `evidence`,
// `source_frame`, `dispatch_id`) lives in `UnifiedSolutionCrew.ruled_out_pains` — an in-memory
// list on the Python crew, persisted to the checkpoint and materialized into the SEPARATE
// preview-report JSON file this route only invalidates the CACHE of, never reads/writes the
// content of. None of that ever touches a Job column these two Express routes read/write, so a
// backend-only mock-DB E2E has no way to observe it. That delivery path already has its own
// coverage: tests/unit/crews/test_seed_pipeline.py::TestRuledOutSeedProvenance (source_frame/
// dispatch_id stamping) and the frontend's SelectionWorkbench.svelte (panel render/highlight).
// ============================================

const jobId = '00000000-0000-0000-0000-000000000001';
const userId = 'user-123';
const authHeaders = { 'x-user-id': userId };

type Row = Record<string, any>;
let jobRow: Row;
let dispatchRow: Row | null;
let receipts: Row[];

function resetState() {
  jobRow = {
    id: jobId,
    userId,
    niche: 'donor-advised fund management',
    status: 'AWAITING_SELECTION',
    seedIdeaCount: 0,
    phase1CheckpointPath: '/cp/phase1',
    // The existing pool this job reached AWAITING_SELECTION with.
    solutionIdeas: [{ solution_name: 'Existing Pool Idea', market_fit_score: 0.65 }],
    costUsd: 0,
    costSummary: null,
    activeDispatchId: null,
    queuedAt: null,
    lastHeartbeat: null,
    workerId: null,
    startedAt: null,
    selectedSolutions: [],
    ideasRegeneratedAt: null,
  };
  dispatchRow = null;
  receipts = [];
}

function matchesJobWhere(where: Record<string, any>): boolean {
  if (where.id !== undefined && where.id !== jobRow.id) return false;
  if (where.userId !== undefined && where.userId !== jobRow.userId) return false;
  if (where.status !== undefined) {
    if (typeof where.status === 'object' && where.status !== null && 'in' in where.status) {
      if (!where.status.in.includes(jobRow.status)) return false;
    } else if (where.status !== jobRow.status) {
      return false;
    }
  }
  if (where.seedIdeaCount !== undefined && where.seedIdeaCount !== (jobRow.seedIdeaCount ?? 0)) return false;
  if (where.activeDispatchId !== undefined && where.activeDispatchId !== (jobRow.activeDispatchId ?? null)) return false;
  return true;
}

function applyJobData(data: Record<string, any>) {
  for (const [key, value] of Object.entries(data)) {
    jobRow[key] = value;
  }
}

function matchesDispatchWhere(where: Record<string, any>): boolean {
  if (!dispatchRow) return false;
  if (where.id !== undefined && where.id !== dispatchRow.id) return false;
  if (where.OR) {
    const ok = (where.OR as Record<string, any>[]).some((cond) => {
      if (cond.state !== undefined && cond.state !== dispatchRow!.state) return false;
      if (cond.workerId !== undefined && cond.workerId !== dispatchRow!.workerId) return false;
      return true;
    });
    if (!ok) return false;
  }
  return true;
}

function applyDispatchData(data: Record<string, any>) {
  Object.assign(dispatchRow!, data);
}

// ---- shared spies: the SAME functions back both the top-level prisma client and every
// $transaction's tx client, so a write made inside a transaction is visible to the next hop
// (mirrors gates.e2e.test.ts / workers.seedIdea.test.ts's single-shared-client shape).
const mockJobFindFirst = vi.fn(async ({ where }: any) => (matchesJobWhere(where) ? { ...jobRow } : null));
const mockJobFindUnique = vi.fn(async ({ where, include }: any) => {
  if (where.id !== jobRow.id) return null;
  const row: Row = { ...jobRow };
  if (include?.user) row.user = { id: jobRow.userId, email: 'owner@example.com' };
  return row;
});
const mockJobUpdate = vi.fn(async ({ where, data }: any) => {
  if (where.id !== jobRow.id) throw new Error('Record not found');
  applyJobData(data);
  return { ...jobRow };
});
const mockJobUpdateMany = vi.fn(async ({ where, data }: any) => {
  if (!matchesJobWhere(where)) return { count: 0 };
  applyJobData(data);
  return { count: 1 };
});
const mockJobProgressUpdateMany = vi.fn(async (_a?: any) => ({ count: 0 }) as any);

const mockDispatchCreate = vi.fn(async ({ data }: any) => {
  const row: Row = {
    id: randomUUID(),
    state: 'AUTHORIZED',
    workerId: null,
    claimedAt: null,
    settledAt: null,
    failureKind: null,
    ...data,
  };
  dispatchRow = row;
  return { id: row.id };
});
const mockDispatchFindUnique = vi.fn(async ({ where }: any) => {
  if (!dispatchRow || dispatchRow.id !== where.id) return null;
  return { ...dispatchRow };
});
const mockDispatchUpdateMany = vi.fn(async ({ where, data }: any) => {
  if (!matchesDispatchWhere(where)) return { count: 0 };
  applyDispatchData(data);
  return { count: 1 };
});

const mockChatMessageCreate = vi.fn(async ({ data }: any) => {
  const row = { id: `receipt-${receipts.length + 1}`, ...data };
  receipts.push(row);
  return { id: row.id };
});
const mockChatMessageDelete = vi.fn(async ({ where }: any) => {
  receipts = receipts.filter((r) => r.id !== where.id);
  return {};
});

const mockTransaction = vi.fn(async (cb: any) => {
  const tx = {
    job: { findFirst: mockJobFindFirst, update: mockJobUpdate, updateMany: mockJobUpdateMany },
    jobDispatch: {
      create: mockDispatchCreate,
      findUnique: mockDispatchFindUnique,
      updateMany: mockDispatchUpdateMany,
    },
    chatMessage: { create: mockChatMessageCreate, delete: mockChatMessageDelete },
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
    jobDispatch: {
      create: (args: any) => mockDispatchCreate(args),
      findUnique: (args: any) => mockDispatchFindUnique(args),
      updateMany: (args: any) => mockDispatchUpdateMany(args),
    },
    jobProgress: { updateMany: (args: any) => mockJobProgressUpdateMany(args) },
    chatMessage: {
      create: (args: any) => mockChatMessageCreate(args),
      delete: (args: any) => mockChatMessageDelete(args),
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

const mockEnqueueSeedIdeaJob = vi.fn();
const mockRemoveFromQueue = vi.fn();
vi.mock('../../services/queueService.js', () => ({
  enqueueJob: vi.fn(),
  enqueueLandingPageJob: vi.fn(),
  enqueuePhase2Job: vi.fn(),
  enqueueRegenerateJob: vi.fn(),
  enqueueContinueFromGateJob: vi.fn(),
  enqueueSeedIdeaJob: (...a: any[]) => mockEnqueueSeedIdeaJob(...a),
  getQueueStats: vi.fn(),
  getQueueLength: vi.fn(),
  removeJobFromQueue: (...a: any[]) => mockRemoveFromQueue(...a),
}));

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

const mockChargeForSeedIdeaInTx = vi.fn();
const mockRefundForSeedIdeaStage = vi.fn();
vi.mock('../../services/creditService.js', () => ({
  createJobAndChargeDiscovery: vi.fn(),
  InsufficientCreditsError: MockInsufficientCreditsError,
  PriceChangedError: MockPriceChangedError,
  refundForStage: vi.fn(),
  refundForRegenerationStage: vi.fn(),
  chargeForStageInTx: vi.fn(),
  chargeForStageWithPriceCasInTx: vi.fn(),
  chargeForRegenerationInTx: vi.fn(),
  chargeForResume: vi.fn(),
  segmentForGateContinue: vi.fn(),
  chargeForSeedIdeaInTx: (...a: any[]) => mockChargeForSeedIdeaInTx(...a),
  refundForSeedIdeaStage: (...a: any[]) => mockRefundForSeedIdeaStage(...a),
  // jobService.js (real, unmocked below) also imports these two at module scope.
  determineFailedStage: vi.fn(),
  isGuidedSegment: vi.fn(),
}));

const mockIsEntitledUser = vi.fn();
vi.mock('../../services/catalogService.js', () => ({
  isEntitledUser: (...a: any[]) => mockIsEntitledUser(...a),
}));

const mockBroadcastProgress = vi.fn();
vi.mock('../../services/progressBroadcastService.js', () => ({
  broadcastProgress: (...a: any[]) => mockBroadcastProgress(...a),
}));

// job-started calls `.catch()` directly on notifyJobStart's return value — these must resolve
// to real promises, or a plain `vi.fn()` (returning undefined) throws synchronously and the
// route 500s before this file's later assertions even get a clean response to check.
vi.mock('../../services/notificationService.js', () => ({
  notifyJobStart: vi.fn().mockResolvedValue(undefined),
  notifyJobComplete: vi.fn().mockResolvedValue(undefined),
  notifyJobError: vi.fn().mockResolvedValue(undefined),
  notifySolutionsReady: vi.fn().mockResolvedValue(undefined),
  notifyGateReached: vi.fn().mockResolvedValue(undefined),
  notifyPhase2Start: vi.fn().mockResolvedValue(undefined),
  notifyRegenerationComplete: vi.fn().mockResolvedValue(undefined),
  notifyLandingPageReady: vi.fn().mockResolvedValue(undefined),
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

// jobService.js and dispatchService.js are DELIBERATELY left unmocked (see file header) — the
// CANCEL hop needs the real cancelJob -> cancelSeedIdeaDispatch branch, and every seed-idea hop
// needs the real openDispatch/claimDispatch/settleDispatch/dispatchGuard CAS plumbing.

let app: Express;

// The chat assistant message that PROPOSED this seed (plan step 1's "sourceMessageId") is a
// row `chat.ts` writes before any of these routes run — out of scope for this file. Here it is
// just the opaque id the seed card carries; SeedIdeaSchema only checks it is a 1-64 char string.
const validSeedBody = {
  free_text: 'A tool that flags donor lapses before year-end for small nonprofits',
  pain_ref: 'Manually tracking donor lapses in spreadsheets',
  tool_ref: 'Spreadsheets',
  sourceMessageId: 'msg-seed-1',
  expectedCost: 2,
};

async function submitSeed(overrides: Record<string, any> = {}) {
  return request(app)
    .post(`/api/jobs/${jobId}/seed-idea`)
    .set(authHeaders)
    .send({ ...validSeedBody, ...overrides });
}

async function claimAsWorker(workerId = 'w1') {
  const res = await request(app)
    .post('/api/workers/job-started')
    .send({ worker_id: workerId, job_id: jobId, dispatch_id: dispatchRow!.id });
  expect(res.status).toBe(200);
  return res;
}

function seedSettledReceipts() {
  return receipts.filter((r) => r.patchJson?.event === 'seed_settled');
}

beforeEach(async () => {
  vi.clearAllMocks();
  resetState();
  mockIsEntitledUser.mockResolvedValue(true);
  mockEnqueueSeedIdeaJob.mockResolvedValue(undefined);
  mockRemoveFromQueue.mockResolvedValue(undefined);
  mockRegisterWorkerHeartbeat.mockResolvedValue(undefined);
  mockChargeForSeedIdeaInTx.mockResolvedValue({ cost: 2, transaction: { id: 'txn-seed-1' } });
  mockRefundForSeedIdeaStage.mockResolvedValue({ amount: -2 });

  app = express();
  app.use(express.json());
  const { jobsRouter } = await import('../jobs.js');
  const { workersRouter } = await import('../workers.js');
  app.use('/api/jobs', jobsRouter);
  app.use('/api/workers', workersRouter);
});

describe('Seed idea E2E: full lifecycle', () => {
  it('happy path: submit -> worker claims -> accepted idea merges into the pool, charged once', async () => {
    // A job that regenerated earlier THIS run (ideasRegeneratedAt set, no selections) is exactly
    // the heuristic trap workers.ts's own comment warns about: without the SEED_IDEA dispatch-kind
    // override, job-started would misread this as isRegenerate and flip to REGENERATING.
    jobRow.ideasRegeneratedAt = new Date('2026-01-01');
    jobRow.selectedSolutions = [];

    // ── Hop 1: user submits the seed ──
    let res = await submitSeed();
    expect(res.status).toBe(200);
    expect(mockChargeForSeedIdeaInTx).toHaveBeenCalledTimes(1);
    expect(mockChargeForSeedIdeaInTx).toHaveBeenCalledWith(
      expect.anything(), userId, jobId, 1, jobRow.niche, 2,
    );
    expect(jobRow.status).toBe('QUEUED');
    expect(jobRow.seedIdeaCount).toBe(1);
    expect(dispatchRow).toBeTruthy();
    expect(dispatchRow!.kind).toBe('SEED_IDEA');
    expect(dispatchRow!.state).toBe('AUTHORIZED');
    expect(dispatchRow!.seedOrdinal).toBe(1);
    expect(dispatchRow!.sourceMessageId).toBe('msg-seed-1');
    expect(dispatchRow!.chargeId).toBe('txn-seed-1');
    expect(jobRow.activeDispatchId).toBe(dispatchRow!.id);
    const submittedReceipt = receipts.find((r) => r.patchJson?.event === 'seed_submitted');
    expect(submittedReceipt).toBeTruthy();
    expect(submittedReceipt!.patchJson.sourceMessageId).toBe('msg-seed-1');
    expect(mockEnqueueSeedIdeaJob).toHaveBeenCalledWith(
      jobId, '/cp/phase1', jobRow.niche,
      validSeedBody.free_text, validSeedBody.pain_ref, validSeedBody.tool_ref,
      dispatchRow!.id,
    );

    // ── Hop 2: worker claims the dispatch ──
    res = await claimAsWorker();
    expect(res.status).toBe(200);
    expect(dispatchRow!.state).toBe('CLAIMED');
    expect(dispatchRow!.workerId).toBe('w1');
    // The heuristic trap above must NOT win: a SEED_IDEA dispatch is exact, so this must be
    // plain RUNNING, never REGENERATING.
    expect(jobRow.status).toBe('RUNNING');

    // ── Hop 3: worker reports the seed accepted (birthed + scored, merged, saved) ──
    const seedIdea = { solution_name: 'AI Donor Lapse Alerts', candidate_status: 'active', market_fit_score: 0.72 };
    res = await request(app).post('/api/workers/seed-complete').send({
      worker_id: 'w1',
      job_id: jobId,
      idea: seedIdea,
      outcome: 'accepted',
      dispatch_id: dispatchRow!.id,
      cost_summary: { total_cost: 0.42 },
    });
    expect(res.status).toBe(200);
    // The seed IS in the pool — merged alongside what was already there.
    expect(jobRow.solutionIdeas).toEqual([
      { solution_name: 'Existing Pool Idea', market_fit_score: 0.65 },
      seedIdea,
    ]);
    expect(jobRow.costUsd).toBeCloseTo(0.42);
    expect(jobRow.status).toBe('AWAITING_SELECTION');
    expect(jobRow.activeDispatchId).toBeNull();
    expect(dispatchRow!.state).toBe('COMPLETED');
    const settled = seedSettledReceipts();
    expect(settled).toHaveLength(1);
    expect(settled[0].patchJson.outcome).toBe('accepted');
    expect(settled[0].patchJson.sourceMessageId).toBe('msg-seed-1');

    // Charged exactly once across the whole chain.
    expect(mockChargeForSeedIdeaInTx).toHaveBeenCalledTimes(1);
    expect(mockRefundForSeedIdeaStage).not.toHaveBeenCalled();
  });

  it('demoted path: settles honestly WITHOUT polluting the selectable pool', async () => {
    await submitSeed();
    await claimAsWorker();
    const poolBefore = [...jobRow.solutionIdeas];

    const demotedIdea = {
      solution_name: 'Niche Satellite Tracker',
      candidate_status: 'demoted',
      source_frame: 'user_seed',
      market_fit_score: 0.18,
    };
    const res = await request(app).post('/api/workers/seed-complete').send({
      worker_id: 'w1',
      job_id: jobId,
      idea: demotedIdea,
      outcome: 'demoted',
      dispatch_id: dispatchRow!.id,
    });

    expect(res.status).toBe(200);
    // A demoted seed does NOT enter Job.solutionIdeas (the selectable pool) — only an
    // ACCEPTED outcome is appended there (workers.ts:1211's `outcome === 'accepted'` branch).
    // The pool is untouched either way; the settlement is still honest and still terminal.
    expect(jobRow.solutionIdeas).toEqual(poolBefore);
    expect(jobRow.status).toBe('AWAITING_SELECTION');
    expect(dispatchRow!.state).toBe('COMPLETED');
    const settled = seedSettledReceipts();
    expect(settled).toHaveLength(1);
    expect(settled[0].patchJson.outcome).toBe('demoted');
    // See the file header HONEST GAP note: "user paid, must still see it" is NOT delivered via
    // Job.solutionIdeas for a demoted seed at all — the worker re-materializes the preview
    // report's `examined_ruled_out` ledger separately, and this route only drops this
    // process's in-memory cache of that asset (`invalidatePreviewReportCache`) so the next
    // read re-parses it. Neither the ruled-out record's CONTENT nor its delivery through that
    // asset is observable from a backend-only mock-DB E2E. Covered instead by
    // test_seed_pipeline.py::TestRuledOutSeedProvenance (source_frame/dispatch_id stamping)
    // and the frontend SelectionWorkbench component (panel render/highlight).
  });

  it('failure + refund: a pipeline failure reverts to AWAITING_SELECTION with the OLD pool intact', async () => {
    await submitSeed();
    await claimAsWorker();
    const poolBefore = [...jobRow.solutionIdeas];

    const res = await request(app).post('/api/workers/seed-failed').send({
      worker_id: 'w1',
      job_id: jobId,
      error_message: 'birth produced nothing',
      dispatch_id: dispatchRow!.id,
    });

    expect(res.status).toBe(200);
    expect(jobRow.status).toBe('AWAITING_SELECTION');
    expect(jobRow.solutionIdeas).toEqual(poolBefore); // untouched — nothing to merge
    expect(jobRow.activeDispatchId).toBeNull();
    // The exact numbered stage this attempt paid for (ordinal 1 -> seed_idea_1).
    expect(mockRefundForSeedIdeaStage).toHaveBeenCalledWith(jobId, 1);
    expect(dispatchRow!.state).toBe('REFUNDED'); // FAILED, then promoted once the credit is back
    const settled = seedSettledReceipts();
    expect(settled).toHaveLength(1);
    expect(settled[0].patchJson.outcome).toBe('failed');
  });
});

describe('Seed idea E2E: guard matrix', () => {
  it('missing expectedCost -> 400, nothing charged, no dispatch opened', async () => {
    const res = await submitSeed({ expectedCost: undefined });

    expect(res.status).toBe(400);
    expect(mockChargeForSeedIdeaInTx).not.toHaveBeenCalled();
    expect(dispatchRow).toBeNull();
    expect(jobRow.status).toBe('AWAITING_SELECTION');
  });

  it('price drift -> 409 PRICE_CHANGED, nothing charged, no dispatch opened', async () => {
    mockChargeForSeedIdeaInTx.mockRejectedValueOnce(new MockPriceChangedError(2, 5));

    const res = await submitSeed();

    expect(res.status).toBe(409);
    expect(res.body).toEqual(expect.objectContaining({ code: 'PRICE_CHANGED', expectedCost: 2, actualCost: 5 }));
    expect(dispatchRow).toBeNull();
    expect(jobRow.status).toBe('AWAITING_SELECTION');
    expect(jobRow.seedIdeaCount).toBe(0);
  });

  it('insufficient credits -> 402 with balance/required, no dispatch opened', async () => {
    mockChargeForSeedIdeaInTx.mockRejectedValueOnce(new MockInsufficientCreditsError(1, 2));

    const res = await submitSeed();

    expect(res.status).toBe(402);
    expect(res.body).toEqual(expect.objectContaining({ code: 'INSUFFICIENT_CREDITS', balance: 1, required: 2 }));
    expect(dispatchRow).toBeNull();
  });

  it('wrong status (job not AWAITING_SELECTION) -> 400, nothing charged', async () => {
    jobRow.status = 'RUNNING';

    const res = await submitSeed();

    expect(res.status).toBe(400);
    expect(res.body.status).toBe('RUNNING');
    expect(mockChargeForSeedIdeaInTx).not.toHaveBeenCalled();
    expect(dispatchRow).toBeNull();
  });

  it('a stale/duplicate seed-complete for an ALREADY-SETTLED dispatch is idempotent — no double merge, no double charge', async () => {
    await submitSeed();
    await claimAsWorker();
    const idea = { solution_name: 'AI Donor Lapse Alerts', candidate_status: 'active' };
    await request(app).post('/api/workers/seed-complete').send({
      worker_id: 'w1', job_id: jobId, idea, outcome: 'accepted', dispatch_id: dispatchRow!.id,
    });
    const poolAfterFirstSettle = [...jobRow.solutionIdeas];

    // A redelivered callback for the SAME (now-settled) dispatch arrives again.
    const res = await request(app).post('/api/workers/seed-complete').send({
      worker_id: 'w1', job_id: jobId, idea, outcome: 'accepted', dispatch_id: dispatchRow!.id,
    });

    expect(res.status).toBe(200);
    expect(res.body.idempotent).toBe(true);
    expect(jobRow.solutionIdeas).toEqual(poolAfterFirstSettle); // no double-merge
    expect(seedSettledReceipts()).toHaveLength(1); // no double receipt
    expect(mockChargeForSeedIdeaInTx).toHaveBeenCalledTimes(1); // no double charge
  });

  it('a seed-complete for a dispatch whose job was force-cancelled out from under it is dropped, not merged', async () => {
    await submitSeed();
    await claimAsWorker();
    // Simulate the job having been cancelled through some OTHER path while this exact dispatch
    // is still nominally active (cancelJob's own SEED_IDEA branch would never leave this
    // combination behind — it always clears activeDispatchId — so this exercises workers.ts's
    // own defensive CANCELLED check for a callback arriving on a since-cancelled job).
    jobRow.status = 'CANCELLED';
    const poolBefore = [...jobRow.solutionIdeas];

    const res = await request(app).post('/api/workers/seed-complete').send({
      worker_id: 'w1', job_id: jobId,
      idea: { solution_name: 'Should Not Merge' }, outcome: 'accepted', dispatch_id: dispatchRow!.id,
    });

    expect(res.status).toBe(200);
    expect(res.body).toEqual({ status: 'ok' }); // plain ok — not stale, not idempotent
    expect(jobRow.solutionIdeas).toEqual(poolBefore); // never merged
    expect(dispatchRow!.state).toBe('CLAIMED'); // never settled
  });

  it('enqueue failure after charge -> compensating refund, dispatch settled FAILED, receipt retracted', async () => {
    mockEnqueueSeedIdeaJob.mockRejectedValueOnce(new Error('Redis unavailable'));

    const res = await submitSeed();

    expect(res.status).toBe(500);
    // The user is not left charged for a seed that never actually started.
    expect(jobRow.status).toBe('AWAITING_SELECTION');
    expect(jobRow.activeDispatchId).toBeNull();
    expect(dispatchRow!.state).toBe('FAILED');
    expect(mockRefundForSeedIdeaStage).toHaveBeenCalledWith(jobId, 1);
    expect(receipts).toHaveLength(0); // the seed_submitted receipt was retracted
  });

  it('cancelling a QUEUED seed refunds it, restores AWAITING_SELECTION, and the PARENT JOB SURVIVES', async () => {
    await submitSeed();
    expect(jobRow.status).toBe('QUEUED'); // the seed op's own status, not the worker having claimed it
    const poolBefore = [...jobRow.solutionIdeas];

    const res = await request(app)
      .post(`/api/jobs/${jobId}/cancel`)
      .set(authHeaders)
      .send({});

    expect(res.status).toBe(200);
    expect(res.body).toEqual(
      expect.objectContaining({ status: 'cancelled', creditRefunded: 2 }),
    );
    // Never the whole-job CANCELLED path — a paid follow-up request being cancelled must not
    // destroy an already-settled, already-selectable research run.
    expect(jobRow.status).toBe('AWAITING_SELECTION');
    expect(jobRow.status).not.toBe('CANCELLED');
    expect(jobRow.activeDispatchId).toBeNull();
    expect(jobRow.solutionIdeas).toEqual(poolBefore); // pool intact — the seed never merged
    expect(dispatchRow!.state).toBe('REFUNDED');
    expect(mockRefundForSeedIdeaStage).toHaveBeenCalledWith(jobId, 1);
    expect(mockRemoveFromQueue).toHaveBeenCalledWith(jobId); // it was QUEUED — pulled from redis too
  });
});
