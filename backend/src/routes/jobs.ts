import { Router, Request, Response } from 'express';
import { z } from 'zod';
import { getJob, getJobAsset, cancelJob } from '../services/jobService.js';
import { getDiscoveryDataForJob, getPreviewReportForJob } from '../services/assetService.js';
import { enqueueJob, enqueueLandingPageJob, enqueuePhase2Job, enqueueContinueFromGateJob, enqueueSeedIdeaJob, getQueueStats, getQueueLength, deliverDispatchWork } from '../services/queueService.js';
import {
  createJobAndChargeDiscovery,
  InsufficientCreditsError,
  PriceChangedError,
  refundForStage,
  chargeForStageInTx,
  chargeForStageWithPriceCasInTx,
  chargeForRegenerationInTx,
  chargeForResume,
  segmentForGateContinue,
  chargeForSeedIdeaInTx,
  refundForSeedIdeaStage,
} from '../services/creditService.js';
import { prisma } from '../services/db.js';
import { CreateJobSchema, SelectSolutionSchema, RegenerateIdeasSchema, SelectionDecisionProfileSchema, SelectionDraftUpdateSchema, GateActionSchema, GateG1PatchSchema, GateG2PatchSchema, SeedIdeaSchema, MAX_IDEA_BATCHES } from '../types/job.js';
import {
  buildPatchEnvelope,
  buildReceiptContent,
  buildRegenerationEnvelope,
  buildRegenerationReceiptContent,
  buildSeedEnvelope,
  buildSeedReceiptContent,
} from '../utils/ledgerEvents.js';
import { JobStatus, AssetType, StageStatus, DispatchKind, BillingModel, DispatchState, Prisma } from '@prisma/client';
import { cancelAuthorizedSelectionDispatch, openDispatch, settleDispatch } from '../services/dispatchService.js';
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
import { canonicalJsonSha256 } from '../utils/canonicalFingerprint.js';
import { exactSelectionFingerprint, workerSelectionFingerprint } from '../utils/selectionFingerprint.js';
import { currentSelectionDraft, selectionDraftDocument } from '../utils/selectionDraft.js';
import { IdeaSynthesisPatchSchema, type IdeaSynthesisPatch } from '../types/ideaSynthesis.js';
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
    if (job.activeDispatchId) {
      const active = await prisma.jobDispatch.findUnique({
        where: { id: job.activeDispatchId },
        select: { kind: true, state: true },
      });
      if (
        active
        && (active.kind === DispatchKind.DEEP_RESEARCH || active.kind === DispatchKind.REGENERATE)
        && (active.state === DispatchState.AUTHORIZED || active.state === DispatchState.CLAIMED)
      ) {
        res.status(409).json({
          error: 'Cancel the active research operation explicitly',
          code: 'ACTIVE_OPERATION_REQUIRES_EXACT_CANCEL',
          operationId: job.activeDispatchId,
          operationState: active.state,
        });
        return;
      }
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

jobsRouter.post(
  '/:jobId/operations/:operationId/cancel',
  requireInternalAuth,
  validateJobId,
  async (req: AuthenticatedRequest, res: Response) => {
    const { jobId, operationId } = req.params;
    const owned = await prisma.job.findFirst({
      where: { id: jobId, userId: req.user!.id },
      select: { id: true },
    });
    if (!owned) {
      res.status(404).json({ error: 'Job not found' });
      return;
    }
    const outcome = await cancelAuthorizedSelectionDispatch(jobId, operationId);
    if (outcome === 'not_found') {
      res.status(404).json({ error: 'Operation not found' });
      return;
    }
    if (outcome === 'started') {
      res.status(409).json({
        error: 'This operation has already started and can no longer be cancelled',
        code: 'OPERATION_ALREADY_STARTED',
      });
      return;
    }
    if (outcome !== 'cancelled') {
      res.status(409).json({ error: 'This operation is no longer cancellable', code: 'STALE_OPERATION' });
      return;
    }
    const dispatch = await prisma.jobDispatch.findUnique({
      where: { id: operationId },
      select: { state: true, refundedAmount: true },
    });
    res.json({
      status: 'cancelled',
      operationId,
      operationState: dispatch?.state ?? DispatchState.CANCELLED,
      creditRefunded: dispatch?.refundedAmount ?? 0,
    });
  },
);

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
    const prior = await prisma.jobDispatch.findFirst({
      where: {
        jobId,
        clientRequestId: input.clientRequestId,
        job: { userId },
      },
      select: { id: true, state: true },
    });
    if (prior) {
      res.json({ status: 'phase2_queued', operationId: prior.id, operationState: prior.state, idempotent: true });
      return;
    }

    const phase2Dispatch = await prisma.$transaction(async (tx) => {
      const job = await tx.job.findFirst({
        where: { id: jobId, userId },
        select: {
          status: true,
          selectedSolutions: true,
          phase1CheckpointPath: true,
          solutionIdeas: true,
          niche: true,
          selectionDraft: true,
          selectionDraftVersion: true,
          activeDispatchId: true,
        },
      });
      if (!job) throw new Error('NOT_FOUND');
      if (job.status !== JobStatus.AWAITING_SELECTION || job.activeDispatchId) {
        throw new Error('DEEP_RESEARCH_START_CONFLICT');
      }
      if (job.selectedSolutions.length) throw new Error('DEEP_RESEARCH_ALREADY_STARTED');
      if (!job.phase1CheckpointPath) throw new Error('MISSING_PHASE1_CHECKPOINT');
      const solutions = ensureIdeaIdentities(jobId, job.solutionIdeas);
      const draft = currentSelectionDraft(job.selectionDraft, job.selectionDraftVersion, solutions);
      if (draft.items.length < 1 || draft.items.length > 3) {
        throw new Error('STALE_SELECTION_DRAFT');
      }

      const selected = draft.items.map((draftRef) => {
        const idea = solutions.find(candidate =>
          candidate.idea_id === draftRef.ideaId && candidate.idea_revision === draftRef.ideaRevision
        );
        if (!idea) {
          throw new Error('STALE_SOLUTION_REVISION');
        }
        const name = ideaName(idea);
        if (!name) throw new Error('INVALID_SOLUTION');
        const ref = {
          ...draftRef,
          snapshotSha256: candidateSnapshotSha256(idea),
        };
        return { ref, idea, name };
      });
      const selectedSolutionRefs = selected.map(item => item.ref);
      const publicSelectionFingerprint = exactSelectionFingerprint(selectedSolutionRefs);
      // The fingerprint is the authority. A draft version can advance and return to the same
      // ordered exact refs while a confirmation dialog is open; that is not a stale selection.
      if (publicSelectionFingerprint !== input.expectedSelectionFingerprint) {
        throw new Error('STALE_SELECTION_DRAFT');
      }
      const normalizedNames = selected.map(item => item.name.trim().replace(/\s+/g, ' ').toLowerCase());
      if (new Set(normalizedNames).size !== normalizedNames.length) {
        throw new Error('AMBIGUOUS_PHASE2_SELECTION');
      }

      const workerSelectionRefs = selected.map(item => ({
        idea_id: item.ref.ideaId,
        idea_revision: item.ref.ideaRevision,
        solution_name: item.name.trim().replace(/\s+/g, ' '),
      }));
      const workFingerprint = workerSelectionFingerprint(workerSelectionRefs);
      const requestSnapshot = {
        schemaVersion: 1,
        kind: 'deep_research',
        draftVersion: job.selectionDraftVersion,
        selectedSolutionRefs,
        selectedSolutionSnapshots: selected.map(item => item.idea),
        publicSelectionFingerprint,
        workerSelectionFingerprint: workFingerprint,
        rationale: input.rationale ?? null,
        expectedCost: input.expectedCost,
      };

      // Job first: worker claim and queued cancellation use the same first write.
      const flipped = await tx.job.updateMany({
        where: {
          id: jobId,
          status: JobStatus.AWAITING_SELECTION,
          activeDispatchId: null,
          selectedSolutions: { equals: [] },
          selectionDraftVersion: job.selectionDraftVersion,
        },
        data: {
          status: JobStatus.QUEUED,
          selectedSolutions: selected.map(item => item.name),
          selectedSolutionIds: selected.map(item => item.ref.ideaId),
          selectedSolutionRefs: selectedSolutionRefs as unknown as Prisma.InputJsonValue,
          selectionRationale: input.rationale ?? null,
          queuedAt: new Date(),
        },
      });
      if (flipped.count !== 1) throw new Error('DEEP_RESEARCH_START_CONFLICT');

      const charge = await chargeForStageWithPriceCasInTx(
        tx, userId, jobId, 'deep_research', 'deep_research', job.niche, input.expectedCost,
      );
      return openDispatch(tx, {
        jobId,
        kind: DispatchKind.DEEP_RESEARCH,
        segment: 'deep_research',
        chargeId: charge.transaction?.id ?? null,
        clientRequestId: input.clientRequestId,
        requestSnapshot: requestSnapshot as unknown as Prisma.InputJsonValue,
        requestFingerprint: publicSelectionFingerprint,
        workPayload: {
          job_id: jobId,
          checkpoint_path: job.phase1CheckpointPath,
          task_type: 'research_phase2',
          selected_solutions: selected.map(item => item.name),
          selected_solution: selected[0].name,
          selected_solution_refs: workerSelectionRefs,
          selected_solution_snapshots: selected.map(item => item.idea),
          selection_fingerprint: workFingerprint,
          selection_rationale: input.rationale ?? '',
          created_at: new Date().toISOString(),
        } as unknown as Prisma.InputJsonValue,
      });
    });

    let deliveryPending = false;
    try {
      await deliverDispatchWork(phase2Dispatch);
    } catch (deliveryError) {
      deliveryPending = true;
      console.error(`[Jobs] Phase-2 dispatch ${phase2Dispatch} delivery pending:`, deliveryError);
    }

    // Auto-deactivate discovery share after successful enqueue (fire-and-forget)
    prisma.discoveryShare.updateMany({
      where: { jobId, isActive: true },
      data: { isActive: false },
    }).catch(err => console.error('Failed to deactivate discovery share:', err));
    const queuedSelection = await prisma.job.findUnique({
      where: { id: jobId },
      select: { selectedSolutionRefs: true },
    });

    res.json({
      status: 'phase2_queued',
      message: 'Solution selected. Deep investigation is now queued.',
      operationId: phase2Dispatch,
      operationState: DispatchState.AUTHORIZED,
      deliveryPending,
      selectedSolutionRefs: queuedSelection?.selectedSolutionRefs ?? null,
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
    if (error instanceof PriceChangedError) {
      res.status(409).json({
        error: 'Deep Research price changed; review the updated price before continuing',
        code: 'PRICE_CHANGED',
        expectedCost: error.expectedCost,
        actualCost: error.actualCost,
      });
      return;
    }
    if (error instanceof Error && error.message === 'NOT_FOUND') return void res.status(404).json({ error: 'Job not found' });
    if (error instanceof Error && error.message === 'MISSING_PHASE1_CHECKPOINT') return void res.status(500).json({ error: 'Missing checkpoint path for phase 2' });
    if (error instanceof Error && [
      'DEEP_RESEARCH_START_CONFLICT',
      'DEEP_RESEARCH_ALREADY_STARTED',
      'STALE_SELECTION_DRAFT',
      'STALE_SOLUTION_REVISION',
      'AMBIGUOUS_PHASE2_SELECTION',
    ].includes(error.message)) {
      res.status(409).json({ error: 'The reviewed selection changed; reload before starting Deep Research', code: error.message });
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
    const input = RegenerateIdeasSchema.parse(req.body);
    const ideaFocus = input.idea_focus;

    const prior = await prisma.jobDispatch.findFirst({
      where: {
        jobId,
        clientRequestId: input.clientRequestId,
        job: { userId },
      },
      select: { id: true, state: true, batchOrdinal: true },
    });
    if (prior) {
      res.json({
        status: 'queued',
        operationId: prior.id,
        operationState: prior.state,
        batchOrdinal: prior.batchOrdinal,
        idempotent: true,
      });
      return;
    }

    const job = await prisma.job.findFirst({
      where: { id: jobId, userId },
      select: {
        status: true,
        ideasRegeneratedAt: true,
        regenerationCount: true,
        phase1CheckpointPath: true,
        solutionIdeas: true,
        niche: true,
        ideaBatchCompletedCount: true,
        activeDispatchId: true,
      },
    });

    if (!job) {
      res.status(404).json({ error: 'Job not found' });
      return;
    }

    if (job.status !== JobStatus.AWAITING_SELECTION) {
      res.status(400).json({ error: 'Can only add another idea batch while awaiting selection', status: job.status });
      return;
    }

    if ((job.ideaBatchCompletedCount ?? 0) >= MAX_IDEA_BATCHES) {
      res.status(400).json({ error: `Maximum additional idea batches (${MAX_IDEA_BATCHES}) reached for this job` });
      return;
    }

    if (!job.phase1CheckpointPath) {
      res.status(500).json({ error: 'Missing checkpoint path for the additional idea batch' });
      return;
    }

    // Get existing solution names to exclude
    const existingSolutions = ensureIdeaIdentities(jobId, job.solutionIdeas);
    const existingSolutionNames = existingSolutions.map(ideaName).filter((name): name is string => !!name);
    const baseCandidateRefs = existingSolutions.flatMap(solution =>
      typeof solution.idea_id === 'string' && typeof solution.idea_revision === 'number'
        ? [{
            ideaId: solution.idea_id,
            ideaRevision: solution.idea_revision,
            snapshotSha256: candidateSnapshotSha256(solution),
          }]
        : []
    );
    const basePoolFingerprint = canonicalJsonSha256(baseCandidateRefs);

    const nextRegenNumber = (job.regenerationCount ?? 0) + 1;

    // Atomically update status + charge for regeneration
    const regenDispatch = await prisma.$transaction(async (tx) => {
      // Job first: prevent a batch admission, Deep Research start, or worker claim from crossing.
      const result = await tx.job.updateMany({
        where: {
          id: jobId,
          status: JobStatus.AWAITING_SELECTION,
          regenerationCount: job.regenerationCount ?? 0,
          ideaBatchCompletedCount: job.ideaBatchCompletedCount ?? 0,
          activeDispatchId: null,
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
      const charge = await chargeForRegenerationInTx(
        tx, userId, jobId, nextRegenNumber, job!.niche, input.expectedCost,
      );

      // Regeneration needs its own identity too: every worker callback carries this dispatch id
      // and is CAS-guarded against Job.activeDispatchId. A stale callback from batch A therefore
      // cannot settle batch B or refund B's numbered charge.
      const dispatchId = await openDispatch(tx, {
        jobId,
        kind: DispatchKind.REGENERATE,
        segment: `regenerate_ideas_${nextRegenNumber}`,
        chargeId: charge.id,
        clientRequestId: input.clientRequestId,
        batchOrdinal: nextRegenNumber,
        requestSnapshot: {
          schemaVersion: 1,
          kind: 'idea_batch',
          ordinal: nextRegenNumber,
          focus: ideaFocus,
          baseCandidateRefs,
          basePoolFingerprint,
          expectedCost: input.expectedCost,
        } as unknown as Prisma.InputJsonValue,
        requestFingerprint: basePoolFingerprint,
        workPayload: {
          job_id: jobId,
          checkpoint_path: job.phase1CheckpointPath,
          existing_solution_names: existingSolutionNames,
          niche: job.niche,
          task_type: 'regenerate_ideas',
          idea_focus: ideaFocus,
          batch_ordinal: nextRegenNumber,
          base_candidate_refs: baseCandidateRefs.map(ref => ({
            idea_id: ref.ideaId,
            idea_revision: ref.ideaRevision,
            snapshot_sha256: ref.snapshotSha256,
          })),
          base_pool_fingerprint: basePoolFingerprint,
          created_at: new Date().toISOString(),
        } as unknown as Prisma.InputJsonValue,
      });
      await tx.chatMessage.create({
        data: {
          jobId,
          gateStage: 5,
          role: 'receipt',
          content: buildRegenerationReceiptContent('regeneration_submitted'),
          operationId: `regeneration:${dispatchId}:submitted`,
          patchJson: buildRegenerationEnvelope({
            event: 'regeneration_submitted',
            operationId: dispatchId,
            ordinal: nextRegenNumber,
            focus: ideaFocus,
          }) as unknown as object,
        },
      });
      return dispatchId;
    });

    // Ambiguous Redis errors leave the durable outbox AUTHORIZED for retry.
    let deliveryPending = false;
    try {
      await deliverDispatchWork(regenDispatch);
    } catch (deliveryError) {
      deliveryPending = true;
      console.error(`[Jobs] Idea-batch dispatch ${regenDispatch} delivery pending:`, deliveryError);
    }

    res.json({
      status: 'queued',
      operationId: regenDispatch,
      batchOrdinal: nextRegenNumber,
      focus: ideaFocus ?? 'auto',
      deliveryPending,
      message: 'Adding another idea batch. Existing candidates and the shortlist are unchanged.',
    });
  } catch (error) {
    if (error instanceof InsufficientCreditsError) {
      res.status(402).json({
        error: 'Insufficient credits to add another idea batch',
        code: 'INSUFFICIENT_CREDITS',
        balance: error.currentBalance,
        required: error.required,
      });
      return;
    }
    if (error instanceof PriceChangedError) {
      res.status(409).json({
        error: 'Idea batch price changed; review the updated price before continuing',
        code: 'PRICE_CHANGED',
        expectedCost: error.expectedCost,
        actualCost: error.actualCost,
      });
      return;
    }
    if (error instanceof Error && error.message === 'CONFLICT') {
      res.status(409).json({ error: 'Another idea batch is already in progress or was already admitted' });
      return;
    }
    if ((error as any)?.code === 'P2002') {
      res.status(409).json({ error: 'Another idea batch is already in progress (duplicate charge prevented)' });
      return;
    }
    if (error instanceof z.ZodError) {
      res.status(400).json({ error: 'Validation error', details: error.errors });
      return;
    }
    console.error('Failed to add another idea batch:', error);
    res.status(500).json({ error: 'Failed to add another idea batch' });
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
    let structuredSynthesis: IdeaSynthesisPatch | undefined;
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
      structuredSynthesis = proposal;
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
          patchJson: buildSeedEnvelope(
            'seed_submitted', input.sourceMessageId, undefined, undefined, dispatchId,
          ) as unknown as object,
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
        structuredSynthesis?.evaluation
          ? {
              evaluation_id: seedDispatch,
              dispatch_id: seedDispatch,
              source_message_id: input.sourceMessageId,
              proposal: structuredSynthesis,
            }
          : undefined,
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
      evaluationId: seedDispatch,
      dispatchId: seedDispatch,
      sourceMessageId: input.sourceMessageId,
      ...(structuredSynthesis ? { proposedTitle: structuredSynthesis.proposedTitle } : {}),
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
        selectionDecisionProfileVersion: { increment: 1 },
        selectionFounderFit: Prisma.JsonNull,
      },
    });

    if (result.count !== 1) {
      res.status(409).json({ error: 'The job changed while saving the decision profile' });
      return;
    }

    const updated = await prisma.job.findUnique({
      where: { id: jobId },
      select: { selectionDecisionProfileVersion: true },
    });
    res.json({
      selectionDecisionProfile: profile,
      selectionDecisionProfileVersion: updated?.selectionDecisionProfileVersion ?? 0,
    });
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
    const ideaByKey = new Map(
      ideas.map(idea => [
        `${idea.idea_id}:${idea.idea_revision}`,
        idea,
      ]),
    );
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
        selectionDraft: selectionDraftDocument(input.items.map(item => {
          const idea = ideaByKey.get(`${item.ideaId}:${item.ideaRevision}`);
          return {
            ...item,
            titleSnapshot: idea ? ideaName(idea) ?? 'Untitled candidate' : undefined,
          };
        })) as Prisma.InputJsonValue,
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
        selectedSolutionRefs: true,
        selectionRationale: true,
        selectionDecisionProfile: true,
        selectionDecisionProfileVersion: true,
        selectionDraft: true,
        selectionDraftVersion: true,
        ideasRegeneratedAt: true,
        regenerationCount: true,
        ideaBatchCompletedCount: true,
        activeDispatchId: true,
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
    const selectionDraft = currentSelectionDraft(
      job.selectionDraft,
      job.selectionDraftVersion,
      solutionIdeas,
    );
    const draftRefsWithSnapshots = selectionDraft.items.flatMap((item) => {
      const idea = solutionIdeas.find(candidate =>
        candidate.idea_id === item.ideaId && candidate.idea_revision === item.ideaRevision
      );
      return idea ? [{ ...item, snapshotSha256: candidateSnapshotSha256(idea) }] : [];
    });
    const selectionFingerprint = draftRefsWithSnapshots.length === selectionDraft.items.length
      ? exactSelectionFingerprint(draftRefsWithSnapshots)
      : null;
    const activeOperation = job.activeDispatchId
      ? await prisma.jobDispatch.findUnique({
          where: { id: job.activeDispatchId },
          select: {
            id: true,
            kind: true,
            state: true,
            batchOrdinal: true,
            createdAt: true,
            refundedAmount: true,
          },
        })
      : null;

    res.json({
      solutionIdeas,
      selectedSolution: job.selectedSolution,
      selectedSolutions,
      selectedSolutionIds,
      selectedSolutionRefs: job.selectedSolutionRefs,
      selectionRationale: job.selectionRationale,
      selectionDecisionProfile: job.selectionDecisionProfile,
      selectionDecisionProfileVersion: job.selectionDecisionProfileVersion,
      selectionDraft: {
        ...selectionDraft,
        selectionFingerprint,
      },
      canRegenerate: (job.ideaBatchCompletedCount ?? 0) < MAX_IDEA_BATCHES,
      ideaBatchCompletedCount: job.ideaBatchCompletedCount,
      activeOperation,
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
