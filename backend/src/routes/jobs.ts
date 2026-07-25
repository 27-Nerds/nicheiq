import { Router, Request, Response } from 'express';
import { z } from 'zod';
import { getJob, getJobAsset, cancelJob } from '../services/jobService.js';
import { getDiscoveryDataForJob, getPreviewReportForJob } from '../services/assetService.js';
import { enqueueJob, enqueueLandingPageJob, enqueuePhase2Job, enqueueRegenerateJob, enqueueContinueFromGateJob, enqueueSeedIdeaJob, getQueueStats, getQueueLength } from '../services/queueService.js';
import {
  createJobAndChargeDiscovery,
  InsufficientCreditsError,
  PriceChangedError,
  refundForStage,
  chargeForStageInTx,
  chargeForStageWithPriceCasInTx,
  chargeForRegenerationInTx,
  refundForRegenerationStage,
  chargeForResume,
  segmentForGateContinue,
  chargeForSeedIdeaInTx,
  refundForSeedIdeaStage,
} from '../services/creditService.js';
import { prisma } from '../services/db.js';
import { CreateJobSchema, SelectSolutionSchema, SelectionDecisionProfileSchema, SelectionDraftUpdateSchema, GateActionSchema, GateG1PatchSchema, GateG2PatchSchema, SeedIdeaSchema } from '../types/job.js';
import { buildPatchEnvelope, buildReceiptContent, buildSeedEnvelope, buildSeedReceiptContent } from '../utils/ledgerEvents.js';
import { JobStatus, AssetType, StageStatus, DispatchKind, BillingModel, DispatchState, Prisma } from '@prisma/client';
import { openDispatch, settleDispatch } from '../services/dispatchService.js';
import { broadcastProgress } from '../services/progressBroadcastService.js';
import { CONFIG } from '../config.js';
import { existsSync, createReadStream, statSync } from 'fs';
import { readFile } from 'fs/promises';
import { requireInternalAuth, requireInternalService, verifyOwnership, AuthenticatedRequest } from '../middleware/auth.js';
import { requireDecisionToolsAccess } from '../middleware/featureAccess.js';
import { jobCreationLimiter } from '../middleware/rateLimit.js';
import { validateJobId } from '../middleware/validation.js';
import { formatJobResponse } from '../utils/jobFormatter.js';
import { candidateSnapshotSha256, ensureIdeaIdentities, ideaName } from '../utils/ideaIdentity.js';
import { currentSelectionDraft, selectionDraftDocument } from '../utils/selectionDraft.js';
import { IdeaSynthesisPatchSchema } from '../types/ideaSynthesis.js';
import { resolveAssetPath } from '../utils/assetPath.js';
import { hasAnalystAccess } from '../services/featureAccess.js';
import { parseCurrentFounderFitArtifact } from '../services/founderFitService.js';
import {
  findIdeaForExport,
  ideaExportFilename,
  renderIdeaMarkdown,
  serializeIdeaJson,
} from '../services/ideaExportService.js';

export const jobsRouter = Router();

function asJsonRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

async function settledSeedOutcome(jobId: string, sourceMessageId: string): Promise<string | null> {
  const receipts = await prisma.chatMessage.findMany({
    where: { jobId, gateStage: 5, role: 'receipt' },
    orderBy: { createdAt: 'desc' },
    take: 100,
    select: { patchJson: true },
  });
  for (const receipt of receipts) {
    const envelope = asJsonRecord(receipt.patchJson);
    if (
      envelope?.kind === 'ledger_event'
      && envelope.event === 'seed_settled'
      && envelope.sourceMessageId === sourceMessageId
      && typeof envelope.outcome === 'string'
    ) {
      return envelope.outcome;
    }
  }
  return null;
}

/**
 * POST /api/jobs
 * Create a new research job (requires authentication and sufficient credits)
 */
jobsRouter.post('/', requireInternalAuth, jobCreationLimiter, async (req: AuthenticatedRequest, res: Response) => {
  try {
    // Validate request body
    const input = CreateJobSchema.parse(req.body);

    // Use authenticated user's ID
    const userId = req.user!.id;

    // Guided research (Phase B) is paid-only — server-side coerce to false for
    // non-entitled users rather than 402ing the whole job-create request, so the
    // request degrades to a normal (non-guided) job instead of failing outright.
    const chatMode = input.chatMode ? await hasAnalystAccess(userId) : false;

    // Create job + charge discovery cost in atomic transaction
    const { job } = await createJobAndChargeDiscovery(
      userId,
      input.niche,
      input.allowedProjectTypes,
      'interactive',
      input.entryMode,
      input.ideaFocus,
      chatMode
    );

    // Open the dispatch BEFORE the queue message exists, so the worker that picks it up can be
    // matched against it. Without one, the initial run is the one path with no identity at all —
    // and a fresh job is precisely where a duplicate delivery can put two workers on the same run.
    const dispatchId = await prisma.$transaction((tx) =>
      openDispatch(tx, { jobId: job.id, kind: DispatchKind.CONTINUE })
    );

    // Enqueue job for Python worker
    await enqueueJob(job.id, input.niche, userId, input.allowedProjectTypes, false, 'interactive', input.entryMode, input.ideaFocus, chatMode, dispatchId);

    // Update status to QUEUED and set queuedAt timestamp
    await prisma.job.update({
      where: { id: job.id },
      data: {
        status: JobStatus.QUEUED,
        queuedAt: new Date(),
      }
    });

    // Return job info with status URL
    res.status(201).json({
      id: job.id,
      status: 'queued',
      statusUrl: `${CONFIG.baseUrl}/jobs/${job.id}`,
      message: 'Research job created. Check the status URL for progress.',
    });
  } catch (error) {
    // Handle insufficient credits error
    if (error instanceof InsufficientCreditsError) {
      res.status(402).json({
        error: 'Insufficient research credits',
        code: 'INSUFFICIENT_CREDITS',
        balance: error.currentBalance,
        required: error.required,
      });
      return;
    }

    if (error instanceof z.ZodError) {
      res.status(400).json({
        error: 'Validation error',
        details: error.errors,
      });
      return;
    }

    console.error('Failed to create job:', error);
    res.status(500).json({ error: 'Failed to create job' });
  }
});

/**
 * GET /api/jobs/:jobId
 * Get job status and progress (requires authentication and ownership)
 */
jobsRouter.get('/:jobId', requireInternalAuth, validateJobId, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const { jobId } = req.params;

    const job = await getJob(jobId);

    if (!job) {
      res.status(404).json({ error: 'Job not found' });
      return;
    }

    // Verify ownership — return 404 to avoid revealing job existence
    if (!verifyOwnership(req, job.userId)) {
      res.status(404).json({ error: 'Job not found' });
      return;
    }

    // Format response using shared helper
    res.json(formatJobResponse(job, {
      includeCreatedAt: true,
      includeProgress: true,
      includeProgressTimestamps: true,
      includeAssets: true,
      includeSolutionIdeas: true,
    }));
  } catch (error) {
    console.error('Failed to get job:', error);
    res.status(500).json({ error: 'Failed to get job status' });
  }
});

/**
 * GET /api/jobs/:jobId/reportjson
 * Download the research report JSON (requires authentication and ownership)
 */
jobsRouter.get('/:jobId/reportjson', requireInternalAuth, validateJobId, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const { jobId } = req.params;

    const job = await getJob(jobId);
    if (!job) {
      res.status(404).json({ error: 'Job not found' });
      return;
    }

    // Verify ownership — return 404 to avoid revealing job existence
    if (!verifyOwnership(req, job.userId)) {
      res.status(404).json({ error: 'Job not found' });
      return;
    }

    // Allow COMPLETED or RUNNING (if report asset exists for early access during landing page generation)
    if (job.status !== JobStatus.COMPLETED) {
      const reportAsset = await getJobAsset(jobId, AssetType.REPORT_JSON);
      if (!reportAsset) {
        res.status(400).json({ error: 'Report not ready yet' });
        return;
      }
    }

    const asset = await getJobAsset(jobId, AssetType.REPORT_JSON);
    const resolvedPath = asset ? resolveAssetPath(asset.filePath) : '';
    if (!asset || !existsSync(resolvedPath)) {
      res.status(404).json({ error: 'Report not found' });
      return;
    }

    const filename = `nicheiq_report_${jobId}.json`;
    res.setHeader('Content-Type', 'application/json');
    res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);

    const stat = statSync(resolvedPath);
    res.setHeader('Content-Length', stat.size);

    createReadStream(resolvedPath).pipe(res);
  } catch (error) {
    console.error('Failed to get report:', error);
    res.status(500).json({ error: 'Failed to download report' });
  }
});

/**
 * GET /api/jobs/:jobId/report-summary
 * Lightweight summary of the report for preview cards (~1KB vs full 100-200KB report)
 * Only available for COMPLETED jobs.
 */
const summaryCache = new Map<string, { data: object; ts: number }>();
const SUMMARY_CACHE_TTL = 10 * 60 * 1000; // 10 minutes
const SUMMARY_CACHE_MAX = 200;

