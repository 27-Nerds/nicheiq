import { prisma } from './db.js';
import { sendCompletionEmail, sendFailureEmail, sendJobStartEmail, sendSolutionsReadyEmail, sendSelectionReminderEmail, sendPhase2StartEmail, sendRegenerationCompleteEmail, sendLandingPageReadyEmail, sendGateReachedEmail } from './emailService.js';
import type { PhaseContextForEmail } from './emailService.js';

export type NotificationType = 'jobStart' | 'jobComplete' | 'jobError' | 'solutionsReady';

const CATALOG_JOB_MODES = ['catalog_pain_points', 'catalog_ideas'] as const;

async function isCatalogJob(jobId: string): Promise<boolean> {
  const job = await prisma.job.findUnique({
    where: { id: jobId },
    select: { jobMode: true },
  });
  return job?.jobMode != null && CATALOG_JOB_MODES.includes(job.jobMode as typeof CATALOG_JOB_MODES[number]);
}

const DEFAULT_PREFERENCES = {
  emailEnabled: true,
  emailOnJobStart: true,
  emailOnJobComplete: true,
  emailOnJobError: true,
  emailOnSolutionsReady: true,
};

/**
 * Check if notification should be sent based on user preferences
 */
export async function shouldNotifyUser(
  userId: string | null | undefined,
  notificationType: NotificationType,
  jobId?: string
): Promise<boolean> {
  if (!userId) return false;
  if (jobId && await isCatalogJob(jobId)) return false;

  const prefs = await prisma.notificationPreferences.findUnique({
    where: { userId },
  });

  const settings = prefs ?? DEFAULT_PREFERENCES;

  if (!settings.emailEnabled) return false;

  switch (notificationType) {
    case 'jobStart':
      return settings.emailOnJobStart;
    case 'jobComplete':
      return settings.emailOnJobComplete;
    case 'jobError':
      return settings.emailOnJobError;
    case 'solutionsReady':
      return settings.emailOnSolutionsReady;
    default:
      return false;
  }
}

/**
 * Send job start email if user preferences allow
 */
export async function notifyJobStart(
  userId: string | null | undefined,
  email: string,
  jobId: string,
  niche: string
): Promise<void> {
  if (!(await shouldNotifyUser(userId, 'jobStart', jobId))) {
    console.log(`[Notification] Skipping start email for job ${jobId} - disabled by preference`);
    return;
  }
  await sendJobStartEmail(email, jobId, niche);
}

/**
 * Send job completion email if user preferences allow
 */
export async function notifyJobComplete(
  userId: string | null | undefined,
  email: string,
  jobId: string,
  niche: string
): Promise<void> {
  if (!(await shouldNotifyUser(userId, 'jobComplete', jobId))) {
    console.log(`[Notification] Skipping completion email for job ${jobId} - disabled by preference`);
    return;
  }
  await sendCompletionEmail(email, jobId, niche);
}

/**
 * Error details interface for user-friendly error messages
 */
interface ErrorDetails {
  userMessage?: string;
  actionableGuidance?: string;
}

/**
 * Send job failure email if user preferences allow
 *
 * @param userId - User ID for preference check
 * @param email - Recipient email
 * @param jobId - The job ID
 * @param niche - The job's niche
 * @param errorMessage - Raw error message (fallback)
 * @param errorDetails - Optional translated error details with user-friendly message
 * @param phaseContext - Optional phase context for stage-aware error messaging
 */
export async function notifyJobError(
  userId: string | null | undefined,
  email: string,
  jobId: string,
  niche: string,
  errorMessage: string,
  errorDetails?: ErrorDetails | null,
  phaseContext?: PhaseContextForEmail | null
): Promise<void> {
  if (!(await shouldNotifyUser(userId, 'jobError', jobId))) {
    console.log(`[Notification] Skipping failure email for job ${jobId} - disabled by preference`);
    return;
  }
  await sendFailureEmail(email, jobId, niche, errorMessage, errorDetails, phaseContext);
}

/**
 * Send solutions ready email if user preferences allow
 */
export async function notifySolutionsReady(
  userId: string | null | undefined,
  email: string,
  jobId: string,
  niche: string,
  solutionCount: number
): Promise<void> {
  if (!(await shouldNotifyUser(userId, 'solutionsReady', jobId))) {
    console.log(`[Notification] Skipping solutions-ready email for job ${jobId} - disabled by preference`);
    return;
  }
  await sendSolutionsReadyEmail(email, jobId, niche, solutionCount);
}

/**
 * Send guided-mode gate-reached email if user preferences allow (Phase B — mirrors
 * notifySolutionsReady; reuses the 'solutionsReady' preference bucket — both are
 * "your run needs your attention" notifications and the plan does not call for a new
 * dedicated preference field/migration for this).
 */
export async function notifyGateReached(
  userId: string | null | undefined,
  email: string,
  jobId: string,
  niche: string,
  gateStage: 1 | 4
): Promise<void> {
  if (!(await shouldNotifyUser(userId, 'solutionsReady', jobId))) {
    console.log(`[Notification] Skipping gate-reached email for job ${jobId} - disabled by preference`);
    return;
  }
  await sendGateReachedEmail(email, jobId, niche, gateStage);
}

/**
 * Send Phase 2 start email if user preferences allow
 */
export async function notifyPhase2Start(
  userId: string | null | undefined,
  email: string,
  jobId: string,
  niche: string,
  selectedSolutions: string[]
): Promise<void> {
  if (!(await shouldNotifyUser(userId, 'jobStart', jobId))) {
    console.log(`[Notification] Skipping phase 2 start email for job ${jobId} - disabled by preference`);
    return;
  }
  await sendPhase2StartEmail(email, jobId, niche, selectedSolutions);
}

/**
 * Send regeneration complete email if user preferences allow
 */
export async function notifyRegenerationComplete(
  userId: string | null | undefined,
  email: string,
  jobId: string,
  niche: string,
  newSolutionCount: number,
  totalSolutionCount: number
): Promise<void> {
  if (!(await shouldNotifyUser(userId, 'solutionsReady', jobId))) {
    console.log(`[Notification] Skipping regeneration-complete email for job ${jobId} - disabled by preference`);
    return;
  }
  await sendRegenerationCompleteEmail(email, jobId, niche, newSolutionCount, totalSolutionCount);
}

/**
 * Send selection reminder email if user preferences allow
 */
export async function notifySelectionReminder(
  userId: string | null | undefined,
  email: string,
  jobId: string,
  niche: string,
  solutionCount: number
): Promise<void> {
  if (!(await shouldNotifyUser(userId, 'solutionsReady', jobId))) {
    console.log(`[Notification] Skipping selection reminder email for job ${jobId} - disabled by preference`);
    return;
  }
  await sendSelectionReminderEmail(email, jobId, niche, solutionCount);
}

/**
 * Send landing page ready email if user preferences allow.
 * Reuses the jobComplete preference — no schema migration needed.
 */
export async function notifyLandingPageReady(
  userId: string | null | undefined,
  email: string,
  jobId: string,
  niche: string
): Promise<void> {
  if (!(await shouldNotifyUser(userId, 'jobComplete', jobId))) {
    console.log(`[Notification] Skipping landing page email for job ${jobId} - disabled by preference`);
    return;
  }
  await sendLandingPageReadyEmail(email, jobId, niche);
}
