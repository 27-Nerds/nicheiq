import { Router, Request, Response } from 'express';
import { z } from 'zod';
import { createJob, getJob, updateJobStatus, getJobAsset } from '../services/jobService.js';
import { enqueueJob } from '../services/queueService.js';
import { CreateJobSchema } from '../types/job.js';
import { JobStatus, AssetType } from '@prisma/client';
import { CONFIG } from '../config.js';
import { existsSync, createReadStream, statSync } from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

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
 * Create a new research job
 */
jobsRouter.post('/', async (req: Request, res: Response) => {
  try {
    // Validate request body
    const input = CreateJobSchema.parse(req.body);

    // Create job in database
    const job = await createJob(input.email, input.niche, input.allowedProjectTypes);

    // Enqueue job for Python worker
    await enqueueJob(job.id, input.niche, input.email, input.allowedProjectTypes);

    // Update status to QUEUED
    await updateJobStatus(job.id, JobStatus.QUEUED);

    // Return job info with status URL
    res.status(201).json({
      id: job.id,
      status: 'queued',
      statusUrl: `${CONFIG.baseUrl}/jobs/${job.id}`,
      message: 'Research job created. Check the status URL for progress.',
    });
  } catch (error) {
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
 * Get job status and progress
 */
jobsRouter.get('/:jobId', async (req: Request, res: Response) => {
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

    // Format response
    res.json({
      id: job.id,
      email: job.email,
      niche: job.niche,
      status: job.status,
      currentStage: job.currentStage,
      currentStageName: job.currentStageName,
      stagesCompleted: job.stagesCompleted,
      totalStages: job.totalStages,
      progressPercent: job.progressPercent,
      errorMessage: job.errorMessage,
      createdAt: job.createdAt.toISOString(),
      startedAt: job.startedAt?.toISOString() || null,
      completedAt: job.completedAt?.toISOString() || null,
      progress: job.progress.map(p => ({
        stageNumber: p.stageNumber,
        stageName: p.stageName,
        status: p.status,
        startedAt: p.startedAt?.toISOString() || null,
        completedAt: p.completedAt?.toISOString() || null,
        durationSeconds: p.durationSeconds,
      })),
      assets: job.assets.map(a => ({
        type: a.assetType,
        url: `/api/jobs/${job.id}/${a.assetType.toLowerCase().replace('_', '')}`,
      })),
    });
  } catch (error) {
    console.error('Failed to get job:', error);
    res.status(500).json({ error: 'Failed to get job status' });
  }
});

/**
 * GET /api/jobs/:jobId/reportjson
 * Download the research report JSON
 */
jobsRouter.get('/:jobId/reportjson', async (req: Request, res: Response) => {
  try {
    const { jobId } = req.params;

    const job = await getJob(jobId);
    if (!job) {
      res.status(404).json({ error: 'Job not found' });
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
 * View or download the landing page HTML
 */
jobsRouter.get('/:jobId/landingpage', async (req: Request, res: Response) => {
  try {
    const { jobId } = req.params;

    const job = await getJob(jobId);
    if (!job) {
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
 * Cancel a pending or running job
 */
jobsRouter.delete('/:jobId', async (req: Request, res: Response) => {
  try {
    const { jobId } = req.params;

    const job = await getJob(jobId);
    if (!job) {
      res.status(404).json({ error: 'Job not found' });
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