jobsRouter.get('/:jobId/report-summary', requireInternalAuth, validateJobId, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const { jobId } = req.params;

    const job = await getJob(jobId);
    if (!job) {
      res.status(404).json({ error: 'Job not found' });
      return;
    }

    if (!verifyOwnership(req, job.userId)) {
      res.status(404).json({ error: 'Job not found' });
      return;
    }

    if (job.status !== JobStatus.COMPLETED) {
      res.status(400).json({ error: 'Report not ready yet' });
      return;
    }

    // Check cache
    const cached = summaryCache.get(jobId);
    if (cached && Date.now() - cached.ts < SUMMARY_CACHE_TTL) {
      res.json(cached.data);
      return;
    }

    const asset = await getJobAsset(jobId, AssetType.REPORT_JSON);
    const resolvedPath = asset ? resolveAssetPath(asset.filePath) : '';
    if (!asset || !existsSync(resolvedPath)) {
      res.status(404).json({ error: 'Report not found' });
      return;
    }

    const raw = await readFile(resolvedPath, 'utf-8');
    const report = JSON.parse(raw);

    const summary = {
      opportunity_score: report.market_analytics?.overall_opportunity_score ?? null,
      market_fit_score: report.executive_dashboard?.key_metrics?.market_fit_score ?? null,
      technical_feasibility_score: report.executive_dashboard?.key_metrics?.technical_feasibility_score ?? null,
      verdict: report.executive_dashboard?.go_no_go_verdict?.verdict ?? null,
      risk_level: report.executive_dashboard?.go_no_go_verdict?.risk_level ?? null,
      primary_concern: report.executive_dashboard?.go_no_go_verdict?.primary_concern ?? null,
      solution_name: report.executive_dashboard?.recommended_solution_snapshot?.name ?? null,
      solution_tagline: report.executive_dashboard?.recommended_solution_snapshot?.tagline ?? null,
      core_value_prop: report.executive_dashboard?.recommended_solution_snapshot?.core_value_prop ?? null,
      project_type: report.executive_dashboard?.recommended_solution_snapshot?.project_type ?? null,
      confidence_score: report.executive_dashboard?.confidence_score ?? null,
      total_keywords: report.executive_dashboard?.key_metrics?.total_keyword_count ?? null,
      total_search_volume: report.executive_dashboard?.key_metrics?.total_keyword_search_volume ?? null,
      competitor_count: report.executive_dashboard?.key_metrics?.primary_competitor_count ?? null,
      pain_points_found: report.executive_dashboard?.key_metrics?.high_priority_pain_points ?? null,
    };

    // Evict oldest entries if cache is full
    if (summaryCache.size >= SUMMARY_CACHE_MAX) {
      const oldest = [...summaryCache.entries()].sort((a, b) => a[1].ts - b[1].ts)[0];
      if (oldest) summaryCache.delete(oldest[0]);
    }
    summaryCache.set(jobId, { data: summary, ts: Date.now() });

    res.json(summary);
  } catch (error) {
    console.error('Failed to get report summary:', error);
    res.status(500).json({ error: 'Failed to get report summary' });
  }
});

/**
 * GET /api/jobs/:jobId/discovery-data
 * Materialized discovery evidence (quotes, audience, influencers) for frontend trust UI.
 * Available after Phase 1 completes (AWAITING_SELECTION and beyond).
 */
jobsRouter.get('/:jobId/discovery-data', requireInternalAuth, validateJobId, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const { jobId } = req.params;

    const job = await getJob(jobId);
    if (!job) {
      res.status(404).json({ error: 'Job not found' });
      return;
    }

    if (!verifyOwnership(req, job.userId)) {
      res.status(404).json({ error: 'Job not found' });
      return;
    }

    // Available after discovery phase completes
    const allowedStatuses: JobStatus[] = [
      JobStatus.AWAITING_SELECTION,
      JobStatus.REGENERATING,
      JobStatus.RUNNING_PHASE2,
      JobStatus.COMPLETED,
      JobStatus.FAILED,
    ];
    if (!allowedStatuses.includes(job.status as JobStatus)) {
      res.status(400).json({ error: 'Discovery data not yet available' });
      return;
    }

    const data = await getDiscoveryDataForJob(jobId);
    if (!data) {
      res.status(404).json({ error: 'Discovery data not available for this job' });
      return;
    }

    res.json(data);
  } catch (error) {
    console.error('Failed to get discovery data:', error);
    res.status(500).json({ error: 'Failed to load discovery data' });
  }
});

/**
 * GET /api/jobs/:jobId/preview-report
 * Phase 1 preview report (lightweight summary for the selection screen).
 * Available after Phase 1 completes (AWAITING_SELECTION and beyond).
 */
jobsRouter.get('/:jobId/preview-report', requireInternalAuth, validateJobId, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const { jobId } = req.params;

    const job = await getJob(jobId);
    if (!job) {
      res.status(404).json({ error: 'Job not found' });
      return;
    }

    if (!verifyOwnership(req, job.userId)) {
      res.status(404).json({ error: 'Job not found' });
      return;
    }

    // Available after discovery phase completes
    const allowedStatuses: JobStatus[] = [
      JobStatus.AWAITING_SELECTION,
      JobStatus.REGENERATING,
      JobStatus.RUNNING_PHASE2,
      JobStatus.COMPLETED,
    ];
    if (!allowedStatuses.includes(job.status as JobStatus)) {
      res.status(400).json({ error: 'Preview report not yet available' });
      return;
    }

    const data = await getPreviewReportForJob(jobId);
    if (!data) {
      res.status(404).json({ error: 'Preview report not available for this job' });
      return;
    }

    res.json(data);
  } catch (error) {
    console.error('Failed to get preview report:', error);
    res.status(500).json({ error: 'Failed to load preview report' });
  }
});

/**
 * GET /api/jobs/:jobId/landingpage
 * View or download the landing page HTML (requires authentication and ownership)
 */
jobsRouter.get('/:jobId/landingpage', requireInternalAuth, validateJobId, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const { jobId } = req.params;

    const job = await getJob(jobId);
    if (!job) {
      res.status(404).json({ error: 'Job not found' });
      return;
    }

    // Verify ownership — return 404 to avoid revealing job existence
    if (!verifyOwnership(req, job.userId)) {
      res.status(404).json({ error: 'Job not found' });
      return;
    }

    if (job.status !== JobStatus.COMPLETED) {
      res.status(400).json({ error: 'Job not completed yet' });
      return;
    }

    const asset = await getJobAsset(jobId, AssetType.LANDING_PAGE);
    const resolvedPath = asset ? resolveAssetPath(asset.filePath) : '';
    if (!asset || !existsSync(resolvedPath)) {
      res.status(404).json({ error: 'Landing page not found' });
      return;
    }

    // Check if download is requested
    const download = req.query.download === 'true';

    if (download) {
      const filename = `landing_page_${jobId}.html`;
      res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
    }

    res.setHeader('Content-Type', 'text/html');

    const stat = statSync(resolvedPath);
    res.setHeader('Content-Length', stat.size);

    createReadStream(resolvedPath).pipe(res);
  } catch (error) {
    console.error('Failed to get landing page:', error);
    res.status(500).json({ error: 'Failed to get landing page' });
  }
});

/**
 * DELETE /api/jobs/:jobId
 * Cancel a pending or running job (requires authentication and ownership)
 */
jobsRouter.delete('/:jobId', requireInternalAuth, validateJobId, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const { jobId } = req.params;

    const job = await getJob(jobId);
    if (!job) {
      res.status(404).json({ error: 'Job not found' });
      return;
    }

    // Verify ownership — return 404 to avoid revealing job existence
    if (!verifyOwnership(req, job.userId)) {
      res.status(404).json({ error: 'Job not found' });
      return;
    }

    const outcome = await cancelJob(jobId);
    if (!outcome.cancelled) {
      if (outcome.reason === 'not_found') {
        res.status(404).json({ error: 'Job not found' });
        return;
      }
      const msg = outcome.status === JobStatus.COMPLETED ? 'Cannot cancel a completed job'
        : outcome.status === JobStatus.CANCELLED ? 'Job already cancelled'
        : 'Cannot cancel job after solution selection';
      res.status(400).json({ error: msg });
      return;
    }

    res.json({ message: 'Job cancelled' });
  } catch (error) {
    console.error('Failed to cancel job:', error);
    res.status(500).json({ error: 'Failed to cancel job' });
  }
});

/**
 * POST /api/jobs/:jobId/cancel
 * Cancel a queued or running job with credit refund (requires authentication and ownership)
 * This endpoint is preferred for user-initiated cancellations as it handles credit refunds
 */
jobsRouter.post('/:jobId/cancel', requireInternalAuth, validateJobId, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const { jobId } = req.params;
    const userId = req.user!.id;

    const job = await prisma.job.findFirst({
      where: { id: jobId, userId },
    });

    if (!job) {
      res.status(404).json({ error: 'Job not found' });
      return;
    }

    const outcome = await cancelJob(jobId);
    if (!outcome.cancelled) {
      if (outcome.reason === 'not_found') {
        res.status(404).json({ error: 'Job not found' });
        return;
      }
      res.status(400).json({
        error: outcome.status === JobStatus.COMPLETED || outcome.status === JobStatus.FAILED || outcome.status === JobStatus.CANCELLED
          ? 'Job already finished'
          : 'Cannot cancel job after solution selection',
        status: outcome.status,
      });
      return;
    }

    if (outcome.creditRefunded) {
      console.log(`[Jobs] Job ${jobId} cancelled by user ${userId}, ${outcome.creditRefunded} credits refunded`);
    }

    res.json({
      status: 'cancelled',
      message: outcome.creditRefunded ? 'Job cancelled and credit refunded' : 'Job cancelled',
      creditRefunded: outcome.creditRefunded,
    });
  } catch (error) {
    console.error('Failed to cancel job:', error);
    res.status(500).json({ error: 'Failed to cancel job' });
  }
});

