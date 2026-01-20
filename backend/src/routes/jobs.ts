import { Router, Request, Response } from 'express';
import { z } from 'zod';
import { getJob, updateJobStatus, getJobAsset } from '../services/jobService.js';
import { enqueueJob, getQueueStats, getQueueLength } from '../services/queueService.js';
import { createJobWithCreditDeduction, InsufficientCreditsError, refundCreditsForJob } from '../services/creditService.js';
import { prisma } from '../services/db.js';
import { CreateJobSchema } from '../types/job.js';
import { JobStatus, AssetType } from '@prisma/client';
import { CONFIG } from '../config.js';
import { existsSync, createReadStream, statSync } from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { requireInternalAuth, requireInternalService, verifyOwnership, AuthenticatedRequest } from '../middleware/auth.js';
import { jobCreationLimiter } from '../middleware/rateLimit.js';
import { formatJobResponse } from '../utils/jobFormatter.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/**
 * Resolve asset file path - handles both absolute (Docker) and relative (dev) paths
 */
function resolveAssetPath(filePath: string): string {
  if (path.isAbsolute(filePath)) {
    return filePath; // Docker: already absolute
  }
  // Dev: resolve relative to project root (parent of backend/)
  return path.resolve(__dirname, '../../../', filePath);
}

export const jobsRouter = Router();

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
      input.allowedProjectTypes
    );

    // Enqueue job for Python worker (email retrieved from DB when needed for notifications)
    await enqueueJob(job.id, input.niche, userId, input.allowedProjectTypes);

    // Update status to QUEUED and set queuedAt timestamp
    await prisma.job.update({
      where: { id: job.id },
      data: {
        status: JobStatus.QUEUED,
        queuedAt: new Date()
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
jobsRouter.get('/:jobId', requireInternalAuth, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const { jobId } = req.params;

    // Validate UUID format
    const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    if (!uuidRegex.test(jobId)) {
      res.status(400).json({ error: 'Invalid job ID format' });
      return;
    }

    const job = await getJob(jobId);

    if (!job) {
      res.status(404).json({ error: 'Job not found' });
      return;
    }

    // Verify ownership
    if (!verifyOwnership(req, job.userId)) {
      res.status(403).json({ error: 'Not authorized to view this job' });
      return;
    }

    // Format response using shared helper
    res.json(formatJobResponse(job, {
      includeCreatedAt: true,
      includeProgress: true,
      includeProgressTimestamps: true,
      includeAssets: true,
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
jobsRouter.get('/:jobId/reportjson', requireInternalAuth, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const { jobId } = req.params;

    const job = await getJob(jobId);
    if (!job) {
      res.status(404).json({ error: 'Job not found' });
      return;
    }

    // Verify ownership
    if (!verifyOwnership(req, job.userId)) {
      res.status(403).json({ error: 'Not authorized to access this report' });
      return;
    }

    if (job.status !== JobStatus.COMPLETED) {
      res.status(400).json({ error: 'Job not completed yet' });
      return;
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
 * GET /api/jobs/:jobId/landingpage
 * View or download the landing page HTML (requires authentication and ownership)
 */
jobsRouter.get('/:jobId/landingpage', requireInternalAuth, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const { jobId } = req.params;

    const job = await getJob(jobId);
    if (!job) {
      res.status(404).json({ error: 'Job not found' });
      return;
    }

    // Verify ownership
    if (!verifyOwnership(req, job.userId)) {
      res.status(403).json({ error: 'Not authorized to access this landing page' });
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
jobsRouter.delete('/:jobId', requireInternalAuth, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const { jobId } = req.params;

    const job = await getJob(jobId);
    if (!job) {
      res.status(404).json({ error: 'Job not found' });
      return;
    }

    // Verify ownership
    if (!verifyOwnership(req, job.userId)) {
      res.status(403).json({ error: 'Not authorized to cancel this job' });
      return;
    }

    if (job.status === JobStatus.COMPLETED) {
      res.status(400).json({ error: 'Cannot cancel a completed job' });
      return;
    }

    if (job.status === JobStatus.CANCELLED) {
      res.status(400).json({ error: 'Job already cancelled' });
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
jobsRouter.post('/:jobId/cancel', requireInternalAuth, async (req: AuthenticatedRequest, res: Response) => {
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

    // Check if job can be cancelled (only PENDING, QUEUED, RUNNING allowed)
    const cancellableStatuses: JobStatus[] = [JobStatus.PENDING, JobStatus.QUEUED, JobStatus.RUNNING];
    if (!cancellableStatuses.includes(job.status)) {
      res.status(400).json({
        error: 'Job already finished',
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
 * PATCH /api/jobs/:jobId/status
 * Update job status (internal only - called by Python worker)
 * Used to mark job as RUNNING when worker picks it up from queue
 */
jobsRouter.patch('/:jobId/status', requireInternalService, async (req: Request, res: Response) => {
  try {
    const { jobId } = req.params;
    const { status } = req.body;

    // Validate job exists
    const job = await getJob(jobId);
    if (!job) {
      res.status(404).json({ error: 'Job not found' });
      return;
    }

    // Only allow RUNNING status transition (from QUEUED)
    if (status !== 'RUNNING') {
      res.status(400).json({ error: 'Invalid status. Only RUNNING is allowed.' });
      return;
    }

    // Only transition from QUEUED to RUNNING
    if (job.status !== JobStatus.QUEUED) {
      // Job already transitioned, return current status (idempotent)
      res.json({ id: job.id, status: job.status });
      return;
    }

    const updatedJob = await updateJobStatus(jobId, JobStatus.RUNNING);
    console.log(`Job ${jobId} status updated to RUNNING by worker`);

    res.json({ id: updatedJob.id, status: updatedJob.status });
  } catch (error) {
    console.error('Failed to update job status:', error);
    res.status(500).json({ error: 'Failed to update job status' });
  }
});

/**
 * GET /api/jobs/:jobId/queue-position
 * Get queue position for a job (requires authentication and ownership)
 */
jobsRouter.get('/:jobId/queue-position', requireInternalAuth, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const { jobId } = req.params;

    const job = await getJob(jobId);
    if (!job) {
      res.status(404).json({ error: 'Job not found' });
      return;
    }

    // Verify ownership
    if (!verifyOwnership(req, job.userId)) {
      res.status(403).json({ error: 'Not authorized to view this job' });
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
