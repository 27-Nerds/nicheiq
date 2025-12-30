import { Router, Request, Response } from 'express';
import { getJob, updateStageProgress, updateJobStatus, completeJob, failJob } from '../services/jobService.js';
import { subscribeToProgress, getProgressChannel } from '../services/queueService.js';
import { sendCompletionEmail, sendFailureEmail } from '../services/emailService.js';
import { JobStatus, StageStatus } from '@prisma/client';

export const eventsRouter = Router();

/**
 * GET /api/jobs/:jobId/events
 * Server-Sent Events endpoint for real-time progress updates
 */
eventsRouter.get('/:jobId/events', async (req: Request, res: Response) => {
  const { jobId } = req.params;

  // Validate job exists
  const job = await getJob(jobId);
  if (!job) {
    res.status(404).json({ error: 'Job not found' });
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

  // Send initial state
  const initialData = formatJobForSSE(job);
  res.write(`data: ${JSON.stringify(initialData)}\n\n`);

  // Subscribe to Redis progress updates
  const { subscriber, unsubscribe } = subscribeToProgress(jobId, async (progressData) => {
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

        // Send completion email
        if (completedJob) {
          sendCompletionEmail(completedJob.email, jobId, completedJob.niche).catch(err => {
            console.error('Failed to send completion email:', err);
          });
        }
      }

      // Handle job failure
      if (progressData.status === 'failed' && progressData.error) {
        await failJob(jobId, progressData.error as string, progressData.stage as number);

        // Send failure email
        const failedJob = await getJob(jobId);
        if (failedJob) {
          sendFailureEmail(failedJob.email, jobId, failedJob.niche, progressData.error as string).catch(err => {
            console.error('Failed to send failure email:', err);
          });
        }
      }

      // Fetch updated job and send to client
      const updatedJob = await getJob(jobId);
      if (updatedJob) {
        const data = formatJobForSSE(updatedJob);
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

/**
 * Format job data for SSE response
 */
function formatJobForSSE(job: Awaited<ReturnType<typeof getJob>>) {
  if (!job) return null;

  return {
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
    startedAt: job.startedAt?.toISOString() || null,
    completedAt: job.completedAt?.toISOString() || null,
    progress: job.progress.map(p => ({
      stageNumber: p.stageNumber,
      stageName: p.stageName,
      status: p.status,
      durationSeconds: p.durationSeconds,
    })),
    assets: job.assets.map(a => ({
      type: a.assetType,
      url: `/api/jobs/${job.id}/${a.assetType.toLowerCase().replace('_', '')}`,
    })),
  };
}