/**
 * POST /api/jobs/:jobId/resume
 * Resume a failed job from checkpoint (requires authentication and ownership)
 * No credit charge - user already paid for the original job
 */
jobsRouter.post('/:jobId/resume', requireInternalAuth, validateJobId, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const { jobId } = req.params;
    const userId = req.user!.id;

    // Get job and verify ownership
    const job = await prisma.job.findFirst({
      where: { id: jobId, userId },
    });

    if (!job) {
      res.status(404).json({ error: 'Job not found' });
      return;
    }

    // Only failed jobs can be resumed
    if (job.status !== JobStatus.FAILED) {
      res.status(400).json({
        error: 'Only failed jobs can be resumed',
        status: job.status,
      });
      return;
    }

    // Re-charge credits if the job was refunded
    let creditCharged = 0;
    try {
      const result = await chargeForResume(userId, jobId);
      creditCharged = result.amount;
      if (result.charged) {
        console.log(`[Jobs] Re-charged ${result.amount} credits for resuming job ${jobId}`);
      }
    } catch (error) {
      if (error instanceof InsufficientCreditsError) {
        res.status(402).json({
          error: 'Insufficient credits to resume job',
          code: 'INSUFFICIENT_CREDITS',
          balance: error.currentBalance,
          required: error.required,
        });
        return;
      }
      throw error;
    }

    // Reset job status to QUEUED
    await prisma.job.update({
      where: { id: jobId },
      data: {
        status: JobStatus.QUEUED,
        errorMessage: null,
        errorStage: null,
        queuedAt: new Date(),
      },
    });

    // A resume is a NEW attempt, so it needs a new dispatch. Without one, the job would still be
    // carrying the activeDispatchId of the run that just failed — nothing clears it — and every
    // callback from the resuming worker (which would send no id) would be rejected as stale. The
    // resume would appear to queue and then silently do nothing.
    const resumeDispatch = await prisma.$transaction((tx) =>
      openDispatch(tx, { jobId: job.id, kind: DispatchKind.CONTINUE })
    );

    // Interactive job that failed during Phase 2: re-enqueue as phase 2
    if (job.jobMode === 'interactive' && (job.selectedSolutions as string[])?.length > 0 && job.phase1CheckpointPath) {
      const selectedSolutions = job.selectedSolutions as string[];
      await enqueuePhase2Job(
        job.id,
        job.phase1CheckpointPath,
        selectedSolutions,
        job.selectionRationale || undefined,
        resumeDispatch,
      );
    } else {
      // Re-enqueue with resume flag
      // Full original inputs (infra review round 2): a failure BEFORE a usable checkpoint
      // previously lost entryMode/ideaFocus on resume — both now come from the Job row.
      await enqueueJob(
        job.id,
        job.niche,
        userId,
        job.allowedProjectTypes as string[] | undefined,
        true, // resume = true
        job.jobMode || undefined,
        job.entryMode || undefined,
        job.ideaFocus || undefined,
        undefined, // chatMode: unchanged on resume (read from the Job row by the worker)
        resumeDispatch
      );
    }

    console.log(`[Jobs] Job ${jobId} queued for resume by user ${userId}${creditCharged ? ' (credit charged)' : ''}`);

    res.json({
      message: creditCharged ? 'Job queued for resume (credit charged)' : 'Job queued for resume',
      jobId,
      status: 'queued',
      creditCharged,
    });
  } catch (error) {
    console.error('Failed to resume job:', error);
    res.status(500).json({ error: 'Failed to resume job' });
  }
});

/**
 * POST /api/jobs/:jobId/generate-landing
 * Generate a landing page for a completed job (on-demand, charged separately).
 */
jobsRouter.post('/:jobId/generate-landing', requireInternalAuth, jobCreationLimiter, validateJobId, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const { jobId } = req.params;
    const userId = req.user!.id;

    // Assigned inside the transaction below, alongside the charge and the status change.
    let landingDispatch: string | undefined;

    // Atomic transaction to prevent race conditions on double-click
    await prisma.$transaction(async (tx) => {
      const job = await tx.job.findFirst({
        where: { id: jobId, userId },
        include: { progress: true, assets: true },
      });

      if (!job) {
        throw new Error('Job not found');
      }

      if (job.status !== JobStatus.COMPLETED) {
        throw new Error('Job must be completed before generating a landing page');
      }

      // Guard: already has landing page or landing generation in progress
      const hasLanding = job.assets.some(a => a.assetType === AssetType.LANDING_PAGE);
      const landingInProgress = job.landingPageStatus === 'QUEUED' || job.landingPageStatus === 'RUNNING';
      if (hasLanding || landingInProgress) {
        throw new Error('Landing page already exists or is being generated');
      }

      // Check report asset exists
      const hasReport = job.assets.some(a => a.assetType === AssetType.REPORT_JSON);
      if (!hasReport) {
        throw new Error('Report not found');
      }

      // Charge for landing page generation
      await chargeForStageInTx(tx, userId, jobId, 'landing_page', job.niche);

      // Create or reset stage 15 progress entry (upsert handles retry after monitor-triggered failure)
      await tx.jobProgress.upsert({
        where: { jobId_stageNumber: { jobId, stageNumber: 15 } },
        create: { jobId, stageNumber: 15, stageName: 'Landing Page Generation', status: StageStatus.PENDING },
        update: { status: StageStatus.PENDING, errorMessage: null, startedAt: null, completedAt: null },
      });

      // Update job
      await tx.job.update({
        where: { id: jobId },
        data: {
          generateLandingPage: true,
          landingPageStatus: 'QUEUED',
          totalStages: { increment: 1 },
        },
      });

      // Same transaction as the charge and the status change — the dispatch is the durable record
      // that this attempt was authorized, so it must not be able to exist without them (or they
      // without it). Landing-page generation runs on an already-COMPLETED job that is still
      // carrying the activeDispatchId of the research run that produced it; this replaces it, so
      // the landing worker's callbacks are matched against ITS attempt and not that older one.
      landingDispatch = await openDispatch(tx, { jobId, kind: DispatchKind.CONTINUE });
    });

    // Get report asset path for the queue
    const reportAsset = await getJobAsset(jobId, AssetType.REPORT_JSON);
    if (!reportAsset) {
      res.status(500).json({ error: 'Report asset not found after transaction' });
      return;
    }

    // Enqueue landing page generation — compensating refund on failure
    try {
      await enqueueLandingPageJob(jobId, reportAsset.filePath, undefined, landingDispatch);
    } catch (enqueueError) {
      console.error(`[Jobs] Failed to enqueue landing page for job ${jobId}, compensating:`, enqueueError);
      await refundForStage(jobId, 'landing_page');
      await prisma.$transaction(async (tx) => {
        await tx.job.update({
          where: { id: jobId },
          data: { landingPageStatus: null, generateLandingPage: false, totalStages: { decrement: 1 } },
        });
        await tx.jobProgress.deleteMany({ where: { jobId, stageNumber: 15 } });
      });
      throw enqueueError;
    }

    res.json({ status: 'ok' });
  } catch (error) {
    if (error instanceof InsufficientCreditsError) {
      res.status(402).json({
        error: 'Insufficient credits for landing page generation',
        code: 'INSUFFICIENT_CREDITS',
        balance: error.currentBalance,
        required: error.required,
      });
      return;
    }
    if (error instanceof Error) {
      if (error.message === 'Job not found') {
        res.status(404).json({ error: error.message });
        return;
      }
      if (error.message.includes('already exists') || error.message.includes('must be completed') || error.message === 'Report not found') {
        res.status(400).json({ error: error.message });
        return;
      }
    }
    console.error('Failed to generate landing page:', error);
    res.status(500).json({ error: 'Failed to generate landing page' });
  }
});

/**
 * PATCH /api/jobs/:jobId/status
 * Update job status to RUNNING (internal only - called by Python worker)
 *
 * This endpoint is ONLY for the initial QUEUED -> RUNNING transition.
 * Stage updates are handled by POST /api/workers/progress.
 */
jobsRouter.patch('/:jobId/status', requireInternalService, validateJobId, async (req: Request, res: Response) => {
  try {
    const { jobId } = req.params;
    const { status } = req.body;

    // Validate job exists
    const job = await getJob(jobId);
    if (!job) {
      res.status(404).json({ error: 'Job not found' });
      return;
    }

    // Only RUNNING status is allowed
    if (status !== 'RUNNING') {
      res.status(400).json({ error: 'Invalid status. Only RUNNING is allowed.' });
      return;
    }

    // Only transition from QUEUED to RUNNING
    if (job.status !== JobStatus.QUEUED) {
      res.json({ id: job.id, status: job.status, currentStage: job.currentStage });
      return;
    }

    // Detect Phase 2 jobs (user has already selected solutions)
    const isPhase2 = job.selectedSolutions && job.selectedSolutions.length > 0;
    const runningStatus = isPhase2 ? JobStatus.RUNNING_PHASE2 : JobStatus.RUNNING;

    // Perform update
    const updatedJob = await prisma.job.update({
      where: { id: jobId },
      data: {
        status: runningStatus,
        startedAt: new Date(),
      },
    });

    console.log(`Job ${jobId} status updated to ${runningStatus} by worker`);

    res.json({ id: updatedJob.id, status: updatedJob.status, currentStage: updatedJob.currentStage });
  } catch (error) {
    console.error('Failed to update job status:', error);
    res.status(500).json({ error: 'Failed to update job status' });
  }
});

