/**
 * Worker Heartbeat Service
 *
 * Handles worker crash detection and job recovery.
 * - Tracks worker heartbeats via Redis
 * - Detects stale jobs (no heartbeat for STALE_THRESHOLD_MS)
 * - Re-queues jobs that can be retried
 * - Marks jobs as FAILED when max retries exceeded
 */

import { prisma } from './db.js';
import { JobStatus } from '@prisma/client';
import { enqueueJob } from './queueService.js';
import { failJob, resetJobProgress } from './jobService.js';
import { sendFailureEmail } from './emailService.js';

// Configuration
const STALE_THRESHOLD_MS = 90 * 1000; // 90 seconds - detect stale jobs within this window
const CHECK_INTERVAL_MS = 30 * 1000;  // 30 seconds - how often to check for stale jobs
const MAX_RETRIES = 2;                 // Maximum retry attempts for crashed jobs
const MAX_RUNTIME_MS = parseInt(process.env.MAX_JOB_RUNTIME_HOURS || '4', 10) * 60 * 60 * 1000; // Absolute max runtime (default 4 hours)

let checkInterval: NodeJS.Timeout | null = null;
let isRunning = false;

/**
 * Get the current email address for a user
 */
async function getUserEmail(userId: string | null): Promise<string | null> {
  if (!userId) return null;

  try {
    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: { email: true },
    });
    return user?.email || null;
  } catch (error) {
    console.error('Failed to fetch user email:', error);
    return null;
  }
}

/**
 * Update worker heartbeat for a job
 * Called by Python worker via API endpoint
 */
export async function updateJobHeartbeat(
  jobId: string,
  workerId: string
): Promise<boolean> {
  try {
    await prisma.job.update({
      where: { id: jobId },
      data: {
        workerId,
        lastHeartbeat: new Date(),
      },
    });
    return true;
  } catch (error) {
    console.error(`Failed to update heartbeat for job ${jobId}:`, error);
    return false;
  }
}

/**
 * Register or update worker heartbeat
 * Called periodically by Python worker
 */
export async function registerWorkerHeartbeat(
  workerId: string,
  currentJobId: string | null,
  hostname?: string,
  processId?: number
): Promise<void> {
  try {
    await prisma.workerHeartbeat.upsert({
      where: { workerId },
      create: {
        workerId,
        currentJobId,
        status: currentJobId ? 'active' : 'idle',
        hostname,
        processId,
        lastHeartbeat: new Date(),
        startedAt: new Date(),
      },
      update: {
        currentJobId,
        status: currentJobId ? 'active' : 'idle',
        hostname,
        processId,
        lastHeartbeat: new Date(),
      },
    });
  } catch (error) {
    console.error(`Failed to register heartbeat for worker ${workerId}:`, error);
  }
}

/**
 * Mark worker as shut down (graceful shutdown)
 */
export async function markWorkerShutdown(workerId: string): Promise<void> {
  try {
    await prisma.workerHeartbeat.update({
      where: { workerId },
      data: {
        status: 'shutdown',
        currentJobId: null,
        lastHeartbeat: new Date(),
      },
    });
    console.log(`Worker ${workerId} marked as shutdown`);
  } catch (error) {
    // Worker may not exist if it never registered
    console.log(`Could not mark worker ${workerId} as shutdown:`, error);
  }
}

/**
 * Find jobs that are stuck in RUNNING status with stale heartbeats or exceeded max runtime
 */
