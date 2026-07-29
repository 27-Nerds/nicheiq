import crypto from 'crypto';
import { getRedis } from './redis.js';

/**
 * Single-flight lock for Concept Forge generation.
 *
 * The partial unique index `("jobId","inputFingerprint") WHERE archivedAt IS NULL`
 * already guarantees one stored SET per request, so a race can never produce duplicate
 * rows. What it cannot prevent is duplicate WORK: two tabs both miss the fingerprint
 * cache, both spend a full generation upstream, and the loser's tokens are billed to the
 * job (`recordForgeCost` runs on the P2002 branch too) for a row that is thrown away.
 *
 * This lock closes that window. Held in Redis rather than in-process because the backend
 * can run more than one instance — an in-process Map would only serialise one of them.
 *
 * FAILS OPEN. If Redis is unavailable the caller proceeds unlocked: the DB index still
 * protects correctness, and a wasted generation is a far better outcome than making the
 * feature unusable whenever the cache layer is down.
 */

const KEY_PREFIX = 'nicheiq:conceptforge:lock:';

/**
 * MUST exceed `GENERATION_BUDGET_MS` (400s), or the lock expires while its holder is
 * still generating and a second tab starts a duplicate run. The margin also covers
 * persisting and responding after the last upstream call returns. It is the only thing
 * that frees the lock if a process dies mid-generation, so it is not set far higher.
 */
export const GENERATION_LOCK_TTL_SECONDS = 480;

export interface GenerationLock {
  /** Release the lock. Idempotent, and a no-op when the lock was not actually held. */
  release: () => Promise<void>;
}

function lockKey(jobId: string): string {
  return `${KEY_PREFIX}${jobId}`;
}

/**
 * Try to become the single in-flight generator for a job.
 *
 * @returns a handle when the lock was taken, or `null` when another request holds it.
 *   A `null` return means "someone else is generating right now" — never "an error
 *   occurred"; Redis failures resolve to a granted no-op lock instead.
 */
export async function acquireGenerationLock(jobId: string): Promise<GenerationLock | null> {
  // Random token so release can verify ownership: without it, a request whose lock had
  // already expired could delete the NEXT request's lock.
  const token = crypto.randomBytes(16).toString('base64url');
  let redis;
  try {
    redis = getRedis();
    const stored = await redis.set(lockKey(jobId), token, 'EX', GENERATION_LOCK_TTL_SECONDS, 'NX');
    if (stored !== 'OK') return null;
  } catch (error) {
    console.warn(`[conceptForge] generation lock unavailable for job ${jobId}; proceeding unlocked:`, error);
    return { release: async () => {} };
  }

  const client = redis;
  let released = false;
  return {
    release: async () => {
      if (released) return;
      released = true;
      try {
        // Compare-and-delete: only the holder may release.
        await client.eval(
          'if redis.call("GET", KEYS[1]) == ARGV[1] then return redis.call("DEL", KEYS[1]) else return 0 end',
          1,
          lockKey(jobId),
          token,
        );
      } catch (error) {
        // The TTL will clear it; a failed release must not fail the user's request.
        console.warn(`[conceptForge] failed to release generation lock for job ${jobId}:`, error);
      }
    },
  };
}
