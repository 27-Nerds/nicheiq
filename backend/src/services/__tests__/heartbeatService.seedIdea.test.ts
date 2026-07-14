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

vi.mock('../jobService.js', () => ({
  failJob: (...a: any[]) => mockFailJob(...a),
  cancelSeedIdeaDispatch: (...a: any[]) => mockCancelSeedIdeaDispatch(...a),
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
}));

vi.mock('../progressBroadcastService.js', () => ({
  broadcastProgress: vi.fn(),
}));

const JOB_ID = 'job-1';

beforeEach(() => {
  vi.clearAllMocks();
  mockFailJob.mockResolvedValue({});
  mockCancelSeedIdeaDispatch.mockResolvedValue({ cancelled: true, creditRefunded: 2 });
});

describe('checkAndRecoverStaleJobs — SEED_IDEA op-scoped recovery', () => {
  it('a stale job with an active SEED_IDEA dispatch settles ONLY that dispatch — never calls failJob (parent job survives)', async () => {
    mockJobFindMany.mockResolvedValue([{
      id: JOB_ID, niche: 'test', userId: 'user-1', lastHeartbeat: new Date(0),
      startedAt: new Date(0), currentStage: 5, selectedSolutions: [],
      activeDispatchId: 'dispatch-1',
    }]);
    mockDispatchFindUnique.mockResolvedValue({
      id: 'dispatch-1', kind: 'SEED_IDEA', seedOrdinal: 2, sourceMessageId: 'msg-1',
    });

    const { checkAndRecoverStaleJobs } = await import('../heartbeatService.js');
    const stats = await checkAndRecoverStaleJobs();

    // sourceMessageId must be selected — cancelSeedIdeaDispatch needs it to key the
    // terminal `seed_settled` receipt back to the right chat card.
    expect(mockDispatchFindUnique).toHaveBeenCalledWith({
      where: { id: 'dispatch-1' },
      select: { id: true, kind: true, seedOrdinal: true, sourceMessageId: true },
    });
    expect(mockCancelSeedIdeaDispatch).toHaveBeenCalledWith(
      JOB_ID,
      { id: 'dispatch-1', kind: 'SEED_IDEA', seedOrdinal: 2, sourceMessageId: 'msg-1' },
      'RUNNING', 'SYSTEM_FAULT',
    );
    expect(mockFailJob).not.toHaveBeenCalled();
    expect(mockNotifyJobError).not.toHaveBeenCalled();
    expect(stats.checked).toBe(1);
  });

  it('a stale job with a non-seed active dispatch falls through to the normal whole-job failJob path', async () => {
    mockJobFindMany.mockResolvedValue([{
      id: JOB_ID, niche: 'test', userId: 'user-1', lastHeartbeat: new Date(0),
      startedAt: new Date(0), currentStage: 5, selectedSolutions: [],
      activeDispatchId: 'dispatch-1',
    }]);
    mockDispatchFindUnique.mockResolvedValue({ id: 'dispatch-1', kind: 'CONTINUE', seedOrdinal: null });

    const { checkAndRecoverStaleJobs } = await import('../heartbeatService.js');
    await checkAndRecoverStaleJobs();

    expect(mockFailJob).toHaveBeenCalledWith(JOB_ID, expect.any(String));
    expect(mockCancelSeedIdeaDispatch).not.toHaveBeenCalled();
  });

  it('a stale job with no active dispatch at all uses the normal whole-job failJob path (pre-existing behavior)', async () => {
    mockJobFindMany.mockResolvedValue([{
      id: JOB_ID, niche: 'test', userId: 'user-1', lastHeartbeat: new Date(0),
      startedAt: new Date(0), currentStage: 5, selectedSolutions: [],
      activeDispatchId: null,
    }]);

    const { checkAndRecoverStaleJobs } = await import('../heartbeatService.js');
    await checkAndRecoverStaleJobs();

    expect(mockDispatchFindUnique).not.toHaveBeenCalled();
    expect(mockFailJob).toHaveBeenCalledWith(JOB_ID, expect.any(String));
    expect(mockCancelSeedIdeaDispatch).not.toHaveBeenCalled();
  });
});
