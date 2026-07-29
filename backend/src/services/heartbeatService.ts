/**
 * Worker Heartbeat Service
 *
 * Handles worker crash detection.
 * - Tracks worker heartbeats
 * - Detects stale jobs (no heartbeat for STALE_THRESHOLD_MS)
 * - Marks stale jobs as FAILED (no automatic retry - use checkpoints for resume)
 */

import { prisma } from './db.js';
import { JobStatus, StageStatus, DispatchKind } from '@prisma/client';
import { failJob, cancelRegenerationDispatch, cancelSeedIdeaDispatch } from './jobService.js';
import { notifyJobError } from './notificationService.js';
import { getPhaseContext } from '../utils/phaseContext.js';
import { refundForStage } from './creditService.js';
import { broadcastProgress } from './progressBroadcastService.js';

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
  activeDispatchId: string | null;
  status: JobStatus;
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
      activeDispatchId: true,
      status: true,
    },
  });

  // Mark jobs that exceeded max runtime
  return staleJobs.map(job => ({
    ...job,
    exceededMaxRuntime: job.startedAt ? job.startedAt < maxRuntimeThreshold : false,
  }));
}

/**
 * Find landing page jobs that are stuck in RUNNING/QUEUED with no active worker.
 * These are invisible to the main stale-job check because the parent job stays COMPLETED.
 */
