import { Router, Request, Response } from 'express';
import { testConnection } from '../services/db.js';
import { checkRedisHealth, getQueueLength } from '../services/queueService.js';

export const healthRouter = Router();

/**
 * GET /api/health
 * Health check endpoint for monitoring and load balancers
 */
healthRouter.get('/health', async (_req: Request, res: Response) => {
  const checks = await Promise.allSettled([
    testConnection(),
    checkRedisHealth(),
    getQueueLength(),
  ]);

  const [dbCheck, redisCheck, queueCheck] = checks;

  const dbHealthy = dbCheck.status === 'fulfilled' && dbCheck.value === true;
  const redisHealthy = redisCheck.status === 'fulfilled' && redisCheck.value === true;
  const queueLength = queueCheck.status === 'fulfilled' ? queueCheck.value : -1;

  const allHealthy = dbHealthy && redisHealthy;

  const status = {
    status: allHealthy ? 'healthy' : 'unhealthy',
    timestamp: new Date().toISOString(),
    services: {
      database: {
        status: dbHealthy ? 'up' : 'down',
      },
      redis: {
        status: redisHealthy ? 'up' : 'down',
        queueLength: queueLength >= 0 ? queueLength : undefined,
      },
    },
  };

  res.status(allHealthy ? 200 : 503).json(status);
});

/**
 * GET /api/health/live
 * Kubernetes liveness probe - is the service running?
 */
healthRouter.get('/live', (_req: Request, res: Response) => {
  res.status(200).json({ status: 'alive' });
});

/**
 * GET /api/health/ready
 * Kubernetes readiness probe - is the service ready to accept traffic?
 */
healthRouter.get('/ready', async (_req: Request, res: Response) => {
  const [dbOk, redisOk] = await Promise.all([
    testConnection().catch(() => false),
    checkRedisHealth().catch(() => false),
  ]);

  if (dbOk && redisOk) {
    res.status(200).json({ status: 'ready' });
  } else {
    res.status(503).json({
      status: 'not ready',
      database: dbOk ? 'ok' : 'unavailable',
      redis: redisOk ? 'ok' : 'unavailable',
    });
  }
});
