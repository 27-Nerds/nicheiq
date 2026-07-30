import { Router, Request, Response } from 'express';
import { z } from 'zod';
import { getJob, getJobAsset, cancelJob } from '../services/jobService.js';
import { getDiscoveryDataForJob, getPreviewReportForJob } from '../services/assetService.js';
import { getQueueStats, getQueueLength, deliverDispatchWork } from '../services/queueService.js';
import {
  createJobAndChargeDiscoveryInTx,
  InsufficientCreditsError,
  PriceChangedError,
  chargeForStageWithPriceCasInTx,
  chargeForRegenerationInTx,
  chargeForResume,
  segmentForGateContinue,
  chargeForSeedIdeaInTx,
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
import { cancelAuthorizedSelectionDispatch, openDispatch } from '../services/dispatchService.js';
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

    // The new Job, the exact charge that bought this attempt, and its dispatch authorization are
    // one commit. A dispatch can therefore never exist without its charge (or vice versa).
    const { job, dispatchId } = await prisma.$transaction(async (tx) => {
      const created = await createJobAndChargeDiscoveryInTx(
        tx,
        userId,
        input.niche,
        input.allowedProjectTypes,
        'interactive',
        input.entryMode,
        input.ideaFocus,
        chatMode,
      );
      const dispatchId = await openDispatch(tx, {
        jobId: created.job.id,
        kind: DispatchKind.CONTINUE,
        segment: created.transaction?.stage ?? null,
        chargeId: created.transaction?.id ?? null,
        workPayload: {
          job_id: created.job.id,
          niche: input.niche,
          user_id: userId,
          allowed_project_types: input.allowedProjectTypes ?? null,
          resume: false,
          job_mode: 'interactive',
          entry_mode: input.entryMode ?? null,
          idea_focus: input.ideaFocus || 'auto',
          chat_mode: chatMode,
          created_at: new Date().toISOString(),
        },
      });
      await tx.job.update({
        where: { id: created.job.id },
        data: { status: JobStatus.QUEUED, queuedAt: new Date() },
      });
      return { job: created.job, dispatchId };
    });

    let deliveryPending = false;
    try {
      await deliverDispatchWork(dispatchId);
    } catch (deliveryError) {
      deliveryPending = true;
      console.error(`[Jobs] Initial dispatch ${dispatchId} delivery pending:`, deliveryError);
    }

    // Return job info with status URL
    res.status(201).json({
      id: job.id,
      status: 'queued',
      statusUrl: `${CONFIG.baseUrl}/jobs/${job.id}`,
      message: 'Research job created. Check the status URL for progress.',
      operationId: dispatchId,
      deliveryPending,
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

    // Available after discovery phase completes. CANCELLED belongs here alongside FAILED
    // and for the same reason — cancelling Deep Research does not un-write Phase 1.
    const allowedStatuses: JobStatus[] = [
      JobStatus.AWAITING_SELECTION,
      JobStatus.REGENERATING,
      JobStatus.RUNNING_PHASE2,
      JobStatus.COMPLETED,
      JobStatus.FAILED,
      JobStatus.CANCELLED,
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

    // Available once discovery has WRITTEN it — which is a fact about the artifact, not
    // about the job still being alive. FAILED/CANCELLED are included for the same reason
    // discovery-data includes them: a run that stopped after Phase 1 still owns (and the
    // owner still paid for) everything Phase 1 produced. Omitting them here 400'd the
    // stopped-run page into a permanent "dossier could not be loaded" banner.
    // A genuinely absent report is the 404 below, which the client treats as "no dossier"
    // rather than as a failure.
    const allowedStatuses: JobStatus[] = [
      JobStatus.AWAITING_SELECTION,
      JobStatus.REGENERATING,
      JobStatus.RUNNING_PHASE2,
      JobStatus.COMPLETED,
      JobStatus.FAILED,
      JobStatus.CANCELLED,
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
 * Resume a failed job (requires authentication and ownership).
 *
 * A failed Phase-2 attempt is not replayable from names alone. Reopen its preserved editable
 * draft at AWAITING_SELECTION so the user explicitly reconfirms and buys a fresh, fully stamped
 * dispatch. Legacy Discovery resumes still run, but their state flip, optional re-charge, and
 * durable dispatch are one transaction.
 */
jobsRouter.post('/:jobId/resume', requireInternalAuth, validateJobId, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const { jobId } = req.params;
    const userId = req.user!.id;
    const input = z.object({
      expectedCost: z.number().int().nonnegative().optional(),
    }).strict().parse(req.body ?? {});
    const outcome = await prisma.$transaction(async (tx) => {
      const job = await tx.job.findFirst({
        where: { id: jobId, userId },
      });
      if (!job) throw new Error('RESUME_NOT_FOUND');
      if (job.status !== JobStatus.FAILED) {
        throw new Error(`RESUME_NOT_FAILED:${job.status}`);
      }

      const isFailedPhase2 =
        job.jobMode === 'interactive'
        && job.entryMode !== 'deep_idea'
        && job.phase1CheckpointPath != null
        && (
          job.selectedSolutions.length > 0
          || (job.selectedSolutionIds?.length ?? 0) > 0
          || job.selectedSolutionRefs != null
        );

      if (isFailedPhase2) {
        const reopened = await tx.job.updateMany({
          where: {
            id: jobId,
            userId,
            status: JobStatus.FAILED,
            activeDispatchId: null,
          },
          data: {
            status: JobStatus.AWAITING_SELECTION,
            selectedSolution: null,
            selectedSolutions: [],
            selectedSolutionIds: [],
            selectedSolutionRefs: Prisma.DbNull,
            selectionRationale: null,
            errorMessage: null,
            errorStage: null,
            errorCode: null,
            errorDetails: Prisma.DbNull,
            stopReason: null,
            stopReasonDetails: Prisma.DbNull,
            queuedAt: null,
            awaitingSelectionAt: new Date(),
          },
        });
        if (reopened.count !== 1) throw new Error('RESUME_CONFLICT');
        return { mode: 'selection' as const };
      }

      // Job-first CAS: if charging or dispatch creation fails, this state flip rolls back with it.
      const flipped = await tx.job.updateMany({
        where: {
          id: jobId,
          userId,
          status: JobStatus.FAILED,
          activeDispatchId: null,
        },
        data: {
          status: JobStatus.QUEUED,
          errorMessage: null,
          errorStage: null,
          errorCode: null,
          errorDetails: Prisma.DbNull,
          stopReason: null,
          stopReasonDetails: Prisma.DbNull,
          queuedAt: new Date(),
        },
      });
      if (flipped.count !== 1) throw new Error('RESUME_CONFLICT');

      let dispatchKind: DispatchKind = DispatchKind.CONTINUE;
      let workPayload: Prisma.InputJsonValue = {
        job_id: jobId,
        niche: job.niche,
        user_id: userId,
        allowed_project_types: job.allowedProjectTypes ?? null,
        resume: true,
        job_mode: job.jobMode ?? null,
        entry_mode: job.entryMode ?? null,
        idea_focus: job.ideaFocus ?? 'auto',
        chat_mode: job.chatMode,
        created_at: new Date().toISOString(),
      } as unknown as Prisma.InputJsonValue;

      if (job.entryMode === 'deep_idea') {
        if (typeof input.expectedCost !== 'number') {
          throw new Error('RESUME_CATALOG_PRICE_REQUIRED');
        }
        const priorDispatch = await tx.jobDispatch.findFirst({
          where: { jobId, kind: DispatchKind.DEEP_RESEARCH },
          orderBy: { createdAt: 'desc' },
          select: { workPayload: true },
        });
        const priorPayload = priorDispatch?.workPayload;
        if (
          !priorPayload
          || Array.isArray(priorPayload)
          || typeof priorPayload !== 'object'
          || priorPayload.task_type !== 'catalog_deep_research'
          || !priorPayload.idea_seed
        ) {
          throw new Error('RESUME_CATALOG_PAYLOAD_MISSING');
        }
        dispatchKind = DispatchKind.DEEP_RESEARCH;
        workPayload = {
          ...priorPayload,
          job_id: jobId,
          user_id: userId,
          created_at: new Date().toISOString(),
        } as Prisma.InputJsonValue;
      }

      const charge = job.entryMode === 'deep_idea'
        ? await chargeForStageWithPriceCasInTx(
            tx,
            userId,
            jobId,
            'deep_research',
            'deep_research',
            job.niche,
            input.expectedCost!,
          )
        : await chargeForResume(userId, jobId, tx);
      const dispatchId = await openDispatch(tx, {
        jobId,
        kind: dispatchKind,
        segment: charge.transaction?.stage ?? null,
        chargeId: charge.transaction?.id ?? null,
        workPayload,
      });
      return {
        mode: 'queued' as const,
        dispatchId,
        creditCharged: 'cost' in charge ? charge.cost : charge.amount,
      };
    });

    if (outcome.mode === 'selection') {
      res.json({
        message: 'Your saved shortlist is ready to review and confirm again.',
        jobId,
        status: JobStatus.AWAITING_SELECTION,
        creditCharged: 0,
        requiresSelectionConfirmation: true,
      });
      return;
    }

    let deliveryPending = false;
    try {
      await deliverDispatchWork(outcome.dispatchId);
    } catch (deliveryError) {
      deliveryPending = true;
      console.error(`[Jobs] Resume dispatch ${outcome.dispatchId} delivery pending:`, deliveryError);
    }

    console.log(`[Jobs] Job ${jobId} queued for resume by user ${userId}${outcome.creditCharged ? ' (credit charged)' : ''}`);
    res.json({
      message: outcome.creditCharged ? 'Job queued for resume (credit charged)' : 'Job queued for resume',
      jobId,
      status: 'queued',
      creditCharged: outcome.creditCharged,
      operationId: outcome.dispatchId,
      operationState: DispatchState.AUTHORIZED,
      deliveryPending,
    });
  } catch (error) {
    if (error instanceof z.ZodError) {
      res.status(400).json({ error: 'Validation error', details: error.errors });
      return;
    }
    if (error instanceof InsufficientCreditsError) {
      res.status(402).json({
        error: 'Insufficient credits to resume job',
        code: 'INSUFFICIENT_CREDITS',
        balance: error.currentBalance,
        required: error.required,
      });
      return;
    }
    if (error instanceof PriceChangedError) {
      res.status(409).json({
        error: 'Deep Research price changed; review the updated price before retrying',
        code: 'PRICE_CHANGED',
        expectedCost: error.expectedCost,
        actualCost: error.actualCost,
      });
      return;
    }
    if (error instanceof Error && error.message === 'RESUME_NOT_FOUND') {
      res.status(404).json({ error: 'Job not found' });
      return;
    }
    if (error instanceof Error && error.message.startsWith('RESUME_NOT_FAILED:')) {
      res.status(400).json({
        error: 'Only failed jobs can be resumed',
        status: error.message.slice('RESUME_NOT_FAILED:'.length),
      });
      return;
    }
    if (error instanceof Error && error.message === 'RESUME_CONFLICT') {
      res.status(409).json({ error: 'This job changed before it could be resumed', code: 'RESUME_CONFLICT' });
      return;
    }
    if (error instanceof Error && error.message === 'RESUME_CATALOG_PAYLOAD_MISSING') {
      res.status(409).json({
        error: 'This catalog research retry cannot be reconstructed safely. Start a fresh research run from the catalog.',
        code: 'RESUME_CATALOG_PAYLOAD_MISSING',
      });
      return;
    }
    if (error instanceof Error && error.message === 'RESUME_CATALOG_PRICE_REQUIRED') {
      res.status(400).json({
        error: 'expectedCost is required to retry catalog Deep Research',
        code: 'EXPECTED_COST_REQUIRED',
      });
      return;
    }
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
    const input = z.object({
      expectedCost: z.number().int().nonnegative(),
    }).strict().parse(req.body);

    // Atomic transaction to prevent race conditions on double-click
    const landingDispatch = await prisma.$transaction(async (tx) => {
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
      const reportAsset = job.assets.find(a => a.assetType === AssetType.REPORT_JSON);
      if (!reportAsset) {
        throw new Error('Report not found');
      }

      // Charge for landing page generation
      const charge = await chargeForStageWithPriceCasInTx(
        tx,
        userId,
        jobId,
        'landing_page',
        'landing_page',
        job.niche,
        input.expectedCost,
      );

      // Create or reset stage 15 progress entry (upsert handles retry after monitor-triggered failure)
      const hasLandingProgress = job.progress.some(progress => progress.stageNumber === 15);
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
          ...(!hasLandingProgress ? { totalStages: { increment: 1 } } : {}),
        },
      });

      // Same transaction as the charge and the status change — the dispatch is the durable record
      // that this attempt was authorized, so it must not be able to exist without them (or they
      // without it). Landing-page generation runs on an already-COMPLETED job that is still
      // carrying the activeDispatchId of the research run that produced it; this replaces it, so
      // the landing worker's callbacks are matched against ITS attempt and not that older one.
      return openDispatch(tx, {
        jobId,
        kind: DispatchKind.CONTINUE,
        segment: 'landing_page',
        chargeId: charge.transaction?.id ?? null,
        workPayload: {
          job_id: jobId,
          report_path: reportAsset.filePath,
          page_mode: 'coming_soon',
          task_type: 'landing_page',
          created_at: new Date().toISOString(),
        },
      });
    });

    let deliveryPending = false;
    try {
      await deliverDispatchWork(landingDispatch);
    } catch (deliveryError) {
      deliveryPending = true;
      console.error(`[Jobs] Landing dispatch ${landingDispatch} delivery pending:`, deliveryError);
    }

    res.json({
      status: 'ok',
      operationId: landingDispatch,
      deliveryPending,
    });
  } catch (error) {
    if (error instanceof z.ZodError) {
      res.status(400).json({ error: 'Validation error', details: error.errors });
      return;
    }
    if (error instanceof InsufficientCreditsError) {
      res.status(402).json({
        error: 'Insufficient credits for landing page generation',
        code: 'INSUFFICIENT_CREDITS',
        balance: error.currentBalance,
        required: error.required,
      });
      return;
    }
    if (error instanceof PriceChangedError) {
      res.status(409).json({
        error: 'Landing page price changed; review the updated price before continuing',
        code: 'PRICE_CHANGED',
        expectedCost: error.expectedCost,
        actualCost: error.actualCost,
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
      const poolNameCounts = new Map<string, number>();
      for (const idea of solutions) {
        const poolName = ideaName(idea);
        if (!poolName) continue;
        const normalized = poolName.trim().replace(/\s+/g, ' ').toLowerCase();
        poolNameCounts.set(normalized, (poolNameCounts.get(normalized) ?? 0) + 1);
      }
      if (normalizedNames.some(name => (poolNameCounts.get(name) ?? 0) !== 1)) {
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
          // Identity is OURS: stamped at /api/workers/ideas-ready and seeded from the Phase-1
          // dispatch id, so it lives only in Postgres — the checkpoint on disk has no idea_id.
          // Without this map the worker falls back to its legacy_backfill scheme, derives
          // different ids for the same candidates, and every exact ref above fails to resolve.
          pool_identity_map: solutions.flatMap(idea => {
            const poolName = ideaName(idea);
            return poolName && typeof idea.idea_id === 'string' && typeof idea.idea_revision === 'number'
              ? [{
                  idea_id: idea.idea_id,
                  idea_revision: idea.idea_revision,
                  solution_name: poolName,
                }]
              : [];
          }),
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
          pool_identity_map: existingSolutions.flatMap(solution => {
            const poolName = ideaName(solution);
            return poolName
              && typeof solution.idea_id === 'string'
              && typeof solution.idea_revision === 'number'
              ? [{
                  idea_id: solution.idea_id,
                  idea_revision: solution.idea_revision,
                  solution_name: poolName,
                }]
              : [];
          }),
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
    const seedDispatch = await prisma.$transaction(async (tx) => {
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

      const synthesisEvaluation = structuredSynthesis?.evaluation
        ? {
            evaluation_id: dispatchId,
            dispatch_id: dispatchId,
            source_message_id: input.sourceMessageId,
            proposal: structuredSynthesis,
          }
        : null;
      await tx.jobDispatch.update({
        where: { id: dispatchId },
        data: {
          workPayload: {
            job_id: jobId,
            checkpoint_path: job.phase1CheckpointPath,
            niche: job.niche,
            seed_text: seedText,
            pain_ref: painRef ?? null,
            tool_ref: toolRef ?? null,
            synthesis_evaluation: synthesisEvaluation,
            task_type: 'seed_idea',
            created_at: new Date().toISOString(),
          } as unknown as Prisma.InputJsonValue,
        },
      });

      await tx.chatMessage.create({
        data: {
          jobId,
          gateStage: 5, // G3/AWAITING_SELECTION sentinel — Phase A/seed chat only ever writes 5
          role: 'receipt',
          content: buildSeedReceiptContent('seed_submitted'),
          patchJson: buildSeedEnvelope(
            'seed_submitted', input.sourceMessageId, undefined, undefined, dispatchId,
          ) as unknown as object,
        },
      });

      return dispatchId;
    });

    // Redis delivery is outside the authorization transaction. A transport failure is ambiguous:
    // the message may have landed, so keep the paid AUTHORIZED attempt and its receipt durable for
    // the outbox monitor to redeliver instead of refunding work that may already be running.
    let deliveryPending = false;
    try {
      await deliverDispatchWork(seedDispatch);
    } catch (deliveryError) {
      deliveryPending = true;
      console.error(`[Jobs] Seed dispatch ${seedDispatch} delivery pending:`, deliveryError);
    }

    res.json({
      status: 'queued',
      evaluationId: seedDispatch,
      dispatchId: seedDispatch,
      operationId: seedDispatch,
      sourceMessageId: input.sourceMessageId,
      deliveryPending,
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
        workPayload: {
          job_id: jobId,
          checkpoint_path: job.phase1CheckpointPath,
          gate_stage: input.gateStage,
          mode: input.action,
          ...(validatedPatch ? { patch: validatedPatch } : {}),
          task_type: 'continue_from_gate',
          created_at: new Date().toISOString(),
        } as unknown as Prisma.InputJsonValue,
      });

      return { count: result.count, receiptId, dispatchId };
    });

    if (flip.count === 0) {
      res.status(409).json({ error: 'Gate action already in progress or the gate has changed' });
      return;
    }

    // An ambiguous Redis error leaves the durable attempt AUTHORIZED. The delivery monitor retries
    // the immutable payload; reverting/refunding here could authorize free work if LPUSH succeeded.
    let deliveryPending = false;
    try {
      await deliverDispatchWork(flip.dispatchId!);
    } catch (deliveryError) {
      deliveryPending = true;
      console.error(`[Jobs] Gate dispatch ${flip.dispatchId} delivery pending:`, deliveryError);
    }

    res.json({
      status: 'queued',
      operationId: flip.dispatchId,
      deliveryPending,
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
