/**
 * heartbeatService's stale-job recovery — op-scoped for a SEED_IDEA dispatch (plan:
 * eager-meandering-feather.md Phase 5, "op-scoped cancel + heartbeat"). A crashed worker mid-
 * seed must not fail the WHOLE research job (the pre-existing behavior, still correct for
 * every other stale job): it must settle just that dispatch, refund seed_idea_N, and restore
 * AWAITING_SELECTION with the pool intact — mirroring cancelJob's own SEED_IDEA branch via the
 * SAME shared helper (cancelSeedIdeaDispatch).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';

const mockJobFindMany = vi.fn();
const mockDispatchFindUnique = vi.fn();

vi.mock('../db.js', () => ({
  prisma: {
    job: { findMany: (...a: any[]) => mockJobFindMany(...a) },
    jobDispatch: { findUnique: (...a: any[]) => mockDispatchFindUnique(...a) },
    // getUserEmail — not under test here, just needs to resolve without throwing.
    user: { findUnique: vi.fn().mockResolvedValue(null) },
  },
}));

const mockFailJob = vi.fn();
const mockCancelSeedIdeaDispatch = vi.fn();
const mockCancelRegenerationDispatch = vi.fn();

vi.mock('../jobService.js', () => ({
  failJob: (...a: any[]) => mockFailJob(...a),
  cancelSeedIdeaDispatch: (...a: any[]) => mockCancelSeedIdeaDispatch(...a),
  cancelRegenerationDispatch: (...a: any[]) => mockCancelRegenerationDispatch(...a),
}));

const mockNotifyJobError = vi.fn();

vi.mock('../notificationService.js', () => ({
  notifyJobError: (...a: any[]) => mockNotifyJobError(...a),
}));

vi.mock('../../utils/phaseContext.js', () => ({
  getPhaseContext: vi.fn().mockReturnValue({}),
}));

vi.mock('../creditService.js', () => ({
  refundForStage: vi.fn(),
  refundChargeInTx: vi.fn(),
}));

vi.mock('../progressBroadcastService.js', () => ({
  broadcastProgress: vi.fn(),
}));

const JOB_ID = 'job-1';

beforeEach(() => {
  vi.clearAllMocks();
  mockFailJob.mockResolvedValue({ applied: true, job: { status: 'FAILED' } });
  mockCancelSeedIdeaDispatch.mockResolvedValue({ cancelled: true, creditRefunded: 2 });
  mockCancelRegenerationDispatch.mockResolvedValue({ cancelled: true, creditRefunded: 2 });
});

describe('checkAndRecoverStaleJobs — SEED_IDEA op-scoped recovery', () => {
  it('a stale job with an active SEED_IDEA dispatch settles ONLY that dispatch — never calls failJob (parent job survives)', async () => {
    mockJobFindMany.mockResolvedValue([{
      id: JOB_ID, niche: 'test', userId: 'user-1', lastHeartbeat: new Date(0),
      startedAt: new Date(0), currentStage: 5, selectedSolutions: [],
      activeDispatchId: 'dispatch-1', status: 'RUNNING',
    }]);
    mockDispatchFindUnique.mockResolvedValue({
      id: 'dispatch-1', kind: 'SEED_IDEA', seedOrdinal: 2, sourceMessageId: 'msg-1',
    });

    const { checkAndRecoverStaleJobs } = await import('../heartbeatService.js');
    const stats = await checkAndRecoverStaleJobs();

    // sourceMessageId must be selected — cancelSeedIdeaDispatch needs it to key the
    // terminal `seed_settled` receipt back to the right chat card. segment/chargeId are for
    // the REGENERATE branch, which shares this one read.
    expect(mockDispatchFindUnique).toHaveBeenCalledWith({
      where: { id: 'dispatch-1' },
      select: {
        id: true,
        kind: true,
        seedOrdinal: true,
        sourceMessageId: true,
        segment: true,
        chargeId: true,
      },
    });
    expect(mockCancelSeedIdeaDispatch).toHaveBeenCalledWith(
      JOB_ID,
      { id: 'dispatch-1', kind: 'SEED_IDEA', seedOrdinal: 2, sourceMessageId: 'msg-1' },
      'RUNNING', 'SYSTEM_FAULT',
      { status: 'RUNNING', lastHeartbeat: new Date(0) },
    );
    expect(mockFailJob).not.toHaveBeenCalled();
    expect(mockNotifyJobError).not.toHaveBeenCalled();
    expect(stats.checked).toBe(1);
  });

  it('a stale REGENERATE dispatch restores selection instead of failing the parent job', async () => {
    mockJobFindMany.mockResolvedValue([{
      id: JOB_ID, niche: 'test', userId: 'user-1', lastHeartbeat: new Date(0),
      startedAt: new Date(0), currentStage: 5, selectedSolutions: [],
      activeDispatchId: 'dispatch-2', status: 'REGENERATING',
    }]);
    mockDispatchFindUnique.mockResolvedValue({
      id: 'dispatch-2',
      kind: 'REGENERATE',
      seedOrdinal: null,
      sourceMessageId: null,
      segment: 'regenerate_ideas_3',
    });

    const { checkAndRecoverStaleJobs } = await import('../heartbeatService.js');
    await checkAndRecoverStaleJobs();

    expect(mockCancelRegenerationDispatch).toHaveBeenCalledWith(
      JOB_ID,
      { id: 'dispatch-2', segment: 'regenerate_ideas_3' },
      'REGENERATING',
      'SYSTEM_FAULT',
      { status: 'REGENERATING', lastHeartbeat: new Date(0) },
    );
    expect(mockFailJob).not.toHaveBeenCalled();
  });

  it('forwards the job ACTUAL status so a still-QUEUED stale batch gets dequeued', async () => {
    // cancelRegenerationDispatch only drops the Redis entry when it is told the batch was
    // QUEUED. Hardcoding REGENERATING here would orphan it for a worker to claim and run
    // after the batch had already been refunded.
    mockJobFindMany.mockResolvedValue([{
      id: JOB_ID, niche: 'test', userId: 'user-1', lastHeartbeat: new Date(0),
      startedAt: new Date(0), currentStage: 5, selectedSolutions: [],
      activeDispatchId: 'dispatch-3', status: 'QUEUED',
    }]);
    mockDispatchFindUnique.mockResolvedValue({
      id: 'dispatch-3',
      kind: 'REGENERATE',
      seedOrdinal: null,
      sourceMessageId: null,
      segment: 'regenerate_ideas_4',
    });

    const { checkAndRecoverStaleJobs } = await import('../heartbeatService.js');
    await checkAndRecoverStaleJobs();

    expect(mockCancelRegenerationDispatch).toHaveBeenCalledWith(
      JOB_ID,
      { id: 'dispatch-3', segment: 'regenerate_ideas_4' },
      'QUEUED',
      'SYSTEM_FAULT',
      { status: 'QUEUED', lastHeartbeat: new Date(0) },
    );
    expect(mockFailJob).not.toHaveBeenCalled();
  });

  it('a stale job with a non-seed active dispatch falls through to the normal whole-job failJob path', async () => {
    mockJobFindMany.mockResolvedValue([{
      id: JOB_ID, niche: 'test', userId: 'user-1', lastHeartbeat: new Date(0),
      startedAt: new Date(0), currentStage: 5, selectedSolutions: [],
      activeDispatchId: 'dispatch-1', status: 'RUNNING',
    }]);
    mockDispatchFindUnique.mockResolvedValue({ id: 'dispatch-1', kind: 'CONTINUE', seedOrdinal: null });

    const { checkAndRecoverStaleJobs } = await import('../heartbeatService.js');
    await checkAndRecoverStaleJobs();

    expect(mockFailJob).toHaveBeenCalledWith(
      JOB_ID,
      expect.any(String),
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      'dispatch-1',
      { status: 'RUNNING', lastHeartbeat: new Date(0) },
    );
    expect(mockCancelSeedIdeaDispatch).not.toHaveBeenCalled();
  });

  it('a stale job with no active dispatch at all uses the normal whole-job failJob path (pre-existing behavior)', async () => {
    mockJobFindMany.mockResolvedValue([{
      id: JOB_ID, niche: 'test', userId: 'user-1', lastHeartbeat: new Date(0),
      startedAt: new Date(0), currentStage: 5, selectedSolutions: [],
      activeDispatchId: null, status: 'RUNNING',
    }]);

    const { checkAndRecoverStaleJobs } = await import('../heartbeatService.js');
    await checkAndRecoverStaleJobs();

    expect(mockDispatchFindUnique).not.toHaveBeenCalled();
    expect(mockFailJob).toHaveBeenCalledWith(
      JOB_ID,
      expect.any(String),
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      { status: 'RUNNING', lastHeartbeat: new Date(0) },
    );
    expect(mockCancelSeedIdeaDispatch).not.toHaveBeenCalled();
  });
});