// ============================================
// Interactive Job Flow User Endpoints
// ============================================

/**
 * POST /api/jobs/:jobId/select-solution
 * User selects a solution for deep investigation (requires authentication and ownership)
 */
jobsRouter.post('/:jobId/select-solution', requireInternalAuth, validateJobId, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const { jobId } = req.params;
    const userId = req.user!.id;

    const input = SelectSolutionSchema.parse(req.body);

    const job = await prisma.job.findFirst({
      where: { id: jobId, userId },
      select: {
        status: true,
        selectedSolutions: true,
        phase1CheckpointPath: true,
        solutionIdeas: true,
        niche: true,
      },
    });

    if (!job) {
      res.status(404).json({ error: 'Job not found' });
      return;
    }

    // Reject if already selected
    if ((job.selectedSolutions as string[])?.length) {
      res.status(409).json({
        error: 'Deep Research has already started for this selection',
        code: 'DEEP_RESEARCH_ALREADY_STARTED',
        status: job.status,
      });
      return;
    }

    const solutions = ensureIdeaIdentities(jobId, job.solutionIdeas);
    const selectedById = input.solutionIds?.map(
      id => solutions.find(solution => solution.idea_id === id),
    );
    if (input.solutionIds && selectedById?.some(solution => !solution)) {
      const missing = input.solutionIds.filter(
        id => !solutions.some(solution => solution.idea_id === id),
      );
      res.status(400).json({ error: 'Selected solution(s) not found in available ideas', missing });
      return;
    }

    const resolvedNames = selectedById
      ? selectedById.map(solution => ideaName(solution!)).filter((name): name is string => !!name)
      : input.solutionNames ?? [];
    const resolvedIds = selectedById
      ? selectedById.map(solution => solution!.idea_id!)
      : resolvedNames.map(name => solutions.find(solution => ideaName(solution) === name)?.idea_id)
          .filter((id): id is string => !!id);

    const missingNames = resolvedNames.filter(
      name => !solutions.some(solution => ideaName(solution) === name),
    );
    if (missingNames.length > 0 || resolvedNames.length === 0) {
      res.status(400).json({ error: 'Selected solution(s) not found in available ideas', missing: missingNames });
      return;
    }
    if (input.solutionNames && input.solutionIds && (
      input.solutionNames.length !== resolvedNames.length
      || input.solutionNames.some((name, index) => name !== resolvedNames[index])
    )) {
      res.status(400).json({ error: 'solutionIds and solutionNames refer to different ideas' });
      return;
    }

    // Phase 2 still joins candidates by solution name. Two distinct identities with
    // the same normalized name would collapse in Python and make the winning identity
    // impossible to recover. Reject before charging rather than silently producing an
    // unresolved final recommendation.
    const normalizedNames = resolvedNames.map(name => name.trim().replace(/\s+/g, ' ').toLowerCase());
    if (new Set(normalizedNames).size !== normalizedNames.length) {
      res.status(409).json({
        error: 'Deep Research cannot compare two candidates with the same name yet. Choose one of them.',
        code: 'AMBIGUOUS_PHASE2_SELECTION',
      });
      return;
    }

    if (job.status !== JobStatus.AWAITING_SELECTION) {
      res.status(409).json({
        error: 'Job not in a state that accepts solution selection',
        code: 'DEEP_RESEARCH_NOT_AWAITING_SELECTION',
        status: job.status,
      });
      return;
    }

    // Worker is done — atomically transition to QUEUED and enqueue phase 2
    if (!job.phase1CheckpointPath) {
      res.status(500).json({ error: 'Missing checkpoint path for phase 2' });
      return;
    }

    const phase2Dispatch = await prisma.$transaction(async (tx) => {
      // Charge for deep research inside the transaction
      await chargeForStageInTx(tx, userId, jobId, 'deep_research', job!.niche);

      // Atomically update status
      const result = await tx.job.updateMany({
        where: {
          id: jobId,
          status: JobStatus.AWAITING_SELECTION,
          selectedSolutions: { equals: [] }, // Guard against double-selection race
        },
        data: {
          status: JobStatus.QUEUED,
          selectedSolutions: resolvedNames,
          selectedSolutionIds: resolvedIds,
          selectionRationale: input.rationale || null,
          queuedAt: new Date(),
        },
      });

      if (result.count === 0) {
        throw new Error('CONFLICT');
      }

      return openDispatch(tx, { jobId, kind: DispatchKind.CONTINUE });
    });

    // Enqueue phase 2 outside transaction - compensating refund on failure
    try {
      await enqueuePhase2Job(
        jobId,
        job.phase1CheckpointPath,
        resolvedNames,
        input.rationale,
        phase2Dispatch,
      );
    } catch (enqueueError) {
      // Compensate: refund deep_research charge and revert job status.
      //
      // GUARDED, not unconditional. An enqueue error is ambiguous — the message may have landed
      // and only the ack failed — so an unconditional update() here would stomp a worker that has
      // already flipped the job to RUNNING_PHASE2, refund its credit, and wipe selectedSolutions
      // (which that worker needs for its own phase-2 identity). Matching on our own dispatch means
      // we can only undo an attempt that genuinely never started.
      console.error(`[Jobs] Failed to enqueue phase 2 for job ${jobId}, compensating:`, enqueueError);
      const reverted = await prisma.job.updateMany({
        where: { id: jobId, status: JobStatus.QUEUED, activeDispatchId: phase2Dispatch },
        data: {
          status: JobStatus.AWAITING_SELECTION,
          selectedSolutions: [],
          selectedSolutionIds: [],
          selectionRationale: null,
          activeDispatchId: null,
        },
      });
      // Only give the credit back if we actually undid the selection. Refunding a job a worker is
      // busy running is how you end up doing paid work for free.
      if (reverted.count > 0) {
        await refundForStage(jobId, 'deep_research');
      } else {
        console.warn(
          `[Jobs] Phase-2 enqueue failed for job ${jobId} but the attempt is no longer QUEUED ` +
          'under this dispatch — a worker likely picked it up. Not refunding, not reverting.'
        );
      }
      throw enqueueError;
    }

    // Auto-deactivate discovery share after successful enqueue (fire-and-forget)
    prisma.discoveryShare.updateMany({
      where: { jobId, isActive: true },
      data: { isActive: false },
    }).catch(err => console.error('Failed to deactivate discovery share:', err));

    res.json({
      status: 'phase2_queued',
      message: 'Solution selected. Deep investigation is now queued.',
      selectedSolutionIds: resolvedIds,
    });
  } catch (error) {
    if (error instanceof InsufficientCreditsError) {
      res.status(402).json({
        error: 'Insufficient credits for deep research',
        code: 'INSUFFICIENT_CREDITS',
        balance: error.currentBalance,
        required: error.required,
      });
      return;
    }
    if (error instanceof Error && error.message === 'CONFLICT') {
      res.status(409).json({
        error: 'Deep Research was started by another request',
        code: 'DEEP_RESEARCH_START_CONFLICT',
      });
      return;
    }
    if (error instanceof z.ZodError) {
      res.status(400).json({ error: 'Validation error', details: error.errors });
      return;
    }
    console.error('Failed to select solution:', error);
    res.status(500).json({ error: 'Failed to select solution' });
  }
});

/**
 * POST /api/jobs/:jobId/regenerate-ideas
 * User requests regeneration of solution ideas (requires authentication and ownership)
 * Only allowed once per job, and only in AWAITING_SELECTION state.
 */
