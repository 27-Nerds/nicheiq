import rateLimit from 'express-rate-limit';
import { Redis } from 'ioredis';
import { CONFIG } from '../config.js';

// Redis client for rate limiting (suggestion endpoints)
const redis = new Redis(CONFIG.redisUrl, {
  retryStrategy: (times: number) => Math.min(times * 100, 3000),
  maxRetriesPerRequest: 3,
});

redis.on('error', (err: Error) => {
  console.error('Rate limit Redis error:', err.message);
});

/**
 * Rate limiter for authentication endpoints (login, register)
 * Prevents brute force attacks
 */
export const authLimiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: CONFIG.nodeEnv === 'production' ? 5 : 100, // 5 attempts in production, 100 in dev
  message: {
    error: 'Too many authentication attempts, please try again later',
  },
  standardHeaders: true,
  legacyHeaders: false,
  // Skip rate limiting for successful requests in development
  skipSuccessfulRequests: CONFIG.isDev,
});

/**
 * Rate limiter for password reset requests
 * More restrictive to prevent email enumeration
 */
export const passwordResetLimiter = rateLimit({
  windowMs: 60 * 60 * 1000, // 1 hour
  max: CONFIG.nodeEnv === 'production' ? 3 : 50, // 3 attempts per hour in production
  message: {
    error: 'Too many password reset requests, please try again later',
  },
  standardHeaders: true,
  legacyHeaders: false,
});

/**
 * General API rate limiter
 * Prevents abuse of API endpoints
 */
export const apiLimiter = rateLimit({
  windowMs: 60 * 1000, // 1 minute
  max: CONFIG.nodeEnv === 'production' ? 60 : 1000, // 60 requests per minute in production
  message: {
    error: 'Too many requests, please slow down',
  },
  standardHeaders: true,
  legacyHeaders: false,
});

/**
 * Strict rate limiter for job creation
 * Prevents abuse of expensive operations
 */
export const jobCreationLimiter = rateLimit({
  windowMs: 60 * 60 * 1000, // 1 hour
  max: CONFIG.nodeEnv === 'production' ? 10 : 100, // 10 jobs per hour in production
  message: {
    error: 'Job creation limit reached, please try again later',
  },
  standardHeaders: true,
  legacyHeaders: false,
});

/**
 * Rate limit result for suggestion endpoints
 */
export interface SuggestRateLimitResult {
  allowed: boolean;
  remaining: {
    hourly: number;
    daily: number;
  };
  retryAfter?: number; // seconds until next allowed request
}

/**
 * Redis-based rate limiter for niche suggestions
 * Uses per-user hourly and daily limits to control costs
 *
 * @param userId - User ID to check rate limit for
 * @returns Rate limit result with remaining quota
 */
export async function checkSuggestRateLimit(userId: string): Promise<SuggestRateLimitResult> {
  const hourlyKey = `nicheiq:suggest:rate:${userId}:hourly`;
  const dailyKey = `nicheiq:suggest:rate:${userId}:daily`;

  const hourlyLimit = CONFIG.suggestRateHourly;
  const dailyLimit = CONFIG.suggestRateDaily;

  try {
    // Get current counts
    const [hourlyCount, dailyCount] = await Promise.all([
      redis.get(hourlyKey),
      redis.get(dailyKey),
    ]);

    const currentHourly = parseInt(hourlyCount || '0', 10);
    const currentDaily = parseInt(dailyCount || '0', 10);

    // Check if rate limited
    if (currentHourly >= hourlyLimit) {
      const ttl = await redis.ttl(hourlyKey);
      return {
        allowed: false,
        remaining: { hourly: 0, daily: Math.max(0, dailyLimit - currentDaily) },
        retryAfter: ttl > 0 ? ttl : 3600,
      };
    }

    if (currentDaily >= dailyLimit) {
      const ttl = await redis.ttl(dailyKey);
      return {
        allowed: false,
        remaining: { hourly: Math.max(0, hourlyLimit - currentHourly), daily: 0 },
        retryAfter: ttl > 0 ? ttl : 86400,
      };
    }

    // Increment counters atomically
    const pipeline = redis.pipeline();
    pipeline.incr(hourlyKey);
    pipeline.expire(hourlyKey, 3600); // 1 hour TTL
    pipeline.incr(dailyKey);
    pipeline.expire(dailyKey, 86400); // 24 hour TTL
    await pipeline.exec();

    return {
      allowed: true,
      remaining: {
        hourly: hourlyLimit - currentHourly - 1,
        daily: dailyLimit - currentDaily - 1,
      },
    };
  } catch (error) {
    console.error('Rate limit check failed:', error);
    // Fail open in case of Redis errors (but log it)
    return {
      allowed: true,
      remaining: { hourly: hourlyLimit, daily: dailyLimit },
    };
  }
}
