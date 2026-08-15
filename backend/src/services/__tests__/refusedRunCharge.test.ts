import { describe, it, expect, vi, beforeEach } from 'vitest';
import express, { Express } from 'express';
import request from 'supertest';

/**
 * S15 — THE COMMERCIAL CONTRACT OF A REFUSAL. THIS FILE PINS BEHAVIOUR; IT DOES NOT ENDORSE IT.
 *
 * A `validate_idea` job is charged the FULL `discovery` stage at creation
 * (`creditService.ts:906` — `entryStage = chatMode ? 'guided_s1' : 'discovery'`, and
 * `types/job.ts` rejects `chatMode` on `entryMode === 'validate_idea'`, so an idea check is
 * always the plain discovery price).
 *
 * When the identity gate refuses, `research_flow._refuse_seed` (`:5596`) sets two state fields
 * and RETURNS `None`. All three of its call sites (`:5478`, `:5525`, `:5544`) `return` after
 * it; none raises. The refusal is deliberately non-fatal — Phase 1 finishes and the
 * alternatives pool ships — so the run terminates through the ordinary success endpoint,
 * `POST /api/workers/ideas-ready`, exactly as an unrefused run does.
 *
 * That endpoint contains no reference to a charge or a refund, and NO refund path anywhere in
 * the backend is keyed on `not_evaluated`: the string appears only in copy and prompt surfaces
 * (`emailService`, `notificationService`, `analystPromptContext`, `chat.ts`,
 * `currentSelectionContext`) and in none of `creditService`, `dispatchService`, `jobService`,
 * `paidPoolRecoveryService` or `workers.ts`. So the user pays in full for a run that graded
 * nothing, and the backend never learns the refusal happened except to write email copy.
 *
 * WHETHER THAT IS RIGHT IS THE OWNER'S CALL, NOT THIS FILE'S. The trade is real: the check
 * failed, but the alternatives pool shipped and has value. Ledger item S15 in
 * `docs/SEED_IDENTITY_REMEDIATION.md` lays out full refund / no refund with disclosure /
 * partial, with the cost and the code change each one implies.
 *
 * What this file guarantees is only that the answer is a DECISION. Before it, nothing in any
 * suite asserted anything about credits on a refused run, so moving the money — in either
 * direction, deliberately or by accident — was a silent change. Now it is a red test.
 *
 * The contrast that shows this is a choice rather than a mechanism: the adjacent in-selection
 * seed op refuses by RAISING, lands on `POST /api/workers/seed-idea-failed`
 * (`workers.ts:2475`), and refunds its `seed_idea_N` charge. Same program, same kind of
 * refusal, opposite commercial outcome. That asymmetry is pinned below too.
 */

const mockJobUpdateMany = vi.fn();
const mockJobFindUnique = vi.fn();
const mockUserFindUnique = vi.fn();
const mockJobDispatchUpdateMany = vi.fn();
const mockJobDispatchFindUnique = vi.fn();
const mockPrismaTransaction = vi.fn();

// Captured, not anonymous: the whole point is to assert these are NEVER called.
const mockRefundChargeInTx = vi.fn();
const mockRefundForStage = vi.fn();
const mockRefundForStageInTx = vi.fn();
const mockRefundForRegenerationStage = vi.fn();

const transactionClient = {
  job: { updateMany: (...args: any[]) => mockJobUpdateMany(...args) },
  jobDispatch: { updateMany: (...args: any[]) => mockJobDispatchUpdateMany(...args) },
  chatMessage: { create: vi.fn() },
};

vi.mock('../../services/db.js', () => ({
  prisma: {
    job: {
      updateMany: (...args: any[]) => mockJobUpdateMany(...args),
      findFirst: vi.fn(),
      findUnique: (...args: any[]) => mockJobFindUnique(...args),
      update: vi.fn(),
    },
    user: { findUnique: (...args: any[]) => mockUserFindUnique(...args) },
    jobDispatch: {
      findUnique: (...args: any[]) => mockJobDispatchFindUnique(...args),
      updateMany: (...args: any[]) => mockJobDispatchUpdateMany(...args),
    },
    chatMessage: { create: vi.fn() },
    $transaction: (callback: any) => mockPrismaTransaction(callback),
  },
}));

vi.mock('../../middleware/auth.js', () => ({
  requireInternalService: (_req: any, _res: any, next: any) => next(),
}));

vi.mock('../../services/progressBroadcastService.js', () => ({
  broadcastProgress: vi.fn(),
}));

vi.mock('../../services/notificationService.js', () => ({
  notifyJobStart: vi.fn(),
  notifySolutionsReady: vi.fn().mockResolvedValue(undefined),
  notifyJobFailed: vi.fn(),
  notifyReportReady: vi.fn(),
  notifySelectionReminder: vi.fn(),
}));

vi.mock('../../services/assetService.js', () => ({
  invalidatePreviewReportCache: vi.fn(),
}));

vi.mock('../../utils/errorTranslator.js', () => ({
  buildErrorDetails: vi.fn().mockReturnValue(null),
}));

vi.mock('../../services/creditService.js', () => ({
  refundChargeInTx: (...args: any[]) => mockRefundChargeInTx(...args),
  refundForStage: (...args: any[]) => mockRefundForStage(...args),
  refundForStageInTx: (...args: any[]) => mockRefundForStageInTx(...args),
  refundForRegenerationStage: (...args: any[]) => mockRefundForRegenerationStage(...args),
  isGuidedSegment: vi.fn(),
}));

