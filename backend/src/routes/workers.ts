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
import {
  cancelRegenerationDispatch,
  cancelSeedIdeaDispatch,
  failJob,
  updateStageProgress,
  completeJob,
  getJob,
  addJobAsset,
  getJobAsset,
} from '../services/jobService.js';
import {
  refundChargeInTx,
  refundForStage,
  refundForStageInTx,
  isGuidedSegment,
} from '../services/creditService.js';
import { broadcastProgress } from '../services/progressBroadcastService.js';
import { notifySolutionsReady, notifyPhase2Start, notifyRegenerationComplete, notifyLandingPageReady } from '../services/notificationService.js';
import {
  IdeasReadySchema,
  RegenerationCompleteSchema,
  RegenerationFailedSchema,
  GateReachedSchema,
  GateFailedSchema,
  SeedIdeaCompleteSchema,
  SeedIdeaFailedSchema,
} from '../types/job.js';
import { notifyJobStart, notifyJobComplete, notifyJobError, notifyGateReached } from '../services/notificationService.js';
import {
  dispatchGuard,
  diagnoseGuardMiss,
  completeLandingPageDispatch,
  failLandingPageDispatch,
  publishDeepResearchReport,
  startLandingPageDispatch,
  startDispatchedJob,
  settleDispatch,
} from '../services/dispatchService.js';
import {
  buildRegenerationEnvelope,
  buildRegenerationReceiptContent,
  buildSeedEnvelope,
  buildSeedReceiptContent,
} from '../utils/ledgerEvents.js';
import {
  ensureIdeaIdentities,
  candidateSnapshotSha256,
  stampNewIdeaIdentities,
  stampSynthesizedIdeaIdentity,
} from '../utils/ideaIdentity.js';
import { canonicalJsonSha256 } from '../utils/canonicalFingerprint.js';
import { IdeaSynthesisPatchSchema } from '../types/ideaSynthesis.js';
import { AssetType, Prisma, DispatchState, DispatchKind, JobStatus } from '@prisma/client';
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
  dispatch_id: z.string().uuid().optional(),
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

    // Check if job should be cancelled
    let shouldCancel = false;
    if (data.job_id) {
      const heartbeat = await updateJobHeartbeat(
        data.job_id,
        data.worker_id,
        data.dispatch_id,
      );
      if (heartbeat === 'stale' || heartbeat === 'not_found') {
        // Keep the worker process visible, but do not advertise a superseded attempt as its
        // current job. shouldCancel stops that stale pipeline at its next cancellation check.
        await registerWorkerHeartbeat(
          data.worker_id,
          null,
          data.hostname,
          data.process_id,
        );
        res.json({
          status: 'ok',
          timestamp: new Date().toISOString(),
          shouldCancel: true,
          stale: true,
        });
        return;
      }

      await registerWorkerHeartbeat(
        data.worker_id,
        data.job_id,
        data.hostname,
        data.process_id,
      );

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
    } else {
      await registerWorkerHeartbeat(
        data.worker_id,
        null,
        data.hostname,
        data.process_id,
      );
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
  dispatch_id: z.string().uuid().optional(),
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
        select: {
          status: true,
          niche: true,
          userId: true,
          currentStage: true,
          selectedSolutions: true,
          activeDispatchId: true,
          landingPageStatus: true,
        },
      });

      if (
        job
        && (
          job.status === JobStatus.RUNNING
          || job.status === JobStatus.REGENERATING
          || job.status === JobStatus.RUNNING_PHASE2
          || (
            job.status === JobStatus.COMPLETED
            && (job.landingPageStatus === 'RUNNING' || job.landingPageStatus === 'QUEUED')
          )
        )
      ) {
        if ((job.activeDispatchId ?? null) !== (data.dispatch_id ?? null)) {
          console.warn(
            `[Workers] Ignoring stale shutdown failure for job ${data.job_id}: ` +
            `dispatch ${data.dispatch_id ?? 'missing'} (active: ${job.activeDispatchId ?? 'none'})`,
          );
          res.json({ status: 'ok', message: 'Shutdown acknowledged', stale: true });
          return;
        }

        const dispatch = data.dispatch_id
          ? await prisma.jobDispatch.findFirst({
              where: { id: data.dispatch_id, jobId: data.job_id },
              select: {
                id: true,
                kind: true,
                segment: true,
                chargeId: true,
                seedOrdinal: true,
                sourceMessageId: true,
              },
            })
          : null;

        // Regeneration and seed generation are paid operations layered on top of a completed
        // Discovery run. A worker shutdown must settle only that operation and restore the
        // selection workspace; failing the whole Job would destroy valid work the user already
        // owns. These helpers repeat the active-dispatch CAS and exact-charge refund atomically.
        if (
          dispatch?.kind === DispatchKind.CONTINUE
          && dispatch.segment === 'landing_page'
        ) {
          const errorMessage =
            `Worker shutdown during landing page generation: ${data.reason || 'graceful shutdown'}.`;
          const settled = await failLandingPageDispatch(data.job_id, dispatch.id, errorMessage);
          if (!settled) {
            res.json({ status: 'ok', message: 'Shutdown acknowledged', stale: true });
            return;
          }
          broadcastProgress(data.job_id, {
            stage: 15,
            name: 'Landing Page Generation',
            status: 'failed',
            error: errorMessage,
          });
          res.json({ status: 'ok', message: 'Shutdown acknowledged' });
          return;
        }

        if (dispatch?.kind === DispatchKind.REGENERATE) {
          const settled = await cancelRegenerationDispatch(
            data.job_id,
            {
              id: dispatch.id,
              segment: dispatch.segment,
              chargeId: dispatch.chargeId,
            },
            job.status,
            'WORKER_CRASH',
          );
          if (!settled.cancelled) {
            res.json({ status: 'ok', message: 'Shutdown acknowledged', stale: true });
            return;
          }
          console.log(
            `[Workers] Regeneration dispatch ${dispatch.id} settled after worker shutdown; ` +
            `job ${data.job_id} restored to selection`,
          );
          res.json({ status: 'ok', message: 'Shutdown acknowledged' });
          return;
        }

        if (dispatch?.kind === DispatchKind.SEED_IDEA) {
          const settled = await cancelSeedIdeaDispatch(
            data.job_id,
            {
              id: dispatch.id,
              seedOrdinal: dispatch.seedOrdinal,
              sourceMessageId: dispatch.sourceMessageId,
              chargeId: dispatch.chargeId,
            },
            job.status,
            'WORKER_CRASH',
          );
          if (!settled.cancelled) {
            res.json({ status: 'ok', message: 'Shutdown acknowledged', stale: true });
            return;
          }
          console.log(
            `[Workers] Seed dispatch ${dispatch.id} settled after worker shutdown; ` +
            `job ${data.job_id} restored to selection`,
          );
          res.json({ status: 'ok', message: 'Shutdown acknowledged' });
          return;
        }

        const errorMessage = `Worker shutdown: ${data.reason || 'graceful shutdown'}. Use checkpoint resume to continue.`;

        // Worker shutdown is classified as WORKER_CRASH for user-friendly messaging
        const translatedErrorDetails = buildErrorDetails('WORKER_CRASH', { rawMessage: errorMessage });

        const failed = await failJob(
          data.job_id,
          errorMessage,
          undefined,
          undefined,
          undefined,
          'WORKER_CRASH',
          translatedErrorDetails ?? undefined,
          data.dispatch_id,
        );
        if (!failed.applied) {
          console.warn(
            `[Workers] Ignoring stale shutdown failure for job ${data.job_id} ` +
            `(dispatch ${data.dispatch_id ?? 'missing'})`,
          );
          res.json({ status: 'ok', message: 'Shutdown acknowledged', stale: true });
          return;
        }
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
  // The claim. This callback is where AUTHORIZED becomes CLAIMED — the boundary that decides
  // whether a later cancel owes the user a refund (nothing ran) or not (work started).
  dispatch_id: z.string().uuid().optional(),
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

    // A SEED_IDEA dispatch takes precedence over the heuristics above: `ideasRegeneratedAt` is
    // a run-level marker that stays set forever once a job has EVER regenerated, so a seed
    // submitted on a job that regenerated earlier this run would otherwise misread as
    // isRegenerate (`ideasRegeneratedAt != null && !hasSelections` — both true for a seed op
    // too) and get labelled REGENERATING. The dispatch kind is exact; the heuristics are a
    // fallback for the legacy (undispatched) path only.
    const dispatch = data.dispatch_id
      ? await prisma.jobDispatch.findUnique({
          where: { id: data.dispatch_id },
          select: { kind: true, segment: true },
        })
      : null;
    const dispatchKind = dispatch?.kind;
    const isLandingPageDispatch =
      dispatchKind === DispatchKind.CONTINUE && dispatch?.segment === 'landing_page';
    const runningStatus =
      dispatchKind === DispatchKind.SEED_IDEA ? JobStatus.RUNNING
      : dispatchKind === DispatchKind.REGENERATE ? JobStatus.REGENERATING
      : dispatchKind === DispatchKind.DEEP_RESEARCH ? JobStatus.RUNNING_PHASE2
      : isRegenerate ? JobStatus.REGENERATING
      : isPhase2 ? JobStatus.RUNNING_PHASE2
      : JobStatus.RUNNING;

    // For dispatched work, start the Job and claim the Dispatch in one job-first transaction.
    // Cancellation updates the Job first too, so exactly one side crosses the billing boundary:
    // either RUNNING + CLAIMED commit together, or cancellation leaves the dispatch refundable.
    let result: { count: number };
    let didStart = false;
    if (data.dispatch_id) {
      const outcome = isLandingPageDispatch
        ? await startLandingPageDispatch(data.dispatch_id, data.worker_id, data.job_id)
        : await startDispatchedJob(data.dispatch_id, data.worker_id, {
            jobId: data.job_id,
            runningStatus,
          });
      if (!outcome) {
        console.warn(
          `[Workers] Job ${data.job_id} dispatch ${data.dispatch_id} could not start — telling ${data.worker_id} to skip`
        );
        return res.json({ status: 'ok', shouldCancel: true, stale: true });
      }
      didStart = outcome === 'started';
      result = { count: 1 };
    } else {
      // Narrow legacy path: a worker without a dispatch id may only start a job that has no
      // active dispatch. Dispatched jobs always use the transaction above.
      result = await prisma.job.updateMany({
        where: {
          id: data.job_id,
          status: { in: [JobStatus.QUEUED, JobStatus.PENDING] },
          ...dispatchGuard(data.dispatch_id),
        },
        data: {
          workerId: data.worker_id,
          lastHeartbeat: new Date(),
          status: runningStatus,
          startedAt: new Date(),
          errorMessage: null,
        },
      });
      didStart = result.count > 0;
    }

    // If no rows updated, check why
    if (result.count === 0) {
      const miss = await diagnoseGuardMiss(data.job_id, data.dispatch_id, [
        JobStatus.QUEUED,
        JobStatus.PENDING,
      ]);

      // The job has moved on to a different attempt than the one this worker is holding. Not an
      // error — the system working. Tell the worker to drop it.
      if (miss === 'stale_dispatch') {
        console.warn(
          `[Workers] Job ${data.job_id} — stale dispatch ${data.dispatch_id ?? '(none)'} on job-started; signaling worker to skip`
        );
        return res.json({ status: 'ok', shouldCancel: true, stale: true });
      }

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
        // Guided mode: a requeued duplicate worker must not keep running while the user is
        // reviewing/chatting at the gate (Codex 17).
        JobStatus.AWAITING_GATE,
      ]);
      if (!job || doNotRun.has(job.status)) {
        console.log(
          `[Workers] Job ${data.job_id} not runnable (status: ${job?.status ?? 'not found'}) - signaling worker to skip`
        );
        return res.json({ status: 'ok', shouldCancel: true });
      }
      // A dispatched zero-count result is the transaction's verified same-worker retry. Legacy
      // jobs retain the historical already-running behavior because they have no attempt id.
      console.log(`[Workers] Job ${data.job_id} not updated (status: ${job.status})`);
    }

    // Update worker heartbeat
    await registerWorkerHeartbeat(data.worker_id, data.job_id);

    // Send job start notification (only if we actually started the job)
    if (didStart) {
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
        } else if (!isRegenerate && !isLandingPageDispatch) {
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
  dispatch_id: z.string().uuid().optional(),
  report_path: z.string().min(1).max(500),
  winner_name: z.string().max(255).optional(),
  winner_ref: z.object({
    idea_id: z.string().min(1).max(128),
    idea_revision: z.number().int().min(1),
  }).optional(),
  cost_summary: z.record(z.any()).optional(),
});

