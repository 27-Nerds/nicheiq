import { Redis } from 'ioredis';
import { CONFIG } from '../config.js';

/**
 * Shared Redis client for the backend.
 *
 * Background: prior to this consolidation, the backend created three separate
 * Redis connections (in rateLimit.ts, adminCatalog.ts, statsService.ts).
 * Each connection holds a TCP socket and listens for events; running three
 * is wasteful and makes pipeline/transaction sharing impossible.
 *
 * This module exposes a single lazily-initialised client. Existing call sites
 * should be migrated to import `getRedis()` instead of constructing their own.
 */

let client: Redis | null = null;

function createClient(): Redis {
  const c = new Redis(CONFIG.redisUrl, {
    retryStrategy: (times: number) => Math.min(times * 100, 3000),
    maxRetriesPerRequest: 3,
  });
  c.on('error', (err: Error) => {
    console.error('Redis connection error:', err.message);
  });
  return c;
}

export function getRedis(): Redis {
  if (!client) {
    client = createClient();
  }
  return client;
}

/**
 * Test helper: closes the shared client. Should not be called from production code.
 */
export async function closeRedis(): Promise<void> {
  if (client) {
    await client.quit();
    client = null;
  }
}