async function findStaleJobs(): Promise<Array<{
  id: string;
  niche: string;
  userId: string | null;
  workerId: string | null;
  retryCount: number;
  lastHeartbeat: Date | null;
  startedAt: Date | null;
  allowedProjectTypes: unknown;
  exceededMaxRuntime: boolean;
}>> {
  const staleThreshold = new Date(Date.now() - STALE_THRESHOLD_MS);
  const maxRuntimeThreshold = new Date(Date.now() - MAX_RUNTIME_MS);

  // Find jobs that are:
  // 1. In RUNNING status
  // 2. AND one of:
  //    a) lastHeartbeat is stale (worker crash)
  //    b) Job never received heartbeat but was started long enough ago
  //    c) Job has exceeded absolute max runtime (safety net)
  const staleJobs = await prisma.job.findMany({
    where: {
      status: JobStatus.RUNNING,
      OR: [
        // Job has a stale heartbeat
        {
          lastHeartbeat: {
            lt: staleThreshold,
          },
        },
        // Job never received any heartbeat but was started long enough ago
        {
          lastHeartbeat: null,
          startedAt: {
            lt: staleThreshold,
          },
        },
        // Job exceeded absolute max runtime (safety net - catches all edge cases)
        {
          startedAt: {
            lt: maxRuntimeThreshold,
          },
        },
      ],
    },
    select: {
      id: true,
      niche: true,
      userId: true,
      workerId: true,
      retryCount: true,
      lastHeartbeat: true,
      startedAt: true,
      allowedProjectTypes: true,
    },
  });

  // Mark jobs that exceeded max runtime (they should be failed immediately, not retried)
  return staleJobs.map(job => ({
    ...job,
    exceededMaxRuntime: job.startedAt ? job.startedAt < maxRuntimeThreshold : false,
  }));
}

/**
 * Re-queue a job for retry
 * Returns true if successful, false if failed
 */
async function requeueJobForRetry(job: {
  id: string;
  niche: string;
  userId: string | null;
  retryCount: number;
  allowedProjectTypes: unknown;
}): Promise<boolean> {
  const newRetryCount = job.retryCount + 1;

  console.log(`[Heartbeat] Re-queuing job ${job.id} for retry (attempt ${newRetryCount}/${MAX_RETRIES})`);

  try {
    // First enqueue to Redis (if this fails, don't change job status)
    await enqueueJob(
      job.id,
      job.niche,
      job.userId || undefined,
      job.allowedProjectTypes as string[] | undefined
    );

    // Only update job status AFTER successful queue
    await prisma.job.update({
      where: { id: job.id },
      data: {
        status: JobStatus.QUEUED,
        workerId: null,
        lastHeartbeat: null,
        retryCount: newRetryCount,
        errorMessage: `Worker crashed - retry attempt ${newRetryCount}`,
        queuedAt: new Date(),
      },
    });

    // Reset progress records so retry starts fresh
    await resetJobProgress(job.id);

    console.log(`[Heartbeat] Job ${job.id} re-queued successfully`);
    return true;
  } catch (enqueueError) {
    // If re-queue fails, fail the job immediately instead of leaving it stuck
    console.error(`[Heartbeat] Failed to re-queue job ${job.id}:`, enqueueError);

    try {
      const errorMessage = `Recovery failed: Unable to re-queue job - ${enqueueError instanceof Error ? enqueueError.message : 'Unknown error'}`;
      await failJob(job.id, errorMessage);

      // Send failure email
      const email = await getUserEmail(job.userId);
      if (email) {
        await sendFailureEmail(email, job.id, job.niche, errorMessage);
      }
    } catch (failError) {
      console.error(`[Heartbeat] Also failed to mark job ${job.id} as failed:`, failError);
    }

    return false;
  }
}

/**
 * Mark a job as permanently failed (max retries exceeded)
 */
async function markJobPermanentlyFailed(job: {
  id: string;
  niche: string;
  userId: string | null;
  retryCount: number;
}): Promise<void> {
  const errorMessage = `Worker crashed - max retries (${MAX_RETRIES}) exceeded`;

  console.log(`[Heartbeat] Job ${job.id} reached max retries, marking as FAILED`);

  // Use failJob which handles credit refunds
  await failJob(job.id, errorMessage);

  // Send failure email
  const email = await getUserEmail(job.userId);
  if (email) {
    try {
      await sendFailureEmail(email, job.id, job.niche, errorMessage);
    } catch (emailError) {
      console.error(`[Heartbeat] Failed to send failure email for job ${job.id}:`, emailError);
    }
  }
}

/**
 * Check for and recover stale jobs
 * This is the main recovery loop function
 */