async function findStaleLandingPageJobs(): Promise<Array<{
  id: string;
  niche: string;
  userId: string | null;
  landingPageStatus: string | null;
}>> {
  const staleThreshold = new Date(Date.now() - STALE_THRESHOLD_MS);
  const maxRuntimeThreshold = new Date(Date.now() - MAX_RUNTIME_MS);

  return prisma.job.findMany({
    where: {
      OR: [
        // Worker crash: LP RUNNING, heartbeat stale (main job COMPLETED)
        {
          status: JobStatus.COMPLETED,
          landingPageStatus: 'RUNNING',
          OR: [
            { lastHeartbeat: { lt: staleThreshold } },
            { lastHeartbeat: null, updatedAt: { lt: staleThreshold } },
          ],
        },
        // Stuck in queue: LP QUEUED beyond max runtime
        {
          status: JobStatus.COMPLETED,
          landingPageStatus: 'QUEUED',
          updatedAt: { lt: maxRuntimeThreshold },
        },
        // Orphan cleanup: main job FAILED/CANCELLED while LP in progress
        {
          status: { in: [JobStatus.FAILED, JobStatus.CANCELLED] },
          landingPageStatus: { in: ['RUNNING', 'QUEUED'] },
        },
      ],
    },
    select: {
      id: true,
      niche: true,
      userId: true,
      landingPageStatus: true,
    },
  });
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
  activeDispatchId: string | null;
  status: JobStatus;
}, reason: string): Promise<void> {
  // A SEED_IDEA dispatch is an operation ON TOP OF an already-settled AWAITING_SELECTION job —
  // a crashed worker must not fail the WHOLE research job over it (plan: eager-meandering-
  // feather.md Phase 5, "op-scoped cancel + heartbeat"). Settle just that dispatch, refund its
  // numbered seed_idea_N charge, and restore AWAITING_SELECTION with the pool intact instead of
  // calling failJob — mirrors cancelJob's own SEED_IDEA branch (shared helper, same contract).
  if (job.activeDispatchId) {
    const dispatch = await prisma.jobDispatch.findUnique({
      where: { id: job.activeDispatchId },
      select: {
        id: true,
        kind: true,
        seedOrdinal: true,
        sourceMessageId: true,
        segment: true,
        chargeId: true,
      },
    });
    if (dispatch?.kind === DispatchKind.SEED_IDEA) {
      console.log(
        `[Heartbeat] Job ${job.id} seed-idea dispatch ${dispatch.id} stale — restoring ` +
        `AWAITING_SELECTION (parent job left alive): ${reason}`
      );
      await cancelSeedIdeaDispatch(job.id, dispatch, JobStatus.RUNNING, 'SYSTEM_FAULT');
      return;
    }
    if (dispatch?.kind === DispatchKind.REGENERATE) {
      console.log(
        `[Heartbeat] Job ${job.id} idea-batch dispatch ${dispatch.id} stale — restoring ` +
        `AWAITING_SELECTION (parent job left alive): ${reason}`
      );
      // Pass the job's ACTUAL status: cancelRegenerationDispatch only drops the Redis
      // queue entry when the batch was still QUEUED. Hardcoding REGENERATING here would
      // orphan the entry, letting a worker later claim and run an already-refunded batch.
      await cancelRegenerationDispatch(
        job.id,
        { id: dispatch.id, segment: dispatch.segment, chargeId: dispatch.chargeId },
        job.status,
        'SYSTEM_FAULT',
      );
      return;
    }
  }

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
 * Check for stale landing page jobs and mark them as failed.
 * Uses atomic CAS to prevent race conditions with worker completion.
 */
export async function checkStaleLandingPageJobs(): Promise<{ recovered: number }> {
  const stats = { recovered: 0 };

  try {
    const staleJobs = await findStaleLandingPageJobs();
    if (staleJobs.length === 0) return stats;

    console.log(`[Heartbeat] Found ${staleJobs.length} stale landing page job(s)`);

    for (const job of staleJobs) {
      try {
        const reason = job.landingPageStatus === 'RUNNING'
          ? 'Worker stopped responding during landing page generation'
          : job.landingPageStatus === 'QUEUED'
            ? 'Landing page generation timed out waiting for a worker'
            : 'Landing page orphaned after job failure';

        // Atomic CAS: only fail if LP status hasn't changed since query
        const result = await prisma.job.updateMany({
          where: {
            id: job.id,
            landingPageStatus: job.landingPageStatus,
          },
          data: { landingPageStatus: 'FAILED' },
        });

        if (result.count === 0) {
          console.log(`[Heartbeat] LP job ${job.id} status already changed, skipping`);
          continue;
        }

        console.warn(`[Heartbeat] Recovered stale LP job ${job.id}: ${reason}`);

        // Update stage 15 progress (may be PENDING or RUNNING)
        await prisma.jobProgress.updateMany({
          where: {
            jobId: job.id,
            stageNumber: 15,
            status: { in: [StageStatus.RUNNING, StageStatus.PENDING] },
          },
          data: { status: StageStatus.FAILED, errorMessage: reason },
        });

        // Refund credits (idempotent — unique constraint prevents double refund)
        try {
          await refundForStage(job.id, 'landing_page');
        } catch (refundErr) {
          console.error(`[Heartbeat] Failed to refund LP credits for ${job.id}:`, refundErr);
        }

        // Broadcast so frontend SSE picks up the FAILED state
        broadcastProgress(job.id, {
          stage: 15,
          name: 'Landing Page Generation',
          status: 'failed',
          error: reason,
        });

        stats.recovered++;
      } catch (jobError) {
        console.error(`[Heartbeat] Error recovering stale LP job ${job.id}:`, jobError);
      }
    }

    if (stats.recovered > 0) {
      console.log(`[Heartbeat] LP recovery complete: ${stats.recovered} recovered`);
    }
  } catch (error) {
    console.error('[Heartbeat] Error checking stale landing page jobs:', error);
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

    // Log stale LP jobs (same passive approach — periodic monitor will recover them)
    const staleLpJobs = await findStaleLandingPageJobs();
    if (staleLpJobs.length > 0) {
      console.log(`[Heartbeat] Found ${staleLpJobs.length} potentially stale LP job(s) - will be handled by periodic monitor`);
      for (const job of staleLpJobs) {
        console.log(`[Heartbeat]   - LP Job ${job.id} (${job.landingPageStatus}): ${job.niche.substring(0, 50)}...`);
      }
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
    await checkStaleLandingPageJobs();
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
