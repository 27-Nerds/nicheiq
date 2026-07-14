import { describe, it, expect, vi, beforeEach } from 'vitest';

// queueService.ts opens a real ioredis connection at import time — stub the client so
// tests never touch a real Redis instance. Only the methods queueService actually calls
// need to exist on the mock instance.
const mockLpush = vi.fn().mockResolvedValue(1);

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
