import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockJobFindMany = vi.fn();
const mockJobProgressUpdateMany = vi.fn();
const mockFailLandingPageDispatch = vi.fn();
const mockRefundForStage = vi.fn();
const mockBroadcastProgress = vi.fn();

vi.mock('../db.js', () => ({
  prisma: {
    job: {
      findMany: (...args: unknown[]) => mockJobFindMany(...args),
      updateMany: vi.fn(),
    },
    jobProgress: {
      updateMany: (...args: unknown[]) => mockJobProgressUpdateMany(...args),
    },
    user: { findUnique: vi.fn().mockResolvedValue(null) },
  },
}));

vi.mock('../jobService.js', () => ({
  failJob: vi.fn(),
  cancelRegenerationDispatch: vi.fn(),
  cancelSeedIdeaDispatch: vi.fn(),
}));

vi.mock('../dispatchService.js', () => ({
  failLandingPageDispatch: (...args: unknown[]) => mockFailLandingPageDispatch(...args),
}));

vi.mock('../creditService.js', () => ({
  refundForStage: (...args: unknown[]) => mockRefundForStage(...args),
}));

vi.mock('../notificationService.js', () => ({
  notifyJobError: vi.fn(),
}));

vi.mock('../progressBroadcastService.js', () => ({
  broadcastProgress: (...args: unknown[]) => mockBroadcastProgress(...args),
}));

vi.mock('../../utils/phaseContext.js', () => ({
  getPhaseContext: vi.fn().mockReturnValue({}),
}));

beforeEach(() => {
  vi.clearAllMocks();
  mockJobProgressUpdateMany.mockResolvedValue({ count: 1 });
  mockFailLandingPageDispatch.mockResolvedValue(true);
  mockJobFindMany.mockResolvedValue([{
    id: 'job-1',
    niche: 'test',
    userId: 'user-1',
    landingPageStatus: 'RUNNING',
    activeDispatchId: 'dispatch-landing-1',
    lastHeartbeat: new Date('2026-07-30T00:00:00.000Z'),
    updatedAt: new Date('2026-07-30T00:00:05.000Z'),
  }]);
});

describe('checkStaleLandingPageJobs', () => {
  it('settles a modern stale landing dispatch exactly before broadcasting recovery', async () => {
    const { checkStaleLandingPageJobs } = await import('../heartbeatService.js');
    const stats = await checkStaleLandingPageJobs();

    expect(mockFailLandingPageDispatch).toHaveBeenCalledWith(
      'job-1',
      'dispatch-landing-1',
      'Worker stopped responding during landing page generation',
      {
        landingPageStatus: 'RUNNING',
        lastHeartbeat: new Date('2026-07-30T00:00:00.000Z'),
        updatedAt: new Date('2026-07-30T00:00:05.000Z'),
      },
    );
    expect(mockRefundForStage).not.toHaveBeenCalled();
    expect(mockJobProgressUpdateMany).not.toHaveBeenCalled();
    expect(mockBroadcastProgress).toHaveBeenCalledOnce();
    expect(stats).toEqual({ recovered: 1 });
  });

  it('suppresses progress and SSE when another callback already settled the dispatch', async () => {
    mockFailLandingPageDispatch.mockResolvedValue(false);

    const { checkStaleLandingPageJobs } = await import('../heartbeatService.js');
    const stats = await checkStaleLandingPageJobs();

    expect(mockRefundForStage).not.toHaveBeenCalled();
    expect(mockJobProgressUpdateMany).not.toHaveBeenCalled();
    expect(mockBroadcastProgress).not.toHaveBeenCalled();
    expect(stats).toEqual({ recovered: 0 });
  });
});
