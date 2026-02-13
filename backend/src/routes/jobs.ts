import { Router, Request, Response } from 'express';
import { z } from 'zod';
import { getJob, updateJobStatus, getJobAsset } from '../services/jobService.js';
import { enqueueJob, enqueueLandingPageJob, enqueuePhase2Job, enqueueRegenerateJob, getQueueStats, getQueueLength } from '../services/queueService.js';
import { createJobWithCreditDeduction, InsufficientCreditsError, refundCreditsForJob } from '../services/creditService.js';
import { prisma } from '../services/db.js';
import { CreateJobSchema, SelectSolutionSchema } from '../types/job.js';
import { JobStatus, AssetType, CreditTransactionType, StageStatus } from '@prisma/client';
import { CONFIG } from '../config.js';
import { existsSync, createReadStream, statSync } from 'fs';
import { readFile } from 'fs/promises';
import { requireInternalAuth, requireInternalService, verifyOwnership, AuthenticatedRequest } from '../middleware/auth.js';
import { jobCreationLimiter } from '../middleware/rateLimit.js';
import { validateJobId } from '../middleware/validation.js';
import { formatJobResponse } from '../utils/jobFormatter.js';
import { resolveAssetPath } from '../utils/assetPath.js';

export const jobsRouter = Router();

/** Statuses from which a user may cancel — only pre-selection (Phase 1) */
const CANCELLABLE_STATUSES: JobStatus[] = [
  JobStatus.PENDING, JobStatus.QUEUED, JobStatus.RUNNING,
];

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

    // Create job with credit deduction in atomic transaction
    // This prevents race conditions and ensures credits are deducted BEFORE job creation
    const { job } = await createJobWithCreditDeduction(
      userId,
      input.niche,
      1, // Credit cost per job
      input.allowedProjectTypes,
      input.generateLandingPage,
      // TODO: jobMode is hardcoded to 'interactive' during feature rollout.
      // All new jobs use the interactive flow. Add jobMode to CreateJobSchema
      // when we need to support both auto and interactive modes.
      'interactive'
    );

    // Enqueue job for Python worker (email retrieved from DB when needed for notifications)
    await enqueueJob(job.id, input.niche, userId, input.allowedProjectTypes, false, input.generateLandingPage ?? false, 'interactive');

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

    if (!CANCELLABLE_STATUSES.includes(job.status as JobStatus)) {
      const msg = job.status === JobStatus.COMPLETED ? 'Cannot cancel a completed job'
        : job.status === JobStatus.CANCELLED ? 'Job already cancelled'
        : 'Cannot cancel job after solution selection';
      res.status(400).json({ error: msg });
      return;
    }

    await updateJobStatus(jobId, JobStatus.CANCELLED);

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

    // Check if job can be cancelled (only pre-selection statuses)
    if (!CANCELLABLE_STATUSES.includes(job.status)) {
      res.status(400).json({
        error: job.status === JobStatus.COMPLETED || job.status === JobStatus.FAILED || job.status === JobStatus.CANCELLED
          ? 'Job already finished'
          : 'Cannot cancel job after solution selection',
        status: job.status,
      });
      return;
    }

    // Update job status to CANCELLED
    await prisma.job.update({
      where: { id: jobId },
      data: {
        status: JobStatus.CANCELLED,
        errorMessage: 'Cancelled by user',
        completedAt: new Date(),
      },
    });

    // Mark any RUNNING stages as FAILED
    await prisma.jobProgress.updateMany({
      where: { jobId, status: StageStatus.RUNNING },
      data: {
        status: StageStatus.FAILED,
        errorMessage: 'Cancelled by user',
      },
    });

    // Refund credit to user using the credit service
    let creditRefunded = 0;
    try {
      const refund = await refundCreditsForJob(jobId, 1);
      if (refund) {
        creditRefunded = 1;
        console.log(`[Jobs] Job ${jobId} cancelled by user ${userId}, credit refunded`);
      }
    } catch (refundError) {
      // Log but don't fail the cancellation
      console.error(`[Jobs] Failed to refund credit for cancelled job ${jobId}:`, refundError);
    }

    res.json({
      status: 'cancelled',
      message: creditRefunded ? 'Job cancelled and credit refunded' : 'Job cancelled',
      creditRefunded,
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

    // Check if job was refunded - if so, we need to charge again
    const refundTransaction = await prisma.creditTransaction.findFirst({
      where: {
        relatedJobId: jobId,
        type: CreditTransactionType.REFUND,
      },
    });

    if (refundTransaction) {
      // Job was refunded, need to charge a credit to resume
      const credits = await prisma.userCredits.findUnique({
        where: { userId },
      });

      if (!credits || credits.balance < 1) {
        res.status(402).json({
          error: 'Insufficient credits to resume job',
          code: 'INSUFFICIENT_CREDITS',
          balance: credits?.balance ?? 0,
          required: 1,
        });
        return;
      }

      // Reverse the refund: delete transaction AND deduct from balance (atomic)
      await prisma.$transaction(async (tx) => {
        // 1. Delete the refund transaction record
        await tx.creditTransaction.delete({
          where: { id: refundTransaction.id },
        });

        // 2. Deduct credit from user's balance (reverses the refund amount)
        await tx.userCredits.update({
          where: { userId },
          data: {
            balance: { decrement: 1 },      // Take back the refunded credit
            totalUsed: { increment: 1 },    // Restore usage count
          },
        });
      });

      console.log(`[Jobs] Refund reversed for resuming job ${jobId} (balance decremented)`);
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

    // Interactive job that failed during Phase 2: re-enqueue as phase 2
    if (job.jobMode === 'interactive' && (job.selectedSolutions as string[])?.length > 0 && job.phase1CheckpointPath) {
      const selectedSolutions = job.selectedSolutions as string[];
      await enqueuePhase2Job(
        job.id,
        job.phase1CheckpointPath,
        selectedSolutions,
        job.selectionRationale || undefined,
        job.generateLandingPage
      );
    } else {
      // Re-enqueue with resume flag
      await enqueueJob(
        job.id,
        job.niche,
        userId,
        job.allowedProjectTypes as string[] | undefined,
        true, // resume = true
        job.generateLandingPage,
        job.jobMode || undefined
      );
    }

    const creditCharged = refundTransaction ? 1 : 0;
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
 * Generate a landing page for a completed job that skipped landing page generation.
 * No additional credit cost - user already paid for the research.
 */
jobsRouter.post('/:jobId/generate-landing', requireInternalAuth, jobCreationLimiter, validateJobId, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const { jobId } = req.params;
    const userId = req.user!.id;

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

      // Create stage 15 progress entry
      await tx.jobProgress.create({
        data: { jobId, stageNumber: 15, stageName: 'Landing Page Generation', status: StageStatus.PENDING },
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
    });

    // Get report asset path for the queue
    const reportAsset = await getJobAsset(jobId, AssetType.REPORT_JSON);
    if (!reportAsset) {
      res.status(500).json({ error: 'Report asset not found after transaction' });
      return;
    }

    // Enqueue landing page generation
    await enqueueLandingPageJob(jobId, reportAsset.filePath);

    res.json({ status: 'ok' });
  } catch (error) {
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
        generateLandingPage: true,
      },
    });

    if (!job) {
      res.status(404).json({ error: 'Job not found' });
      return;
    }

    // Reject if already selected
    if ((job.selectedSolutions as string[])?.length) {
      res.status(400).json({ error: 'Solution already selected' });
      return;
    }

    // Validate ALL selected solutions exist in solutionIdeas
    const solutions = (job.solutionIdeas as any[]) || [];
    const missingNames = input.solutionNames.filter(
      name => !solutions.some((s: any) => s.name === name || s.solution_name === name)
    );
    if (missingNames.length > 0) {
      res.status(400).json({ error: 'Selected solution(s) not found in available ideas', missing: missingNames });
      return;
    }

    if (job.status !== JobStatus.AWAITING_SELECTION) {
      res.status(400).json({
        error: 'Job not in a state that accepts solution selection',
        status: job.status,
      });
      return;
    }

    // Worker is done — atomically transition to QUEUED and enqueue phase 2
    if (!job.phase1CheckpointPath) {
      res.status(500).json({ error: 'Missing checkpoint path for phase 2' });
      return;
    }

    await prisma.$transaction(async (tx) => {
      // Atomically update status
      const result = await tx.job.updateMany({
        where: {
          id: jobId,
          status: JobStatus.AWAITING_SELECTION,
          selectedSolutions: { equals: [] }, // Guard against double-selection race
        },
        data: {
          status: JobStatus.QUEUED,
          selectedSolutions: input.solutionNames,
          selectionRationale: input.rationale || null,
          queuedAt: new Date(),
        },
      });

      if (result.count === 0) {
        throw new Error('CONFLICT');
      }
    });

    // Enqueue phase 2 outside transaction
    await enqueuePhase2Job(
      jobId,
      job.phase1CheckpointPath,
      input.solutionNames,
      input.rationale,
      job.generateLandingPage
    );

    res.json({
      status: 'phase2_queued',
      message: 'Solution selected. Deep investigation is now queued.',
    });
  } catch (error) {
    if (error instanceof Error && error.message === 'CONFLICT') {
      res.status(409).json({ error: 'Solution already selected by another request' });
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

    const job = await prisma.job.findFirst({
      where: { id: jobId, userId },
      select: {
        status: true,
        ideasRegeneratedAt: true,
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

    if (job.ideasRegeneratedAt !== null) {
      res.status(400).json({ error: 'Ideas can only be regenerated once per job' });
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

    // Atomically update status
    await prisma.$transaction(async (tx) => {
      const result = await tx.job.updateMany({
        where: {
          id: jobId,
          status: JobStatus.AWAITING_SELECTION,
          ideasRegeneratedAt: null,
        },
        data: {
          status: JobStatus.QUEUED,
          ideasRegeneratedAt: new Date(),
          queuedAt: new Date(),
          lastHeartbeat: null,        // Clear stale heartbeat from Phase 1; worker will send fresh ones
        },
      });

      if (result.count === 0) {
        throw new Error('CONFLICT');
      }
    });

    // Enqueue regeneration
    await enqueueRegenerateJob(jobId, job.phase1CheckpointPath, existingSolutionNames, job.niche);

    res.json({
      status: 'queued',
      message: 'Generating new solution ideas. Existing ideas will be preserved.',
    });
  } catch (error) {
    if (error instanceof Error && error.message === 'CONFLICT') {
      res.status(409).json({ error: 'Regeneration already in progress or completed' });
      return;
    }
    console.error('Failed to regenerate ideas:', error);
    res.status(500).json({ error: 'Failed to regenerate ideas' });
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
        selectionRationale: true,
        ideasRegeneratedAt: true,
        status: true,
      },
    });

    if (!job) {
      res.status(404).json({ error: 'Job not found' });
      return;
    }

    res.json({
      solutionIdeas: job.solutionIdeas || [],
      selectedSolution: job.selectedSolution,
      selectedSolutions: job.selectedSolutions?.length ? job.selectedSolutions : null,
      selectionRationale: job.selectionRationale,
      canRegenerate: job.ideasRegeneratedAt === null,
      status: job.status,
    });
  } catch (error) {
    console.error('Failed to get solutions:', error);
    res.status(500).json({ error: 'Failed to get solutions' });
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
