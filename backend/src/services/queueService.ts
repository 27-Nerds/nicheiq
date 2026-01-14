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

// Redis client for pub/sub subscriptions (separate connection required)
export function createSubscriber(): Redis {
  const subscriber = new Redis(CONFIG.redisUrl, redisOptions);

  subscriber.on('error', (err: Error) => {
    console.error('Redis subscriber error:', err.message);
  });

  return subscriber;
}

// Queue name for research jobs
const QUEUE_NAME = 'nicheiq:jobs';

// Progress channel pattern
export function getProgressChannel(jobId: string): string {
  return `job:${jobId}:progress`;
}

/**
 * Enqueue a job for processing by Python worker
 */
export async function enqueueJob(
  jobId: string,
  niche: string,
  email: string,
  userId?: string,
  allowedProjectTypes?: string[]
): Promise<void> {
  const jobData = JSON.stringify({
    job_id: jobId,
    niche,
    email,
    user_id: userId,
    allowed_project_types: allowedProjectTypes,
    created_at: new Date().toISOString(),
  });

  // Push to the left (LPUSH), workers pop from the right (BRPOP)
  await redis.lpush(QUEUE_NAME, jobData);
  console.log(`Enqueued job ${jobId} to ${QUEUE_NAME}`);
}

/**
 * Publish a progress update for a job
 * (Called by Python worker, but useful for testing)
 */
export async function publishProgress(
  jobId: string,
  data: Record<string, unknown>
): Promise<void> {
  const channel = getProgressChannel(jobId);
  await redis.publish(channel, JSON.stringify(data));
}

/**
 * Subscribe to progress updates for a job
 */
export function subscribeToProgress(
  jobId: string,
  callback: (data: Record<string, unknown>) => void
): { subscriber: Redis; unsubscribe: () => Promise<void> } {
  const subscriber = createSubscriber();
  const channel = getProgressChannel(jobId);

  subscriber.subscribe(channel);

  subscriber.on('message', (ch: string, message: string) => {
    if (ch === channel) {
      try {
        const data = JSON.parse(message);
        callback(data);
      } catch (error) {
        console.error('Failed to parse progress message:', error);
      }
    }
  });

  const unsubscribe = async () => {
    try {
      await subscriber.unsubscribe(channel);
      await subscriber.quit();
    } catch (err) {
      // Connection may already be closed, ignore errors during cleanup
      console.log(`Cleanup for channel ${channel}: ${err instanceof Error ? err.message : 'unknown error'}`);
    }
  };

  return { subscriber, unsubscribe };
}

/**
 * Get queue length
 */
export async function getQueueLength(): Promise<number> {
  return redis.llen(QUEUE_NAME);
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
