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
import { refundForStage } from '../services/creditService.js';
import { broadcastProgress } from '../services/progressBroadcastService.js';
import { notifySolutionsReady, notifyPhase2Start, notifyRegenerationComplete, notifyLandingPageReady } from '../services/notificationService.js';
import {
  IdeasReadySchema,
  RegenerationCompleteSchema,
  RegenerationFailedSchema,
} from '../types/job.js';
import { notifyJobStart, notifyJobComplete, notifyJobError } from '../services/notificationService.js';
import { AssetType } from '@prisma/client';
import { requireInternalService } from '../middleware/auth.js';
import { StageStatus } from '@prisma/client';
import { PIPELINE_STAGES } from '../types/job.js';
import { buildErrorDetails } from '../utils/errorTranslator.js';
import { getPhaseContext } from '../utils/phaseContext.js';

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
        select: { status: true, niche: true, userId: true, currentStage: true, selectedSolutions: true },
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

        // Send failure notification with user-friendly details and phase context
        if (job.userId) {
          const user = await prisma.user.findUnique({
            where: { id: job.userId },
            select: { email: true },
          });
          if (user?.email) {
            const phaseCtx = getPhaseContext(job.currentStage, job.selectedSolutions);
            notifyJobError(job.userId, user.email, data.job_id, job.niche, errorMessage, translatedErrorDetails, phaseCtx).catch(emailError => {
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
 * Worker reports it has started processing a job.
 * Returns shouldCancel: true if job was cancelled while in queue.
 */
workersRouter.post('/job-started', async (req: Request, res: Response) => {
  try {
    const data = JobStartedSchema.parse(req.body);

    const { prisma } = await import('../services/db.js');
    const { JobStatus } = await import('@prisma/client');

    // Detect Phase 2 and regeneration jobs
    const existingJob = await prisma.job.findUnique({
      where: { id: data.job_id },
      select: { selectedSolutions: true, ideasRegeneratedAt: true },
    });
    const hasSelections = existingJob?.selectedSolutions && existingJob.selectedSolutions.length > 0;
    const isRegenerate = existingJob?.ideasRegeneratedAt != null && !hasSelections;
    const isPhase2 = !isRegenerate && hasSelections;
    const runningStatus = isRegenerate ? JobStatus.REGENERATING : isPhase2 ? JobStatus.RUNNING_PHASE2 : JobStatus.RUNNING;

    // Atomic conditional update - only if job is in startable state
    // This prevents overwriting CANCELLED status when a job was cancelled while in queue
    const result = await prisma.job.updateMany({
      where: {
        id: data.job_id,
        status: { in: [JobStatus.QUEUED, JobStatus.PENDING] },
      },
      data: {
        workerId: data.worker_id,
        lastHeartbeat: new Date(),
        status: runningStatus,
        startedAt: new Date(),
        errorMessage: null, // Clear any retry messages from previous attempts
      },
    });

    // If no rows updated, check why
    if (result.count === 0) {
      const job = await prisma.job.findUnique({
        where: { id: data.job_id },
        select: { status: true },
      });

      if (job?.status === JobStatus.CANCELLED) {
        console.log(`[Workers] Job ${data.job_id} was cancelled - signaling worker to skip`);
        return res.json({ status: 'ok', shouldCancel: true });
      }
      // Job might already be RUNNING (duplicate call) or not found - proceed normally
      console.log(`[Workers] Job ${data.job_id} not updated (status: ${job?.status ?? 'not found'})`);
    }

    // Update worker heartbeat
    await registerWorkerHeartbeat(data.worker_id, data.job_id);

    // Send job start notification (only if we actually started the job)
    if (result.count > 0) {
      const job = await prisma.job.findUnique({
        where: { id: data.job_id },
        include: {
          user: {
            select: { id: true, email: true },
          },
        },
      });

      if (job?.user?.email) {
        if (isPhase2 && existingJob?.selectedSolutions?.length) {
          notifyPhase2Start(job.userId, job.user.email, data.job_id, job.niche, existingJob.selectedSolutions).catch(err => {
            console.error('Failed to send phase 2 start notification:', err);
          });
        } else if (!isRegenerate) {
          notifyJobStart(job.userId, job.user.email, data.job_id, job.niche).catch(err => {
            console.error('Failed to send job start notification:', err);
          });
        }
        // Regeneration start: no email (user just triggered it from UI)
      }

      console.log(`[Workers] Job ${data.job_id} started by worker ${data.worker_id}`);
    }

    res.json({ status: 'ok', shouldCancel: false });
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
  winner_name: z.string().max(255).optional(),
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
      select: { userId: true, niche: true, selectedSolutions: true },
    });

    // Persist Phase 2 winner if provided
    if (data.winner_name && job?.selectedSolutions?.includes(data.winner_name)) {
      await prisma.job.update({
        where: { id: data.job_id },
        data: { selectedSolution: data.winner_name },
      });
    }

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
      stage: 14,
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
    const isLandingPageFailure = data.error_stage === 15 && reportAsset;

    let jobStatus: string;

    if (isLandingPageFailure) {
      // Landing page failure only - don't fail the entire job, refund landing page credit
      console.log(`[Workers] Landing page failure for job ${data.job_id} - completing job without landing page`);

      // Refund landing page credits
      try {
        await refundForStage(data.job_id, 'landing_page');
      } catch (refundErr) {
        console.error(`[Workers] Failed to refund landing page credits for job ${data.job_id}:`, refundErr);
      }

      await prisma.job.update({
        where: { id: data.job_id },
        data: { landingPageStatus: 'FAILED' },
      });

      // Mark stage 15 as FAILED
      try {
        await prisma.jobProgress.updateMany({
          where: { jobId: data.job_id, stageNumber: 15, status: StageStatus.RUNNING },
          data: { status: StageStatus.FAILED, errorMessage: data.error_message },
        });
      } catch (stageErr) {
        console.error(`[Workers] Failed to update stage 15 to FAILED:`, stageErr);
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
  status: z.enum(['running', 'completed', 'skipped', 'failed']),
  error: z.string().max(10000).optional(),
  report_path: z.string().max(500).optional(),
  landing_path: z.string().max(500).optional(),
  artifact: z.record(z.unknown()).optional(),
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
      : data.status === 'skipped' ? StageStatus.SKIPPED
      : data.status === 'failed' ? StageStatus.FAILED
      : StageStatus.PENDING;

    // 1. Update stage progress in database
    await updateStageProgress(
      data.job_id,
      data.stage,
      stageStatus,
      data.error,
      data.artifact
    );

    // Track landing page lifecycle via landingPageStatus
    if (data.stage === 15) {
      const { prisma: db } = await import('../services/db.js');
      if (data.status === 'running') {
        // CAS: only transition QUEUED → RUNNING, also reset heartbeat so monitor
        // doesn't immediately flag this as stale from an old pipeline heartbeat
        await db.job.updateMany({
          where: {
            id: data.job_id,
            OR: [
              { landingPageStatus: 'QUEUED' },
              { landingPageStatus: null },
            ],
          },
          data: {
            landingPageStatus: 'RUNNING',
            lastHeartbeat: new Date(),
          },
        });
      } else if (data.status === 'completed') {
        // Record asset unconditionally — the file exists on disk regardless of status race
        if (data.landing_path) {
          await import('../services/jobService.js').then(m =>
            m.addJobAsset(data.job_id, AssetType.LANDING_PAGE, data.landing_path!)
          );
        }

        // CAS: only transition RUNNING/QUEUED → COMPLETED
        const lpResult = await db.job.updateMany({
          where: {
            id: data.job_id,
            landingPageStatus: { in: ['RUNNING', 'QUEUED'] },
          },
          data: { landingPageStatus: 'COMPLETED' },
        });

        if (lpResult.count > 0) {
          // Notify user landing page is ready
          const lpJob = await getJob(data.job_id);
          if (lpJob) {
            const email = await getCurrentEmailForJob(lpJob);
            if (email) {
              notifyLandingPageReady(lpJob.userId, email, data.job_id, lpJob.niche).catch(err => {
                console.error('Failed to send landing page notification:', err);
              });
            }
          }
        } else {
          console.warn(`[Workers] LP status for job ${data.job_id} already changed, skipping completion`);
        }
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

    // 3. Handle job failure
    if (data.status === 'failed' && data.error) {
      // Check if this is a landing-page-only failure
      const reportAsset = await getJobAsset(data.job_id, AssetType.REPORT_JSON);
      if (data.stage === 15 && reportAsset) {
        // Landing page failure - don't fail the entire job, refund landing page credit
        const { prisma: db } = await import('../services/db.js');
        await db.job.update({
          where: { id: data.job_id },
          data: { landingPageStatus: 'FAILED' },
        });
        // Refund landing page credits
        try {
          await refundForStage(data.job_id, 'landing_page');
        } catch (refundErr) {
          console.error(`[Workers] Failed to refund landing page credits for job ${data.job_id}:`, refundErr);
        }
        // Complete the job if not already completed
        await completeJob(data.job_id, reportAsset.filePath);
        console.log(`[Workers] Landing page failed for job ${data.job_id} but job completed`);
      } else {
        await failJob(data.job_id, data.error, data.stage);

        // Send failure notification with phase context
        const failedJob = await getJob(data.job_id);
        if (failedJob) {
          const email = await getCurrentEmailForJob(failedJob);
          if (email) {
            const phaseCtx = getPhaseContext(data.stage, failedJob.selectedSolutions);
            notifyJobError(failedJob.userId, email, data.job_id, failedJob.niche, data.error, null, phaseCtx).catch(err => {
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

// ============================================
// Interactive Job Flow Worker Endpoints
// ============================================

/**
 * POST /api/workers/ideas-ready
 * Worker reports that Phase 1 solution ideas are ready for user review.
 * Transitions job from RUNNING → AWAITING_SELECTION.
 */
workersRouter.post('/ideas-ready', async (req: Request, res: Response) => {
  try {
    const data = IdeasReadySchema.parse(req.body);
    const { prisma } = await import('../services/db.js');
    const { JobStatus } = await import('@prisma/client');

    // Atomic conditional update: RUNNING → AWAITING_SELECTION
    const result = await prisma.job.updateMany({
      where: {
        id: data.job_id,
        status: JobStatus.RUNNING,
      },
      data: {
        status: JobStatus.AWAITING_SELECTION,
        solutionIdeas: data.solutions as any,
        phase1CheckpointPath: data.checkpoint_path,
        ideasShownAt: new Date(),
        awaitingSelectionAt: new Date(),
      },
    });

    if (result.count === 0) {
      res.status(409).json({ error: 'Job not in RUNNING state' });
      return;
    }

    // Broadcast progress update to SSE clients
    broadcastProgress(data.job_id, {
      stage: 5,
      name: 'Solution Pipeline',
      status: 'completed',
    });

    // Send "solutions ready" email notification
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
        notifySolutionsReady(job.userId, user.email, data.job_id, job.niche, data.solutions.length).catch(err => {
          console.error('Failed to send solutions-ready notification:', err);
        });
      }
    }

    console.log(`[Workers] Ideas ready for job ${data.job_id}: ${data.solutions.length} solutions`);
    res.json({ status: 'ok' });
  } catch (error) {
    if (error instanceof z.ZodError) {
      res.status(400).json({ error: 'Validation error', details: error.errors });
      return;
    }
    console.error('[Workers] Ideas ready error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

/**
 * POST /api/workers/regeneration-complete
 * Worker reports new solution ideas from regeneration. Merges new solutions and transitions REGENERATING → AWAITING_SELECTION.
 */
workersRouter.post('/regeneration-complete', async (req: Request, res: Response) => {
  try {
    const data = RegenerationCompleteSchema.parse(req.body);
    const { prisma } = await import('../services/db.js');
    const { JobStatus } = await import('@prisma/client');

    // Get existing solutions to merge with new ones
    const job = await prisma.job.findFirst({
      where: {
        id: data.job_id,
        status: { in: [JobStatus.REGENERATING, JobStatus.QUEUED] },
        ideasRegeneratedAt: { not: null },  // Guard: only regen-queued, not initial queued
      },
      select: { solutionIdeas: true, userId: true, niche: true },
    });

    if (!job) {
      res.status(409).json({ error: 'Job not in REGENERATING state' });
      return;
    }

    const existingSolutions = (job.solutionIdeas as any[]) || [];
    const mergedSolutions = [...existingSolutions, ...data.solutions];

    // Atomic update: REGENERATING/QUEUED → AWAITING_SELECTION (skip validation)
    const result = await prisma.job.updateMany({
      where: {
        id: data.job_id,
        status: { in: [JobStatus.REGENERATING, JobStatus.QUEUED] },
        ideasRegeneratedAt: { not: null },
      },
      data: {
        status: JobStatus.AWAITING_SELECTION,
        solutionIdeas: mergedSolutions as any,
      },
    });

    if (result.count === 0) {
      res.status(409).json({ error: 'Job state changed during regeneration' });
      return;
    }

    // Broadcast progress update
    broadcastProgress(data.job_id, {
      stage: 5,
      name: 'Solution Pipeline',
      status: 'completed',
    });

    // Send regeneration-complete notification
    if (job.userId) {
      const user = await prisma.user.findUnique({ where: { id: job.userId }, select: { email: true } });
      if (user?.email) {
        notifyRegenerationComplete(job.userId, user.email, data.job_id, job.niche, data.solutions.length, mergedSolutions.length).catch(err => {
          console.error('Failed to send regeneration-complete notification:', err);
        });
      }
    }

    console.log(`[Workers] Regeneration complete for job ${data.job_id}: ${data.solutions.length} new solutions`);
    res.json({ status: 'ok' });
  } catch (error) {
    if (error instanceof z.ZodError) {
      res.status(400).json({ error: 'Validation error', details: error.errors });
      return;
    }
    console.error('[Workers] Regeneration complete error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

/**
 * POST /api/workers/regeneration-failed
 * Worker reports that idea regeneration failed. Reverts REGENERATING → AWAITING_SELECTION
 * so the user can see existing solutions and retry. Refunds regeneration credits.
 */
workersRouter.post('/regeneration-failed', async (req: Request, res: Response) => {
  try {
    const data = RegenerationFailedSchema.parse(req.body);
    const { prisma } = await import('../services/db.js');
    const { JobStatus } = await import('@prisma/client');

    // Refund regeneration credits
    try {
      await refundForStage(data.job_id, 'regenerate_ideas');
    } catch (refundErr) {
      console.error(`[Workers] Failed to refund regeneration credits for job ${data.job_id}:`, refundErr);
    }

    // Atomic revert: REGENERATING/QUEUED → AWAITING_SELECTION, reset ideasRegeneratedAt
    const result = await prisma.job.updateMany({
      where: {
        id: data.job_id,
        status: { in: [JobStatus.REGENERATING, JobStatus.QUEUED] },
        ideasRegeneratedAt: { not: null },  // Guard: only revert regen-queued, not initial queued
      },
      data: {
        status: JobStatus.AWAITING_SELECTION,
        ideasRegeneratedAt: null,
      },
    });

    if (result.count === 0) {
      res.status(409).json({ error: 'Job not in REGENERATING state' });
      return;
    }

    // Clear worker's current job
    await registerWorkerHeartbeat(data.worker_id, null);

    // Revert stage 5 from RUNNING back to COMPLETED (original solutions still valid)
    await updateStageProgress(data.job_id, 5, StageStatus.COMPLETED);

    // Broadcast progress so frontend re-fetches and shows solutions
    broadcastProgress(data.job_id, {
      stage: 5,
      name: 'Solution Pipeline',
      status: 'completed',
    });

    console.log(`[Workers] Regeneration failed for job ${data.job_id}, reverted to AWAITING_SELECTION: ${data.error_message}`);
    res.json({ status: 'ok' });
  } catch (error) {
    if (error instanceof z.ZodError) {
      res.status(400).json({ error: 'Validation error', details: error.errors });
      return;
    }
    console.error('[Workers] Regeneration failed error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