let app: Express;
const jobId = '00000000-0000-0000-0000-000000000001';

beforeEach(async () => {
  vi.clearAllMocks();
  mockJobDispatchUpdateMany.mockResolvedValue({ count: 1 });
  mockPrismaTransaction.mockImplementation(async (callback: any) => callback(transactionClient));

  app = express();
  app.use(express.json());
  const { workersRouter } = await import('../../routes/workers.js');
  app.use('/api/workers', workersRouter);
});

/** The payload a REFUSED idea check delivers: Phase 1 completed, the pool shipped. */
const refusedRunPayload = {
  worker_id: 'w1',
  job_id: jobId,
  solutions: [{ solution_name: 'An alternative the pool produced' }],
  checkpoint_path: '/tmp/cp',
  total_to_validate: 3,
};

describe('S15 · a refused idea check keeps the charge — pinned, not endorsed', () => {
  it('completes to AWAITING_SELECTION and refunds NOTHING', async () => {
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockJobFindUnique.mockResolvedValue({
      userId: 'user-1',
      niche: 'my submitted pitch',
      entryMode: 'validate_idea',
    });
    mockUserFindUnique.mockResolvedValue({ email: 'buyer@example.com' });

    const response = await request(app)
      .post('/api/workers/ideas-ready')
      .send(refusedRunPayload);

    expect(response.status).toBe(200);

    // The run REACHES a terminal, user-visible, non-failed status…
    expect(mockJobUpdateMany).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({ id: jobId, status: 'RUNNING' }),
        data: expect.objectContaining({ status: 'AWAITING_SELECTION' }),
      }),
    );

    // …and not one credit goes back. If you are here because this line went red, you are
    // changing who keeps the money on a refused paid run. That is an owner decision (S15);
    // make it deliberately and update the ledger, do not just re-green the test.
    expect(mockRefundChargeInTx, 'a refund was issued on a refused run').not.toHaveBeenCalled();
    expect(mockRefundForStage).not.toHaveBeenCalled();
    expect(mockRefundForStageInTx).not.toHaveBeenCalled();
    expect(mockRefundForRegenerationStage).not.toHaveBeenCalled();
  });

  it('takes the SAME money path as an unrefused run — the endpoint cannot tell them apart', async () => {
    // The refusal is invisible here by construction: `ideas-ready` receives no idea-check
    // outcome at all. This is the mechanism behind "the backend never learns the refusal
    // happened" — not an oversight in one branch, but an absence of any input to branch on.
    const body = JSON.stringify(refusedRunPayload);
    expect(body).not.toMatch(/not_evaluated|user_idea_failure_reason|outcome/);

    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockJobFindUnique.mockResolvedValue({ userId: 'user-1', niche: 'n', entryMode: 'validate_idea' });
    mockUserFindUnique.mockResolvedValue({ email: 'buyer@example.com' });

    await request(app).post('/api/workers/ideas-ready').send(refusedRunPayload);
    const refusedCalls = mockJobUpdateMany.mock.calls.length;

    vi.clearAllMocks();
    mockJobDispatchUpdateMany.mockResolvedValue({ count: 1 });
    mockPrismaTransaction.mockImplementation(async (cb: any) => cb(transactionClient));
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockJobFindUnique.mockResolvedValue({ userId: 'user-1', niche: 'n', entryMode: null });
    mockUserFindUnique.mockResolvedValue({ email: 'buyer@example.com' });

    await request(app).post('/api/workers/ideas-ready').send(refusedRunPayload);

    expect(mockJobUpdateMany.mock.calls.length).toBe(refusedCalls);
    expect(mockRefundChargeInTx).not.toHaveBeenCalled();
  });
});

describe('S15 · the asymmetry with the adjacent seed op', () => {
  it('the in-selection seed op DOES refund when its birth fails', async () => {
    // Same program, same class of refusal, opposite commercial outcome — the contrast that
    // makes "no refund" a choice rather than an absence of machinery. `run_seed_idea` RAISES
    // on total birth failure; this endpoint settles the dispatch and refunds `seed_idea_N`.
    const dispatchId = '00000000-0000-4000-8000-000000000010';
    mockJobUpdateMany.mockResolvedValue({ count: 1 });
    mockRefundChargeInTx.mockResolvedValue({ id: 'refund-1', amount: 3 });
    mockRefundForStageInTx.mockResolvedValue({ id: 'refund-1', amount: 3 });
    mockJobDispatchUpdateMany.mockResolvedValue({ count: 1 });
    mockJobDispatchFindUnique.mockResolvedValue({
      id: dispatchId,
      jobId,
      chargeId: 'charge-seed_idea_2',
      seedOrdinal: 2,
    });
    mockJobFindUnique.mockResolvedValue({ userId: 'user-1', niche: 'n' });

    const res = await request(app)
      .post('/api/workers/seed-failed')
      .send({
        worker_id: 'w1',
        job_id: jobId,
        dispatch_id: dispatchId,
        error_message: 'seed birth produced no idea',
      });

    // The endpoint exists and reaches its refund machinery; a 404 here would mean this
    // contrast has moved and the S15 note in the ledger needs re-deriving.
    expect(res.status, 'seed-idea-failed endpoint moved').not.toBe(404);
    expect(
      mockRefundChargeInTx.mock.calls.length + mockRefundForStageInTx.mock.calls.length,
      'the seed op no longer refunds — the S15 asymmetry has changed',
    ).toBeGreaterThan(0);
  });
});