jobsRouter.post('/:jobId/regenerate-ideas', requireInternalAuth, validateJobId, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const { jobId } = req.params;
    const userId = req.user!.id;

    // Optional batch-scoped GTM-focus override for this regeneration (auto | novelty | distribution).
    // Allow-listed; anything else is ignored (worker falls back to the run's original focus).
    const allowedFocus = ['auto', 'novelty', 'distribution'];
    const ideaFocus = allowedFocus.includes(req.body?.idea_focus) ? req.body.idea_focus : undefined;

    const job = await prisma.job.findFirst({
      where: { id: jobId, userId },
      select: {
        status: true,
        ideasRegeneratedAt: true,
        regenerationCount: true,
        phase1CheckpointPath: true,
        solutionIdeas: true,
        niche: true,
      },
    });

    if (!job) {
      res.status(404).json({ error: 'Job not found' });
      return;
    }

    if (job.status !== JobStatus.AWAITING_SELECTION) {
      res.status(400).json({ error: 'Can only regenerate ideas when awaiting selection', status: job.status });
      return;
    }

    const MAX_REGENERATIONS = 10;
    if ((job.regenerationCount ?? 0) >= MAX_REGENERATIONS) {
      res.status(400).json({ error: `Maximum regenerations (${MAX_REGENERATIONS}) reached for this job` });
      return;
    }

    if (!job.phase1CheckpointPath) {
      res.status(500).json({ error: 'Missing checkpoint path for regeneration' });
      return;
    }

    // Get existing solution names to exclude
    const existingSolutionNames = ((job.solutionIdeas as any[]) || []).map(
      (s: any) => s.name || s.solution_name
    );

    const nextRegenNumber = (job.regenerationCount ?? 0) + 1;

    // Atomically update status + charge for regeneration
    const regenDispatch = await prisma.$transaction(async (tx) => {
      // Charge with numbered stage
      await chargeForRegenerationInTx(tx, userId, jobId, nextRegenNumber, job!.niche);

      // Optimistic lock on regenerationCount to prevent concurrent requests
      const result = await tx.job.updateMany({
        where: {
          id: jobId,
          status: JobStatus.AWAITING_SELECTION,
          regenerationCount: job.regenerationCount ?? 0,
        },
        data: {
          status: JobStatus.QUEUED,
          ideasRegeneratedAt: new Date(),
          regenerationCount: nextRegenNumber,
          queuedAt: new Date(),
          lastHeartbeat: null,
        },
      });

      if (result.count === 0) {
        throw new Error('CONFLICT');
      }

      // Regeneration needs its own identity too: its completion and failure callbacks correlate
      // on status plus a re-read regenerationCount, so a stale failure from regen-A could revert
      // regen-B and refund B's charge.
      return openDispatch(tx, { jobId, kind: DispatchKind.REGENERATE });
    });

    // Enqueue regeneration — compensating refund on failure
    try {
      await enqueueRegenerateJob(jobId, job.phase1CheckpointPath, existingSolutionNames, job.niche, ideaFocus, regenDispatch);
    } catch (enqueueError) {
      // Guarded for the same reason as phase 2: an ambiguous enqueue error must not let us stomp
      // a REGENERATING worker back to AWAITING_SELECTION and hand back a credit for work that is
      // actually running.
      console.error(`[Jobs] Failed to enqueue regeneration for job ${jobId}, compensating:`, enqueueError);
      const reverted = await prisma.job.updateMany({
        where: { id: jobId, status: JobStatus.QUEUED, activeDispatchId: regenDispatch },
        data: { status: JobStatus.AWAITING_SELECTION, queuedAt: null, activeDispatchId: null },
      });
      if (reverted.count > 0) {
        await refundForRegenerationStage(jobId, nextRegenNumber);
      } else {
        console.warn(
          `[Jobs] Regeneration enqueue failed for job ${jobId} but the attempt is no longer ` +
          'QUEUED under this dispatch — not refunding, not reverting.'
        );
      }
      throw enqueueError;
    }

    res.json({
      status: 'queued',
      message: 'Generating new solution ideas. Existing ideas will be preserved.',
    });
  } catch (error) {
    if (error instanceof InsufficientCreditsError) {
      res.status(402).json({
        error: 'Insufficient credits to regenerate ideas',
        code: 'INSUFFICIENT_CREDITS',
        balance: error.currentBalance,
        required: error.required,
      });
      return;
    }
    if (error instanceof Error && error.message === 'CONFLICT') {
      res.status(409).json({ error: 'Regeneration already in progress or completed' });
      return;
    }
    if ((error as any)?.code === 'P2002') {
      res.status(409).json({ error: 'Regeneration already in progress (duplicate charge)' });
      return;
    }
    console.error('Failed to regenerate ideas:', error);
    res.status(500).json({ error: 'Failed to regenerate ideas' });
  }
});

/**
 * POST /api/jobs/:jobId/seed-idea
 * User composes their own idea at selection chat (plans/eager-meandering-feather.md Phase 5).
 * Required free text + optional pain/tool references; runs the SAME birth + scoring path as a
 * pool idea and merges the result (active or demoted) into the pool. Paid — numbered
 * seed_idea_N, like regenerate_ideas_N, but reuses the DispatchKind.SEED_IDEA lifecycle
 * (openDispatch/settleDispatch) rather than regenerate-ideas' legacy status-field guard, and
 * REQUIRES a confirmed expectedCost (the seed card always shows a price up front).
 */
jobsRouter.post('/:jobId/seed-idea', requireInternalAuth, validateJobId, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const { jobId } = req.params;
    const userId = req.user!.id;
    const input = SeedIdeaSchema.parse(req.body);

    // Selection chat (and the seed it produces) is paid-only, same entitlement gate as guided
    // gate-action — re-checked here, not just at job-create, since a subscription can lapse.
    const entitled = await hasAnalystAccess(userId);
    if (!entitled) {
      res.status(402).json({
        error: 'Generating an idea from your own idea requires an active subscription',
        code: 'NOT_ENTITLED',
      });
      return;
    }

    const job = await prisma.job.findFirst({
      where: { id: jobId, userId },
      select: {
        status: true,
        seedIdeaCount: true,
        phase1CheckpointPath: true,
        niche: true,
        solutionIdeas: true,
        selectionDecisionProfile: true,
        selectionFounderFit: true,
      },
    });

    if (!job) {
      res.status(404).json({ error: 'Job not found' });
      return;
    }

    if (job.status !== JobStatus.AWAITING_SELECTION) {
      res.status(400).json({
        error: 'Can only generate an idea from your own idea while awaiting selection',
        status: job.status,
      });
      return;
    }

    if (!job.phase1CheckpointPath) {
      res.status(500).json({ error: 'Missing checkpoint path for seed idea' });
      return;
    }

    const priorOutcome = await settledSeedOutcome(jobId, input.sourceMessageId);
    if (priorOutcome) {
      res.json({
        status: 'settled',
        outcome: priorOutcome,
        message: 'This proposal has already been evaluated.',
      });
      return;
    }

    let seedText: string;
    let painRef: string | undefined;
    let toolRef: string | undefined;
    if (input.kind === 'idea_synthesis') {
      const sourceMessage = await prisma.chatMessage.findFirst({
        where: {
          id: input.sourceMessageId,
          jobId,
          gateStage: 5,
          role: 'assistant',
        },
        select: { patchJson: true },
      });
      const parsedProposal = IdeaSynthesisPatchSchema.safeParse(sourceMessage?.patchJson);
      if (!parsedProposal.success) {
        res.status(400).json({
          error: 'This synthesis proposal is missing or invalid. Ask the analyst to propose it again.',
          code: 'INVALID_SYNTHESIS_PROPOSAL',
        });
        return;
      }

      const currentIdeas = ensureIdeaIdentities(jobId, job.solutionIdeas);
      const fitRef = parsedProposal.data.evidence.founderFitRef;
      if (fitRef) {
        const currentFit = parseCurrentFounderFitArtifact(
          job.selectionFounderFit,
          job.selectionDecisionProfile,
          currentIdeas,
        );
        const currentResult = currentFit?.results.find((result) =>
          result.ideaId === fitRef.ideaId
          && result.ideaRevision === fitRef.ideaRevision
          && result.verdict === 'needs_reshape'
        );
        if (!currentFit || currentFit.inputFingerprint !== fitRef.inputFingerprint || !currentResult) {
          res.status(409).json({
            error: 'The founder profile or fit analysis changed after this proposal was created. Prepare a new reshape proposal.',
            code: 'STALE_FOUNDER_FIT_RESHAPE',
          });
          return;
        }
      }
      const staleParent = parsedProposal.data.parents.some((parent) => {
        const current = currentIdeas.find((idea) =>
          idea.idea_id === parent.ideaId
          && idea.idea_revision === parent.ideaRevision
        );
        const anchor = parsedProposal.data.evidence.sourceAnchors.find((candidate) =>
          candidate.ideaId === parent.ideaId
          && candidate.ideaRevision === parent.ideaRevision
        );
        return (
          !current ||
          !anchor ||
          ideaName(current) !== parent.solutionName ||
          candidateSnapshotSha256(current) !== anchor.candidateSnapshotSha256
        );
      });
      if (staleParent) {
        res.status(409).json({
          error: 'A source candidate changed after this proposal was created. Ask the analyst to rebuild it from the current candidates.',
          code: 'STALE_SYNTHESIS_SOURCE',
        });
        return;
      }

      const proposal = parsedProposal.data;
      seedText = [
        proposal.proposedTitle,
        proposal.proposedBrief,
        `Transformation: ${proposal.operation}. ${proposal.changeSummary}`,
        `Retain from sources: ${proposal.parents.map((parent) => `${parent.solutionName}: ${parent.contribution}`).join('; ')}`,
      ].join('\n\n');
      painRef = proposal.evidence.sourceAnchors.map((anchor) => anchor.pain).find(Boolean);
      toolRef = undefined;
    } else {
      seedText = input.free_text;
      painRef = input.pain_ref;
      toolRef = input.tool_ref;
    }

    const nextSeedOrdinal = (job.seedIdeaCount ?? 0) + 1;

    // Atomically update status + charge (required price CAS, INSIDE the transaction) + open
    // the dispatch this attempt's callbacks will be guarded against + write the durable
    // 'seed_submitted' receipt (continuous-analyst-ledger idiom — mirrors gate-action's
    // 'gate_patch_submitted' receipt) so the seed card survives a reload as "evaluating",
    // keyed on the SAME sourceMessageId the dispatch itself carries.
    const { dispatchId: seedDispatch, receiptId } = await prisma.$transaction(async (tx) => {
      const charge = await chargeForSeedIdeaInTx(
        tx, userId, jobId, nextSeedOrdinal, job.niche, input.expectedCost,
      );

      // Optimistic lock on seedIdeaCount, mirroring regenerate-ideas' regenerationCount CAS —
      // prevents a concurrent second seed request from reusing the same ordinal.
      const result = await tx.job.updateMany({
        where: {
          id: jobId,
          status: JobStatus.AWAITING_SELECTION,
          seedIdeaCount: job.seedIdeaCount ?? 0,
        },
        data: {
          status: JobStatus.QUEUED,
          seedIdeaCount: nextSeedOrdinal,
          queuedAt: new Date(),
          lastHeartbeat: null,
        },
      });

      if (result.count === 0) {
        throw new Error('CONFLICT');
      }

      const dispatchId = await openDispatch(tx, {
        jobId,
        kind: DispatchKind.SEED_IDEA,
        chargeId: charge.transaction?.id ?? null,
        seedOrdinal: nextSeedOrdinal,
        sourceMessageId: input.sourceMessageId,
      });

      const receipt = await tx.chatMessage.create({
        data: {
          jobId,
          gateStage: 5, // G3/AWAITING_SELECTION sentinel — Phase A/seed chat only ever writes 5
          role: 'receipt',
          content: buildSeedReceiptContent('seed_submitted'),
          patchJson: buildSeedEnvelope('seed_submitted', input.sourceMessageId) as unknown as object,
        },
        select: { id: true },
      });

      return { dispatchId, receiptId: receipt.id };
    });

    // Enqueue OUTSIDE the transaction — compensating refund + dispatch settle + receipt
    // retraction on failure (mirrors regenerate-ideas/gate-action, but this ALSO settles the
    // dispatch since it is never revisited otherwise: an ambiguous enqueue error must not
    // leave an AUTHORIZED dispatch dangling forever with a live CAS that nothing will settle).
    try {
      await enqueueSeedIdeaJob(
        jobId, job.phase1CheckpointPath, job.niche,
        seedText, painRef, toolRef, seedDispatch,
      );
    } catch (enqueueError) {
      console.error(`[Jobs] Failed to enqueue seed idea for job ${jobId}, compensating:`, enqueueError);
      const reverted = await prisma.$transaction(async (tx) => {
        const r = await tx.job.updateMany({
          where: { id: jobId, status: JobStatus.QUEUED, activeDispatchId: seedDispatch },
          data: { status: JobStatus.AWAITING_SELECTION, queuedAt: null, activeDispatchId: null },
        });
        if (r.count > 0) {
          await settleDispatch(tx, seedDispatch, DispatchState.FAILED, 'SYSTEM_FAULT');
        }
        return r.count;
      });
      if (reverted > 0) {
        await refundForSeedIdeaStage(jobId, nextSeedOrdinal);
        // The seed never got queued — retract the 'submitted' receipt, or the ledger would
        // claim an evaluation is in flight that never actually started.
        await prisma.chatMessage
          .delete({ where: { id: receiptId } })
          .catch((err) => console.error('[Jobs] Failed to retract seed-submitted receipt after compensation:', err));
      } else {
        console.warn(
          `[Jobs] Seed idea enqueue failed for job ${jobId} but the attempt is no longer ` +
          'QUEUED under this dispatch — not refunding, not reverting, not settling.'
        );
      }
      throw enqueueError;
    }

    res.json({
      status: 'queued',
      message: input.kind === 'idea_synthesis'
        ? 'Evaluating the proposed candidate variant.'
        : 'Generating an idea from your own idea.',
    });
  } catch (error) {
    if (error instanceof z.ZodError) {
      res.status(400).json({ error: 'Validation error', details: error.errors });
      return;
    }
    if (error instanceof InsufficientCreditsError) {
      res.status(402).json({
        error: 'Insufficient credits to generate an idea from your own idea',
        code: 'INSUFFICIENT_CREDITS',
        balance: error.currentBalance,
        required: error.required,
      });
      return;
    }
    if (error instanceof PriceChangedError) {
      res.status(409).json({
        error: 'The price changed. Refresh to see the current cost.',
        code: 'PRICE_CHANGED',
        expectedCost: error.expectedCost,
        actualCost: error.actualCost,
      });
      return;
    }
    if (error instanceof Error && error.message === 'CONFLICT') {
      res.status(409).json({ error: 'Another operation is already in progress for this job' });
      return;
    }
    if ((error as any)?.code === 'P2002') {
      res.status(409).json({ error: 'Seed idea already in progress (duplicate charge)' });
      return;
    }
    console.error('Failed to submit seed idea:', error);
    res.status(500).json({ error: 'Failed to submit seed idea' });
  }
});

