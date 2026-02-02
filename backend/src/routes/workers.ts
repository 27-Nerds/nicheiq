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
import { failJob, updateStageProgress, completeJob, getJob, addJobAsset, getJobAsset } from '../services/jobService.js';
import { broadcastProgress } from '../services/progressBroadcastService.js';
import { notifyJobStart, notifyJobComplete, notifyJobError } from '../services/notificationService.js';
import { AssetType } from '@prisma/client';
import { requireInternalService } from '../middleware/auth.js';
import { StageStatus } from '@prisma/client';
import { PIPELINE_STAGES } from '../types/job.js';
import { buildErrorDetails } from '../utils/errorTranslator.js';

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

      const job = await prisma.job.findUnique({
        where: { id: data.job_id },
        select: { status: true, niche: true, userId: true },
      });

      if (job && job.status === JobStatus.RUNNING) {
        const errorMessage = `Worker shutdown: ${data.reason || 'graceful shutdown'}. Use checkpoint resume to continue.`;

        // Worker shutdown is classified as WORKER_CRASH for user-friendly messaging
        const translatedErrorDetails = buildErrorDetails('WORKER_CRASH', { rawMessage: errorMessage });

        await failJob(data.job_id, errorMessage, undefined, undefined, undefined, 'WORKER_CRASH', translatedErrorDetails ?? undefined);
        console.log(`[Workers] Job ${data.job_id} marked as failed due to worker shutdown`);

        // Mark ALL running stages as FAILED
        try {
          await prisma.jobProgress.updateMany({
            where: { jobId: data.job_id, status: StageStatus.RUNNING },
            data: {
              status: StageStatus.FAILED,
              errorMessage,
            },
          });
        } catch (stageErr) {
          console.error(`[Workers] Failed to update running stages to FAILED:`, stageErr);
        }

        // Broadcast failure to SSE clients
        try {
          broadcastProgress(data.job_id, {
            stage: 1,
            name: 'Failed',
            status: 'failed',
            error: errorMessage,
          });
        } catch (broadcastErr) {
          console.error('[Workers] Broadcast failed but DB updated:', broadcastErr);
        }

        // Send failure notification with user-friendly details
        if (job.userId) {
          const user = await prisma.user.findUnique({
            where: { id: job.userId },
            select: { email: true },
          });
          if (user?.email) {
            notifyJobError(job.userId, user.email, data.job_id, job.niche, errorMessage, translatedErrorDetails).catch(emailError => {
              console.error(`[Workers] Failed to send failure notification for job ${data.job_id}:`, emailError);
            });
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
    const job = await prisma.job.update({
      where: { id: data.job_id },
      data: {
        workerId: data.worker_id,
        lastHeartbeat: new Date(),
        status: JobStatus.RUNNING,
        startedAt: new Date(),
        errorMessage: null, // Clear any retry messages from previous attempts
      },
      include: {
        user: {
          select: { id: true, email: true },
        },
      },
    });

    // Update worker heartbeat
    await registerWorkerHeartbeat(data.worker_id, data.job_id);

    // Send job start notification
    if (job.user?.email) {
      notifyJobStart(job.userId, job.user.email, data.job_id, job.niche).catch(err => {
        console.error('Failed to send job start notification:', err);
      });
    }

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
 * Report ready request schema
 */
const ReportReadySchema = z.object({
  worker_id: z.string().min(1),
  job_id: z.string().uuid(),
  report_path: z.string().min(1).max(500),
});

/**
 * POST /api/workers/report-ready
 * Worker reports that the research report is ready (before landing page).
 * This triggers "report ready" notification so users can view reports immediately.
 */
workersRouter.post('/report-ready', async (req: Request, res: Response) => {
  try {
    const data = ReportReadySchema.parse(req.body);

    // Add report asset
    await addJobAsset(data.job_id, AssetType.REPORT_JSON, data.report_path);

    // Send "report ready" notification
    const { prisma } = await import('../services/db.js');
    const job = await prisma.job.findUnique({
      where: { id: data.job_id },
      select: { userId: true, niche: true },
    });

    if (job?.userId) {
      const user = await prisma.user.findUnique({
        where: { id: job.userId },
        select: { email: true },
      });
      if (user?.email) {
        notifyJobComplete(job.userId, user.email, data.job_id, job.niche).catch(err => {
          console.error('Failed to send report-ready notification:', err);
        });
      }
    }

    // Broadcast SSE event so frontend can show the report
    broadcastProgress(data.job_id, {
      stage: 10,
      name: 'Report Generation',
      status: 'completed',
      report_path: data.report_path,
    });

    console.log(`[Workers] Report ready for job ${data.job_id}: ${data.report_path}`);
    res.json({ status: 'ok' });
  } catch (error) {
    if (error instanceof z.ZodError) {
      res.status(400).json({ error: 'Validation error', details: error.errors });
      return;
    }
    console.error('Report ready error:', error);
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
  // Classified error fields for user-friendly messaging
  error_code: z.string().max(50).optional(),
  error_details: z.record(z.any()).optional(),
  // Quality gate stop fields (for intentional stops, not errors)
  stop_reason: z.string().max(50).optional(),
  stop_reason_details: z.record(z.any()).optional(),
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

    // Log quality gate stops differently from errors
    if (data.stop_reason) {
      console.log(`[Workers] Job ${data.job_id} stopped by quality gate (${data.stop_reason}) at stage ${data.error_stage}`);
    } else {
      console.log(`[Workers] Job ${data.job_id} failed reported by worker ${data.worker_id}: ${data.error_message.substring(0, 100)}`);
      if (data.error_code) {
        console.log(`[Workers] Error code: ${data.error_code}`);
      }
    }

    // Build translated error details for user-friendly messaging
    const translatedErrorDetails = buildErrorDetails(data.error_code, data.error_details);

    const { prisma } = await import('../services/db.js');

    // Check if this is a landing-page-only failure with existing report
    const reportAsset = await getJobAsset(data.job_id, AssetType.REPORT_JSON);
    const isLandingPageFailure = data.error_stage === 11 && reportAsset;

    let jobStatus: string;

    if (isLandingPageFailure) {
      // Landing page failure only - don't fail the entire job, no credit refund
      console.log(`[Workers] Landing page failure for job ${data.job_id} - completing job without landing page`);

      await prisma.job.update({
        where: { id: data.job_id },
        data: { landingPageStatus: 'FAILED' },
      });

      // Mark stage 11 as FAILED
      try {
        await prisma.jobProgress.updateMany({
          where: { jobId: data.job_id, stageNumber: 11, status: StageStatus.RUNNING },
          data: { status: StageStatus.FAILED, errorMessage: data.error_message },
        });
      } catch (stageErr) {
        console.error(`[Workers] Failed to update stage 11 to FAILED:`, stageErr);
      }

      // Complete the job if not already completed
      const completedJob = await completeJob(data.job_id, reportAsset.filePath);
      jobStatus = completedJob?.status ?? 'COMPLETED';
    } else {
      // Normal failure handling - failJob is idempotent
      const job = await failJob(
        data.job_id,
        data.error_message,
        data.error_stage ?? undefined,
        data.stop_reason,
        data.stop_reason_details,
        data.error_code,
        translatedErrorDetails ?? undefined
      );
      jobStatus = job?.status ?? 'unknown';

      // Mark ALL running stages as FAILED (handles parallel stages 6 & 6.5)
      try {
        await prisma.jobProgress.updateMany({
          where: { jobId: data.job_id, status: StageStatus.RUNNING },
          data: {
            status: StageStatus.FAILED,
            errorMessage: data.error_message,
            // Do NOT set completedAt - preserve null so resume gets correct duration
          },
        });
      } catch (stageErr) {
        console.error(`[Workers] Failed to update running stages to FAILED:`, stageErr);
      }
    }

    // Broadcast failure to SSE clients
    try {
      broadcastProgress(data.job_id, {
        stage: data.error_stage ?? 1,
        name: isLandingPageFailure ? 'Landing Page Generation' : 'Failed',
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
      status: jobStatus,
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

    // Track landing page lifecycle via landingPageStatus
    if (data.stage === 11) {
      const { prisma: db } = await import('../services/db.js');
      if (data.status === 'running') {
        await db.job.update({
          where: { id: data.job_id },
          data: { landingPageStatus: 'RUNNING' },
        });
      } else if (data.status === 'completed' && !data.landing_path) {
        // Stage 11 completed without landing_path means guardrail failure (None result)
        await db.job.update({
          where: { id: data.job_id },
          data: { landingPageStatus: 'COMPLETED' },
        });
      }
    }

    // 2. Handle job completion (report_path indicates final success)
    if (data.status === 'completed' && data.report_path) {
      await completeJob(
        data.job_id,
        data.report_path,
        data.landing_path
      );

      // Skip email notification here - already sent by /report-ready endpoint
      console.log(`[Workers] Job ${data.job_id} completed - report: ${data.report_path}`);
    }

    // 2b. Handle landing page completion (landing_path without report_path = landing-only task)
    if (data.status === 'completed' && data.landing_path && !data.report_path) {
      const { prisma: db } = await import('../services/db.js');
      await import('../services/jobService.js').then(m => m.addJobAsset(data.job_id, AssetType.LANDING_PAGE, data.landing_path!));
      await db.job.update({
        where: { id: data.job_id },
        data: { landingPageStatus: 'COMPLETED' },
      });
      console.log(`[Workers] Landing page completed for job ${data.job_id}: ${data.landing_path}`);
    }

    // 3. Handle job failure
    if (data.status === 'failed' && data.error) {
      // Check if this is a landing-page-only failure
      const reportAsset = await getJobAsset(data.job_id, AssetType.REPORT_JSON);
      if (data.stage === 11 && reportAsset) {
        // Landing page failure - don't fail the entire job
        const { prisma: db } = await import('../services/db.js');
        await db.job.update({
          where: { id: data.job_id },
          data: { landingPageStatus: 'FAILED' },
        });
        // Complete the job if not already completed
        await completeJob(data.job_id, reportAsset.filePath);
        console.log(`[Workers] Landing page failed for job ${data.job_id} but job completed`);
      } else {
        await failJob(data.job_id, data.error, data.stage);

        // Send failure notification
        const failedJob = await getJob(data.job_id);
        if (failedJob) {
          const email = await getCurrentEmailForJob(failedJob);
          if (email) {
            notifyJobError(failedJob.userId, email, data.job_id, failedJob.niche, data.error).catch(err => {
              console.error('Failed to send failure notification:', err);
            });
          }
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
