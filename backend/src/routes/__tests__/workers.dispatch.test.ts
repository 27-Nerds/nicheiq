/**
 * Dispatch identity on worker callbacks.
 *
 * These are the regression tests for the races the guided flow actually had. Each one fails
 * against the pre-dispatch code:
 *
 *  - a delayed callback from a superseded attempt rewound a healthy job
 *  - a MATCHING callback arriving after cancellation resurrected a cancelled job
 *    (this is why the CAS is on dispatch AND status — either alone is exploitable)
 *  - /job-started waved a second worker through onto a job that was already RUNNING
 *  - a stale /gate-failed from attempt A reverted attempt B and burned B's apply budget
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';
import express from 'express';
import request from 'supertest';

const mockJobUpdateMany = vi.fn();
const mockJobFindUnique = vi.fn();
const mockJobUpdate = vi.fn(async (_a?: any) => ({}) as any);
const mockChatMessageFindFirst = vi.fn(async (_a?: any) => null as any);
const mockChatMessageUpdate = vi.fn(async (_a?: any) => ({}) as any);
const mockChatMessageDelete = vi.fn(async (_a?: any) => ({}) as any);
const mockDispatchFindUnique = vi.fn();
const mockDispatchUpdateMany = vi.fn(async (_a?: any) => ({ count: 1 }) as any);

vi.mock('../../services/db.js', () => {
  const client: any = {
    job: {
      updateMany: (a: any) => mockJobUpdateMany(a),
      findUnique: (a: any) => mockJobFindUnique(a),
      findFirst: vi.fn(),
      update: (a: any) => mockJobUpdate(a),
    },
    user: { findUnique: vi.fn(async () => null) },
    chatMessage: {
      findFirst: (a: any) => mockChatMessageFindFirst(a),
      update: (a: any) => mockChatMessageUpdate(a),
      delete: (a: any) => mockChatMessageDelete(a),
    },
    jobDispatch: {
      findUnique: (a: any) => mockDispatchFindUnique(a),
      updateMany: (a: any) => mockDispatchUpdateMany(a),
      create: vi.fn(async () => ({ id: 'new-dispatch' })),
    },
  };
  client.$transaction = (arg: any) => (typeof arg === 'function' ? arg(client) : Promise.all(arg));
  return { prisma: client };
});

vi.mock('../../middleware/auth.js', () => ({
  requireInternalService: (_r: any, _s: any, n: any) => n(),
  requireInternalAuth: (_r: any, _s: any, n: any) => n(),
  requireAuth: (_r: any, _s: any, n: any) => n(),
}));
vi.mock('../../services/heartbeatService.js', () => ({
  registerWorkerHeartbeat: vi.fn(async () => {}),
  updateWorkerHeartbeat: vi.fn(async () => {}),
  cleanupStaleWorkers: vi.fn(async () => {}),
}));
vi.mock('../../services/jobService.js', () => ({
  failJob: vi.fn(async () => {}),
  updateStageProgress: vi.fn(async () => {}),
  completeJob: vi.fn(async () => {}),
  getJob: vi.fn(async () => null),
  addJobAsset: vi.fn(async () => {}),
  getJobAsset: vi.fn(async () => null),
}));
vi.mock('../../services/creditService.js', () => ({
  refundForStage: vi.fn(async () => null),
  refundForRegenerationStage: vi.fn(async () => null),
}));
vi.mock('../../services/progressBroadcastService.js', () => ({ broadcastProgress: vi.fn() }));
vi.mock('../../services/notificationService.js', () => ({
  notifySolutionsReady: vi.fn(),
  notifyPhase2Start: vi.fn(),
  notifyRegenerationComplete: vi.fn(),
  notifyLandingPageReady: vi.fn(),
  notifyJobStart: vi.fn(),
  notifyJobComplete: vi.fn(),
  notifyJobError: vi.fn(),
  notifyGateReached: vi.fn(),
}));

const JOB = '00000000-0000-0000-0000-0000000000aa';
const MINE = '11111111-1111-1111-1111-111111111111';
const THEIRS = '22222222-2222-2222-2222-222222222222';

const gateBody = (dispatch_id?: string) => ({
  worker_id: 'worker-1',
  job_id: JOB,
  gate_stage: 1 as const,
  checkpoint_path: '/tmp/ckpt.json',
  gate_artifact: { niche: 'x' },
  ...(dispatch_id ? { dispatch_id } : {}),
});

let app: express.Express;

beforeEach(async () => {
  vi.clearAllMocks();
  mockDispatchUpdateMany.mockResolvedValue({ count: 1 });
  mockChatMessageFindFirst.mockResolvedValue(null);
  const { workersRouter } = await import('../workers.js');
  app = express();
  app.use(express.json());
  app.use('/api/workers', workersRouter);
});

describe('worker callbacks are dispatch-addressed', () => {
  it('gate-reached from a SUPERSEDED dispatch changes nothing', async () => {
    // The CAS matches no rows because the job's active dispatch is a different attempt.
    mockJobUpdateMany.mockResolvedValue({ count: 0 });
    mockJobFindUnique.mockResolvedValue({
      status: 'RUNNING',
      gateStage: 1,
      gateReachedAt: new Date(),
      activeDispatchId: THEIRS, // the job has moved on to another attempt
    });

    const res = await request(app).post('/api/workers/gate-reached').send(gateBody(MINE));

    expect(res.status).toBe(200);
    expect(res.body.stale).toBe(true);
    // The guard was actually in the predicate — not merely checked afterwards.
    expect(mockJobUpdateMany).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({ id: JOB, activeDispatchId: MINE }),
      }),
    );
  });

  it('a MATCHING gate-reached arriving after cancellation does not resurrect the job', async () => {
    // The nastiest case, and the reason the CAS carries status as well as the dispatch id.
    // Cancel writes CANCELLED but leaves the dispatch id alone, so a token-only predicate would
    // still match here and drag the job back to AWAITING_GATE.
    mockJobUpdateMany.mockResolvedValue({ count: 0 }); // status guard rejected it
    mockJobFindUnique.mockResolvedValue({
      status: 'CANCELLED',
      gateStage: 1,
      gateReachedAt: null,
      activeDispatchId: MINE, // token MATCHES — only the status saves us
    });

    const res = await request(app).post('/api/workers/gate-reached').send(gateBody(MINE));

    expect(res.status).toBe(200);
    // Whatever we answer, the one thing that must not happen is a write.
    const wrote = mockJobUpdateMany.mock.calls.some(
      ([arg]: any[]) => arg?.data?.status === 'AWAITING_GATE' && arg?.where?.status === undefined,
    );
    expect(wrote).toBe(false);
    // And the status predicate must be present in the attempted CAS.
    expect(mockJobUpdateMany).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({
          status: { in: ['RUNNING', 'QUEUED'] },
          activeDispatchId: MINE,
        }),
      }),
    );
  });

  it('gate-failed from a superseded dispatch does not revert the current attempt', async () => {
    // Previously a delayed failure from apply-attempt A reverted attempt B — and burned B's
    // steering budget with it.
    mockDispatchFindUnique.mockResolvedValue({ id: MINE, kind: 'APPLY_STAY', gateStage: 1 });
    mockJobUpdateMany.mockResolvedValue({ count: 0 });
    mockJobFindUnique.mockResolvedValue({
      status: 'RUNNING',
      gateStage: 1,
      activeDispatchId: THEIRS,
    });

    const res = await request(app).post('/api/workers/gate-failed').send({
      worker_id: 'worker-1',
      job_id: JOB,
      gate_stage: 1,
      error_message: 'boom',
      dispatch_id: MINE,
    });

    expect(res.status).toBe(200);
    expect(res.body.stale).toBe(true);
    // No revert, and crucially no decrement of somebody else's apply budget.
    const decremented = mockJobUpdateMany.mock.calls.some(
      ([arg]: any[]) => arg?.data?.gateApplyCount !== undefined && arg?.where?.activeDispatchId !== MINE,
    );
    expect(decremented).toBe(false);
  });

  it('a failed apply_stay gives the steering budget back', async () => {
    // Five infra failures used to permanently burn a user's five applies without a single
    // successful change. The budget means SUCCESSFUL applies.
    mockDispatchFindUnique.mockResolvedValue({ id: MINE, kind: 'APPLY_STAY', gateStage: 1 });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });

    const res = await request(app).post('/api/workers/gate-failed').send({
      worker_id: 'worker-1',
      job_id: JOB,
      gate_stage: 1,
      error_message: 'llm exploded',
      dispatch_id: MINE,
      failure_kind: 'SYSTEM_FAULT',
    });

    expect(res.status).toBe(200);
    expect(mockJobUpdateMany).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({ gateApplyCount: { decrement: 1 } }),
      }),
    );
  });

  it('a failed CONTINUE does not touch the apply budget', async () => {
    mockDispatchFindUnique.mockResolvedValue({ id: MINE, kind: 'CONTINUE', gateStage: 1 });
    mockJobUpdateMany.mockResolvedValue({ count: 1 });

    await request(app).post('/api/workers/gate-failed').send({
      worker_id: 'worker-1',
      job_id: JOB,
      gate_stage: 1,
      error_message: 'boom',
      dispatch_id: MINE,
      failure_kind: 'SYSTEM_FAULT',
    });

    const touched = mockJobUpdateMany.mock.calls.some(
      ([arg]: any[]) => arg?.data?.gateApplyCount !== undefined,
    );
    expect(touched).toBe(false);
  });

  it('ideas-ready is guarded too — it is where a guided G2 continue actually lands', async () => {
    // Guarding only the two gate endpoints would have left the entire G2 continuation open,
    // because a G2 Continue runs on to stage 5 and terminates at /ideas-ready, not /gate-reached.
    mockJobUpdateMany.mockResolvedValue({ count: 0 });
    mockJobFindUnique.mockResolvedValue({ status: 'RUNNING', activeDispatchId: THEIRS });

    await request(app).post('/api/workers/ideas-ready').send({
      worker_id: 'worker-1',
      job_id: JOB,
      solutions: [{ solution_name: 'idea' }],
      checkpoint_path: '/tmp/c.json',
      dispatch_id: MINE,
    });

    expect(mockJobUpdateMany).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({ activeDispatchId: MINE }),
      }),
    );
  });

  it('a legacy worker (no dispatch id) may only act on a job with no active dispatch', async () => {
    // The narrow legacy path. Absence of an id is NOT a free pass — if it were, one surviving old
    // worker anywhere in the fleet would reinstate every race for as long as it lived.
    mockJobUpdateMany.mockResolvedValue({ count: 1 });

    await request(app).post('/api/workers/gate-reached').send(gateBody(undefined));

    expect(mockJobUpdateMany).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({ activeDispatchId: null }),
      }),
    );
  });
});

/**
 * Cross-flow guard: the three flows this system actually runs.
 *
 * The rule is uniform — EVERY queue message carries a dispatch, so every callback is addressable.
 * Getting this wrong is not theoretical: an earlier version of this change minted a dispatch only
 * at job creation and gate-action, which silently broke RESUME. A resumed job still carried the
 * activeDispatchId of the run that had just failed (nothing clears it), so the resuming worker —
 * which sent no id — was rejected as stale on every callback. The resume "queued" and then did
 * absolutely nothing.
 */