/**
 * Cross-check a gate patch's referenced names/titles against the job's stored gateArtifact
 * (the last-delivered gate card data) — a fast 400 without a worker round-trip. G1 has no
 * artifact-derived whitelist beyond field SHAPE (already enforced by GateG1PatchSchema), so
 * this only does real work for G2. Mirrors src/nicheiq/flows/gate_patches.py's validation
 * (the worker re-validates authoritatively — this is defense in depth, not the only guard).
 */
function crossCheckGatePatch(
  gateStage: number,
  patch: Record<string, any>,
  gateArtifact: unknown
): string | null {
  if (gateStage !== 4) return null;

  const artifact = (gateArtifact as any) || {};
  const segmentNames = new Set<string>((artifact.segments || []).map((s: any) => s.segment_name));
  const painTitles = new Set<string>((artifact.pains || []).map((p: any) => p.title));

  if (patch.primary_target_segment && !segmentNames.has(patch.primary_target_segment)) {
    return `primary_target_segment "${patch.primary_target_segment}" does not match an existing audience segment`;
  }
  if (patch.excluded_segments) {
    const unknown = (patch.excluded_segments as string[]).filter(s => !segmentNames.has(s));
    if (unknown.length) return `excluded_segments references unknown segment(s): ${unknown.join(', ')}`;
  }
  if (patch.segment_emphasis) {
    const unknown = Object.keys(patch.segment_emphasis).filter(s => !segmentNames.has(s));
    if (unknown.length) return `segment_emphasis references unknown segment(s): ${unknown.join(', ')}`;
  }
  if (patch.pain_scope) {
    const excluded: string[] = patch.pain_scope.excluded_titles || [];
    const pinned: string[] = patch.pain_scope.pinned_titles || [];
    const unknown = [...excluded, ...pinned].filter(t => !painTitles.has(t));
    if (unknown.length) return `pain_scope references unknown pain title(s): ${unknown.join(', ')}`;
    const overlap = excluded.filter(t => pinned.includes(t));
    if (overlap.length) return `pain_scope cannot both exclude and pin the same title(s): ${overlap.join(', ')}`;
  }
  return null;
}

/**
 * POST /api/jobs/:jobId/gate-action
 * Continue past, or apply-and-stay at, a guided-mode (chatMode) G1 (post-Stage-1) / G2
 * (post-Stage-4) stage gate (requires authentication and ownership). No credit charge in v1.
 *
 * action='continue': optional patch applied, then the run advances to the NEXT stop.
 * action='apply_stay': REQUIRED patch applied, the SAME gate re-notifies with a refreshed
 *   artifact — capped at 5 applies per gate (Decisions SC3; a separate counter from the
 *   30-turn chat cap, since each apply re-runs a Stage-1 LLM call for G1).
 */
