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
const mockWorkerHeartbeatFindUnique = vi.fn();

vi.mock('../db.js', () => ({
  prisma: {
    job: { findMany: (...a: any[]) => mockJobFindMany(...a) },
    jobDispatch: { findUnique: (...a: any[]) => mockDispatchFindUnique(...a) },
    workerHeartbeat: { findUnique: (...a: any[]) => mockWorkerHeartbeatFindUnique(...a) },
    // getUserEmail — not under test here, just needs to resolve without throwing.
    user: { findUnique: vi.fn().mockResolvedValue(null) },
  },
}));

const mockEnqueuePaidPoolRecovery = vi.fn();
vi.mock('../queueService.js', () => ({
  enqueuePaidPoolRecovery: (...a: any[]) => mockEnqueuePaidPoolRecovery(...a),
}));

const mockFencePaidPoolMutationForRecovery = vi.fn();
const mockRefencePaidPoolRecovery = vi.fn();
const mockFailUnpreparedPaidPoolMutation = vi.fn();
vi.mock('../paidPoolRecoveryService.js', () => ({
  fencePaidPoolMutationForRecovery: (...a: any[]) => mockFencePaidPoolMutationForRecovery(...a),
  failUnpreparedPaidPoolMutation: (...a: any[]) => mockFailUnpreparedPaidPoolMutation(...a),
  refencePaidPoolRecovery: (...a: any[]) => mockRefencePaidPoolRecovery(...a),
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
  mockWorkerHeartbeatFindUnique.mockResolvedValue(null);
  mockFencePaidPoolMutationForRecovery.mockResolvedValue({
    recoveryToken: '22222222-2222-4222-8222-222222222222',
    journal: { schemaVersion: 1, lockPath: '/tmp/lock', files: [] },
  });
  mockEnqueuePaidPoolRecovery.mockResolvedValue(undefined);
  mockFailUnpreparedPaidPoolMutation.mockResolvedValue(true);
});

describe('checkAndRecoverStaleJobs — SEED_IDEA op-scoped recovery', () => {
  it('fences a dead prepared SEED_IDEA writer and schedules restore before any refund', async () => {
    const staleAt = new Date(Date.now() - 120_000);
    mockJobFindMany.mockResolvedValue([{
      id: JOB_ID, niche: 'test', userId: 'user-1', lastHeartbeat: staleAt,
      startedAt: staleAt, currentStage: 5, selectedSolutions: [], workerId: 'worker-dead',
      activeDispatchId: 'dispatch-1', status: 'RUNNING',
    }]);
    mockDispatchFindUnique.mockResolvedValue({
      id: 'dispatch-1', kind: 'SEED_IDEA', state: 'CLAIMED', workerId: 'worker-dead',
      seedOrdinal: 2, sourceMessageId: 'msg-1', recoveryPreparedAt: new Date(),
      recoveryJournal: { schemaVersion: 1, lockPath: '/tmp/lock', files: [] },
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
        state: true,
        seedOrdinal: true,
        sourceMessageId: true,
        segment: true,
        chargeId: true,
        workerId: true,
        recoveryPreparedAt: true,
        recoveryJournal: true,
        recoveryToken: true,
        lastDeliveryAt: true,
        claimedAt: true,
        createdAt: true,
      },
    });
    expect(mockFencePaidPoolMutationForRecovery).toHaveBeenCalledWith(
      JOB_ID,
      'dispatch-1',
      { status: 'RUNNING', workerId: 'worker-dead', lastHeartbeat: staleAt },
    );
    expect(mockEnqueuePaidPoolRecovery).toHaveBeenCalledWith(
      JOB_ID,
      'dispatch-1',
      '22222222-2222-4222-8222-222222222222',
      expect.objectContaining({ schemaVersion: 1 }),
    );
    expect(mockCancelSeedIdeaDispatch).not.toHaveBeenCalled();
    expect(mockFailJob).not.toHaveBeenCalled();
    expect(mockNotifyJobError).not.toHaveBeenCalled();
    expect(stats.checked).toBe(1);
    expect(stats.failed).toBe(1);
    expect(stats.timedOut).toBe(0);
  });

  it('does not recover a fresh REGENERATE just because the parent job started long ago', async () => {
    mockJobFindMany.mockResolvedValue([{
      id: JOB_ID, niche: 'test', userId: 'user-1', lastHeartbeat: new Date(0),
      startedAt: new Date(0), currentStage: 5, selectedSolutions: [],
      activeDispatchId: 'dispatch-2', status: 'REGENERATING', workerId: 'worker-live',
    }]);
    mockDispatchFindUnique.mockResolvedValue({
      id: 'dispatch-2',
      kind: 'REGENERATE',
      state: 'CLAIMED',
      workerId: 'worker-live',
      recoveryPreparedAt: new Date(),
      recoveryJournal: { schemaVersion: 1, lockPath: '/tmp/lock', files: [] },
      seedOrdinal: null,
      sourceMessageId: null,
      segment: 'regenerate_ideas_3',
      claimedAt: new Date(),
      createdAt: new Date(),
    });
    mockWorkerHeartbeatFindUnique.mockResolvedValue({
      currentJobId: JOB_ID,
      status: 'active',
      lastHeartbeat: new Date(),
    });

    const { checkAndRecoverStaleJobs } = await import('../heartbeatService.js');
    await checkAndRecoverStaleJobs();

    expect(mockCancelRegenerationDispatch).not.toHaveBeenCalled();
    expect(mockFencePaidPoolMutationForRecovery).not.toHaveBeenCalled();
    expect(mockEnqueuePaidPoolRecovery).not.toHaveBeenCalled();
    expect(mockFailJob).not.toHaveBeenCalled();
  });

  it('fences a prepared operation after its own hard runtime even with fresh heartbeats', async () => {
    const freshHeartbeat = new Date();
    mockJobFindMany.mockResolvedValue([{
      id: JOB_ID, niche: 'test', userId: 'user-1', lastHeartbeat: freshHeartbeat,
      startedAt: new Date(0), currentStage: 5, selectedSolutions: [],
      activeDispatchId: 'dispatch-hard-timeout', status: 'REGENERATING', workerId: 'worker-live',
    }]);
    mockDispatchFindUnique.mockResolvedValue({
      id: 'dispatch-hard-timeout',
      kind: 'REGENERATE',
      state: 'CLAIMED',
      workerId: 'worker-live',
      recoveryPreparedAt: new Date(),
      recoveryJournal: { schemaVersion: 1, lockPath: '/tmp/lock', files: [] },
      recoveryToken: null,
      claimedAt: new Date(0),
      createdAt: new Date(0),
      seedOrdinal: null,
      sourceMessageId: null,
      segment: 'regenerate_ideas_3',
    });
    mockWorkerHeartbeatFindUnique.mockResolvedValue({
      currentJobId: JOB_ID,
      status: 'active',
      lastHeartbeat: freshHeartbeat,
    });

    const { checkAndRecoverStaleJobs } = await import('../heartbeatService.js');
    await checkAndRecoverStaleJobs();

    expect(mockFencePaidPoolMutationForRecovery).toHaveBeenCalledWith(
      JOB_ID,
      'dispatch-hard-timeout',
      { status: 'REGENERATING', workerId: 'worker-live', lastHeartbeat: freshHeartbeat },
    );
    expect(mockEnqueuePaidPoolRecovery).toHaveBeenCalledOnce();
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
      state: 'AUTHORIZED',
      seedOrdinal: null,
      sourceMessageId: null,
      segment: 'regenerate_ideas_4',
    });

    const { checkAndRecoverStaleJobs } = await import('../heartbeatService.js');
    await checkAndRecoverStaleJobs();

    expect(mockCancelRegenerationDispatch).toHaveBeenCalledWith(
      JOB_ID,
      { id: 'dispatch-3', segment: 'regenerate_ideas_4', chargeId: undefined },
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
    mockDispatchFindUnique.mockResolvedValue({ id: 'dispatch-1', kind: 'CONTINUE', state: 'CLAIMED', seedOrdinal: null });

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