describe('the guard holds across all three flows', () => {
  it('rejects a worker whose id does not match the job (the resume bug, generalised)', async () => {
    // Job carries dispatch from a PREVIOUS attempt; this worker reports with no id at all.
    mockJobUpdateMany.mockResolvedValue({ count: 0 });
    mockJobFindUnique.mockResolvedValue({
      status: 'RUNNING',
      gateStage: 1,
      gateReachedAt: null,
      activeDispatchId: THEIRS,
    });

    const res = await request(app).post('/api/workers/gate-reached').send(gateBody(undefined));

    // Must NOT be waved through just because it claimed nothing.
    expect(res.body.stale).toBe(true);
    expect(mockJobUpdateMany).toHaveBeenCalledWith(
      expect.objectContaining({ where: expect.objectContaining({ activeDispatchId: null }) }),
    );
  });

  it('accepts a matching dispatch — the normal case for every flow', async () => {
    mockJobUpdateMany.mockResolvedValue({ count: 1 });

    const res = await request(app).post('/api/workers/gate-reached').send(gateBody(MINE));

    expect(res.status).toBe(200);
    expect(res.body.stale).toBeUndefined();
    expect(mockJobUpdateMany).toHaveBeenCalledWith(
      expect.objectContaining({ where: expect.objectContaining({ activeDispatchId: MINE }) }),
    );
  });
});
