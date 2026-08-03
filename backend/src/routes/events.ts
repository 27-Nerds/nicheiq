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

  // Set SSE headers
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.setHeader('X-Accel-Buffering', 'no'); // Disable nginx buffering
  res.flushHeaders();

  const terminalStatuses: string[] = [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED];
  const interactiveStatuses = ['AWAITING_SELECTION', 'REGENERATING', 'RUNNING_PHASE2', 'AWAITING_GATE'];
  let queuePollInterval: NodeJS.Timeout | null = null;
  let heartbeat: NodeJS.Timeout | null = null;
  let unsubscribe: (() => void) | null = null;
  let closed = false;
  let latestStatus = job.status;

  const terminalWithoutLandingPage = (currentJob: typeof job): boolean => {
    const landingInProgress = currentJob.landingPageStatus === 'QUEUED' || currentJob.landingPageStatus === 'RUNNING';
    return terminalStatuses.includes(currentJob.status) && !landingInProgress;
  };

  const cleanup = (endResponse: boolean): void => {
    if (closed) return;
    closed = true;

    if (heartbeat) {
      clearInterval(heartbeat);
      heartbeat = null;
    }
    if (queuePollInterval) {
      clearInterval(queuePollInterval);
      queuePollInterval = null;
    }
    if (unsubscribe) {
      const stopListening = unsubscribe;
      unsubscribe = null;
      stopListening();
    }
    if (endResponse && !res.writableEnded) {
      res.end();
    }
  };

  const sendCurrentState = async (initial = false): Promise<void> => {
    if (closed) return;

    const currentJob = await getJob(jobId);
    if (closed) return;
    if (!currentJob) {
      cleanup(true);
      return;
    }

    latestStatus = currentJob.status;
    if (currentJob.status !== JobStatus.QUEUED && queuePollInterval) {
      clearInterval(queuePollInterval);
      queuePollInterval = null;
    }

    const queueStats = currentJob.status === JobStatus.QUEUED ? await getQueueStats(jobId) : null;
    if (closed) return;

    const includeSolutions = interactiveStatuses.includes(currentJob.status) ||
      (currentJob.status === JobStatus.QUEUED && (currentJob.solutionIdeas as any[])?.length > 0) ||
      (currentJob.status === JobStatus.COMPLETED && (currentJob.selectedSolutions as string[])?.length > 0);
    const formatted = formatJobResponse(currentJob, {
      includeProgress: true,
      includeAssets: true,
      includeCreatedAt: true,
      includeAssetFlags: true,
      includeSolutionIdeas: includeSolutions,
      queueStats,
    });
    const finished = terminalWithoutLandingPage(currentJob);
    const data = initial && finished
      ? { ...formatted, message: 'Job already finished' }
      : formatted;
    res.write(`data: ${JSON.stringify(data)}\n\n`);

    if (finished) {
      cleanup(true);
    }
  };

  // Subscribe before the authoritative snapshot. Once the first getJob() has
  // established ownership, there is no await between here and listener registration,
  // so a terminal transition cannot land in a subscribe-after-snapshot gap.
  unsubscribe = subscribeToJobProgress(jobId, (_progressData: ProgressData) => {
    void sendCurrentState().catch(error => {
      console.error('Error processing progress update:', error);
    });
  });

  // Cleanup on client disconnect. cleanup() is idempotent because a terminal write
  // followed by the socket close event is the normal successful path.
  req.on('close', () => {
    cleanup(false);
    console.log(`SSE connection closed for job ${jobId}`);
  });

  // Re-read only after subscribing; this is the authoritative initial snapshot.
  await sendCurrentState(true);
  if (closed) return;

  // Poll queue position while queued so users see movement as other jobs complete.
  if (latestStatus === JobStatus.QUEUED) {
    queuePollInterval = setInterval(() => {
      void sendCurrentState().catch(error => {
        console.error('Error polling queue position:', error);
      });
    }, 10000);
  }

  // Send heartbeat every 30 seconds to keep connection alive
  heartbeat = setInterval(() => {
    if (!closed) {
      res.write(': heartbeat\n\n');
    }
  }, 30000);
});
