/**
 * Worker Heartbeat Service
 *
 * Handles worker crash detection.
 * - Tracks worker heartbeats
 * - Detects stale jobs (no heartbeat for STALE_THRESHOLD_MS)
 * - Marks stale jobs as FAILED (no automatic retry - use checkpoints for resume)
 */

import { prisma } from './db.js';
import { JobStatus } from '@prisma/client';
import { failJob } from './jobService.js';
import { notifyJobError } from './notificationService.js';
import { getPhaseContext } from '../utils/phaseContext.js';

// Configuration
const STALE_THRESHOLD_MS = 90 * 1000; // 90 seconds - detect stale jobs within this window
const CHECK_INTERVAL_MS = 30 * 1000;  // 30 seconds - how often to check for stale jobs
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
  lastHeartbeat: Date | null;
  startedAt: Date | null;
  currentStage: number | null;
  selectedSolutions: string[];
  exceededMaxRuntime: boolean;
}>> {
  const staleThreshold = new Date(Date.now() - STALE_THRESHOLD_MS);
  const maxRuntimeThreshold = new Date(Date.now() - MAX_RUNTIME_MS);

  // Find jobs that are:
  // 1. In an active-worker status
  // 2. AND one of:
  //    a) lastHeartbeat is stale (worker crash)
  //    b) Job never received heartbeat but was started long enough ago
  //    c) Job has exceeded absolute max runtime (safety net)
  // Note: AWAITING_SELECTION is excluded — it is a user-wait state with no active
  // worker and doesn't participate in the heartbeat lifecycle.
  const staleJobs = await prisma.job.findMany({
    where: {
      status: { in: [JobStatus.RUNNING, JobStatus.REGENERATING, JobStatus.RUNNING_PHASE2] },
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
      lastHeartbeat: true,
      startedAt: true,
      currentStage: true,
      selectedSolutions: true,
    },
  });

  // Mark jobs that exceeded max runtime
  return staleJobs.map(job => ({
    ...job,
    exceededMaxRuntime: job.startedAt ? job.startedAt < maxRuntimeThreshold : false,
  }));
}

/**
 * Mark a job as failed due to stale heartbeat (worker crash)
 */
async function markJobFailed(job: {
  id: string;
  niche: string;
  userId: string | null;
  currentStage: number | null;
  selectedSolutions: string[];
}, reason: string): Promise<void> {
  console.log(`[Heartbeat] Job ${job.id} failed: ${reason}`);

  // Use failJob which handles credit refunds
  await failJob(job.id, reason);

  // Send failure notification with phase context
  const email = await getUserEmail(job.userId);
  if (email) {
    try {
      const phaseCtx = getPhaseContext(job.currentStage, job.selectedSolutions);
      await notifyJobError(job.userId, email, job.id, job.niche, reason, null, phaseCtx);
    } catch (emailError) {
      console.error(`[Heartbeat] Failed to send failure notification for job ${job.id}:`, emailError);
    }
  }
}

/**
 * Check for stale jobs and mark them as failed
 * No automatic retry - users can manually retry using checkpoints
 */
export async function checkAndRecoverStaleJobs(): Promise<{
  checked: number;
  failed: number;
  timedOut: number;
}> {
  const stats = { checked: 0, failed: 0, timedOut: 0 };

  try {
    const staleJobs = await findStaleJobs();
    stats.checked = staleJobs.length;

    if (staleJobs.length === 0) {
      return stats;
    }

    console.log(`[Heartbeat] Found ${staleJobs.length} stale job(s)`);

    for (const job of staleJobs) {
      try {
        if (job.exceededMaxRuntime) {
          const runtimeHours = MAX_RUNTIME_MS / (60 * 60 * 1000);
          await markJobFailed(job, `Job exceeded maximum runtime of ${runtimeHours} hours`);
          stats.timedOut++;
        } else {
          await markJobFailed(job, 'Worker stopped sending heartbeats - job marked as failed. Use checkpoint resume to continue.');
          stats.failed++;
        }
      } catch (jobError) {
        console.error(`[Heartbeat] Error processing stale job ${job.id}:`, jobError);
      }
    }

    if (stats.failed > 0 || stats.timedOut > 0) {
      console.log(`[Heartbeat] Recovery complete: ${stats.failed} failed, ${stats.timedOut} timed out`);
    }
  } catch (error) {
    console.error('[Heartbeat] Error checking for stale jobs:', error);
  }

  return stats;
}

/**
 * Startup check - log stale jobs when backend starts
 * Does NOT take action - lets periodic heartbeat monitor handle recovery
 * This avoids marking jobs as failed before workers have a chance to resume
 */
export async function performStartupRecovery(): Promise<void> {
  console.log('[Heartbeat] Performing startup check...');

  try {
    const staleJobs = await findStaleJobs();
    if (staleJobs.length > 0) {
      console.log(`[Heartbeat] Found ${staleJobs.length} potentially stale job(s) - will be handled by periodic monitor`);
      for (const job of staleJobs) {
        console.log(`[Heartbeat]   - Job ${job.id}: ${job.niche.substring(0, 50)}...`);
      }
    } else {
      console.log('[Heartbeat] No stale jobs found');
    }

    // Clean up stale worker records (safe - doesn't affect jobs)
    const staleWorkerThreshold = new Date(Date.now() - STALE_THRESHOLD_MS * 2);
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
    console.error('[Heartbeat] Startup check failed:', error);
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
