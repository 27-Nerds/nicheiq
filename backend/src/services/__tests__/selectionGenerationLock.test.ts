import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({ getRedis: vi.fn() }));
vi.mock('../redis.js', () => ({ getRedis: mocks.getRedis }));

const { acquireGenerationLock, GENERATION_LOCK_TTL_SECONDS } =
  await import('../selectionGenerationLock.js');
const { GENERATION_BUDGET_MS, CALL_TIMEOUT_MS, MIN_RETRY_BUDGET_MS } =
  await import('../selectionConceptSetService.js');

/** Minimal Redis double honouring SET NX semantics and the compare-and-delete script. */
function fakeRedis() {
  const store = new Map<string, string>();
  return {
    store,
    set: vi.fn(async (key: string, value: string, _ex: string, _ttl: number, nx?: string) => {
      if (nx === 'NX' && store.has(key)) return null;
      store.set(key, value);
      return 'OK';
    }),
    eval: vi.fn(async (_script: string, _n: number, key: string, token: string) => {
      if (store.get(key) !== token) return 0;
      store.delete(key);
      return 1;
    }),
  };
}

beforeEach(() => vi.clearAllMocks());

describe('acquireGenerationLock', () => {
  it('grants the lock to the first caller with the generation-budget TTL', async () => {
    const redis = fakeRedis();
    mocks.getRedis.mockReturnValue(redis);

    const lock = await acquireGenerationLock('job-1');
    expect(lock).not.toBeNull();
    expect(redis.set).toHaveBeenCalledWith(
      'nicheiq:conceptforge:lock:job-1',
      expect.any(String),
      'EX',
      GENERATION_LOCK_TTL_SECONDS,
      'NX',
    );
    // Must outlast the whole generation budget plus persistence, or the lock frees
    // itself mid-run and a second tab starts a duplicate.
    expect(GENERATION_LOCK_TTL_SECONDS * 1000).toBeGreaterThan(GENERATION_BUDGET_MS);
  });

  it('refuses a second caller while the first still holds it', async () => {
    mocks.getRedis.mockReturnValue(fakeRedis());
    const first = await acquireGenerationLock('job-1');
    expect(first).not.toBeNull();
    expect(await acquireGenerationLock('job-1')).toBeNull();
  });

  it('lets the next caller through once released', async () => {
    mocks.getRedis.mockReturnValue(fakeRedis());
    const first = await acquireGenerationLock('job-1');
    await first!.release();
    expect(await acquireGenerationLock('job-1')).not.toBeNull();
  });

  it('locks per job, not globally', async () => {
    mocks.getRedis.mockReturnValue(fakeRedis());
    expect(await acquireGenerationLock('job-1')).not.toBeNull();
    expect(await acquireGenerationLock('job-2')).not.toBeNull();
  });

  it('release is idempotent', async () => {
    const redis = fakeRedis();
    mocks.getRedis.mockReturnValue(redis);
    const lock = await acquireGenerationLock('job-1');
    await lock!.release();
    await lock!.release();
    expect(redis.eval).toHaveBeenCalledTimes(1);
  });

  it('will not delete a lock it no longer owns', async () => {
    // The holder's TTL expired and a NEW request took the lock; the stale holder's
    // release must not free the new one.
    const redis = fakeRedis();
    mocks.getRedis.mockReturnValue(redis);
    const stale = await acquireGenerationLock('job-1');
    redis.store.set('nicheiq:conceptforge:lock:job-1', 'a-newer-holders-token');

    await stale!.release();
    expect(redis.store.get('nicheiq:conceptforge:lock:job-1')).toBe('a-newer-holders-token');
  });

  it('fails OPEN when Redis is unreachable — the DB index still protects correctness', async () => {
    mocks.getRedis.mockImplementation(() => { throw new Error('ECONNREFUSED'); });
    const lock = await acquireGenerationLock('job-1');
    expect(lock).not.toBeNull();
    await expect(lock!.release()).resolves.toBeUndefined();
  });

  it('fails OPEN when the SET command itself rejects', async () => {
    mocks.getRedis.mockReturnValue({
      set: vi.fn().mockRejectedValue(new Error('LOADING')),
      eval: vi.fn(),
    });
    expect(await acquireGenerationLock('job-1')).not.toBeNull();
  });

  it('never fails the request when release throws', async () => {
    const redis = fakeRedis();
    redis.eval.mockRejectedValue(new Error('connection lost'));
    mocks.getRedis.mockReturnValue(redis);
    const lock = await acquireGenerationLock('job-1');
    await expect(lock!.release()).resolves.toBeUndefined();
  });

  it('gives each holder a distinct token', async () => {
    const redis = fakeRedis();
    mocks.getRedis.mockReturnValue(redis);
    await acquireGenerationLock('job-a');
    await acquireGenerationLock('job-b');
    const [tokenA, tokenB] = redis.set.mock.calls.map((call) => call[1]);
    expect(tokenA).not.toBe(tokenB);
  });
});

describe('generation timing invariants', () => {
  it('never starts a retry with markedly less time than a call needs', () => {
    // The old pair (150s call, 70s retry floor) let a retry begin with 90s — less than
    // the budget that had already proved insufficient, so it was doomed before it ran.
    expect(MIN_RETRY_BUDGET_MS).toBeGreaterThanOrEqual(CALL_TIMEOUT_MS * 0.7);
  });

  it('leaves room for two full attempts inside the total budget', () => {
    expect(GENERATION_BUDGET_MS).toBeGreaterThanOrEqual(CALL_TIMEOUT_MS + MIN_RETRY_BUDGET_MS);
  });

  it('holds the lock longer than a generation can possibly run', () => {
    expect(GENERATION_LOCK_TTL_SECONDS * 1000).toBeGreaterThan(GENERATION_BUDGET_MS);
  });
});