/**
 * POST /api/workers/report-ready
 * Worker reports that the research report is ready (before landing page).
 * This triggers "report ready" notification so users can view reports immediately.
 */
workersRouter.post('/report-ready', async (req: Request, res: Response) => {
  try {
    const data = ReportReadySchema.parse(req.body);

    const { prisma } = await import('../services/db.js');
    const job = await prisma.job.findUnique({
      where: { id: data.job_id },
      select: {
        userId: true,
        niche: true,
        selectedSolutions: true,
        selectedSolutionIds: true,
        selectedSolutionRefs: true,
        solutionIdeas: true,
        entryMode: true,
        status: true,
        activeDispatchId: true,
      },
    });

    if (!job) {
      res.status(404).json({ error: 'Job not found' });
      return;
    }
    if (job.activeDispatchId && !data.dispatch_id) {
      res.json({ status: 'ok', stale: true, reason: 'missing_dispatch_identity' });
      return;
    }
    let deepIdeaAuthorizedName: string | null = null;
    if (data.dispatch_id) {
      const dispatch = await prisma.jobDispatch.findUnique({
        where: { id: data.dispatch_id },
        select: { jobId: true, kind: true, state: true, workPayload: true },
      });
      const activeDelivery =
        dispatch?.state === DispatchState.CLAIMED
        && job.activeDispatchId === data.dispatch_id
        && job.status === JobStatus.RUNNING_PHASE2;
      const completedRetry =
        dispatch?.state === DispatchState.COMPLETED
        && job.activeDispatchId === null
        && job.status === JobStatus.COMPLETED;
      if (
        dispatch?.jobId !== data.job_id
        || dispatch.kind !== DispatchKind.DEEP_RESEARCH
        || (!activeDelivery && !completedRetry)
      ) {
        res.json({ status: 'ok', stale: true, reason: 'stale_dispatch' });
        return;
      }
      if (job.entryMode === 'deep_idea') {
        const workPayload =
          dispatch.workPayload && typeof dispatch.workPayload === 'object' && !Array.isArray(dispatch.workPayload)
            ? dispatch.workPayload as Record<string, unknown>
            : null;
        const ideaSeed =
          workPayload?.idea_seed && typeof workPayload.idea_seed === 'object' && !Array.isArray(workPayload.idea_seed)
            ? workPayload.idea_seed as Record<string, unknown>
            : null;
        deepIdeaAuthorizedName =
          typeof ideaSeed?.solution_name === 'string' ? ideaSeed.solution_name : null;
      }
    }

    // Resolve the worker's name back to exactly one persisted candidate before registering
    // the report. A successful response without this identity would leave the immutable
    // decision artifact unable to reference the Deep Research recommendation.
    const normalizeName = (s: string) => s.trim().replace(/\s+/g, ' ').toLowerCase();
    let winnerUpdate: Prisma.JobUpdateInput = {};
    if (job.entryMode === 'deep_idea') {
      const selectedName = job.selectedSolutions.length === 1 ? job.selectedSolutions[0] : null;
      if (
        !data.winner_name
        || !selectedName
        || !deepIdeaAuthorizedName
        || normalizeName(data.winner_name) !== normalizeName(selectedName)
        || normalizeName(deepIdeaAuthorizedName) !== normalizeName(selectedName)
      ) {
        res.status(409).json({
          error: 'Catalog Deep Research winner does not match its authorized seed',
          code: 'WINNER_IDENTITY_UNRESOLVED',
        });
        return;
      }
      // Catalog seeds predate the Phase-1 candidate identity pool. Preserve the exact authorized
      // name without inventing an idea id/revision that has no persisted candidate behind it.
      winnerUpdate = { selectedSolution: selectedName };
    } else if (data.winner_ref) {
      const selectedRefs = Array.isArray(job.selectedSolutionRefs)
        ? job.selectedSolutionRefs as Array<Record<string, unknown>>
        : [];
      const matchedIndex = selectedRefs.findIndex(ref =>
        ref.ideaId === data.winner_ref!.idea_id
        && ref.ideaRevision === data.winner_ref!.idea_revision
      );
      if (matchedIndex < 0) {
        res.status(409).json({
          error: 'Deep Research winner is not part of the authorized exact selection',
          code: 'WINNER_IDENTITY_UNRESOLVED',
        });
        return;
      }
      winnerUpdate = {
        selectedSolution: job.selectedSolutions[matchedIndex],
        deepResearchRecommendedIdeaId: data.winner_ref.idea_id,
        deepResearchRecommendedIdeaRevision: data.winner_ref.idea_revision,
      };
    } else if (data.winner_name) {
      const winnerNorm = normalizeName(data.winner_name);
      const matchingIndexes = job.selectedSolutions.flatMap((solutionName, index) =>
        normalizeName(solutionName) === winnerNorm ? [index] : [],
      );
      if (matchingIndexes.length !== 1) {
        res.status(409).json({
          error: 'Deep Research winner does not resolve to exactly one selected candidate',
          code: 'WINNER_IDENTITY_UNRESOLVED',
        });
        return;
      }

      const matchedIndex = matchingIndexes[0];
      const matchedId = job.selectedSolutionIds[matchedIndex];
      const matchedIdea = matchedId
        ? ensureIdeaIdentities(data.job_id, job.solutionIdeas).find(idea => idea.idea_id === matchedId)
        : null;
      if (!matchedId || !matchedIdea?.idea_revision) {
        res.status(409).json({
          error: 'Deep Research winner is missing its persisted candidate identity',
          code: 'WINNER_IDENTITY_UNRESOLVED',
        });
        return;
      }

      winnerUpdate = {
        selectedSolution: job.selectedSolutions[matchedIndex],
        deepResearchRecommendedIdeaId: matchedId,
        deepResearchRecommendedIdeaRevision: matchedIdea.idea_revision,
      };
    }

    // Single Job update: LLM cost breakdown (for the admin pricing view) + Phase-2 winner.
    const jobUpdate: Prisma.JobUpdateInput = winnerUpdate;

    // Cost: persist only when the summary reports real spend. Writing NULL for empty /
    // $0 / partial-retry summaries keeps them out of the admin average and count.
    const cost = data.cost_summary;
    const totalCost = typeof cost?.total_cost === 'number' ? cost.total_cost : null;
    if (cost && totalCost && totalCost > 0) {
      jobUpdate.costUsd = totalCost;
      jobUpdate.costSummary = cost as Prisma.InputJsonValue;
    }

    let isFirstDelivery: boolean;
    if (data.dispatch_id) {
      const existingAsset = await getJobAsset(data.job_id, AssetType.REPORT_JSON);
      const resultSnapshot = {
        schemaVersion: 1,
        kind: 'deep_research_report',
        reportPath: data.report_path,
        winnerRef: data.winner_ref ?? null,
        winnerName: data.winner_name ?? null,
      };
      const resultFingerprint = canonicalJsonSha256(resultSnapshot);
      const publication = await publishDeepResearchReport(
        data.job_id,
        data.dispatch_id,
        data.report_path,
        resultSnapshot as unknown as Prisma.InputJsonValue,
        resultFingerprint,
        jobUpdate as Prisma.JobUpdateManyMutationInput,
      );
      if (publication === 'stale') {
        res.json({ status: 'ok', stale: true, reason: 'stale_dispatch' });
        return;
      }
      if (publication === 'idempotent') {
        res.json({ status: 'ok', idempotent: true });
        return;
      }
      isFirstDelivery = existingAsset == null;
    } else {
      if (Object.keys(jobUpdate).length > 0) {
        await prisma.job.update({ where: { id: data.job_id }, data: jobUpdate });
      }
      const existingAsset = await getJobAsset(data.job_id, AssetType.REPORT_JSON);
      isFirstDelivery = existingAsset == null;
      await addJobAsset(data.job_id, AssetType.REPORT_JSON, data.report_path);
    }

    const { extractOrCreateResearchContext } = await import('../services/researchContextService.js');
    try {
      await extractOrCreateResearchContext(data.job_id, { forceRefreshAll: true });
    } catch (contextError) {
      // The report + exact dispatch are already durable. A projection failure must not turn that
      // committed success into a worker failure/refund race.
      console.error('Failed to extract report research context:', contextError);
    }

    if (data.dispatch_id) {
      try {
        const { getReportJsonForJob } = await import('../services/assetService.js');
        const report = await getReportJsonForJob(data.job_id);
        if (report) {
          const { createReportAnalystFollowup } = await import('../services/analystFollowupService.js');
          await createReportAnalystFollowup({
            jobId: data.job_id,
            operationId: data.dispatch_id,
            niche: job.niche,
            report,
          });
        }
      } catch (followupError) {
        console.error('[Workers] Failed to create report analyst follow-up:', followupError);
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
    try {
      broadcastProgress(data.job_id, {
        stage: 14,
        name: 'Report Generation',
        status: 'completed',
        report_path: data.report_path,
      });
    } catch (broadcastError) {
      console.error('[Workers] Failed to broadcast report-ready:', broadcastError);
    }

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
  dispatch_id: z.string().uuid().optional(),
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

    // Reject a stale or identityless-modern callback before it can touch progress, refunds,
    // notifications, or SSE. The service repeats this ownership check in its terminal CAS; this
    // early read protects every route-level side effect that happens around that transaction.
    const owner = await prisma.job.findUnique({
      where: { id: data.job_id },
      select: { activeDispatchId: true },
    });
    if ((owner?.activeDispatchId ?? null) !== (data.dispatch_id ?? null)) {
      console.warn(
        `[Workers] Ignoring stale job-failed callback for ${data.job_id}: ` +
        `dispatch ${data.dispatch_id ?? 'missing'} (active: ${owner?.activeDispatchId ?? 'none'})`,
      );
      await registerWorkerHeartbeat(data.worker_id, null);
      res.json({
        success: true,
        stale: true,
        shouldCancel: true,
        job_id: data.job_id,
        status: 'ignored',
      });
      return;
    }

    // Check if this is a landing-page-only failure with existing report
    const reportAsset = await getJobAsset(data.job_id, AssetType.REPORT_JSON);
    const isLandingPageFailure = data.error_stage === 15 && reportAsset;

    let jobStatus: string;

    if (isLandingPageFailure) {
      console.log(`[Workers] Landing page failure for job ${data.job_id} - completing job without landing page`);

      if (data.dispatch_id) {
        const settled = await failLandingPageDispatch(
          data.job_id,
          data.dispatch_id,
          data.error_message,
        );
        if (!settled) {
          await registerWorkerHeartbeat(data.worker_id, null);
          res.json({
            success: true,
            stale: true,
            shouldCancel: true,
            job_id: data.job_id,
            status: 'ignored',
          });
          return;
        }
        jobStatus = JobStatus.COMPLETED;
      } else {
        // Rolling-deploy fallback for a genuinely legacy, identityless landing attempt.
        try {
          await refundForStage(data.job_id, 'landing_page');
        } catch (refundErr) {
          console.error(`[Workers] Failed to refund landing page credits for job ${data.job_id}:`, refundErr);
        }
        await prisma.job.update({
          where: { id: data.job_id },
          data: { landingPageStatus: 'FAILED' },
        });
        const completedJob = await completeJob(data.job_id, reportAsset.filePath);
        jobStatus = completedJob?.status ?? 'COMPLETED';
      }

      if (!data.dispatch_id) {
        try {
          await prisma.jobProgress.updateMany({
            where: { jobId: data.job_id, stageNumber: 15, status: StageStatus.RUNNING },
            data: { status: StageStatus.FAILED, errorMessage: data.error_message },
          });
        } catch (stageErr) {
          console.error(`[Workers] Failed to update stage 15 to FAILED:`, stageErr);
        }
      }

    } else {
      // Normal failure handling - failJob is idempotent
      const failure = await failJob(
        data.job_id,
        data.error_message,
        data.error_stage ?? undefined,
        data.stop_reason,
        data.stop_reason_details,
        data.error_code,
        translatedErrorDetails ?? undefined,
        data.dispatch_id,
      );
      jobStatus = failure.job?.status ?? 'unknown';
      if (!failure.applied) {
        await registerWorkerHeartbeat(data.worker_id, null);
        res.json({
          success: true,
          stale: true,
          shouldCancel: true,
          job_id: data.job_id,
          status: jobStatus,
        });
        return;
      }

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
  dispatch_id: z.string().uuid().optional(),
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

    // 0. Reject progress from a superseded attempt BEFORE it writes anything.
    //
    // This endpoint mutates JobProgress, which is the ledger everything else reads — including,
    // once segment billing lands, how much work a cancelled run actually consumed. A stale worker
    // writing here doesn't just add noise; it rewrites history that money depends on.
    const { prisma: progressDb } = await import('../services/db.js');
    const progressOwner = await progressDb.job.findUnique({
      where: { id: data.job_id },
      select: { activeDispatchId: true },
    });
    if (
      progressOwner
      && (progressOwner.activeDispatchId ?? null) !== (data.dispatch_id ?? null)
    ) {
      console.warn(
        `[Workers] Ignoring progress for job ${data.job_id} from stale dispatch ${data.dispatch_id ?? 'missing'} ` +
        `(active: ${progressOwner.activeDispatchId ?? 'none'})`
      );
      // shouldCancel tells the worker to stop, which is what we want: it is running work nobody
      // is waiting for.
      return res.json({ status: 'ok', stale: true, shouldCancel: true });
    }

    const progressDispatch = data.dispatch_id
      ? await progressDb.jobDispatch.findUnique({
          where: { id: data.dispatch_id },
          select: { jobId: true, kind: true, segment: true },
        })
      : null;
    const isModernLandingDispatch =
      progressDispatch?.jobId === data.job_id
      && progressDispatch.kind === DispatchKind.CONTINUE
      && progressDispatch.segment === 'landing_page';

    // The current landing worker reports the stage as completed once before it publishes the
    // generated file. Acknowledge that intermediate callback without closing stage 15; the final
    // callback below carries landing_path and owns the atomic asset + dispatch settlement.
    if (
      isModernLandingDispatch
      && data.status === 'completed'
      && !data.report_path
      && !data.landing_path
    ) {
      return res.json({ status: 'ok', awaitingArtifact: true, shouldCancel: false });
    }

    // A guardrail can return no landing page, after which the worker publishes the existing
    // report path as its final callback. That is not a paid landing-page success: settle and
    // refund the exact attempt while preserving the already-completed research Job.
    if (
      isModernLandingDispatch
      && data.status === 'completed'
      && data.report_path
      && !data.landing_path
    ) {
      const errorMessage = 'Landing page generation completed without an output file';
      const settled = await failLandingPageDispatch(
        data.job_id,
        data.dispatch_id!,
        errorMessage,
      );
      if (!settled) {
        return res.json({ status: 'ok', stale: true, shouldCancel: true });
      }
      broadcastProgress(data.job_id, {
        stage: 15,
        name: 'Landing Page Generation',
        status: 'failed',
        error: errorMessage,
      });
      return res.json({ status: 'ok', shouldCancel: false, landingPageStatus: 'FAILED' });
    }

    let modernLandingCompleted = false;
    if (isModernLandingDispatch && data.status === 'completed' && data.landing_path) {
      modernLandingCompleted = await completeLandingPageDispatch(
        data.job_id,
        data.dispatch_id!,
        data.landing_path,
      );
      if (!modernLandingCompleted) {
        return res.json({ status: 'ok', stale: true, shouldCancel: true });
      }
    }

    // For whole-job failures, claim the terminal transition before writing JobProgress. The
    // ownership read above is only advisory: another callback can settle the dispatch immediately
    // after it. failJob's dispatch CAS is the authority, and a loser must leave every downstream
    // projection untouched.
    let failureReportAsset: Awaited<ReturnType<typeof getJobAsset>> = null;
    let modernLandingFailed = false;
    let terminalFailureApplied = false;
    if (data.status === 'failed' && data.error) {
      failureReportAsset = await getJobAsset(data.job_id, AssetType.REPORT_JSON);
      const isLandingPageOnlyFailure = data.stage === 15 && failureReportAsset;
      if (isLandingPageOnlyFailure && data.dispatch_id) {
        modernLandingFailed = await failLandingPageDispatch(
          data.job_id,
          data.dispatch_id,
          data.error,
        );
        if (!modernLandingFailed) {
          return res.json({ status: 'ok', stale: true, shouldCancel: true });
        }
      } else if (!isLandingPageOnlyFailure) {
        const failure = await failJob(
          data.job_id,
          data.error,
          data.stage,
          undefined,
          undefined,
          undefined,
          undefined,
          data.dispatch_id,
        );
        if (!failure.applied) {
          return res.json({ status: 'ok', stale: true, shouldCancel: true });
        }
        terminalFailureApplied = true;
      }
    }

    // 1. Update stage progress in database
    if (!modernLandingCompleted && !modernLandingFailed) {
      const progress = await updateStageProgress(
        data.job_id,
        data.stage,
        stageStatus,
        data.error,
        data.artifact,
        terminalFailureApplied ? undefined : data.dispatch_id,
      );
      if (progress === null) {
        return res.json({ status: 'ok', stale: true, shouldCancel: true });
      }
    }

    // Track landing page lifecycle via landingPageStatus
    if (data.stage === 15) {
      const { prisma: db } = await import('../services/db.js');
      if (data.status === 'running') {
        if (isModernLandingDispatch) {
          // /job-started already claimed the exact landing dispatch and moved QUEUED -> RUNNING.
          // Do not perform a weaker status-only write here.
        } else {
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
        }
      } else if (data.status === 'completed') {
        if (modernLandingCompleted) {
          // Asset, status, and dispatch settlement committed together above.
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
    }

    // 2. Handle job completion (report_path indicates final success)
    if (data.status === 'completed' && data.report_path && !isModernLandingDispatch) {
      const { prisma: completionDb } = await import('../services/db.js');
      if (data.dispatch_id) {
        let completed = false;
        try {
          completed = await completionDb.$transaction(async tx => {
            const job = await tx.job.updateMany({
              where: {
                id: data.job_id,
                status: JobStatus.RUNNING_PHASE2,
                activeDispatchId: data.dispatch_id,
              },
              data: {
                status: JobStatus.COMPLETED,
                completedAt: new Date(),
                progressPercent: 100,
                activeDispatchId: null,
              },
            });
            if (job.count !== 1) throw new Error('STALE_COMPLETION_DISPATCH');
            const dispatch = await tx.jobDispatch.updateMany({
              where: {
                id: data.dispatch_id,
                jobId: data.job_id,
                kind: DispatchKind.DEEP_RESEARCH,
                state: DispatchState.CLAIMED,
              },
              data: { state: DispatchState.COMPLETED, settledAt: new Date() },
            });
            if (dispatch.count !== 1) throw new Error('STALE_COMPLETION_DISPATCH');
            await tx.jobAsset.upsert({
              where: {
                jobId_assetType: { jobId: data.job_id, assetType: AssetType.REPORT_JSON },
              },
              create: {
                jobId: data.job_id,
                assetType: AssetType.REPORT_JSON,
                filePath: data.report_path!,
              },
              update: { filePath: data.report_path! },
            });
            if (data.landing_path) {
              await tx.jobAsset.upsert({
                where: {
                  jobId_assetType: { jobId: data.job_id, assetType: AssetType.LANDING_PAGE },
                },
                create: {
                  jobId: data.job_id,
                  assetType: AssetType.LANDING_PAGE,
                  filePath: data.landing_path,
                },
                update: { filePath: data.landing_path },
              });
            }
            return true;
          });
        } catch (error) {
          if (!(error instanceof Error) || error.message !== 'STALE_COMPLETION_DISPATCH') throw error;
        }
        if (!completed) {
          return res.json({ status: 'ok', stale: true, shouldCancel: true });
        }
      } else {
        await completeJob(
          data.job_id,
          data.report_path,
          data.landing_path
        );
      }

      try {
        const completedJob = await completionDb.job.findUnique({
          where: { id: data.job_id },
          select: { niche: true },
        });
        const { getReportJsonForJob } = await import('../services/assetService.js');
        const report = await getReportJsonForJob(data.job_id);
        if (completedJob && report) {
          const { createReportAnalystFollowup } = await import('../services/analystFollowupService.js');
          await createReportAnalystFollowup({
            jobId: data.job_id,
            operationId: data.dispatch_id ?? data.job_id,
            niche: completedJob.niche,
            report,
          });
        }
      } catch (followupError) {
        console.error('[Workers] Failed to create report analyst follow-up:', followupError);
      }

      // Skip email notification here - already sent by /report-ready endpoint
      console.log(`[Workers] Job ${data.job_id} completed - report: ${data.report_path}`);
    }

    // 3. Handle job failure
    if (data.status === 'failed' && data.error) {
      if (data.stage === 15 && failureReportAsset) {
        if (!modernLandingFailed) {
          // Rolling-deploy fallback for a genuinely legacy, identityless landing attempt.
          const { prisma: db } = await import('../services/db.js');
          await db.job.update({
            where: { id: data.job_id },
            data: { landingPageStatus: 'FAILED' },
          });
          try {
            await refundForStage(data.job_id, 'landing_page');
          } catch (refundErr) {
            console.error(`[Workers] Failed to refund landing page credits for job ${data.job_id}:`, refundErr);
          }
          await completeJob(data.job_id, failureReportAsset.filePath);
        }
        console.log(`[Workers] Landing page failed for job ${data.job_id} but job completed`);
      } else {
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
    const stampedSolutions = stampNewIdeaIdentities(
      data.job_id,
      data.solutions,
      'phase1',
      data.dispatch_id ?? 'initial',
    );
    const { prisma } = await import('../services/db.js');
    const { JobStatus } = await import('@prisma/client');

    // Phase-1 LLM cost (for the admin pricing view). Persist only real spend so empty /
    // $0 summaries don't create misleading rows. When Phase-2 completes, report-ready
    // overwrites this with the cumulative Phase-1 + Phase-2 total.
    const cost = data.cost_summary;
    const totalCost = typeof cost?.total_cost === 'number' ? cost.total_cost : null;
    const costData: Prisma.JobUpdateManyMutationInput =
      cost && totalCost && totalCost > 0
        ? { costUsd: totalCost, costSummary: cost as Prisma.InputJsonValue }
        : {};

    // Atomic conditional update: RUNNING → AWAITING_SELECTION.
    //
    // The dispatch guard matters MORE here than at the gate callbacks, not less: a guided G2
    // Continue does not end at /gate-reached — it runs on to stage 5 and terminates HERE. Guarding
    // only the two gate endpoints would have left the entire G2 continuation unprotected, which is
    // to say the busiest path in the whole flow.
    const transition = {
      where: {
        id: data.job_id,
        status: JobStatus.RUNNING,
        ...dispatchGuard(data.dispatch_id),
      },
      data: {
        status: JobStatus.AWAITING_SELECTION,
        solutionIdeas: stampedSolutions as any,
        phase1CheckpointPath: data.checkpoint_path,
        ideasShownAt: new Date(),
        awaitingSelectionAt: new Date(),
        ...(data.dispatch_id ? { activeDispatchId: null } : {}),
        ...costData,
      },
    };

    let result: { count: number };
    if (data.dispatch_id) {
      try {
        result = await prisma.$transaction(async (tx) => {
          // Job first, matching start/cancel lock order. If the exact CLAIMED dispatch cannot
          // close, throw so the Job transition rolls back with it; AWAITING_SELECTION must never
          // coexist with a dangling in-flight attempt.
          const jobResult = await tx.job.updateMany(transition);
          if (jobResult.count === 0) return jobResult;
          const dispatchResult = await tx.jobDispatch.updateMany({
            where: {
              id: data.dispatch_id,
              jobId: data.job_id,
              kind: DispatchKind.CONTINUE,
              state: DispatchState.CLAIMED,
            },
            data: { state: DispatchState.COMPLETED, settledAt: new Date() },
          });
          if (dispatchResult.count !== 1) {
            throw new Error('IDEAS_READY_DISPATCH_CONFLICT');
          }
          return jobResult;
        });
      } catch (error) {
        if (!(error instanceof Error) || error.message !== 'IDEAS_READY_DISPATCH_CONFLICT') {
          throw error;
        }
        result = { count: 0 };
      }
    } else {
      // Legacy queue messages have no dispatch row to close, but remain fenced to jobs whose
      // activeDispatchId is also null by dispatchGuard(undefined).
      result = await prisma.job.updateMany(transition);
    }

    if (result.count === 0) {
      // Distinguish WHY the conditional update missed (mirrors the /job-complete precedent):
      // a lost-response retry must read as idempotent success, while a cancelled/failed job
      // must NOT — the worker previously treated every 409 as "delivered", silently
      // discarding a completed run's ideas.
      const job = await prisma.job.findUnique({
        where: { id: data.job_id },
        select: { status: true, ideasShownAt: true, activeDispatchId: true },
      });
      if (!job) {
        res.status(404).json({ error: 'Job not found' });
        return;
      }
      const dispatch = data.dispatch_id
        ? await prisma.jobDispatch.findUnique({
            where: { id: data.dispatch_id },
            select: { jobId: true, kind: true, state: true },
          })
        : null;
      const exactDispatchCompleted =
        dispatch?.jobId === data.job_id
        && dispatch.kind === DispatchKind.CONTINUE
        && dispatch.state === DispatchState.COMPLETED;
      if (
        (!data.dispatch_id && (job.status === JobStatus.AWAITING_SELECTION || job.ideasShownAt !== null))
        || (
          data.dispatch_id
          && exactDispatchCompleted
          && job.status === JobStatus.AWAITING_SELECTION
          && job.ideasShownAt !== null
        )
      ) {
        // A previous attempt landed and the response was lost — idempotent success.
        // Skip re-broadcast/notify: the first delivery already did both.
        res.json({ status: 'ok', idempotent: true });
        return;
      }
      if (data.dispatch_id && job.activeDispatchId !== data.dispatch_id) {
        res.json({ status: 'ok', stale: true, shouldCancel: true });
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
        ...dispatchGuard(data.dispatch_id),
      },
      select: {
        solutionIdeas: true,
        userId: true,
        niche: true,
        costUsd: true,
        regenerationCount: true,
        ideaBatchCompletedCount: true,
      },
    });

    if (!job) {
      if (data.dispatch_id) {
        const dispatch = await prisma.jobDispatch.findUnique({
          where: { id: data.dispatch_id },
          select: { jobId: true, kind: true, state: true },
        });
        if (
          dispatch?.jobId === data.job_id
          && dispatch.kind === DispatchKind.REGENERATE
          && dispatch.state === DispatchState.COMPLETED
        ) {
          res.json({ status: 'ok', idempotent: true });
          return;
        }
        const reason = await diagnoseGuardMiss(
          data.job_id,
          data.dispatch_id,
          [JobStatus.REGENERATING, JobStatus.QUEUED],
        );
        res.json({ status: 'ok', stale: true, reason });
        return;
      }
      res.status(409).json({ error: 'Job not in REGENERATING state' });
      return;
    }

    const existingSolutions = ensureIdeaIdentities(data.job_id, job.solutionIdeas);
    const dispatch = data.dispatch_id
      ? await prisma.jobDispatch.findUnique({
          where: { id: data.dispatch_id },
          select: {
            jobId: true,
            kind: true,
            state: true,
            requestFingerprint: true,
            batchOrdinal: true,
          },
        })
      : null;
    if (
      data.dispatch_id
      && (
        dispatch?.jobId !== data.job_id
        || dispatch.kind !== DispatchKind.REGENERATE
        || (
          dispatch.state !== DispatchState.AUTHORIZED
          && dispatch.state !== DispatchState.CLAIMED
        )
      )
    ) {
      res.json({ status: 'ok', stale: true, reason: 'stale_dispatch' });
      return;
    }
    const currentBaseFingerprint = canonicalJsonSha256(existingSolutions.flatMap(solution =>
      typeof solution.idea_id === 'string' && typeof solution.idea_revision === 'number'
        ? [{
            ideaId: solution.idea_id,
            ideaRevision: solution.idea_revision,
            snapshotSha256: candidateSnapshotSha256(solution),
          }]
        : []
    ));
    if (dispatch?.requestFingerprint && dispatch.requestFingerprint !== currentBaseFingerprint) {
      res.status(409).json({
        error: 'Candidate pool changed after this batch was authorized',
        code: 'STALE_BATCH_BASE_POOL',
      });
      return;
    }
    const stampedSolutions = stampNewIdeaIdentities(
      data.job_id,
      data.solutions,
      'regeneration',
      data.dispatch_id ?? `regeneration-${job.regenerationCount}`,
    );
    const mergedSolutions = [...existingSolutions, ...stampedSolutions];

    // Regeneration LLM cost (for the admin pricing view). Unlike report-ready (which OVERWRITES
    // costUsd with the run's cumulative total), regeneration ADDS spend to an already-settled
    // job — so costUsd must ACCUMULATE. costSummary is replaced with the latest batch's breakdown
    // rather than merged (cheap; a full stage_breakdown merge isn't worth the complexity here).
    const cost = data.cost_summary;
    const batchCost = typeof cost?.total_cost === 'number' ? cost.total_cost : null;
    const costData: Prisma.JobUpdateManyMutationInput =
      cost && batchCost && batchCost > 0
        ? { costUsd: (job.costUsd ?? 0) + batchCost, costSummary: cost as Prisma.InputJsonValue }
        : {};

    // Merge + status transition + dispatch settlement are one commit. Otherwise a
    // second paid operation can be admitted after AWAITING_SELECTION is visible but
    // before the first dispatch has been disarmed.
    const commit = async (tx: Prisma.TransactionClient) => {
      const updated = await tx.job.updateMany({
        where: {
          id: data.job_id,
          status: { in: [JobStatus.REGENERATING, JobStatus.QUEUED] },
          ideasRegeneratedAt: { not: null },
          ...dispatchGuard(data.dispatch_id),
        },
        data: {
          status: JobStatus.AWAITING_SELECTION,
          solutionIdeas: mergedSolutions as any,
          ideaBatchCompletedCount: { increment: 1 },
          ...costData,
        },
      });
      if (updated.count > 0 && data.dispatch_id) {
        const addedRefs = stampedSolutions.flatMap((idea) =>
          typeof idea.idea_id === 'string' && typeof idea.idea_revision === 'number'
            ? [{
                ideaId: idea.idea_id,
                ideaRevision: idea.idea_revision,
                snapshotSha256: candidateSnapshotSha256(idea),
              }]
            : []
        );
        const resultSnapshot = {
          schemaVersion: 1,
          kind: 'idea_batch_result',
          ordinal: data.batch_ordinal ?? dispatch?.batchOrdinal ?? job.regenerationCount,
          generatedCount: data.generated_count ?? data.solutions.length,
          addedRefs,
          ruledOutCount: data.ruled_out_count ?? 0,
          ruledOutRefs: data.ruled_out_refs ?? [],
        };
        await tx.jobDispatch.updateMany({
          where: { id: data.dispatch_id, resultSnapshot: { equals: Prisma.AnyNull } },
          data: {
            resultSnapshot: resultSnapshot as unknown as Prisma.InputJsonValue,
            resultFingerprint: canonicalJsonSha256(resultSnapshot),
          },
        });
        await settleDispatch(tx, data.dispatch_id, DispatchState.COMPLETED);
        const addedIdeaIds = stampedSolutions.flatMap((idea) =>
          typeof idea.idea_id === 'string' ? [idea.idea_id] : []
        );
        const outcome = addedIdeaIds.length > 0 ? 'completed' : 'no_candidates_added';
        await tx.chatMessage.create({
          data: {
            jobId: data.job_id,
            gateStage: 5,
            role: 'receipt',
            content: buildRegenerationReceiptContent(
              'regeneration_settled',
              outcome,
              addedIdeaIds.length,
            ),
            operationId: `regeneration:${data.dispatch_id}:settled`,
            patchJson: buildRegenerationEnvelope({
              event: 'regeneration_settled',
              operationId: data.dispatch_id,
              ordinal: data.batch_ordinal ?? job.regenerationCount,
              outcome,
              generatedCount: data.generated_count ?? data.solutions.length,
              addedIdeaIds,
              addedIdeas: addedRefs.map(ref => ({
                ideaId: ref.ideaId,
                ideaRevision: ref.ideaRevision,
              })),
              refPrecision: 'exact',
              ruledOutCount: data.ruled_out_count ?? 0,
              refunded: false,
            }) as unknown as object,
          },
        });
      }
      return updated;
    };
    const result = data.dispatch_id
      ? await prisma.$transaction(commit)
      : await prisma.job.updateMany({
          where: {
            id: data.job_id,
            status: { in: [JobStatus.REGENERATING, JobStatus.QUEUED] },
            ideasRegeneratedAt: { not: null },
            activeDispatchId: null,
          },
          data: {
            status: JobStatus.AWAITING_SELECTION,
            solutionIdeas: mergedSolutions as any,
            ...costData,
          },
        });

    if (result.count === 0) {
      if (data.dispatch_id) {
        const reason = await diagnoseGuardMiss(
          data.job_id,
          data.dispatch_id,
          [JobStatus.REGENERATING, JobStatus.QUEUED],
        );
        res.json({ status: 'ok', stale: true, reason });
        return;
      }
      res.status(409).json({ error: 'Job state changed during regeneration' });
      return;
    }

    // The worker rewrites PREVIEW_REPORT in place from the merged candidate pool. Evict
    // this process's 10-minute parse cache before any analyst/UI reader can observe the
    // updated Job.solutionIdeas alongside the old preview-backed dossier.
    const { invalidatePreviewReportCache } = await import('../services/assetService.js');
    invalidatePreviewReportCache(data.job_id);

    const { createRegenerationAnalystFollowup } = await import('../services/analystFollowupService.js');
    await createRegenerationAnalystFollowup({
      jobId: data.job_id,
      dispatchId: data.dispatch_id ?? `legacy-${data.job_id}-${job.regenerationCount}`,
      niche: job.niche,
      ideas: stampedSolutions,
    });

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

    if (data.dispatch_id) {
      const [job, dispatch] = await Promise.all([
        prisma.job.findFirst({
          where: {
            id: data.job_id,
            status: { in: [JobStatus.REGENERATING, JobStatus.QUEUED] },
            ...dispatchGuard(data.dispatch_id),
          },
          select: { status: true },
        }),
        prisma.jobDispatch.findUnique({
          where: { id: data.dispatch_id },
          select: { id: true, kind: true, segment: true, chargeId: true },
        }),
      ]);
      if (!job || dispatch?.kind !== DispatchKind.REGENERATE) {
        const reason = await diagnoseGuardMiss(
          data.job_id,
          data.dispatch_id,
          [JobStatus.REGENERATING, JobStatus.QUEUED],
        );
        res.json({ status: 'ok', stale: true, reason });
        return;
      }
      const settled = await cancelRegenerationDispatch(
        data.job_id,
        { id: dispatch.id, segment: dispatch.segment, chargeId: dispatch.chargeId },
        job.status,
        'SYSTEM_FAULT',
      );
      if (!settled.cancelled) {
        res.json({ status: 'ok', stale: true, reason: settled.reason });
        return;
      }
    } else {
      // Narrow rolling-deploy compatibility path. Undispatched callbacks may only
      // touch jobs that likewise have no active dispatch.
      const legacyJob = await prisma.job.findUnique({
        where: { id: data.job_id },
        select: { regenerationCount: true },
      });
      const result = await prisma.job.updateMany({
        where: {
          id: data.job_id,
          status: { in: [JobStatus.REGENERATING, JobStatus.QUEUED] },
          ideasRegeneratedAt: { not: null },
          activeDispatchId: null,
        },
        data: { status: JobStatus.AWAITING_SELECTION },
      });
      if (result.count === 0) {
        res.status(409).json({ error: 'Job not in REGENERATING state' });
        return;
      }
      if (legacyJob?.regenerationCount) {
        const { refundForRegenerationStage } = await import('../services/creditService.js');
        await refundForRegenerationStage(data.job_id, legacyJob.regenerationCount);
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

/**
 * POST /api/workers/seed-complete
 * Worker reports a user-composed idea seed (plans/eager-meandering-feather.md Phase 5) finished
 * birth + scoring and was already merged/saved by the worker. Merges the ONE outcome idea
 * (active or demoted — the worker never drops a paid seed) into the pool and settles the
 * dispatch, mirroring /regeneration-complete's merge but on the DispatchKind.SEED_IDEA
 * lifecycle (dispatchGuard/settleDispatch) rather than the legacy status-field guard.
 */
workersRouter.post('/seed-complete', async (req: Request, res: Response) => {
  try {
    const data = SeedIdeaCompleteSchema.parse(req.body);
    const { prisma } = await import('../services/db.js');
    const { JobStatus } = await import('@prisma/client');

    const cost = data.cost_summary;
    const batchCost = typeof cost?.total_cost === 'number' ? cost.total_cost : null;

    // Read + merge + flip + settle all inside ONE transaction, so the merged solutionIdeas
    // array is never built from a snapshot that could go stale before the write lands.
    const result = await prisma.$transaction(async (tx) => {
      const current = await tx.job.findFirst({
        where: {
          id: data.job_id,
          status: { in: [JobStatus.QUEUED, JobStatus.RUNNING] },
          ...dispatchGuard(data.dispatch_id),
        },
        select: { solutionIdeas: true, costUsd: true, niche: true, seedIdeaCount: true },
      });
      if (!current) return { count: 0 };
      const dispatch = data.dispatch_id
        ? await tx.jobDispatch.findUnique({
            where: { id: data.dispatch_id },
            select: { sourceMessageId: true },
          })
        : null;
      const sourceMessage = dispatch?.sourceMessageId
        ? await tx.chatMessage.findFirst({
            where: {
              id: dispatch.sourceMessageId,
              jobId: data.job_id,
              gateStage: 5,
              role: 'assistant',
            },
            select: { patchJson: true },
          })
        : null;
      const synthesisProposal = IdeaSynthesisPatchSchema.safeParse(sourceMessage?.patchJson);
      const stampedIdea = synthesisProposal.success && dispatch?.sourceMessageId
          ? stampSynthesizedIdeaIdentity(
            data.job_id,
            data.idea,
            // Exact Concept Forge evaluations are attempt-scoped: the dispatch is
            // their immutable evaluation identity. Legacy synthesis proposals did
            // not carry an exact evaluation brief, so retain their historical
            // source-message identity for retry-stable idea IDs.
            synthesisProposal.data.evaluation
              ? data.dispatch_id!
              : dispatch.sourceMessageId,
            synthesisProposal.data,
            dispatch.sourceMessageId,
          )
        : stampNewIdeaIdentities(
            data.job_id,
            [data.idea],
            'seed',
            data.dispatch_id ?? `seed-${current.seedIdeaCount}`,
          )[0];
      const existingSolutions = ensureIdeaIdentities(data.job_id, current.solutionIdeas);

      // A demoted seed must NOT enter the selectable pool — it belongs only in the
      // preview report's `examined_ruled_out` ledger (worker re-materializes that asset
      // separately; see the cache invalidation below). Only an accepted seed is appended.
      const mergedSolutions = data.outcome === 'accepted'
        ? [...existingSolutions, stampedIdea]
        : existingSolutions;
      const costData: Prisma.JobUpdateManyMutationInput =
        cost && batchCost && batchCost > 0
          ? { costUsd: (current.costUsd ?? 0) + batchCost, costSummary: cost as Prisma.InputJsonValue }
          : {};

      const flipped = await tx.job.updateMany({
        where: {
          id: data.job_id,
          status: { in: [JobStatus.QUEUED, JobStatus.RUNNING] },
          ...dispatchGuard(data.dispatch_id),
        },
        data: {
          status: JobStatus.AWAITING_SELECTION,
          solutionIdeas: mergedSolutions as any,
          ...costData,
        },
      });
      if (flipped.count === 0) return { count: 0 };

      if (data.dispatch_id) {
        await settleDispatch(tx, data.dispatch_id, DispatchState.COMPLETED);

        // Durable 'seed_settled' receipt (continuous-analyst-ledger idiom) — a SEPARATE row
        // from the 'seed_submitted' one written at admission, keyed on the SAME
        // sourceMessageId the dispatch itself carries, so the seed card resolves its
        // terminal state across a reload without the worker having to resend it.
        if (dispatch?.sourceMessageId) {
          await tx.chatMessage.create({
            data: {
              jobId: data.job_id,
              gateStage: 5,
              role: 'receipt',
              content: buildSeedReceiptContent('seed_settled', data.outcome),
              patchJson: buildSeedEnvelope(
                'seed_settled', dispatch.sourceMessageId, data.outcome, stampedIdea,
                data.dispatch_id,
              ) as unknown as object,
            },
          });
        }
      }
      return { count: flipped.count, niche: current.niche, idea: stampedIdea };
    });

    if (result.count === 0) {
      const current = await prisma.job.findUnique({
        where: { id: data.job_id },
        select: { status: true, activeDispatchId: true },
      });
      if (!current) {
        res.status(404).json({ error: 'Job not found' });
        return;
      }
      // Superseded attempt — checked before the idempotency/cancellation reads below, which
      // would otherwise mistake another attempt's arrival for "my own, already landed".
      if ((current.activeDispatchId ?? null) !== (data.dispatch_id ?? null)) {
        const dispatch = data.dispatch_id
          ? await prisma.jobDispatch.findUnique({
              where: { id: data.dispatch_id },
              select: { jobId: true, kind: true, state: true },
            })
          : null;
        if (
          dispatch?.jobId === data.job_id
          && dispatch.kind === DispatchKind.SEED_IDEA
          && dispatch.state === DispatchState.COMPLETED
        ) {
          // A previous delivery of THIS attempt already landed and the response was lost.
          res.json({ status: 'ok', idempotent: true });
          return;
        }
        console.warn(
          `[Workers] Stale seed-complete for job ${data.job_id}: dispatch ${data.dispatch_id ?? '(none)'} ` +
          `is not the job's active dispatch (${current.activeDispatchId ?? 'none'}) — ignoring`
        );
        res.json({ status: 'ok', stale: true });
        return;
      }
      if (current.status === JobStatus.CANCELLED) {
        console.log(
          `[Workers] Seed-complete for job ${data.job_id}: job was cancelled — nothing to deliver, not retrying`
        );
        res.json({ status: 'ok' });
        return;
      }
      res.status(409).json({
        error: `Job not in QUEUED/RUNNING state (current: ${current.status})`,
        state: current.status,
      });
      return;
    }

    // The worker re-materializes the preview report in place (same path, keyed by job_id)
    // whenever a seed settles, to fold in the new ruled-out/accepted record — drop the
    // in-memory cache so the next read re-parses it instead of serving the pre-seed
    // snapshot for up to CACHE_TTL.
    const { invalidatePreviewReportCache } = await import('../services/assetService.js');
    invalidatePreviewReportCache(data.job_id);

    if (data.dispatch_id) {
      const { createSeedAnalystFollowup } = await import('../services/analystFollowupService.js');
      await createSeedAnalystFollowup({
        jobId: data.job_id,
        dispatchId: data.dispatch_id,
        niche: result.niche!,
        outcome: data.outcome,
        idea: result.idea!,
      });
    }

    broadcastProgress(data.job_id, { stage: 5, name: 'Solution Pipeline', status: 'completed' });

    console.log(`[Workers] Seed idea complete for job ${data.job_id}: outcome=${data.outcome}`);
    res.json({ status: 'ok' });
  } catch (error) {
    if (error instanceof z.ZodError) {
      res.status(400).json({ error: 'Validation error', details: error.errors });
      return;
    }
    console.error('[Workers] Seed-complete error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

/**
 * POST /api/workers/seed-failed
 * Worker reports that a user-composed idea seed failed BEFORE anything was merged/saved.
 * Reverts QUEUED/RUNNING -> AWAITING_SELECTION, settles the dispatch, and refunds the numbered
 * seed_idea_N charge — mirrors /gate-failed's dispatch-settlement shape, not /regeneration-
 * failed's legacy status-field guard.
 */
workersRouter.post('/seed-failed', async (req: Request, res: Response) => {
  try {
    const data = SeedIdeaFailedSchema.parse(req.body);
    const { prisma } = await import('../services/db.js');
    const { JobStatus } = await import('@prisma/client');

    const dispatch = data.dispatch_id
      ? await prisma.jobDispatch.findUnique({ where: { id: data.dispatch_id } })
      : null;

    const result = await prisma.$transaction(async (tx) => {
      const reverted = await tx.job.updateMany({
        where: {
          id: data.job_id,
          status: { in: [JobStatus.QUEUED, JobStatus.RUNNING] },
          ...dispatchGuard(data.dispatch_id),
        },
        data: { status: JobStatus.AWAITING_SELECTION },
      });
      if (reverted.count === 0) return { count: 0 };

      let refund: Awaited<ReturnType<typeof refundChargeInTx>> = null;
      if (data.dispatch_id) {
        await settleDispatch(tx, data.dispatch_id, DispatchState.FAILED, 'SYSTEM_FAULT');

        // Durable 'seed_settled' receipt with outcome='failed' — the birth produced nothing,
        // so the seed card resolves to its terminal failed state on reload instead of
        // staying stuck on the 'seed_submitted' (evaluating) receipt forever.
        if (dispatch?.sourceMessageId) {
          await tx.chatMessage.create({
            data: {
              jobId: data.job_id,
              gateStage: 5,
              role: 'receipt',
              content: buildSeedReceiptContent('seed_settled', 'failed'),
              patchJson: buildSeedEnvelope(
                'seed_settled', dispatch.sourceMessageId, 'failed', undefined,
                data.dispatch_id,
              ) as unknown as object,
            },
          });
        }

        refund = dispatch?.chargeId
          ? await refundChargeInTx(tx, dispatch.chargeId)
          : dispatch?.seedOrdinal != null
            ? await refundForStageInTx(tx, data.job_id, `seed_idea_${dispatch.seedOrdinal}`)
            : null;
        if (refund) {
          await tx.jobDispatch.updateMany({
            where: { id: data.dispatch_id, state: DispatchState.FAILED },
            data: {
              state: DispatchState.REFUNDED,
              refundTransactionId: refund.id,
              refundedAt: new Date(),
              refundedAmount: refund.amount,
            },
          });
        }
      }
      return { count: reverted.count, refund };
    });

    if (result.count === 0) {
      const settled = await prisma.job.findUnique({
        where: { id: data.job_id },
        select: { status: true, activeDispatchId: true },
      });
      if (settled && (settled.activeDispatchId ?? null) !== (data.dispatch_id ?? null)) {
        console.warn(
          `[Workers] Stale seed-failed for job ${data.job_id}: dispatch ${data.dispatch_id ?? '(none)'} ` +
          `is not active (${settled.activeDispatchId ?? 'none'}) — ignoring, not reverting`
        );
        res.json({ status: 'ok', stale: true });
        return;
      }
      if (settled?.status === JobStatus.AWAITING_SELECTION) {
        res.json({ status: 'ok', idempotent: true });
        return;
      }
      res.status(409).json({ error: 'Job not in QUEUED/RUNNING state for a seed idea' });
      return;
    }

    if (result.refund) {
      console.log(
        `[Workers] Refunded ${Math.abs(result.refund.amount)} credits for job ${data.job_id} — seed idea failed`
      );
    }

    // Clear worker's current job
    await registerWorkerHeartbeat(data.worker_id, null);

    broadcastProgress(data.job_id, { stage: 5, name: 'Solution Pipeline', status: 'completed' });

    console.log(`[Workers] Seed idea failed for job ${data.job_id}, reverted to AWAITING_SELECTION: ${data.error_message}`);
    res.json({ status: 'ok' });
  } catch (error) {
    if (error instanceof z.ZodError) {
      res.status(400).json({ error: 'Validation error', details: error.errors });
      return;
    }
    console.error('[Workers] Seed-failed error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// ============================================
// Guided Mode Worker Endpoints (Phase B — G1/G2 stage gates)
// ============================================

/**
 * POST /api/workers/gate-reached
 * Worker reports a guided-mode (chatMode) job reached a G1 (post-Stage-1) or G2
 * (post-Stage-4) stage gate — either the FIRST arrival (RUNNING -> AWAITING_GATE) or a
 * RE-arrival at the SAME gate after an `apply_stay` gate-action round-trip
 * (QUEUED -> AWAITING_GATE, refreshed gateArtifact). Mirrors /ideas-ready's atomic-update +
 * idempotency contract (Codex 11 / DR A4): a lost-response retry reads back as
 * `{idempotent:true}`; CANCELLED has nothing to deliver to (quiet 200); any other
 * conflicting state raises a 409 so a reached gate is never silently discarded.
 */
workersRouter.post('/gate-reached', async (req: Request, res: Response) => {
  try {
    const data = GateReachedSchema.parse(req.body);
    const { prisma } = await import('../services/db.js');
    const { JobStatus } = await import('@prisma/client');

    // Live cost-tracker summary (mirrors /ideas-ready): persist only real spend so an
    // empty/$0 summary never creates a misleading row.
    const cost = data.cost_summary;
    const totalCost = typeof cost?.total_cost === 'number' ? cost.total_cost : null;
    const costData: Prisma.JobUpdateManyMutationInput =
      cost && totalCost && totalCost > 0
        ? { costUsd: totalCost, costSummary: cost as Prisma.InputJsonValue }
        : {};

    // A genuinely NEW gate (different from the job's current gateStage) resets the
    // apply_stay cap counter; a same-stage re-arrival (the apply_stay round-trip) leaves it
    // untouched — the counter is incremented by the gate-action route on each accepted apply.
    const preRow = await prisma.job.findUnique({
      where: { id: data.job_id },
      select: { gateStage: true },
    });
    const isNewGate = preRow?.gateStage !== data.gate_stage;

    // Monotonic guard (Codex review finding 9, REGRESSION, top-3): a delayed retry of a
    // PREVIOUS gate's notification (e.g. a duplicate worker execution surviving the reliable
    // queue's stale-claim requeue sweep) must not rewind a job that has already legitimately
    // progressed to a LATER gate. Reject as a no-op (200, not mutated) when the incoming
    // gate_stage regresses behind the job's currently recorded gateStage — the simplest
    // reliable guard given the existing payload shape (no new gate-token plumbing needed).
    if (preRow?.gateStage != null && data.gate_stage < preRow.gateStage) {
      console.warn(
        `[Workers] Stale gate-reached for job ${data.job_id}: incoming gate_stage=${data.gate_stage} ` +
        `< current gateStage=${preRow.gateStage} — ignoring (superseded by a later gate)`
      );
      res.json({ status: 'ok', stale: true });
      return;
    }

    // Arrival, receipt promotion and dispatch settlement in ONE transaction.
    //
    // These used to be three separate top-level calls, and the receipt promotion's failure was
    // swallowed by a .catch(console.error) — leaving the artifact committed while its audit row
    // still said 'submitted', which the retry then skipped as "idempotent, nothing to do". The
    // ledger would claim a change had never been applied when it had.
    //
    // The CAS is on dispatch AND status. Status alone lets a *matching* callback resurrect a
    // CANCELLED job; dispatch alone lets a superseded attempt land. Both, or neither.
    const result = await prisma.$transaction(async (tx) => {
      const flipped = await tx.job.updateMany({
        where: {
          id: data.job_id,
          status: { in: [JobStatus.RUNNING, JobStatus.QUEUED] },
          ...dispatchGuard(data.dispatch_id),
        },
        data: {
          status: JobStatus.AWAITING_GATE,
          gateStage: data.gate_stage,
          gateArtifact: data.gate_artifact as Prisma.InputJsonValue,
          gateReachedAt: new Date(),
          phase1CheckpointPath: data.checkpoint_path,
          ...(isNewGate ? { gateApplyCount: 0 } : {}),
          ...costData,
        },
      });

      if (flipped.count === 0) return { count: 0 };

      // A same-gate re-arrival IS the completion of an apply_stay round-trip: the refreshed
      // artifact in this very payload reflects the user's patch. Promote the receipt gate-action
      // wrote from 'submitted' to 'applied' — the ledger only claims a change once the pipeline
      // has actually re-derived with it. In-transaction, so a failure here rolls the arrival back
      // rather than silently desynchronising the record from the artifact.
      if (!isNewGate) {
        const pending = await tx.chatMessage.findFirst({
          where: { jobId: data.job_id, gateStage: data.gate_stage, role: 'receipt' },
          orderBy: { createdAt: 'desc' },
          select: { id: true, patchJson: true },
        });
        const envelope = pending?.patchJson as { event?: string } | null;
        if (pending && envelope?.event === 'gate_patch_submitted') {
          await tx.chatMessage.update({
            where: { id: pending.id },
            data: {
              patchJson: {
                ...(pending.patchJson as object),
                event: 'gate_patch_applied',
              } as Prisma.InputJsonValue,
            },
          });
        }
      }

      // The attempt delivered. Close it and disarm the CAS, so any straggler callback still in
      // flight for this dispatch now matches nothing.
      if (data.dispatch_id) {
        await settleDispatch(tx, data.dispatch_id, DispatchState.COMPLETED);
      }

      return { count: flipped.count };
    });

    if (result.count === 0) {
      const job = await prisma.job.findUnique({
        where: { id: data.job_id },
        select: { status: true, gateStage: true, gateReachedAt: true, activeDispatchId: true },
      });
      if (!job) {
        res.status(404).json({ error: 'Job not found' });
        return;
      }

      // The job has moved on to a different attempt than the one this callback is reporting for.
      // Checked BEFORE the idempotency branch below, which would otherwise mistake a superseded
      // attempt's arrival for "my own delivery, already landed".
      // Both sides are ?? null-normalised: an absent column reads `undefined`, and `undefined !==
      // null` would condemn a perfectly good legacy callback as stale.
      if ((job.activeDispatchId ?? null) !== (data.dispatch_id ?? null)) {
        console.warn(
          `[Workers] Stale gate-reached for job ${data.job_id}: dispatch ${data.dispatch_id ?? '(none)'} ` +
          `is not the job's active dispatch (${job.activeDispatchId ?? 'none'}) — ignoring`
        );
        res.json({ status: 'ok', stale: true });
        return;
      }

      if (job.status === JobStatus.CANCELLED) {
        console.log(
          `[Workers] Gate-reached for job ${data.job_id}: job was cancelled — nothing to deliver, not retrying`
        );
        res.json({ status: 'ok' });
        return;
      }
      if (job.status === JobStatus.AWAITING_GATE && job.gateStage === data.gate_stage && job.gateReachedAt !== null) {
        // A previous attempt landed and the response was lost — idempotent success.
        res.json({ status: 'ok', idempotent: true });
        return;
      }
      res.status(409).json({
        error: `Job not in RUNNING/QUEUED state (current: ${job.status})`,
        state: job.status,
      });
      return;
    }

    // Broadcast progress update to SSE clients so the job page re-fetches and shows the gate.
    broadcastProgress(data.job_id, {
      stage: data.gate_stage,
      name: data.gate_stage === 1 ? 'Niche Validation' : 'Audience Mapping',
      status: 'completed',
    });

    // Send "gate reached" email notification — gates wait indefinitely (same semantics as
    // AWAITING_SELECTION), so this email is the funnel back to a paused run. Sent on every
    // arrival (including an apply_stay re-arrival at the same gate) — low-frequency,
    // user-initiated action, so a repeat email is rare and expected, not spammy.
    const job = await prisma.job.findUnique({
      where: { id: data.job_id },
      select: { userId: true, niche: true },
    });
    if (job?.userId) {
      const user = await prisma.user.findUnique({ where: { id: job.userId }, select: { email: true } });
      if (user?.email) {
        notifyGateReached(job.userId, user.email, data.job_id, job.niche, data.gate_stage).catch(err => {
          console.error('Failed to send gate-reached notification:', err);
        });
      }
    }

    console.log(`[Workers] Gate reached for job ${data.job_id}: stage ${data.gate_stage}`);
    res.json({ status: 'ok' });
  } catch (error) {
    if (error instanceof z.ZodError) {
      res.status(400).json({ error: 'Validation error', details: error.errors });
      return;
    }
    console.error('[Workers] Gate reached error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

/**
 * POST /api/workers/gate-failed
 * Worker reports that a gate continuation (`continue_from_gate`) failed — either resuming
 * the checkpoint or running to the next stop. Reverts QUEUED -> AWAITING_GATE (mirrors
 * /regeneration-failed's QUEUED -> AWAITING_SELECTION revert) so the existing gate
 * artifact/patch history is preserved and the run is retryable, instead of FAILED (which
 * would trigger an incorrect credit refund).
 */
workersRouter.post('/gate-failed', async (req: Request, res: Response) => {
  try {
    const data = GateFailedSchema.parse(req.body);
    const { prisma } = await import('../services/db.js');
    const { JobStatus } = await import('@prisma/client');

    // What this failure is FOR. Without the dispatch, a failure could only be aimed at
    // "(job, status, gateStage)" — so a delayed failure from attempt A reverted attempt B, and
    // a payload with gate_stage=null dropped the stage filter ENTIRELY and could revert any
    // QUEUED/RUNNING job at all. The dispatch id makes the target exact.
    const dispatch = data.dispatch_id
      ? await prisma.jobDispatch.findUnique({ where: { id: data.dispatch_id } })
      : null;

    // A failed apply must give the steering budget back. gateApplyCount is incremented before the
    // stage runs and was never restored, so five infrastructure failures permanently burned a
    // user's five applies without a single successful change. The budget means SUCCESSFUL applies.
    const failedApply = dispatch?.kind === 'APPLY_STAY';
    const refundableSegment =
      data.failure_kind === 'SYSTEM_FAULT'
      && dispatch?.segment
      && isGuidedSegment(dispatch.segment)
        ? dispatch.segment
        : null;
    if (
      data.failure_kind === 'SYSTEM_FAULT'
      && dispatch?.segment
      && !refundableSegment
    ) {
      console.warn(
        `[Workers] Dispatch ${dispatch.id} has unrecognised segment '${dispatch.segment}' — skipping refund`
      );
    }

    // Revert + settle in one transaction, so the job cannot land back at the gate with its budget
    // still spent and a receipt still claiming a change is pending.
    const result = await prisma.$transaction(async (tx) => {
      const reverted = await tx.job.updateMany({
        where: {
          id: data.job_id,
          status: { in: [JobStatus.QUEUED, JobStatus.RUNNING] },
          ...dispatchGuard(data.dispatch_id),
          // Keep the stage predicate for the LEGACY (undispatched) path only — there it is the
          // only targeting we have. With a dispatch id the guard above is strictly better, and
          // the stage is redundant.
          ...(!data.dispatch_id && data.gate_stage !== null ? { gateStage: data.gate_stage } : {}),
        },
        data: {
          status: JobStatus.AWAITING_GATE,
          gateReachedAt: new Date(),
          // Restore the apply this attempt consumed. Guarded so it can never go negative.
          ...(failedApply ? { gateApplyCount: { decrement: 1 } } : {}),
        },
      });

      if (reverted.count === 0) return { count: 0 };

      if (failedApply) {
        // Drop the 'submitted' receipt. It promised a change that never happened, and leaving it
        // there strands the proposal card mid-state forever — the promotion path only ever looks
        // for the NEWEST receipt, so an orphan is never repaired.
        const pending = await tx.chatMessage.findFirst({
          where: { jobId: data.job_id, gateStage: dispatch?.gateStage ?? undefined, role: 'receipt' },
          orderBy: { createdAt: 'desc' },
          select: { id: true, patchJson: true },
        });
        const envelope = pending?.patchJson as { event?: string } | null;
        if (pending && envelope?.event === 'gate_patch_submitted') {
          await tx.chatMessage.delete({ where: { id: pending.id } });
        }
      }

      let refund: Awaited<ReturnType<typeof refundChargeInTx>> = null;
      if (data.dispatch_id) {
        await settleDispatch(tx, data.dispatch_id, DispatchState.FAILED, data.failure_kind);
        if (refundableSegment) {
          refund = dispatch?.chargeId
            ? await refundChargeInTx(tx, dispatch.chargeId)
            : await refundForStageInTx(tx, data.job_id, refundableSegment);
          if (refund) {
            await tx.jobDispatch.updateMany({
              where: { id: data.dispatch_id, state: DispatchState.FAILED },
              data: {
                state: DispatchState.REFUNDED,
                refundTransactionId: refund.id,
                refundedAt: new Date(),
                refundedAmount: refund.amount,
              },
            });
          }
        }
      }

      return { count: reverted.count, refund };
    });

    if (result.refund && refundableSegment) {
      console.log(
        `[Workers] Refunded ${Math.abs(result.refund.amount)} credits for job ${data.job_id} — ` +
        `system fault on segment ${refundableSegment}`
      );
    }

    if (result.count === 0) {
      // Idempotency (finding 10, AMEND): a retried delivery landing after an earlier attempt
      // already reverted the job reads back as success instead of a spurious 409.
      const settled = await prisma.job.findUnique({
        where: { id: data.job_id },
        select: { status: true, gateStage: true, activeDispatchId: true },
      });

      // Superseded attempt — checked before idempotency, which would otherwise read another
      // attempt's successful revert as "my own, already landed". Both sides ?? null-normalised
      // (an absent column reads undefined, which would wrongly read as "different").
      if (settled && (settled.activeDispatchId ?? null) !== (data.dispatch_id ?? null)) {
        console.warn(
          `[Workers] Stale gate-failed for job ${data.job_id}: dispatch ${data.dispatch_id ?? '(none)'} ` +
          `is not active (${settled.activeDispatchId ?? 'none'}) — ignoring, not reverting`
        );
        res.json({ status: 'ok', stale: true });
        return;
      }

      if (
        settled
        && settled.status === JobStatus.AWAITING_GATE
        && (data.gate_stage === null || settled.gateStage === data.gate_stage)
      ) {
        res.json({ status: 'ok', idempotent: true });
        return;
      }
      res.status(409).json({ error: 'Job not in QUEUED/RUNNING state for a gate continuation' });
      return;
    }

    // Clear worker's current job
    await registerWorkerHeartbeat(data.worker_id, null);

    const job = await prisma.job.findUnique({
      where: { id: data.job_id },
      select: { gateStage: true },
    });

    // Broadcast so the frontend re-fetches and shows the (unchanged) gate again instead of
    // staying stuck on the optimistic "Resuming research..." state.
    broadcastProgress(data.job_id, {
      stage: job?.gateStage ?? data.gate_stage ?? 0,
      name: 'Gate',
      status: 'completed',
    });

    console.log(
      `[Workers] Gate continuation failed for job ${data.job_id} (gate_stage=${data.gate_stage}), reverted to AWAITING_GATE: ${data.error_message}`
    );
    res.json({ status: 'ok' });
  } catch (error) {
    if (error instanceof z.ZodError) {
      res.status(400).json({ error: 'Validation error', details: error.errors });
      return;
    }
    console.error('[Workers] Gate failed error:', error);
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
