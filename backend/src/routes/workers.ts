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

import { Router, Request, Response, json as expressJson } from 'express';
import { z } from 'zod';
import {
  updateJobHeartbeat,
  registerWorkerHeartbeat,
  markWorkerShutdown,
} from '../services/heartbeatService.js';
import { failJob, updateStageProgress, completeJob, getJob, addJobAsset, getJobAsset } from '../services/jobService.js';
import { refundForStage, refundForRegenerationStage } from '../services/creditService.js';
import { broadcastProgress } from '../services/progressBroadcastService.js';
import { notifySolutionsReady, notifyPhase2Start, notifyRegenerationComplete, notifyLandingPageReady } from '../services/notificationService.js';
import {
  IdeasReadySchema,
  RegenerationCompleteSchema,
  RegenerationFailedSchema,
} from '../types/job.js';
import { notifyJobStart, notifyJobComplete, notifyJobError } from '../services/notificationService.js';
import { AssetType } from '@prisma/client';
import type { JobStatus as JobStatusType } from '@prisma/client';
import { bigramSimilarity, canonicalizeAddressedTitles, normalizeTitle } from '../services/titleMatching.js';
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

      // Terminal/settled states must NOT be re-run (infra review round 2: a stale-requeued
      // job whose backend heartbeat already marked it FAILED — and refunded it — was being
      // blessed to run again). Missing jobs likewise: nothing to run for.
      const doNotRun = new Set<string>([
        JobStatus.CANCELLED,
        JobStatus.FAILED,
        JobStatus.COMPLETED,
        JobStatus.AWAITING_SELECTION,
      ]);
      if (!job || doNotRun.has(job.status)) {
        console.log(
          `[Workers] Job ${data.job_id} not runnable (status: ${job?.status ?? 'not found'}) - signaling worker to skip`
        );
        return res.json({ status: 'ok', shouldCancel: true });
      }
      // Job might already be RUNNING (duplicate call) - proceed normally
      console.log(`[Workers] Job ${data.job_id} not updated (status: ${job.status})`);
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

    // Phase 5.4 — pre-check asset existence so the user-facing notification
    // fires exactly once even if the worker re-delivers (publish_report_ready
    // now re-raises on POST failure). Asset upsert is naturally idempotent;
    // the notification is the side-effect that needs gating.
    const existingAsset = await getJobAsset(data.job_id, AssetType.REPORT_JSON);
    const isFirstDelivery = existingAsset == null;

    await addJobAsset(data.job_id, AssetType.REPORT_JSON, data.report_path);

    // Phase 5.4 — pre-project sanitized context for the SAME sourceJobId.
    // For catalog jobs that already have a preview-derived row, this upgrades
    // it to the richer REPORT_JSON projection (forceRefreshAll). For /new
    // jobs without an existing context row, this pre-projects context that
    // future publish hooks will short-circuit on. NOT a no-op.
    const { extractOrCreateResearchContext } = await import('../services/researchContextService.js');
    await extractOrCreateResearchContext(data.job_id, { forceRefreshAll: true });

    // Send "report ready" notification
    const { prisma } = await import('../services/db.js');
    const job = await prisma.job.findUnique({
      where: { id: data.job_id },
      select: { userId: true, niche: true, selectedSolutions: true },
    });

    // Persist Phase 2 winner if provided. Normalized comparison (trim + collapse
    // whitespace + casefold): the Python side may sanitize/echo the name with
    // trivial drift, which must not silently drop winner persistence.
    const normalizeName = (s: string) => s.trim().replace(/\s+/g, ' ').toLowerCase();
    if (data.winner_name && job?.selectedSolutions?.length) {
      const winnerNorm = normalizeName(data.winner_name);
      const matched = job.selectedSolutions.find((s) => normalizeName(s) === winnerNorm);
      if (matched) {
        await prisma.job.update({
          where: { id: data.job_id },
          // Persist the user-selected spelling, not the worker echo.
          data: { selectedSolution: matched },
        });
      }
    }

    if (isFirstDelivery && job?.userId) {
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

    console.log(`[Workers] Report ready for job ${data.job_id}: ${data.report_path} (firstDelivery=${isFirstDelivery})`);
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
      // Distinguish WHY the conditional update missed (mirrors the /job-complete precedent):
      // a lost-response retry must read as idempotent success, while a cancelled/failed job
      // must NOT — the worker previously treated every 409 as "delivered", silently
      // discarding a completed run's ideas.
      const job = await prisma.job.findUnique({
        where: { id: data.job_id },
        select: { status: true, ideasShownAt: true },
      });
      if (!job) {
        res.status(404).json({ error: 'Job not found' });
        return;
      }
      if (job.status === JobStatus.AWAITING_SELECTION || job.ideasShownAt !== null) {
        // A previous attempt landed and the response was lost — idempotent success.
        // Skip re-broadcast/notify: the first delivery already did both.
        res.json({ status: 'ok', idempotent: true });
        return;
      }
      res.status(409).json({
        error: `Job not in RUNNING state (current: ${job.status})`,
        state: job.status,
      });
      return;
    }

    // Register discovery data asset if provided
    if (data.discovery_data_path) {
      const { AssetType } = await import('@prisma/client');
      const { addJobAsset } = await import('../services/jobService.js');
      try {
        await addJobAsset(data.job_id, AssetType.DISCOVERY_DATA, data.discovery_data_path);
        console.log(`[Workers] Discovery data asset registered for job ${data.job_id}`);
      } catch (err) {
        console.warn(`[Workers] Failed to register discovery data asset: ${err}`);
      }
    }

    // Register preview report asset if provided
    if (data.preview_report_path) {
      const { AssetType } = await import('@prisma/client');
      const { addJobAsset } = await import('../services/jobService.js');
      try {
        await addJobAsset(data.job_id, AssetType.PREVIEW_REPORT, data.preview_report_path);
        console.log(`[Workers] Preview report asset registered for job ${data.job_id}`);
      } catch (err) {
        console.warn(`[Workers] Failed to register preview report asset:`, err);
      }
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

    // Fetch regenerationCount before reverting (needed for numbered refund)
    const jobForRefund = await prisma.job.findUnique({
      where: { id: data.job_id },
      select: { regenerationCount: true },
    });

    // Atomic revert: REGENERATING/QUEUED → AWAITING_SELECTION
    const result = await prisma.job.updateMany({
      where: {
        id: data.job_id,
        status: { in: [JobStatus.REGENERATING, JobStatus.QUEUED] },
        ideasRegeneratedAt: { not: null },  // Guard: only revert regen-queued, not initial queued
      },
      data: {
        status: JobStatus.AWAITING_SELECTION,
      },
    });

    if (result.count === 0) {
      res.status(409).json({ error: 'Job not in REGENERATING state' });
      return;
    }

    // Refund regeneration credits AFTER confirming the job was actually reverted
    if (jobForRefund?.regenerationCount) {
      try {
        await refundForRegenerationStage(data.job_id, jobForRefund.regenerationCount);
      } catch (refundErr) {
        console.error(`[Workers] Failed to refund regeneration credits for job ${data.job_id}:`, refundErr);
      }
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

// ============================================
// Catalog Generation Worker Endpoints
// ============================================

// `normalizeTitle` and `bigramSimilarity` now live in services/titleMatching.ts —
// shared with publishIdea / catalog-ideas-ready / backfill so all sites apply
// identical match semantics. Imported above.

const OPPORTUNITY_RANK: Record<string, number> = { high: 3, medium: 2, low: 1 };

const CatalogPainPointsReadySchema = z.object({
  worker_id: z.string().min(1),
  job_id: z.string().uuid(),
  category_id: z.string().uuid(),
  pain_points: z.array(z.record(z.unknown())),
  niche: z.string(),
  // Phase 5.4 — load-bearing: catalog flow must materialize a preview report
  // before notifying. Worker raises if materialization fails. Optional in
  // schema for forward compat but rejected at handler level when absent.
  preview_report_path: z.string().min(1).max(500).optional(),
});

/**
 * POST /api/workers/catalog-pain-points-ready
 * Worker reports catalog pain points are ready. Merges similar and inserts new.
 *
 * Phase 5.4 invariants:
 * - Three-tier status guard at entry (404 / already_processed / 409 / process)
 * - preview_report_path required (load-bearing for projection)
 * - Asset registration + extraction run OUTSIDE the transaction (idempotent)
 * - hasMeaningfulResearchContext assertion before any catalog mutations
 * - Merge/insert loop + status flip wrapped in a transaction with a
 *   `FOR UPDATE` row lock on the Job row to serialize concurrent duplicates
 * - P2002 on lineage advance → merge data into the conflicting new-source
 *   row and deactivate the old-lineage row (preserves "latest wins")
 * - SSE broadcast + cache invalidation run outside the transaction
 */
workersRouter.post('/catalog-pain-points-ready', async (req: Request, res: Response) => {
  try {
    const data = CatalogPainPointsReadySchema.parse(req.body);
    const { prisma } = await import('../services/db.js');
    const { JobStatus, AssetType } = await import('@prisma/client');

    // ─── Three-tier status guard ─────────────────────────────────────────
    const job = await prisma.job.findUnique({
      where: { id: data.job_id },
      select: { status: true },
    });
    if (!job) {
      res.status(404).json({ error: 'Job not found' });
      return;
    }
    if (job.status === JobStatus.COMPLETED) {
      console.log(`[Workers] catalog-pain-points-ready: job ${data.job_id} already COMPLETED — skipping reprocess`);
      res.json({ status: 'already_processed' });
      return;
    }
    if (job.status !== JobStatus.RUNNING && job.status !== JobStatus.QUEUED) {
      console.warn(`[Workers] catalog-pain-points-ready: job ${data.job_id} in status ${job.status} — refusing to mutate`);
      res.status(409).json({ error: `Job not in RUNNING/QUEUED state (current: ${job.status})` });
      return;
    }

    // ─── Reject missing preview path (load-bearing) ──────────────────────
    if (!data.preview_report_path) {
      res.status(400).json({ error: 'preview_report_path required for catalog pain-points' });
      return;
    }

    // ─── Asset registration + extraction OUTSIDE transaction ─────────────
    // Both are idempotent. Reading the preview file is sync I/O and must
    // not hold a transactional connection.
    const { addJobAsset } = await import('../services/jobService.js');
    await addJobAsset(data.job_id, AssetType.PREVIEW_REPORT, data.preview_report_path);

    const { extractOrCreateResearchContext, hasMeaningfulResearchContext, MEANINGFUL_SELECT } = await import(
      '../services/researchContextService.js'
    );
    const ctx = await extractOrCreateResearchContext(data.job_id, {
      forceRefreshPlaceholders: true,
      sourceKind: 'catalog',
    });

    // Meaningfulness gate. Applies to both pain-points-present and -empty
    // paths: the preview must yield renderable content for the catalog row
    // to be useful. Otherwise fail → RQ retry.
    if (!hasMeaningfulResearchContext(ctx)) {
      console.error(
        `[Workers] Catalog research context for ${data.job_id} has no meaningful data; aborting for RQ retry`,
      );
      res.status(500).json({ error: 'Research context not meaningful; will retry' });
      return;
    }

    // ─── Transactional mutation block ────────────────────────────────────
    const buildMergeData = (
      bestMatch: { mentionCount: number; severityScore: number; commercialIntentScore: number; representativeQuotes: unknown; sourcePlatforms: unknown; affectedSegments: unknown; opportunityLevel: string; themeId: string | null },
      newPp: Record<string, unknown>,
    ) => {
      const existingQuotes = (bestMatch.representativeQuotes as string[] | null) || [];
      const newQuotes = (newPp.representative_quotes as string[] | null) || [];
      const mergedQuotes = [...new Set([...existingQuotes, ...newQuotes])].slice(0, 12);

      const existingPlatforms = (bestMatch.sourcePlatforms as string[] | null) || [];
      const newPlatforms = (newPp.source_platforms as string[] | null) || [];
      const mergedPlatforms = [...new Set([...existingPlatforms, ...newPlatforms])];

      const existingSegments = (bestMatch.affectedSegments as string[] | null) || [];
      const newSegments = (newPp.affected_segments as string[] | null) || [];
      const mergedSegments = [...new Set([...existingSegments, ...newSegments])];

      const newOppLevel = String(newPp.opportunity_level || 'medium');
      const existingOppRank = OPPORTUNITY_RANK[bestMatch.opportunityLevel] || 0;
      const newOppRank = OPPORTUNITY_RANK[newOppLevel] || 0;

      // Latest research wins for themeId — same policy as sourceJobId/sourceGeneratedAt
      // advance on lineage update. Fall back to the existing themeId if the new
      // payload didn't supply one (defensive: don't lose linkage on partial reingest).
      const newThemeId = typeof newPp.parent_theme_id === 'string' && newPp.parent_theme_id
        ? newPp.parent_theme_id
        : null;

      return {
        mentionCount: bestMatch.mentionCount + (Number(newPp.mention_count) || 0),
        severityScore: Math.max(bestMatch.severityScore, Number(newPp.severity_score) || 0),
        commercialIntentScore: Math.max(bestMatch.commercialIntentScore, Number(newPp.commercial_intent) || 0),
        representativeQuotes: mergedQuotes,
        sourcePlatforms: mergedPlatforms,
        affectedSegments: mergedSegments,
        opportunityLevel: newOppRank > existingOppRank ? newOppLevel : bestMatch.opportunityLevel,
        themeId: newThemeId ?? bestMatch.themeId,
      };
    };

    const result = await prisma.$transaction(async (tx) => {
      // Row-level lock serializes concurrent duplicate callbacks. Second
      // caller waits; when it gets through, status check below short-circuits.
      const lockedJob = await tx.$queryRaw<{ id: string; status: JobStatusType }[]>`
        SELECT id, status FROM "Job" WHERE id = ${data.job_id} FOR UPDATE
      `;
      if (lockedJob.length === 0) {
        throw new Error(`Job ${data.job_id} not found inside tx`);
      }
      if (lockedJob[0].status === JobStatus.COMPLETED) {
        return { alreadyProcessed: true as const };
      }
      if (lockedJob[0].status !== JobStatus.RUNNING && lockedJob[0].status !== JobStatus.QUEUED) {
        throw new Error(`Job ${data.job_id} in status ${lockedJob[0].status} inside tx`);
      }

      const existing = await tx.catalogPainPoint.findMany({
        where: { categoryId: data.category_id, isActive: true },
      });
      const existingNormalized = existing.map(pp => ({
        ...pp,
        normalized: normalizeTitle(pp.title),
      }));

      const { generatePainPointSlug } = await import('../services/catalogService.js');

      // Legacy-sweep prep: load the CatalogResearchContext rows backing existing
      // pain points (scoped to those sourceJobIds only — bounded by category
      // size). Rows that fail the meaningfulness predicate are placeholder
      // contexts; their pain points are "legacy" and eligible for sweep below
      // if the new run doesn't match them.
      const existingJobIds = [...new Set(existing.map(pp => pp.sourceJobId))];
      const existingCtxs = existingJobIds.length > 0
        ? await tx.catalogResearchContext.findMany({
            where: { sourceJobId: { in: existingJobIds } },
            select: { sourceJobId: true, ...MEANINGFUL_SELECT },
          })
        : [];
      const legacyJobIds = new Set(
        existingCtxs
          .filter(c => !hasMeaningfulResearchContext(c))
          .map(c => c.sourceJobId),
      );
      const matchedPpIds = new Set<string>();

      let merged = 0;
      let created = 0;

      for (let ppIdx = 0; ppIdx < data.pain_points.length; ppIdx++) {
        const newPp = data.pain_points[ppIdx];
        const newTitle = String(newPp.title || '');
        const newNorm = normalizeTitle(newTitle);

        let bestMatch: (typeof existingNormalized)[0] | null = null;
        let bestScore = 0;
        for (const ex of existingNormalized) {
          const score = bigramSimilarity(newNorm, ex.normalized);
          if (score > bestScore) {
            bestScore = score;
            bestMatch = ex;
          }
        }

        if (bestMatch && bestScore >= 0.7) {
          const mergeData = buildMergeData(bestMatch, newPp);
          try {
            await tx.catalogPainPoint.update({
              where: { id: bestMatch.id },
              data: {
                ...mergeData,
                // Phase 5.4 — advance lineage. Latest research wins.
                sourceJobId: data.job_id,
                sourceGeneratedAt: new Date(),
              },
            });
            matchedPpIds.add(bestMatch.id);
            merged++;
          } catch (err: unknown) {
            const code = (err as { code?: string } | null)?.code;
            if (code === 'P2002') {
              // Conflict: another row already has (data.job_id, bestMatch.title).
              // Merge bestMatch's accumulated data INTO that row (preserves
              // latest-wins) and deactivate bestMatch.
              const conflicting = await tx.catalogPainPoint.findUnique({
                where: { sourceJobId_title: { sourceJobId: data.job_id, title: bestMatch.title } },
              });
              if (conflicting) {
                await tx.catalogPainPoint.update({
                  where: { id: conflicting.id },
                  data: buildMergeData(conflicting, newPp),
                });
                await tx.catalogPainPoint.update({
                  where: { id: bestMatch.id },
                  data: { isActive: false },
                });
                // Both rows are handled — don't let the legacy sweep below
                // touch them. (bestMatch.id is already inactive; conflicting.id
                // is the surviving merge target.)
                matchedPpIds.add(conflicting.id);
                matchedPpIds.add(bestMatch.id);
                console.warn(
                  `[Workers] P2002 on lineage advance for "${bestMatch.title}"; merged into ${conflicting.id} and deactivated ${bestMatch.id}`,
                );
                merged++;
              } else {
                console.error(
                  `[Workers] P2002 fired but no conflicting (sourceJobId, title) row found for "${bestMatch.title}"; skipping`,
                );
              }
            } else {
              throw err;
            }
          }
        } else {
          // INSERT — uniqueness check threaded through tx so it sees the
          // tx snapshot.
          try {
            const slug = await generatePainPointSlug(
              { title: newTitle, categoryId: data.category_id },
              tx,
            );
            await tx.catalogPainPoint.create({
              data: {
                categoryId: data.category_id,
                slug,
                sourceJobId: data.job_id,
                sourceNiche: data.niche,
                sourceGeneratedAt: new Date(),
                sourceItemIndex: ppIdx,
                title: newTitle,
                description: String(newPp.description || ''),
                mentionCount: Number(newPp.mention_count) || 0,
                severityScore: Number(newPp.severity_score) || 0,
                commercialIntentScore: Number(newPp.commercial_intent) || 0,
                opportunityLevel: String(newPp.opportunity_level || 'medium'),
                representativeQuotes: (newPp.representative_quotes as string[]) || [],
                sourcePlatforms: (newPp.source_platforms as string[]) || [],
                categories: (newPp.categories as string[]) || [],
                affectedSegments: (newPp.affected_segments as string[]) || [],
                themeId: typeof newPp.parent_theme_id === 'string' && newPp.parent_theme_id
                  ? newPp.parent_theme_id
                  : null,
                publishedById: 'system',
                isActive: true,
              },
            });
            created++;
          } catch (createErr: unknown) {
            const code = (createErr as { code?: string } | null)?.code;
            if (code === 'P2002') {
              console.log(`[Workers] Skipping duplicate pain point: ${newTitle}`);
            } else {
              throw createErr;
            }
          }
        }
      }

      // Legacy sweep — deactivate previously-active pain points whose source
      // job's CRC is a placeholder AND that the new run did not match. Gated
      // on data.pain_points.length > 0 so a run that returns no pain points
      // (but otherwise meaningful context — e.g. only verdict / social counts)
      // doesn't wipe the category. Acts only on legacy rows; non-legacy
      // unmatched rows are preserved in case the new run simply re-prioritized.
      let deactivated = 0;
      if (data.pain_points.length > 0 && legacyJobIds.size > 0) {
        const toDeactivateIds = existing
          .filter(pp => !matchedPpIds.has(pp.id) && legacyJobIds.has(pp.sourceJobId))
          .map(pp => pp.id);
        if (toDeactivateIds.length > 0) {
          const swept = await tx.catalogPainPoint.updateMany({
            where: {
              id: { in: toDeactivateIds },
              categoryId: data.category_id,
              isActive: true,
            },
            data: { isActive: false },
          });
          deactivated = swept.count;
        }
      }

      // Status flip inside tx — atomic with merge/insert/sweep.
      await tx.job.updateMany({
        where: { id: data.job_id, status: { in: [JobStatus.RUNNING, JobStatus.QUEUED] } },
        data: { status: JobStatus.COMPLETED, completedAt: new Date() },
      });

      return {
        alreadyProcessed: false as const,
        merged,
        created,
        deactivated,
        totalExisting: existing.length,
      };
    });

    if (result.alreadyProcessed) {
      res.json({ status: 'already_processed' });
      return;
    }

    // SSE + cache invalidation outside tx (idempotent).
    broadcastProgress(data.job_id, {
      stage: 3,
      name: 'Pain Point Analysis',
      status: 'completed',
    });
    if (result.created > 0 || result.merged > 0 || result.deactivated > 0) {
      const {
        invalidateCategoryLanding,
        invalidateCatalogTotals,
        invalidateTopCatalogPainPoints,
      } = await import('../services/catalogService.js');
      await invalidateCategoryLanding(data.category_id);
      // Sweep changes active row counts on global surfaces (catalog totals,
      // /ideas top-pains list); invalidate those too so they don't lag.
      if (result.deactivated > 0) {
        await invalidateCatalogTotals();
        await invalidateTopCatalogPainPoints();
      }
    }

    console.log(
      `[Workers] Catalog pain points for job ${data.job_id}: ${result.created} created, ${result.merged} merged, ${result.deactivated} deactivated`,
    );
    res.json({
      merged: result.merged,
      created: result.created,
      deactivated: result.deactivated,
      // Active rows in the category after the operation.
      total: result.totalExisting + result.created - result.deactivated,
    });
  } catch (error) {
    if (error instanceof z.ZodError) {
      res.status(400).json({ error: 'Validation error', details: error.errors });
      return;
    }
    console.error('[Workers] Catalog pain points ready error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

const CatalogIdeasReadySchema = z.object({
  worker_id: z.string().min(1),
  job_id: z.string().uuid(),
  category_id: z.string().uuid(),
  ideas: z.array(z.record(z.unknown())),
  niche: z.string(),
  // Phase 5.4 — when admin generates ideas from existing pain points, the
  // ideas inherit the parent pain-points-job's sourceJobId so they share
  // one CatalogResearchContext row. NOT .uuid() — legacy rows may have
  // non-UUID-shaped sourceJobIds. .max(100) matches schema VarChar.
  parent_source_job_id: z.string().min(1).max(100).optional(),
});

/**
 * POST /api/workers/catalog-ideas-ready
 * Worker reports catalog ideas are ready. Insert new, skip duplicates.
 *
 * Phase 5.4: ideas inherit parent_source_job_id when set so they FK into
 * the same CatalogResearchContext row as the pain points they were
 * generated from.
 */
workersRouter.post('/catalog-ideas-ready', async (req: Request, res: Response) => {
  try {
    const data = CatalogIdeasReadySchema.parse(req.body);
    const { prisma } = await import('../services/db.js');
    const { JobStatus } = await import('@prisma/client');

    // ─── Three-tier status guard ─────────────────────────────────────────
    const job = await prisma.job.findUnique({
      where: { id: data.job_id },
      select: { status: true },
    });
    if (!job) {
      res.status(404).json({ error: 'Job not found' });
      return;
    }
    if (job.status === JobStatus.COMPLETED) {
      console.log(`[Workers] catalog-ideas-ready: job ${data.job_id} already COMPLETED — skipping reprocess`);
      res.json({ status: 'already_processed' });
      return;
    }
    if (job.status !== JobStatus.RUNNING && job.status !== JobStatus.QUEUED) {
      console.warn(`[Workers] catalog-ideas-ready: job ${data.job_id} in status ${job.status} — refusing to mutate`);
      res.status(409).json({ error: `Job not in RUNNING/QUEUED state (current: ${job.status})` });
      return;
    }

    const effectiveSourceJobId = data.parent_source_job_id ?? data.job_id;

    // Defensive idempotent extraction. If parent_source_job_id is set, the
    // pain-points run already populated context — this is a no-op real-row
    // short-circuit. If absent (no parent), this creates a placeholder row
    // for the ideas job itself.
    const { extractOrCreateResearchContext, hasMeaningfulResearchContext } = await import(
      '../services/researchContextService.js'
    );
    const ctx = await extractOrCreateResearchContext(effectiveSourceJobId, {
      forceRefreshPlaceholders: true,
      sourceKind: 'catalog',
    });

    // Generated ideas should not point at an empty parent context.
    if (!hasMeaningfulResearchContext(ctx)) {
      console.error(
        `[Workers] Ideas job ${data.job_id} parent context ${effectiveSourceJobId} is not meaningful; aborting`,
      );
      res.status(500).json({ error: 'Parent research context not meaningful; will retry' });
      return;
    }

    // ─── Transactional mutation block ────────────────────────────────────
    const result = await prisma.$transaction(async (tx) => {
      const lockedJob = await tx.$queryRaw<{ id: string; status: JobStatusType }[]>`
        SELECT id, status FROM "Job" WHERE id = ${data.job_id} FOR UPDATE
      `;
      if (lockedJob.length === 0) {
        throw new Error(`Job ${data.job_id} not found inside tx`);
      }
      if (lockedJob[0].status === JobStatus.COMPLETED) {
        return { alreadyProcessed: true as const };
      }
      if (lockedJob[0].status !== JobStatus.RUNNING && lockedJob[0].status !== JobStatus.QUEUED) {
        throw new Error(`Job ${data.job_id} in status ${lockedJob[0].status} inside tx`);
      }

      const existingIdeas = await tx.catalogIdea.findMany({
        where: { categoryId: data.category_id, isActive: true },
        select: { solutionName: true },
      });
      const existingNames = new Set(existingIdeas.map(i => i.solutionName.toLowerCase()));

      const { generateIdeaSlug } = await import('../services/catalogService.js');

      let created = 0;
      let skipped = 0;

      for (let ideaIdx = 0; ideaIdx < data.ideas.length; ideaIdx++) {
        const idea = data.ideas[ideaIdx];
        const name = String(idea.solution_name || idea.name || '');
        if (!name) { skipped++; continue; }

        if (existingNames.has(name.toLowerCase())) {
          skipped++;
          continue;
        }

        try {
          const projectType = idea.project_type ? String(idea.project_type) : null;
          const slug = await generateIdeaSlug(
            { name, categoryId: data.category_id, format: projectType },
            tx,
          );
          const formatSlug = projectType
            ? projectType.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'saas'
            : 'saas';

          // Validate + canonicalize addressed pain titles against the parent
          // research context's pain list. Drops titles with no plausible
          // canonical counterpart; logs corrections for audit. Same fuzzy
          // threshold (0.7 bigram) as the pain-points dedup above.
          const llmAddressedTitles = Array.isArray(idea.pain_points_addressed)
            ? (idea.pain_points_addressed as unknown[]).filter(
                (s): s is string => typeof s === 'string',
              )
            : [];
          const ctxPains = Array.isArray(ctx?.detailedPainPoints)
            ? (ctx.detailedPainPoints as Array<{ title?: unknown }>)
            : [];
          const canon = canonicalizeAddressedTitles(llmAddressedTitles, ctxPains);
          if (canon.dropped.length > 0 || canon.corrected.length > 0) {
            console.warn('[catalog-ideas-ready] addressedPainTitles canonicalization', {
              jobId: data.job_id,
              effectiveSourceJobId,
              ideaSlug: slug,
              dropped: canon.dropped,
              corrected: canon.corrected,
            });
          }

          await tx.catalogIdea.create({
            data: {
              categoryId: data.category_id,
              slug,
              format: formatSlug,
              sourceJobId: effectiveSourceJobId,
              sourceNiche: data.niche,
              sourceGeneratedAt: new Date(),
              sourceItemIndex: ideaIdx,
              solutionName: name,
              headline: idea.headline ? String(idea.headline) : null,
              shortDescription: idea.short_description ? String(idea.short_description) : null,
              description: String(idea.description || ''),
              valueProposition: idea.value_proposition ? String(idea.value_proposition) : null,
              projectType,
              coreFeatures: (idea.core_features as string[]) || null,
              targetPersonas: (idea.target_personas as string[]) || null,
              technicalApproach: idea.technical_approach ? String(idea.technical_approach) : null,
              differentiationFactors: (idea.differentiation_factors as string[]) || null,
              pricingStrategy: idea.pricing_strategy ? String(idea.pricing_strategy) : null,
              estimatedDevTime: idea.estimated_development_time ? String(idea.estimated_development_time) : null,
              marketFitScore: idea.market_fit_score != null ? Number(idea.market_fit_score) : null,
              technicalFeasibility: idea.technical_feasibility_score != null ? Number(idea.technical_feasibility_score) : null,
              seoScalabilityScore: idea.seo_scalability_score != null ? Number(idea.seo_scalability_score) : null,
              noveltyScore: idea.novelty_score != null ? Number(idea.novelty_score) : null,
              soloDevFeasibility: idea.solo_dev_feasibility != null ? Number(idea.solo_dev_feasibility) : null,
              estimatedCacOrganic: idea.estimated_cac_organic ? String(idea.estimated_cac_organic) : null,
              estimatedIndexablePages: idea.estimated_indexable_pages != null ? Number(idea.estimated_indexable_pages) : null,
              programmaticSeoOpp: idea.programmatic_seo_opportunity ? String(idea.programmatic_seo_opportunity) : null,
              // Phase 13 of detail-page IA rework — populate idea-specific
              // BaseSolutionIdea fields from worker payload. Pydantic
              // BaseSolutionIdea includes all of these (solution_idea.py:252+).
              whyItWorks: idea.why_it_works ? String(idea.why_it_works) : null,
              conventionalApproach: idea.conventional_approach ? String(idea.conventional_approach) : null,
              innovationAngle: idea.innovation_angle ? String(idea.innovation_angle) : null,
              estimatedCacPaid: idea.estimated_cac_paid ? String(idea.estimated_cac_paid) : null,
              organicDiscoveryQueries: Array.isArray(idea.organic_discovery_queries)
                ? (idea.organic_discovery_queries as unknown[]).filter((s): s is string => typeof s === 'string')
                : [],
              // Phase 1 of detail-page IA rework — denormalize pain titles
              // for fast pain → ideas lookup. Now validated + canonicalized
              // against the parent research context's pain list before persist;
              // see canonicalizeAddressedTitles call above.
              addressedPainTitles: canon.canonical,
              publishedById: 'system',
              isActive: true,
            },
          });
          created++;
          existingNames.add(name.toLowerCase());
        } catch (createErr: unknown) {
          const code = (createErr as { code?: string } | null)?.code;
          if (code === 'P2002') {
            skipped++;
          } else {
            throw createErr;
          }
        }
      }

      await tx.job.updateMany({
        where: { id: data.job_id, status: { in: [JobStatus.RUNNING, JobStatus.QUEUED] } },
        data: { status: JobStatus.COMPLETED, completedAt: new Date() },
      });

      return { alreadyProcessed: false as const, created, skipped, totalExisting: existingNames.size };
    });

    if (result.alreadyProcessed) {
      res.json({ status: 'already_processed' });
      return;
    }

    broadcastProgress(data.job_id, {
      stage: 5,
      name: 'Solution Pipeline',
      status: 'completed',
    });
    if (result.created > 0) {
      const { invalidateCategoryLanding } = await import('../services/catalogService.js');
      await invalidateCategoryLanding(data.category_id);
    }

    console.log(
      `[Workers] Catalog ideas for job ${data.job_id}: ${result.created} created, ${result.skipped} skipped`,
    );
    res.json({ created: result.created, skipped: result.skipped, total: result.totalExisting });
  } catch (error) {
    if (error instanceof z.ZodError) {
      res.status(400).json({ error: 'Validation error', details: error.errors });
      return;
    }
    console.error('[Workers] Catalog ideas ready error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// ============================================
// Reddit Thread Cache
// ============================================

const REDDIT_CACHE_TTL_HOURS = parseInt(process.env.REDDIT_CACHE_TTL_HOURS || '168', 10); // 7 days

const PostIdRegex = /^[a-z0-9]{1,20}$/;

const BatchLookupSchema = z.object({
  postIds: z.array(z.string().regex(PostIdRegex)).min(1).max(100),
});

const UpsertRedditThreadSchema = z.object({
  postId: z.string().regex(PostIdRegex),
  url: z.string().max(2048),
  title: z.string().max(500),
  selftext: z.string().max(40000),
  author: z.string().max(100),
  subreddit: z.string().max(50).regex(/^[A-Za-z0-9_]+$/),
  score: z.number().int(),
  numComments: z.number().int(),
  comments: z.any().nullable().optional(),
  redditCreatedAt: z.string().datetime({ offset: true }),
});

/**
 * POST /api/workers/reddit-threads/batch-lookup
 * Look up cached Reddit threads by post IDs with TTL staleness check.
 */
workersRouter.post('/reddit-threads/batch-lookup', async (req: Request, res: Response) => {
  try {
    const parsed = BatchLookupSchema.safeParse(req.body);
    if (!parsed.success) {
      res.status(400).json({ error: 'Validation error', details: parsed.error.errors });
      return;
    }

    const { postIds } = parsed.data;
    const { prisma } = await import('../services/db.js');

    const ttlCutoff = new Date(Date.now() - REDDIT_CACHE_TTL_HOURS * 60 * 60 * 1000);

    const threads = await prisma.redditThread.findMany({
      where: {
        postId: { in: postIds },
        fetchedAt: { gte: ttlCutoff },
      },
    });

    const found: Record<string, any> = {};
    const foundIds = new Set<string>();
    for (const t of threads) {
      found[t.postId] = {
        postId: t.postId,
        url: t.url,
        title: t.title,
        selftext: t.selftext,
        author: t.author,
        subreddit: t.subreddit,
        score: t.score,
        numComments: t.numComments,
        comments: t.comments,
        redditCreatedAt: t.redditCreatedAt.toISOString(),
      };
      foundIds.add(t.postId);
    }

    const missing = postIds.filter(id => !foundIds.has(id));

    res.json({ found, missing });
  } catch (error) {
    console.error('[Workers] Reddit thread batch-lookup error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

/**
 * POST /api/workers/reddit-threads
 * Upsert a Reddit thread into the cache.
 */
workersRouter.post('/reddit-threads', expressJson({ limit: '10mb' }), async (req: Request, res: Response) => {
  try {
    // Check payload size for comments
    const bodyStr = JSON.stringify(req.body?.comments);
    if (bodyStr && bodyStr.length > 8 * 1024 * 1024) {
      res.status(413).json({ error: 'Comments payload too large (max 8MB)' });
      return;
    }

    const parsed = UpsertRedditThreadSchema.safeParse(req.body);
    if (!parsed.success) {
      res.status(400).json({ error: 'Validation error', details: parsed.error.errors });
      return;
    }

    const data = parsed.data;
    const { prisma } = await import('../services/db.js');

    await prisma.redditThread.upsert({
      where: { postId: data.postId },
      create: {
        postId: data.postId,
        url: data.url,
        title: data.title,
        selftext: data.selftext,
        author: data.author,
        subreddit: data.subreddit,
        score: data.score,
        numComments: data.numComments,
        comments: data.comments ?? undefined,
        redditCreatedAt: new Date(data.redditCreatedAt),
        fetchedAt: new Date(),
      },
      update: {
        url: data.url,
        title: data.title,
        selftext: data.selftext,
        author: data.author,
        subreddit: data.subreddit,
        score: data.score,
        numComments: data.numComments,
        comments: data.comments ?? undefined,
        redditCreatedAt: new Date(data.redditCreatedAt),
        fetchedAt: new Date(),
      },
    });

    res.json({ success: true });
  } catch (error) {
    console.error('[Workers] Reddit thread upsert error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

