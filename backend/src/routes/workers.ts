/**
 * Worker API Routes
 *
 * Internal endpoints for Python workers to:
 * - Send heartbeats
 * - Report graceful shutdown
 * - Register themselves
 *
 * All endpoints require INTERNAL_SERVICE_SECRET authentication.
 */

import { Router, Request, Response } from 'express';
import { z } from 'zod';
import {
  updateJobHeartbeat,
  registerWorkerHeartbeat,
  markWorkerShutdown,
} from '../services/heartbeatService.js';
import { requireInternalService } from '../middleware/auth.js';

export const workersRouter = Router();

// Apply internal service middleware to all routes
workersRouter.use(requireInternalService);

/**
 * Heartbeat request schema
 */
const HeartbeatSchema = z.object({
  worker_id: z.string().min(1),
  job_id: z.string().uuid().nullable(),
  hostname: z.string().optional(),
  process_id: z.number().int().optional(),
});

/**
 * POST /api/workers/heartbeat
 * Worker sends periodic heartbeat to indicate it's alive
 * Returns shouldCancel: true if the job has been cancelled by user
 */
workersRouter.post('/heartbeat', async (req: Request, res: Response) => {
  try {
    const data = HeartbeatSchema.parse(req.body);

    // Register/update worker heartbeat
    await registerWorkerHeartbeat(
      data.worker_id,
      data.job_id,
      data.hostname,
      data.process_id
    );

    // Check if job should be cancelled
    let shouldCancel = false;
    if (data.job_id) {
      await updateJobHeartbeat(data.job_id, data.worker_id);

      // Check job status for cancellation
      const { prisma } = await import('../services/db.js');
      const job = await prisma.job.findUnique({
        where: { id: data.job_id },
        select: { status: true },
      });

      // Signal worker to stop if job was cancelled
      if (job?.status === 'CANCELLED') {
        shouldCancel = true;
      }
    }

    res.json({
      status: 'ok',
      timestamp: new Date().toISOString(),
      shouldCancel,
    });
  } catch (error) {
    if (error instanceof z.ZodError) {
      res.status(400).json({ error: 'Validation error', details: error.errors });
      return;
    }
    console.error('Heartbeat error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

/**
 * Shutdown request schema
 */
const ShutdownSchema = z.object({
  worker_id: z.string().min(1),
  job_id: z.string().uuid().nullable().optional(),
  reason: z.string().optional(),
});

/**
 * POST /api/workers/shutdown
 * Worker reports graceful shutdown (SIGTERM/SIGINT)
 */
workersRouter.post('/shutdown', async (req: Request, res: Response) => {
  try {
    const data = ShutdownSchema.parse(req.body);

    console.log(`[Workers] Worker ${data.worker_id} shutting down. Reason: ${data.reason || 'unknown'}`);

    // Mark worker as shutdown
    await markWorkerShutdown(data.worker_id);

    // If worker was processing a job, handle immediate re-queue or failure
    if (data.job_id) {
      const { failJob } = await import('../services/jobService.js');
      const { prisma } = await import('../services/db.js');
      const { JobStatus } = await import('@prisma/client');
      const { enqueueJob } = await import('../services/queueService.js');
      const { sendFailureEmail } = await import('../services/emailService.js');

      // Check if job is still running (hasn't been completed)
      const job = await prisma.job.findUnique({
        where: { id: data.job_id },
        select: { status: true, retryCount: true, niche: true, userId: true, allowedProjectTypes: true },
      });

      if (job && job.status === JobStatus.RUNNING) {
        const MAX_RETRIES = 2;

        if (job.retryCount < MAX_RETRIES) {
          // Immediately re-queue for retry (don't wait for heartbeat checker)
          const newRetryCount = job.retryCount + 1;

          await prisma.job.update({
            where: { id: data.job_id },
            data: {
              status: JobStatus.QUEUED,
              workerId: null,
              lastHeartbeat: null,
              retryCount: newRetryCount,
              errorMessage: `Worker shutdown - retry attempt ${newRetryCount}`,
              queuedAt: new Date(),
            },
          });

          // Re-enqueue job to Redis immediately
          await enqueueJob(
            data.job_id,
            job.niche,
            job.userId || undefined,
            job.allowedProjectTypes as string[] | undefined
          );

          console.log(`[Workers] Job ${data.job_id} immediately re-queued for retry (attempt ${newRetryCount}/${MAX_RETRIES})`);
        } else {
          // Max retries exceeded - fail the job
          const errorMessage = 'Worker shutdown - max retries exceeded';
          await failJob(data.job_id, errorMessage);
          console.log(`[Workers] Job ${data.job_id} failed - max retries exceeded`);

          // Send failure email
          if (job.userId) {
            const user = await prisma.user.findUnique({
              where: { id: job.userId },
              select: { email: true },
            });
            if (user?.email) {
              try {
                await sendFailureEmail(user.email, data.job_id, job.niche, errorMessage);
              } catch (emailError) {
                console.error(`[Workers] Failed to send failure email for job ${data.job_id}:`, emailError);
              }
            }
          }
        }
      }
    }

    res.json({ status: 'ok', message: 'Shutdown acknowledged' });
  } catch (error) {
    if (error instanceof z.ZodError) {
      res.status(400).json({ error: 'Validation error', details: error.errors });
      return;
    }
    console.error('Shutdown error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

/**
 * Job started request schema
 */
const JobStartedSchema = z.object({
  worker_id: z.string().min(1),
  job_id: z.string().uuid(),
});

/**
 * POST /api/workers/job-started
 * Worker reports it has started processing a job
 */
workersRouter.post('/job-started', async (req: Request, res: Response) => {
  try {
    const data = JobStartedSchema.parse(req.body);

    const { prisma } = await import('../services/db.js');
    const { JobStatus } = await import('@prisma/client');

    // Update job with worker ID and initial heartbeat
    await prisma.job.update({
      where: { id: data.job_id },
      data: {
        workerId: data.worker_id,
        lastHeartbeat: new Date(),
        status: JobStatus.RUNNING,
        startedAt: new Date(),
        errorMessage: null, // Clear any retry messages from previous attempts
      },
    });

    // Update worker heartbeat
    await registerWorkerHeartbeat(data.worker_id, data.job_id);

    console.log(`[Workers] Job ${data.job_id} started by worker ${data.worker_id}`);

    res.json({ status: 'ok' });
  } catch (error) {
    if (error instanceof z.ZodError) {
      res.status(400).json({ error: 'Validation error', details: error.errors });
      return;
    }
    console.error('Job started error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

/**
 * Job completed request schema
 */
const JobCompletedSchema = z.object({
  worker_id: z.string().min(1),
  job_id: z.string().uuid(),
});

/**
 * POST /api/workers/job-completed
 * Worker reports it has finished processing a job (success or failure handled separately)
 */
workersRouter.post('/job-completed', async (req: Request, res: Response) => {
  try {
    const data = JobCompletedSchema.parse(req.body);

    // Clear worker's current job
    await registerWorkerHeartbeat(data.worker_id, null);

    console.log(`[Workers] Job ${data.job_id} completed by worker ${data.worker_id}`);

    res.json({ status: 'ok' });
  } catch (error) {
    if (error instanceof z.ZodError) {
      res.status(400).json({ error: 'Validation error', details: error.errors });
      return;
    }
    console.error('Job completed error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});