jobsRouter.post('/:jobId/gate-action', requireInternalAuth, validateJobId, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const { jobId } = req.params;
    const userId = req.user!.id;

    const input = GateActionSchema.parse(req.body);

    const job = await prisma.job.findFirst({
      where: { id: jobId, userId },
      select: {
        status: true,
        gateStage: true,
        gateArtifact: true,
        gateApplyCount: true,
        phase1CheckpointPath: true,
        // The billing contract this run was sold under. A job created before segment billing has
        // ALREADY paid for the whole discovery phase, so its Continue must charge nothing — read
        // the marker, never infer from chatMode.
        billingModel: true,
        niche: true,
      },
    });

    if (!job) {
      res.status(404).json({ error: 'Job not found' });
      return;
    }

    // Guided chat is paid-only; re-check entitlement here (not just at job-create) since a
    // subscription can lapse between job creation and reaching a gate — mirrors the chat
    // route's per-request 402 (chat.ts) rather than trusting a one-time chatMode flag.
    const entitled = await hasAnalystAccess(userId);
    if (!entitled) {
      res.status(402).json({ error: 'Guided research requires an active subscription', code: 'NOT_ENTITLED' });
      return;
    }

    // Gate-instance guard (Codex 11 — the selectedSolutions=[] analog): the request must
    // name the SAME gate the job is actually sitting at, protecting against a stale
    // browser tab acting on a gate the job has already moved past.
    if (job.status !== JobStatus.AWAITING_GATE || job.gateStage !== input.gateStage) {
      res.status(409).json({
        error: 'Job is not at the expected gate',
        status: job.status,
        gateStage: job.gateStage,
      });
      return;
    }

    if (input.action === 'apply_stay' && (job.gateApplyCount ?? 0) >= 5) {
      res.status(400).json({ error: 'Maximum gate patch applies (5) reached for this gate' });
      return;
    }

    let validatedPatch: Record<string, unknown> | undefined;
    if (input.patch) {
      const patchSchema = input.gateStage === 1 ? GateG1PatchSchema : GateG2PatchSchema;
      const parsed = patchSchema.safeParse(input.patch);
      if (!parsed.success) {
        res.status(400).json({ error: 'Invalid patch', details: parsed.error.errors });
        return;
      }
      const crossCheckError = crossCheckGatePatch(input.gateStage, parsed.data, job.gateArtifact);
      if (crossCheckError) {
        res.status(400).json({ error: crossCheckError });
        return;
      }
      validatedPatch = parsed.data;
    }

    if (!job.phase1CheckpointPath) {
      res.status(500).json({ error: 'Missing checkpoint path for gate continuation' });
      return;
    }

    // Atomic optimistic flip AWAITING_GATE -> QUEUED, guarding the GATE INSTANCE
    // (id + status + gateStage) so a stale/duplicate gate-action can't double-fire. Clears
    // gateReachedAt so a lost-response retry of a DIFFERENT prior call can't be misread by
    // /gate-reached's idempotency check as "still at this gate".
    // An apply_stay also writes a DURABLE receipt row (ledger Phase 2) in the same
    // transaction as the flip — phase one of two. It records what the user approved;
    // /gate-reached promotes it to 'applied' when the refreshed gate comes back, and
    // the compensation path below deletes it if the work never got queued. Without
    // this the applied change lived only in browser session state and vanished on
    // reload (taking the proposal card's terminal state with it).
    // What this Continue costs, and what it buys.
    //
    // apply_stay is FREE: it re-runs a stage the user has already paid for, and the 5-per-gate cap
    // is the control, not a price. Taxing steering would discourage the one behaviour the whole
    // checkpoint exists to enable.
    //
    // A Continue on a DISCOVERY_PREPAID_V1 job is also free — that run bought the entire discovery
    // phase at creation. Charging it here would bill those users twice.
    const segment =
      input.action === 'continue' && job.billingModel === BillingModel.GUIDED_SEGMENTS_V1
        ? segmentForGateContinue(input.gateStage)
        : null;

    // The price the user was shown must be the price they pay. A priced Continue REQUIRES the
    // confirmed price up front — the actual compare happens INSIDE the charging transaction
    // below (chargeForStageWithPriceCasInTx), against the price read in that same transaction,
    // so a reprice landing between this request and the charge can never slip through. Free
    // paths (apply_stay, any Continue on a DISCOVERY_PREPAID_V1 job) need no confirmation at all
    // — nothing is charged.
    if (segment && typeof input.expectedCost !== 'number') {
      res.status(400).json({ error: 'expectedCost is required to continue a priced segment' });
      return;
    }

    const flip = await prisma.$transaction(async (tx) => {
      // Charge INSIDE the flip. If the charge fails (insufficient credits, or the price CAS
      // below throws PriceChangedError) the whole transaction rolls back: no debit, no status
      // change, no queue message. The three cannot disagree.
      let chargeId: string | null = null;
      if (segment) {
        const charge = await chargeForStageWithPriceCasInTx(
          tx, userId, jobId, segment, segment, job.niche, input.expectedCost!,
        );
        chargeId = charge.transaction?.id ?? null;
      }

      const result = await tx.job.updateMany({
        where: { id: jobId, status: JobStatus.AWAITING_GATE, gateStage: input.gateStage },
        data: {
          status: JobStatus.QUEUED,
          queuedAt: new Date(),
          gateReachedAt: null,
          ...(input.action === 'apply_stay' ? { gateApplyCount: { increment: 1 } } : {}),
        },
      });
      if (result.count === 0) {
        return { count: 0, receiptId: null as string | null, dispatchId: null as string | null };
      }

      let receiptId: string | null = null;
      if (input.action === 'apply_stay' && validatedPatch) {
        const receipt = await tx.chatMessage.create({
          data: {
            jobId,
            gateStage: input.gateStage,
            role: 'receipt',
            content: buildReceiptContent(validatedPatch),
            patchJson: buildPatchEnvelope(
              'gate_patch_submitted',
              validatedPatch,
              input.sourceMessageId
            ) as unknown as object,
          },
          select: { id: true },
        });
        receiptId = receipt.id;
      }

      // The attempt, opened in the SAME transaction as the charge and the flip. This is what makes
      // every callback for this continuation addressable — and what tells a later failure WHICH
      // charge to give back. "Refund the latest charge" would be wrong: during a free apply_stay
      // the latest charge belongs to a segment that completed successfully.
      const dispatchId = await openDispatch(tx, {
        jobId,
        kind: input.action === 'apply_stay' ? DispatchKind.APPLY_STAY : DispatchKind.CONTINUE,
        gateStage: input.gateStage,
        segment,
        chargeId,
      });

      return { count: result.count, receiptId, dispatchId };
    });

    if (flip.count === 0) {
      res.status(409).json({ error: 'Gate action already in progress or the gate has changed' });
      return;
    }

    // Enqueue OUTSIDE the transaction — compensating revert on failure (mirrors
    // regenerate-ideas above).
    try {
      await enqueueContinueFromGateJob(jobId, job.phase1CheckpointPath, input.gateStage, input.action, validatedPatch, flip.dispatchId ?? undefined);
    } catch (enqueueError) {
      console.error(`[Jobs] Failed to enqueue gate continuation for job ${jobId}, compensating:`, enqueueError);
      // Codex review finding 7 (REGRESSION): an enqueue failure here is ambiguous — the
      // job could still be QUEUED (safe to revert), but it could also have already been
      // picked up by a worker and flipped to RUNNING (e.g. the enqueue actually landed and
      // only the client-side confirmation errored). Only revert if the job is STILL QUEUED;
      // an unconditional update() would stomp a legitimate RUNNING continuation back to
      // AWAITING_GATE out from under the worker.
      // Scoped to THIS attempt, not merely to "still QUEUED". Status alone has an ABA hole: if
      // the queue actually accepted our message and only the ack failed, the worker can run it,
      // re-arrive at the gate, and the user can start a NEW attempt — putting the job back at
      // QUEUED. A late catch here would then see QUEUED and revert somebody else's attempt.
      // Matching the dispatch id means we can only ever compensate our own.
      const reverted = await prisma.job.updateMany({
        where: {
          id: jobId,
          status: JobStatus.QUEUED,
          ...(flip.dispatchId ? { activeDispatchId: flip.dispatchId } : {}),
        },
        data: {
          status: JobStatus.AWAITING_GATE,
          gateStage: input.gateStage,
          gateReachedAt: new Date(),
          queuedAt: null,
          activeDispatchId: null,
          ...(input.action === 'apply_stay' ? { gateApplyCount: { decrement: 1 } } : {}),
        },
      });
      if (reverted.count === 0) {
        console.warn(
          `[Jobs] Gate continuation enqueue failed for job ${jobId} but it is no longer ` +
          'QUEUED under this dispatch — skipping compensation (a worker may have already ' +
          'started it, or a newer attempt has replaced it); leaving status as-is.'
        );
      } else {
        // The status/dispatch revert above undid the ATTEMPT, but on its own leaves the segment
        // charge (if any) committed with nothing to give it back, and the dispatch itself sitting
        // AUTHORIZED forever — a retry's own charge would then collide with this row's (job, type,
        // stage, cycle) and 500 with P2002 instead of queueing. Settle the dispatch and refund the
        // segment, mirroring seed-idea's compensation (refund + settle + receipt retraction) so a
        // retry is clean. A free apply_stay/Continue (DISCOVERY_PREPAID_V1, or gate 4->5) never had
        // a segment, so there is nothing to refund — only the dispatch needs settling.
        if (flip.dispatchId) {
          await prisma.jobDispatch.updateMany({
            where: { id: flip.dispatchId },
            data: { state: DispatchState.FAILED, failureKind: 'SYSTEM_FAULT', settledAt: new Date() },
          });
        }
        if (segment) {
          await refundForStage(jobId, segment);
        }
        if (flip.receiptId) {
          // The apply never got queued and the status was reverted — retract the
          // receipt too, or the ledger would claim a change that never happened.
          await prisma.chatMessage
            .delete({ where: { id: flip.receiptId } })
            .catch((err) => console.error('[Jobs] Failed to retract gate receipt after compensation:', err));
        }
      }
      throw enqueueError;
    }

    res.json({
      status: 'queued',
      message: input.action === 'apply_stay'
        ? 'Applying changes and refreshing this checkpoint.'
        : 'Continuing research.',
    });
  } catch (error) {
    if (error instanceof z.ZodError) {
      res.status(400).json({ error: 'Validation error', details: error.errors });
      return;
    }
    // Not enough credits to buy the next segment. The whole transaction rolled back, so the job is
    // still sitting at its gate, unchanged and un-charged — the user can top up and click again.
    // This is the point of charging at the checkpoint: they are standing right here when it
    // happens, instead of the run dying unattended at stage 3.
    if (error instanceof InsufficientCreditsError) {
      res.status(402).json({
        error: 'Not enough credits to continue',
        code: 'INSUFFICIENT_CREDITS',
        balance: error.currentBalance,
        required: error.required,
      });
      return;
    }
    // An admin re-priced the segment between the gate rendering and the click. The transaction
    // rolled back — nothing was charged — so the job is still sitting at its gate, unchanged.
    if (error instanceof PriceChangedError) {
      res.status(409).json({
        error: 'The price of this step changed. Refresh to see the current cost.',
        code: 'PRICE_CHANGED',
        expectedCost: error.expectedCost,
        actualCost: error.actualCost,
      });
      return;
    }
    console.error('Failed to process gate action:', error);
    res.status(500).json({ error: 'Failed to process gate action' });
  }
});

/**
 * PUT /api/jobs/:jobId/decision-profile
 * Persist the owner's selection constraints without changing research scores.
 */
