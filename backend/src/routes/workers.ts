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
import { failJob, updateStageProgress, completeJob, getJob } from '../services/jobService.js';
import { broadcastProgress } from '../services/progressBroadcastService.js';
import { sendCompletionEmail, sendFailureEmail } from '../services/emailService.js';
import { requireInternalService } from '../middleware/auth.js';
import { StageStatus } from '@prisma/client';
import { PIPELINE_STAGES } from '../types/job.js';

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
 * Job will be marked as failed - user can resume via checkpoint
 */
workersRouter.post('/shutdown', async (req: Request, res: Response) => {
  try {
    const data = ShutdownSchema.parse(req.body);

    console.log(`[Workers] Worker ${data.worker_id} shutting down. Reason: ${data.reason || 'unknown'}`);

    // Mark worker as shutdown
    await markWorkerShutdown(data.worker_id);

    // If worker was processing a job, mark it as failed
    if (data.job_id) {
      const { prisma } = await import('../services/db.js');
      const { JobStatus } = await import('@prisma/client');
      const { sendFailureEmail } = await import('../services/emailService.js');

      const job = await prisma.job.findUnique({
        where: { id: data.job_id },
        select: { status: true, niche: true, userId: true },
      });

      if (job && job.status === JobStatus.RUNNING) {
        const errorMessage = `Worker shutdown: ${data.reason || 'graceful shutdown'}. Use checkpoint resume to continue.`;
        await failJob(data.job_id, errorMessage);
        console.log(`[Workers] Job ${data.job_id} marked as failed due to worker shutdown`);

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

/**
 * Job failed request schema
 */
const JobFailedSchema = z.object({
  worker_id: z.string().min(1),
  job_id: z.string().uuid(),
  error_message: z.string(),
  error_stage: z.number().int().nullable().optional(),
});

/**
 * POST /api/workers/job-failed
 * Worker reports that a job has failed.
 * This endpoint is IDEMPOTENT - safe to call multiple times for the same job.
 * The backend's failJob() function handles idempotency and auto-refunds.
 */
workersRouter.post('/job-failed', async (req: Request, res: Response) => {
  try {
    const data = JobFailedSchema.parse(req.body);

    console.log(`[Workers] Job ${data.job_id} failed reported by worker ${data.worker_id}: ${data.error_message.substring(0, 100)}`);

    // failJob is idempotent - safe to call multiple times
    const job = await failJob(data.job_id, data.error_message, data.error_stage ?? undefined);

    // Broadcast failure to SSE clients
    try {
      broadcastProgress(data.job_id, {
        stage: data.error_stage ?? 1,
        name: 'Failed',
        status: 'failed',
        error: data.error_message,
      });
    } catch (broadcastErr) {
      console.error('[Workers] Broadcast failed but DB updated:', broadcastErr);
    }

    // Clear worker's current job
    await registerWorkerHeartbeat(data.worker_id, null);

    res.json({
      success: true,
      job_id: data.job_id,
      status: job?.status ?? 'unknown',
    });
  } catch (error) {
    if (error instanceof z.ZodError) {
      return res.status(400).json({ error: 'Invalid request', details: error.errors });
    }
    console.error('[Workers] Error processing job-failed:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

/**
 * Progress update request schema
 */
const VALID_STAGE_NUMBERS: number[] = PIPELINE_STAGES.map(s => s.number);

const ProgressSchema = z.object({
  worker_id: z.string().min(1).max(100),
  job_id: z.string().uuid(),
  stage: z.number().refine(n => Number.isFinite(n) && VALID_STAGE_NUMBERS.includes(n), {
    message: `Stage must be one of: ${VALID_STAGE_NUMBERS.join(', ')}`,
  }),
  name: z.string().min(1).max(100),
  status: z.enum(['running', 'completed', 'failed']),
  error: z.string().max(10000).optional(),
  report_path: z.string().max(500).optional(),
  landing_path: z.string().max(500).optional(),
});

/**
 * Get the current email address for a job's user.
 */
async function getCurrentEmailForJob(job: { userId: string | null }): Promise<string | null> {
  if (!job.userId) {
    return null;
  }

  try {
    const { prisma } = await import('../services/db.js');
    const user = await prisma.user.findUnique({
      where: { id: job.userId },
      select: { email: true },
    });
    return user?.email || null;
  } catch (error) {
    console.error('Failed to fetch current user email:', error);
    return null;
  }
}

/**
 * POST /api/workers/progress
 * Worker reports stage progress. This is the single source of truth for progress updates.
 *
 * This endpoint:
 * 1. Updates stage progress in the database
 * 2. Handles job completion (when report_path is provided)
 * 3. Handles job failure (when error is provided with status='failed')
 * 4. Broadcasts to SSE clients via EventEmitter
 * 5. Returns shouldCancel flag for cancellation detection
 */
workersRouter.post('/progress', async (req: Request, res: Response) => {
  try {
    const data = ProgressSchema.parse(req.body);

    // Convert status string to StageStatus enum
    const stageStatus = data.status === 'running' ? StageStatus.RUNNING
      : data.status === 'completed' ? StageStatus.COMPLETED
      : data.status === 'failed' ? StageStatus.FAILED
      : StageStatus.PENDING;

    // 1. Update stage progress in database
    await updateStageProgress(
      data.job_id,
      data.stage,
      stageStatus,
      data.error
    );

    // 2. Handle job completion (report_path indicates final success)
    if (data.status === 'completed' && data.report_path) {
      const completedJob = await completeJob(
        data.job_id,
        data.report_path,
        data.landing_path
      );

      // Send completion email
      if (completedJob) {
        const email = await getCurrentEmailForJob(completedJob);
        if (email) {
          sendCompletionEmail(email, data.job_id, completedJob.niche).catch(err => {
            console.error('Failed to send completion email:', err);
          });
        }
      }

      console.log(`[Workers] Job ${data.job_id} completed - report: ${data.report_path}`);
    }

    // 3. Handle job failure
    if (data.status === 'failed' && data.error) {
      await failJob(data.job_id, data.error, data.stage);

      // Send failure email
      const failedJob = await getJob(data.job_id);
      if (failedJob) {
        const email = await getCurrentEmailForJob(failedJob);
        if (email) {
          sendFailureEmail(email, data.job_id, failedJob.niche, data.error).catch(err => {
            console.error('Failed to send failure email:', err);
          });
        }
      }
    }

    // 4. Broadcast to SSE clients via EventEmitter
    try {
      broadcastProgress(data.job_id, {
        stage: data.stage,
        name: data.name,
        status: data.status,
        error: data.error,
        report_path: data.report_path,
        landing_path: data.landing_path,
      });
    } catch (broadcastErr) {
      // DB is already updated, broadcast failure is non-critical
      console.error('[Workers] Broadcast failed but DB updated:', broadcastErr);
    }

    // 5. Check if job should be cancelled
    const { prisma } = await import('../services/db.js');
    const job = await prisma.job.findUnique({
      where: { id: data.job_id },
      select: { status: true },
    });

    const shouldCancel = job?.status === 'CANCELLED';

    res.json({
      shouldCancel,
      timestamp: new Date().toISOString(),
    });
  } catch (error) {
    if (error instanceof z.ZodError) {
      res.status(400).json({ error: 'Validation error', details: error.errors });
      return;
    }
    console.error('[Workers] Progress update error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});
