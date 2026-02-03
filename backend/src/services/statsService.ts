import { Redis } from 'ioredis';
import { prisma } from './db.js';
import { CONFIG } from '../config.js';

const CACHE_KEY = 'public_stats:completed_jobs';
const CACHE_TTL = 300; // 5 minutes

// Redis client for stats caching
const redis = new Redis(CONFIG.redisUrl, {
  retryStrategy: (times: number) => Math.min(times * 100, 3000),
  maxRetriesPerRequest: 3,
});

redis.on('error', (err: Error) => {
  console.error('Stats Redis connection error:', err.message);
});

export async function getPublicStats(): Promise<{ completedJobs: number }> {
  try {
    const cached = await redis.get(CACHE_KEY);
    if (cached) {
      return { completedJobs: parseInt(cached, 10) };
    }

    const count = await prisma.job.count({
      where: { status: 'COMPLETED' },
    });

    await redis.setex(CACHE_KEY, CACHE_TTL, count.toString());
    return { completedJobs: count };
  } catch (error) {
    console.error('Failed to get public stats:', error);
    return { completedJobs: 47 }; // Fallback
  }
}