jobsRouter.put('/:jobId/decision-profile', requireInternalAuth, requireDecisionToolsAccess, validateJobId, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const { jobId } = req.params;
    const userId = req.user!.id;
    const profile = SelectionDecisionProfileSchema.parse(req.body);

    const job = await prisma.job.findFirst({
      where: { id: jobId, userId },
      select: { status: true },
    });

    if (!job) {
      res.status(404).json({ error: 'Job not found' });
      return;
    }

    if (
      job.status !== JobStatus.AWAITING_SELECTION
      && job.status !== JobStatus.REGENERATING
    ) {
      res.status(409).json({ error: 'Decision profile is only editable during idea selection' });
      return;
    }

    const result = await prisma.job.updateMany({
      where: { id: jobId, userId, status: job.status },
      data: {
        selectionDecisionProfile: profile,
        selectionFounderFit: Prisma.JsonNull,
      },
    });

    if (result.count !== 1) {
      res.status(409).json({ error: 'The job changed while saving the decision profile' });
      return;
    }

    res.json({ selectionDecisionProfile: profile });
  } catch (error) {
    if (error instanceof z.ZodError) {
      res.status(400).json({ error: 'Validation error', details: error.errors });
      return;
    }
    console.error('Failed to save selection decision profile:', error);
    res.status(500).json({ error: 'Failed to save selection decision profile' });
  }
});

/**
 * PUT /api/jobs/:jobId/selection-draft
 * Persist the owner's editable, exact-revision shortlist without finalizing it.
 */
jobsRouter.put('/:jobId/selection-draft', requireInternalAuth, validateJobId, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const { jobId } = req.params;
    const userId = req.user!.id;
    const input = SelectionDraftUpdateSchema.parse(req.body);

    const job = await prisma.job.findFirst({
      where: { id: jobId, userId },
      select: {
        status: true,
        solutionIdeas: true,
        selectionDraft: true,
        selectionDraftVersion: true,
      },
    });

    if (!job) {
      res.status(404).json({ error: 'Job not found' });
      return;
    }

    if (job.status !== JobStatus.AWAITING_SELECTION) {
      res.status(409).json({
        error: 'The shortlist is only editable during idea selection',
        code: 'SELECTION_DRAFT_LOCKED',
        status: job.status,
      });
      return;
    }

    const ideas = ensureIdeaIdentities(jobId, job.solutionIdeas);
    const currentKeys = new Set(
      ideas.map(idea => `${idea.idea_id}:${idea.idea_revision}`),
    );
    const staleItems = input.items.filter(
      item => !currentKeys.has(`${item.ideaId}:${item.ideaRevision}`),
    );
    if (staleItems.length) {
      res.status(409).json({
        error: 'The candidate list changed. Refresh before editing the shortlist.',
        code: 'SELECTION_DRAFT_STALE_IDEA',
        selectionDraft: currentSelectionDraft(
          job.selectionDraft,
          job.selectionDraftVersion,
          ideas,
        ),
      });
      return;
    }

    const result = await prisma.job.updateMany({
      where: {
        id: jobId,
        userId,
        status: JobStatus.AWAITING_SELECTION,
        selectionDraftVersion: input.expectedVersion,
      },
      data: {
        selectionDraft: selectionDraftDocument(input.items) as Prisma.InputJsonValue,
        selectionDraftVersion: { increment: 1 },
      },
    });

    if (result.count !== 1) {
      const latest = await prisma.job.findFirst({
        where: { id: jobId, userId },
        select: {
          solutionIdeas: true,
          selectionDraft: true,
          selectionDraftVersion: true,
        },
      });
      const latestIdeas = latest ? ensureIdeaIdentities(jobId, latest.solutionIdeas) : [];
      res.status(409).json({
        error: 'The shortlist changed in another session. Refresh to reconcile it.',
        code: 'SELECTION_DRAFT_CONFLICT',
        selectionDraft: latest
          ? currentSelectionDraft(latest.selectionDraft, latest.selectionDraftVersion, latestIdeas)
          : currentSelectionDraft(job.selectionDraft, job.selectionDraftVersion, ideas),
      });
      return;
    }

    res.json({
      selectionDraft: {
        version: input.expectedVersion + 1,
        items: input.items,
      },
    });

    // Notify other open tabs via the job's SSE progress channel. The SSE
    // handler re-reads the job and sends the standard job payload, which
    // carries the new selectionDraft version, so a stale tab can refresh
    // before its next edit hits a 409. After res.json so the saving tab's own
    // response (which bumps its local version) usually lands first.
    try {
      broadcastProgress(jobId, {
        stage: 0,
        name: 'Selection Draft',
        status: 'completed',
      });
    } catch (broadcastErr) {
      console.error('Broadcast failed but selection draft was saved:', broadcastErr);
    }
  } catch (error) {
    if (error instanceof z.ZodError) {
      res.status(400).json({ error: 'Validation error', details: error.errors });
      return;
    }
    console.error('Failed to save selection draft:', error);
    res.status(500).json({ error: 'Failed to save shortlist' });
  }
});

/**
 * GET /api/jobs/:jobId/solutions
 * Get solution ideas for an interactive job (requires authentication and ownership)
 */
jobsRouter.get('/:jobId/solutions', requireInternalAuth, validateJobId, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const { jobId } = req.params;

    const job = await prisma.job.findFirst({
      where: { id: jobId, userId: req.user!.id },
      select: {
        solutionIdeas: true,
        selectedSolution: true,
        selectedSolutions: true,
        selectedSolutionIds: true,
        selectionRationale: true,
        selectionDecisionProfile: true,
        selectionDraft: true,
        selectionDraftVersion: true,
        ideasRegeneratedAt: true,
        status: true,
      },
    });

    if (!job) {
      res.status(404).json({ error: 'Job not found' });
      return;
    }

    const solutionIdeas = ensureIdeaIdentities(jobId, job.solutionIdeas);
    const selectedSolutions = job.selectedSolutions?.length ? job.selectedSolutions : null;
    const selectedSolutionIds = job.selectedSolutionIds?.length
      ? job.selectedSolutionIds
      : selectedSolutions?.map(
          name => solutionIdeas.find(solution => ideaName(solution) === name)?.idea_id,
        ).filter((id): id is string => !!id) ?? null;

    res.json({
      solutionIdeas,
      selectedSolution: job.selectedSolution,
      selectedSolutions,
      selectedSolutionIds,
      selectionRationale: job.selectionRationale,
      selectionDecisionProfile: job.selectionDecisionProfile,
      selectionDraft: currentSelectionDraft(
        job.selectionDraft,
        job.selectionDraftVersion,
        solutionIdeas,
      ),
      canRegenerate: true,
      status: job.status,
    });
  } catch (error) {
    console.error('Failed to get solutions:', error);
    res.status(500).json({ error: 'Failed to get solutions' });
  }
});

const IdeaExportParamsSchema = z.object({
  jobId: z.string().uuid(),
  ideaId: z.string().min(1),
  format: z.enum(['md', 'json']),
});

/**
 * GET /api/jobs/:jobId/solutions/:ideaId/export/:format?revision=N
 * Private download of one exact stored candidate (md or json). An explicit
 * revision must match exactly; without one the current revision is exported.
 */
jobsRouter.get('/:jobId/solutions/:ideaId/export/:format', requireInternalAuth, validateJobId, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const { jobId, ideaId, format } = IdeaExportParamsSchema.parse(req.params);
    let revision: number | undefined;
    if (req.query.revision !== undefined) {
      const parsed = z.coerce.number().int().positive().safeParse(req.query.revision);
      if (!parsed.success) {
        res.status(400).json({ error: 'Invalid candidate revision' });
        return;
      }
      revision = parsed.data;
    }

    const job = await prisma.job.findFirst({
      where: { id: jobId, userId: req.user!.id },
      select: { solutionIdeas: true },
    });
    if (!job) {
      res.status(404).json({ error: 'Job not found' });
      return;
    }

    const idea = findIdeaForExport(ensureIdeaIdentities(jobId, job.solutionIdeas), ideaId, revision);
    if (!idea) {
      res.status(404).json({ error: 'Candidate not found' });
      return;
    }

    res.setHeader('Cache-Control', 'private, no-store');
    res.setHeader('Content-Disposition', `attachment; filename="${ideaExportFilename(idea, format)}"`);
    if (format === 'md') {
      res.type('text/markdown').send(renderIdeaMarkdown(idea));
      return;
    }
    res.type('application/json').send(serializeIdeaJson(idea));
  } catch (error) {
    if (error instanceof z.ZodError) {
      res.status(400).json({ error: 'Invalid export reference' });
      return;
    }
    console.error('Failed to export idea:', error);
    res.status(500).json({ error: 'Failed to export idea' });
  }
});

/**
 * GET /api/jobs/:jobId/queue-position
 * Get queue position for a job (requires authentication and ownership)
 */
jobsRouter.get('/:jobId/queue-position', requireInternalAuth, validateJobId, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const { jobId } = req.params;

    const job = await getJob(jobId);
    if (!job) {
      res.status(404).json({ error: 'Job not found' });
      return;
    }

    // Verify ownership — return 404 to avoid revealing job existence
    if (!verifyOwnership(req, job.userId)) {
      res.status(404).json({ error: 'Job not found' });
      return;
    }

    // Only return position for QUEUED jobs
    if (job.status !== JobStatus.QUEUED) {
      const totalQueued = await getQueueLength();
      res.json({
        position: null,
        aheadCount: 0,
        totalQueued,
        status: job.status
      });
      return;
    }

    const stats = await getQueueStats(jobId);
    res.json({
      position: stats.position,
      aheadCount: stats.aheadCount,
      totalQueued: stats.totalQueued,
      status: job.status
    });
  } catch (error) {
    console.error('Failed to get queue position:', error);
    res.status(500).json({ error: 'Failed to get queue position' });
  }
});