export async function checkAndRecoverStaleJobs(): Promise<{
  checked: number;
  requeued: number;
  failed: number;
  timedOut: number;
}> {
  const stats = { checked: 0, requeued: 0, failed: 0, timedOut: 0 };

  try {
    const staleJobs = await findStaleJobs();
    stats.checked = staleJobs.length;

    if (staleJobs.length === 0) {
      return stats;
    }

    console.log(`[Heartbeat] Found ${staleJobs.length} stale job(s)`);

    for (const job of staleJobs) {
      try {
        // Jobs that exceeded absolute max runtime are failed immediately (no retry)
        if (job.exceededMaxRuntime) {
          const runtimeHours = MAX_RUNTIME_MS / (60 * 60 * 1000);
          const errorMessage = `Job exceeded maximum runtime of ${runtimeHours} hours`;
          console.log(`[Heartbeat] Job ${job.id} exceeded max runtime, failing immediately`);

          await failJob(job.id, errorMessage);

          const email = await getUserEmail(job.userId);
          if (email) {
            try {
              await sendFailureEmail(email, job.id, job.niche, errorMessage);
            } catch (emailError) {
              console.error(`[Heartbeat] Failed to send timeout email for job ${job.id}:`, emailError);
            }
          }

          stats.timedOut++;
        } else if (job.retryCount < MAX_RETRIES) {
          // Can retry - re-queue the job
          const success = await requeueJobForRetry(job);
          if (success) {
            stats.requeued++;
          } else {
            stats.failed++;
          }
        } else {
          // Max retries exceeded - mark as permanently failed
          await markJobPermanentlyFailed(job);
          stats.failed++;
        }
      } catch (jobError) {
        console.error(`[Heartbeat] Error processing stale job ${job.id}:`, jobError);
      }
    }

    if (stats.requeued > 0 || stats.failed > 0 || stats.timedOut > 0) {
      console.log(`[Heartbeat] Recovery complete: ${stats.requeued} requeued, ${stats.failed} failed, ${stats.timedOut} timed out`);
    }
  } catch (error) {
    console.error('[Heartbeat] Error checking for stale jobs:', error);
  }

  return stats;
}

/**
 * Startup recovery - check for stale jobs when backend starts
 * This handles the case where backend was down while workers crashed
 */
export async function performStartupRecovery(): Promise<void> {
  console.log('[Heartbeat] Performing startup recovery check...');

  try {
    const stats = await checkAndRecoverStaleJobs();
    console.log(`[Heartbeat] Startup recovery: found ${stats.checked} stale jobs, requeued ${stats.requeued}, failed ${stats.failed}, timed out ${stats.timedOut}`);

    // Also clean up any workers that haven't sent heartbeats (they're probably dead)
    const staleWorkerThreshold = new Date(Date.now() - STALE_THRESHOLD_MS * 2); // 3 minutes for workers
    const staleWorkers = await prisma.workerHeartbeat.findMany({
      where: {
        lastHeartbeat: {
          lt: staleWorkerThreshold,
        },
        status: {
          not: 'shutdown',
        },
      },
    });

    if (staleWorkers.length > 0) {
      console.log(`[Heartbeat] Cleaning up ${staleWorkers.length} stale worker record(s)`);
      await prisma.workerHeartbeat.deleteMany({
        where: {
          workerId: {
            in: staleWorkers.map(w => w.workerId),
          },
        },
      });
    }
  } catch (error) {
    console.error('[Heartbeat] Startup recovery failed:', error);
  }
}

/**
 * Start the heartbeat monitoring service
 */
export function startHeartbeatMonitor(): void {
  if (isRunning) {
    console.log('[Heartbeat] Monitor already running');
    return;
  }

  isRunning = true;
  console.log(`[Heartbeat] Starting monitor (check interval: ${CHECK_INTERVAL_MS / 1000}s, stale threshold: ${STALE_THRESHOLD_MS / 1000}s)`);

  // Perform startup recovery immediately
  performStartupRecovery().catch(err => {
    console.error('[Heartbeat] Startup recovery error:', err);
  });

  // Start periodic checking
  checkInterval = setInterval(async () => {
    await checkAndRecoverStaleJobs();
  }, CHECK_INTERVAL_MS);
}

/**
 * Stop the heartbeat monitoring service
 */
export function stopHeartbeatMonitor(): void {
  if (!isRunning) {
    return;
  }

  console.log('[Heartbeat] Stopping monitor');

  if (checkInterval) {
    clearInterval(checkInterval);
    checkInterval = null;
  }

  isRunning = false;
}

/**
 * Check if the heartbeat monitor is running
 */
export function isHeartbeatMonitorRunning(): boolean {
  return isRunning;
}
