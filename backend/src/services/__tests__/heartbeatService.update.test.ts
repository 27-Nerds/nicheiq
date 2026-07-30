import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockJobFindUnique = vi.fn();
const mockJobUpdateMany = vi.fn();
const mockDispatchFindUnique = vi.fn();

vi.mock('../db.js', () => ({
  prisma: {
    job: {
      findUnique: (...args: any[]) => mockJobFindUnique(...args),
      updateMany: (...args: any[]) => mockJobUpdateMany(...args),
    },
    jobDispatch: {
      findUnique: (...args: any[]) => mockDispatchFindUnique(...args),
    },
  },
}));

vi.mock('../jobService.js', () => ({
  failJob: vi.fn(),
  cancelRegenerationDispatch: vi.fn(),
  cancelSeedIdeaDispatch: vi.fn(),
}));

vi.mock('../notificationService.js', () => ({
  notifyJobError: vi.fn(),
}));

vi.mock('../../utils/phaseContext.js', () => ({
  getPhaseContext: vi.fn(),
}));

vi.mock('../creditService.js', () => ({
  refundForStage: vi.fn(),
}));

vi.mock('../dispatchService.js', () => ({
  failLandingPageDispatch: vi.fn(),
}));

vi.mock('../progressBroadcastService.js', () => ({
  broadcastProgress: vi.fn(),
}));

beforeEach(() => {
  vi.clearAllMocks();
  mockJobUpdateMany.mockResolvedValue({ count: 1 });
});

describe('updateJobHeartbeat — exact attempt ownership', () => {
  it('updates a claimed dispatch only for its owning worker', async () => {
    mockJobFindUnique.mockResolvedValue({
      activeDispatchId: 'dispatch-1',
      workerId: 'worker-1',
    });
    mockDispatchFindUnique.mockResolvedValue({
      jobId: 'job-1',
      state: 'CLAIMED',
      workerId: 'worker-1',
    });

    const { updateJobHeartbeat } = await import('../heartbeatService.js');
    const result = await updateJobHeartbeat('job-1', 'worker-1', 'dispatch-1');

    expect(result).toBe('updated');
    expect(mockJobUpdateMany).toHaveBeenCalledWith({
      where: {
        id: 'job-1',
        activeDispatchId: 'dispatch-1',
        workerId: 'worker-1',
      },
      data: { lastHeartbeat: expect.any(Date) },
    });
  });

  it('rejects an old dispatch after a newer attempt becomes active', async () => {
    mockJobFindUnique.mockResolvedValue({
      activeDispatchId: 'dispatch-2',
      workerId: 'worker-2',
    });

    const { updateJobHeartbeat } = await import('../heartbeatService.js');
    const result = await updateJobHeartbeat('job-1', 'worker-1', 'dispatch-1');

    expect(result).toBe('stale');
    expect(mockDispatchFindUnique).not.toHaveBeenCalled();
    expect(mockJobUpdateMany).not.toHaveBeenCalled();
  });

  it('rejects an identityless callback when a modern dispatch is active', async () => {
    mockJobFindUnique.mockResolvedValue({
      activeDispatchId: 'dispatch-2',
      workerId: 'worker-2',
    });

    const { updateJobHeartbeat } = await import('../heartbeatService.js');
    const result = await updateJobHeartbeat('job-1', 'legacy-worker');

    expect(result).toBe('stale');
    expect(mockJobUpdateMany).not.toHaveBeenCalled();
  });

  it('does not let a second worker refresh the same claimed dispatch', async () => {
    mockJobFindUnique.mockResolvedValue({
      activeDispatchId: 'dispatch-1',
      workerId: 'worker-1',
    });
    mockDispatchFindUnique.mockResolvedValue({
      jobId: 'job-1',
      state: 'CLAIMED',
      workerId: 'worker-1',
    });

    const { updateJobHeartbeat } = await import('../heartbeatService.js');
    const result = await updateJobHeartbeat('job-1', 'worker-2', 'dispatch-1');

    expect(result).toBe('stale');
    expect(mockJobUpdateMany).not.toHaveBeenCalled();
  });

  it('ignores a pre-claim heartbeat without cancelling the authorized attempt', async () => {
    mockJobFindUnique.mockResolvedValue({
      activeDispatchId: 'dispatch-1',
      workerId: 'previous-worker',
    });
    mockDispatchFindUnique.mockResolvedValue({
      jobId: 'job-1',
      state: 'AUTHORIZED',
      workerId: null,
    });

    const { updateJobHeartbeat } = await import('../heartbeatService.js');
    const result = await updateJobHeartbeat('job-1', 'worker-1', 'dispatch-1');

    expect(result).toBe('pending');
    expect(mockJobUpdateMany).not.toHaveBeenCalled();
  });

  it('loses cleanly when attempt ownership changes between the read and guarded write', async () => {
    mockJobFindUnique.mockResolvedValue({
      activeDispatchId: 'dispatch-1',
      workerId: 'worker-1',
    });
    mockDispatchFindUnique.mockResolvedValue({
      jobId: 'job-1',
      state: 'CLAIMED',
      workerId: 'worker-1',
    });
    mockJobUpdateMany.mockResolvedValue({ count: 0 });

    const { updateJobHeartbeat } = await import('../heartbeatService.js');
    const result = await updateJobHeartbeat('job-1', 'worker-1', 'dispatch-1');

    expect(result).toBe('stale');
  });

  it('keeps the identityless legacy path only when no dispatch exists', async () => {
    mockJobFindUnique.mockResolvedValue({
      activeDispatchId: null,
      workerId: 'legacy-worker',
    });

    const { updateJobHeartbeat } = await import('../heartbeatService.js');
    const result = await updateJobHeartbeat('job-1', 'legacy-worker');

    expect(result).toBe('updated');
    expect(mockJobUpdateMany).toHaveBeenCalledWith({
      where: {
        id: 'job-1',
        activeDispatchId: null,
        workerId: 'legacy-worker',
      },
      data: {
        workerId: 'legacy-worker',
        lastHeartbeat: expect.any(Date),
      },
    });
  });
});
