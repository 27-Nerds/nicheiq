import { Router, Response } from 'express';
import { getJob } from '../services/jobService.js';
import { subscribeToJobProgress, ProgressData } from '../services/progressBroadcastService.js';
import { getQueueStats } from '../services/queueService.js';
import { JobStatus } from '@prisma/client';
import { requireInternalAuth, verifyOwnership, AuthenticatedRequest } from '../middleware/auth.js';
import { formatJobResponse } from '../utils/jobFormatter.js';

export const eventsRouter = Router();

/**
 * GET /api/jobs/:jobId/events
 * Server-Sent Events endpoint for real-time progress updates (requires authentication and ownership)
 *
 * The progress updates come from the EventEmitter in progressBroadcastService,
 * which is triggered by POST /api/workers/progress endpoint.
 */
eventsRouter.get('/:jobId/events', requireInternalAuth, async (req: AuthenticatedRequest, res: Response) => {
  const { jobId } = req.params;

  // Validate job exists
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

  // If job is already completed or failed, send final state and close
  if (job.status === JobStatus.COMPLETED || job.status === JobStatus.FAILED || job.status === JobStatus.CANCELLED) {
    res.json({
      id: job.id,
      status: job.status,
      progressPercent: job.progressPercent,
      message: 'Job already finished',
    });
    return;
  }

  // Set SSE headers
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.setHeader('X-Accel-Buffering', 'no'); // Disable nginx buffering
  res.flushHeaders();

  // Send initial state with queue position if queued
  const queueStats = job.status === JobStatus.QUEUED ? await getQueueStats(jobId) : null;
  const initialData = formatJobResponse(job, {
    includeProgress: true,
    includeAssets: true,
    includeCreatedAt: true,
    includeAssetFlags: true,
    queueStats,
  });
  res.write(`data: ${JSON.stringify(initialData)}\n\n`);

  // Queue position polling interval (only for QUEUED jobs)
  // This ensures users see updated queue positions as other jobs complete
  let queuePollInterval: NodeJS.Timeout | null = null;

  if (job.status === JobStatus.QUEUED) {
    queuePollInterval = setInterval(async () => {
      try {
        const currentJob = await getJob(jobId);
        if (currentJob?.status === JobStatus.QUEUED) {
          const stats = await getQueueStats(jobId);
          const data = formatJobResponse(currentJob, {
            includeProgress: true,
            includeAssets: true,
            includeCreatedAt: true,
            includeAssetFlags: true,
            queueStats: stats,
          });
          res.write(`data: ${JSON.stringify(data)}\n\n`);
        } else {
          // Job no longer queued, stop polling (progress updates will take over)
          if (queuePollInterval) {
            clearInterval(queuePollInterval);
            queuePollInterval = null;
          }
        }
      } catch (error) {
        console.error('Error polling queue position:', error);
      }
    }, 10000); // Poll every 10 seconds
  }

  // Subscribe to progress updates via EventEmitter
  // Note: progressData is unused because we fetch fresh state from DB
  const unsubscribe = subscribeToJobProgress(jobId, async (_progressData: ProgressData) => {
    try {
      // Fetch updated job state from DB and send to client
      const updatedJob = await getJob(jobId);
      if (updatedJob) {
        // Stop queue polling if job is no longer queued
        if (updatedJob.status !== JobStatus.QUEUED && queuePollInterval) {
          clearInterval(queuePollInterval);
          queuePollInterval = null;
        }

        const updatedQueueStats = updatedJob.status === JobStatus.QUEUED ? await getQueueStats(jobId) : null;
        const data = formatJobResponse(updatedJob, {
          includeProgress: true,
          includeAssets: true,
          includeCreatedAt: true,
          includeAssetFlags: true,
          queueStats: updatedQueueStats,
        });
        res.write(`data: ${JSON.stringify(data)}\n\n`);

        // Close connection if job is done
        if (updatedJob.status === JobStatus.COMPLETED ||
            updatedJob.status === JobStatus.FAILED ||
            updatedJob.status === JobStatus.CANCELLED) {
          clearInterval(heartbeat);
          if (queuePollInterval) {
            clearInterval(queuePollInterval);
            queuePollInterval = null;
          }
          unsubscribe();
          res.end();
        }
      }
    } catch (error) {
      console.error('Error processing progress update:', error);
    }
  });

  // Send heartbeat every 30 seconds to keep connection alive
  const heartbeat = setInterval(() => {
    res.write(': heartbeat\n\n');
  }, 30000);

  // Cleanup on client disconnect
  req.on('close', () => {
    clearInterval(heartbeat);
    if (queuePollInterval) {
      clearInterval(queuePollInterval);
      queuePollInterval = null;
    }
    unsubscribe();
    console.log(`SSE connection closed for job ${jobId}`);
  });
});
