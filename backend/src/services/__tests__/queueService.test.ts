import { describe, it, expect, vi, beforeEach } from 'vitest';

// queueService.ts opens a real ioredis connection at import time — stub the client so
// tests never touch a real Redis instance. Only the methods queueService actually calls
// need to exist on the mock instance.
const mockLpush = vi.fn().mockResolvedValue(1);
const mockDispatchFindMany = vi.fn();
const mockDispatchFindUnique = vi.fn();
const mockDispatchUpdateMany = vi.fn();

vi.mock('ioredis', () => {
  class MockRedis {
    lpush = mockLpush;
    on = vi.fn();
    lrange = vi.fn().mockResolvedValue([]);
    lrem = vi.fn().mockResolvedValue(0);
    llen = vi.fn().mockResolvedValue(0);
    ping = vi.fn().mockResolvedValue('PONG');
    quit = vi.fn().mockResolvedValue('OK');
  }
  return { Redis: MockRedis };
});

vi.mock('../../config.js', () => ({
  CONFIG: { redisUrl: 'redis://localhost:6379' },
}));

vi.mock('../db.js', () => ({
  prisma: {
    jobDispatch: {
      findMany: (...args: unknown[]) => mockDispatchFindMany(...args),
      findUnique: (...args: unknown[]) => mockDispatchFindUnique(...args),
      updateMany: (...args: unknown[]) => mockDispatchUpdateMany(...args),
    },
  },
}));

describe('queueService — enqueueJob chatMode payload', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('includes chat_mode=true in the job payload when passed', async () => {
    const { enqueueJob } = await import('../queueService.js');

    await enqueueJob('job-1', 'a niche', 'user-1', undefined, false, 'interactive', undefined, undefined, true);

    expect(mockLpush).toHaveBeenCalledTimes(1);
    const [, payload] = mockLpush.mock.calls[0];
    const parsed = JSON.parse(payload);
    expect(parsed.chat_mode).toBe(true);
  });

  it('defaults chat_mode to false when omitted', async () => {
    const { enqueueJob } = await import('../queueService.js');

    await enqueueJob('job-1', 'a niche', 'user-1');

    const [, payload] = mockLpush.mock.calls[0];
    const parsed = JSON.parse(payload);
    expect(parsed.chat_mode).toBe(false);
  });
});

describe('queueService — enqueueContinueFromGateJob payload', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('builds a continue_from_gate task payload with checkpoint path, gate stage, and mode', async () => {
    const { enqueueContinueFromGateJob } = await import('../queueService.js');

    await enqueueContinueFromGateJob('job-1', '/tmp/checkpoint-g1', 1, 'continue');

    expect(mockLpush).toHaveBeenCalledTimes(1);
    const [queueName, payload] = mockLpush.mock.calls[0];
    expect(queueName).toBe('nicheiq:jobs');
    const parsed = JSON.parse(payload);
    expect(parsed).toMatchObject({
      job_id: 'job-1',
      checkpoint_path: '/tmp/checkpoint-g1',
      gate_stage: 1,
      mode: 'continue',
      task_type: 'continue_from_gate',
    });
    expect(parsed.patch).toBeUndefined();
  });

  it('includes the patch when apply_stay is used', async () => {
    const { enqueueContinueFromGateJob } = await import('../queueService.js');

    await enqueueContinueFromGateJob(
      'job-1', '/tmp/cp', 4, 'apply_stay', { excluded_segments: ['SegB'] }
    );

    const [, payload] = mockLpush.mock.calls[0];
    const parsed = JSON.parse(payload);
    expect(parsed.mode).toBe('apply_stay');
    expect(parsed.patch).toEqual({ excluded_segments: ['SegB'] });
  });
});

