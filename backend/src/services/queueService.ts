import { Redis } from 'ioredis';
import { CONFIG } from '../config.js';

// Redis connection options with retry logic
const redisOptions = {
  retryStrategy: (times: number) => Math.min(times * 100, 3000),
  maxRetriesPerRequest: 3,
};

// Redis client for queue operations
const redis = new Redis(CONFIG.redisUrl, redisOptions);

redis.on('error', (err: Error) => {
  console.error('Redis connection error:', err.message);
});

redis.on('connect', () => {
  console.log('Redis connected');
});

// Queue name for research jobs
const QUEUE_NAME = 'nicheiq:jobs';

/**
 * Enqueue a job for processing by Python worker
 */
export async function enqueueJob(
  jobId: string,
  niche: string,
  userId?: string,
  allowedProjectTypes?: string[],
  resume: boolean = false
): Promise<void> {
  const jobData = JSON.stringify({
    job_id: jobId,
    niche,
    user_id: userId,
    allowed_project_types: allowedProjectTypes,
    resume,
    created_at: new Date().toISOString(),
  });

  // Push to the left (LPUSH), workers pop from the right (BRPOP)
  await redis.lpush(QUEUE_NAME, jobData);
  console.log(`Enqueued job ${jobId} to ${QUEUE_NAME}`);
}

/**
 * Get queue length
 */
export async function getQueueLength(): Promise<number> {
  return redis.llen(QUEUE_NAME);
}

/**
 * Get all queued job IDs in order (oldest first = next to be processed)
 */
export async function getQueuedJobIds(): Promise<string[]> {
  const queue = await redis.lrange(QUEUE_NAME, 0, -1);
  // Queue is LPUSH (newest at head/left), BRPOP (oldest at tail/right)
  // So reverse to get oldest-first order (processing order)
  return queue.reverse().map(item => {
    try {
      const parsed = JSON.parse(item);
      return parsed.job_id;
    } catch {
      return null;
    }
  }).filter((id): id is string => id !== null);
}

/**
 * Get position of a specific job in the queue (1-based, null if not in queue)
 */
export async function getJobQueuePosition(jobId: string): Promise<number | null> {
  const queuedIds = await getQueuedJobIds();
  const index = queuedIds.indexOf(jobId);
  return index === -1 ? null : index + 1;
}

/**
 * Queue stats for a specific job
 */
export interface QueueStats {
  position: number | null;  // 1-based position, null if not in queue
  totalQueued: number;      // Total jobs in queue
  aheadCount: number;       // Jobs ahead of this one (position - 1)
}

/**
 * Get queue stats for a specific job
 */
export async function getQueueStats(jobId: string): Promise<QueueStats> {
  const queuedIds = await getQueuedJobIds();
  const index = queuedIds.indexOf(jobId);
  const totalQueued = queuedIds.length;

  if (index === -1) {
    return { position: null, totalQueued, aheadCount: 0 };
  }

  return {
    position: index + 1,
    totalQueued,
    aheadCount: index  // Jobs ahead of this one
  };
}

/**
 * Health check for Redis connection
 */
export async function checkRedisHealth(): Promise<boolean> {
  try {
    const result = await redis.ping();
    return result === 'PONG';
  } catch (error) {
    console.error('Redis health check failed:', error);
    return false;
  }
}

// Cleanup on shutdown
export async function closeRedis(): Promise<void> {
  await redis.quit();
}
