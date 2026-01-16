import { Router, Response } from 'express';
import { getJob, updateStageProgress, completeJob, failJob } from '../services/jobService.js';
import { subscribeToProgress, getQueueStats } from '../services/queueService.js';
import { sendCompletionEmail, sendFailureEmail } from '../services/emailService.js';
import { JobStatus, StageStatus } from '@prisma/client';
import { prisma } from '../services/db.js';
import { requireInternalAuth, verifyOwnership, AuthenticatedRequest } from '../middleware/auth.js';
import { formatJobResponse } from '../utils/jobFormatter.js';

/**
 * Get the current email address for a job.
 * Queries the User table for the current email using userId.
 * Returns null if user not found (e.g., deleted user).
 */
async function getCurrentEmailForJob(job: { userId: string | null }): Promise<string | null> {
  if (!job.userId) {
    return null;
  }

  try {
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

export const eventsRouter = Router();

/**
 * GET /api/jobs/:jobId/events
 * Server-Sent Events endpoint for real-time progress updates (requires authentication and ownership)
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
    queueStats,
  });
  res.write(`data: ${JSON.stringify(initialData)}\n\n`);

  // Subscribe to Redis progress updates
  const { unsubscribe } = subscribeToProgress(jobId, async (progressData) => {
    try {
      // Update database with progress
      if (progressData.stage && progressData.status) {
        const stageStatus = progressData.status === 'running' ? StageStatus.RUNNING
          : progressData.status === 'completed' ? StageStatus.COMPLETED
          : progressData.status === 'failed' ? StageStatus.FAILED
          : StageStatus.PENDING;

        await updateStageProgress(
          jobId,
          progressData.stage as number,
          stageStatus,
          progressData.error as string | undefined
        );
      }

      // Handle job completion
      if (progressData.status === 'completed' && progressData.report_path) {
        const completedJob = await completeJob(
          jobId,
          progressData.report_path as string,
          progressData.landing_path as string | undefined
        );

        // Send completion email (use current user email if available)
        if (completedJob) {
          getCurrentEmailForJob(completedJob).then(email => {
            if (email) {
              sendCompletionEmail(email, jobId, completedJob.niche).catch(err => {
                console.error('Failed to send completion email:', err);
              });
            }
          });
        }
      }

      // Handle job failure
      if (progressData.status === 'failed' && progressData.error) {
        await failJob(jobId, progressData.error as string, progressData.stage as number);

        // Send failure email (use current user email if available)
        const failedJob = await getJob(jobId);
        if (failedJob) {
          getCurrentEmailForJob(failedJob).then(email => {
            if (email) {
              sendFailureEmail(email, jobId, failedJob.niche, progressData.error as string).catch(err => {
                console.error('Failed to send failure email:', err);
              });
            }
          });
        }
      }

      // Fetch updated job and send to client
      const updatedJob = await getJob(jobId);
      if (updatedJob) {
        const updatedQueueStats = updatedJob.status === JobStatus.QUEUED ? await getQueueStats(jobId) : null;
        const data = formatJobResponse(updatedJob, {
          includeProgress: true,
          includeAssets: true,
          queueStats: updatedQueueStats,
        });
        res.write(`data: ${JSON.stringify(data)}\n\n`);

        // Close connection if job is done
        if (updatedJob.status === JobStatus.COMPLETED ||
            updatedJob.status === JobStatus.FAILED ||
            updatedJob.status === JobStatus.CANCELLED) {
          await unsubscribe();
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
  req.on('close', async () => {
    clearInterval(heartbeat);
    await unsubscribe();
    console.log(`SSE connection closed for job ${jobId}`);
  });
});