describe('queueService — catalog deep-research dispatch payload', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('carries the authorized dispatch id to the worker', async () => {
    const { enqueueDeepIdeaResearchJob } = await import('../queueService.js');

    await enqueueDeepIdeaResearchJob(
      'job-1',
      { solution_name: 'InvoiceFlow' },
      'Invoice automation',
      'user-1',
      'dispatch-deep-1',
    );

    const [, payload] = mockLpush.mock.calls[0];
    expect(JSON.parse(payload)).toMatchObject({
      job_id: 'job-1',
      task_type: 'catalog_deep_research',
      dispatch_id: 'dispatch-deep-1',
    });
  });
});

describe('queueService — exact synthesis evaluation payload', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('carries the complete structured evaluation alongside the legacy seed text', async () => {
    const { enqueueSeedIdeaJob } = await import('../queueService.js');
    const evaluation = {
      evaluation_id: '11111111-1111-1111-1111-111111111111',
      dispatch_id: '11111111-1111-1111-1111-111111111111',
      source_message_id: 'proposal-1',
      proposal: {
        proposedTitle: 'Exact direction',
        evaluation: {
          changedAxes: [{ axis: 'scope', from: 'broad', to: 'narrow' }],
          disqualifiers: ['No buyer commits'],
        },
      },
    };

    await enqueueSeedIdeaJob(
      'job-1', '/tmp/cp', 'niche', 'legacy summary', undefined, undefined,
      '11111111-1111-1111-1111-111111111111', evaluation,
    );

    const [, payload] = mockLpush.mock.calls[0];
    expect(JSON.parse(payload)).toMatchObject({
      task_type: 'seed_idea',
      seed_text: 'legacy summary',
      synthesis_evaluation: evaluation,
    });
  });
});

describe('queueService — dispatch outbox retry', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockDispatchFindMany.mockResolvedValue([{
      id: 'dispatch-1',
      deliveryAttempts: 0,
      lastDeliveryAt: null,
    }]);
    mockDispatchFindUnique.mockResolvedValue({
      state: 'AUTHORIZED',
      workPayload: { job_id: 'job-1', task_type: 'research_phase2' },
    });
    mockDispatchUpdateMany.mockResolvedValue({ count: 1 });
  });

  it('redelivers every due AUTHORIZED payload, including an enqueue whose success was later lost', async () => {
    mockDispatchFindMany.mockResolvedValue([{
      id: 'dispatch-1',
      deliveryAttempts: 1,
      lastDeliveryAt: new Date(Date.now() - 20_000),
    }]);
    const { redeliverAuthorizedDispatches } = await import('../queueService.js');

    await expect(redeliverAuthorizedDispatches(5)).resolves.toBe(1);

    expect(mockDispatchFindMany).toHaveBeenCalledWith(expect.objectContaining({
      where: expect.objectContaining({
        state: 'AUTHORIZED',
        OR: [
          { lastDeliveryAt: null },
          { lastDeliveryAt: { lte: expect.any(Date) } },
        ],
      }),
      take: 5,
    }));
    expect(mockLpush).toHaveBeenCalledWith(
      'nicheiq:jobs',
      JSON.stringify({
        job_id: 'job-1',
        task_type: 'research_phase2',
        dispatch_id: 'dispatch-1',
      }),
    );
    expect(mockDispatchUpdateMany).toHaveBeenCalledWith(expect.objectContaining({
      where: { id: 'dispatch-1', state: 'AUTHORIZED' },
      data: expect.objectContaining({
        deliveryAttempts: { increment: 1 },
        lastDeliveryError: null,
      }),
    }));
  });

  it('does not redeliver a recent AUTHORIZED attempt before its backoff expires', async () => {
    mockDispatchFindMany.mockResolvedValue([{
      id: 'dispatch-recent',
      deliveryAttempts: 1,
      lastDeliveryAt: new Date(),
    }]);
    const { redeliverAuthorizedDispatches } = await import('../queueService.js');

    await expect(redeliverAuthorizedDispatches()).resolves.toBe(0);

    expect(mockDispatchFindUnique).not.toHaveBeenCalled();
    expect(mockLpush).not.toHaveBeenCalled();
  });
});
