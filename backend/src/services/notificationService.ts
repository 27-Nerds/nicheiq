import { prisma } from './db.js';
import { sendCompletionEmail, sendFailureEmail, sendJobStartEmail, sendSolutionsReadyEmail, sendSelectionReminderEmail } from './emailService.js';

export type NotificationType = 'jobStart' | 'jobComplete' | 'jobError' | 'solutionsReady';

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
  notificationType: NotificationType
): Promise<boolean> {
  if (!userId) return false;

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
  if (!(await shouldNotifyUser(userId, 'jobStart'))) {
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
  if (!(await shouldNotifyUser(userId, 'jobComplete'))) {
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
 */
export async function notifyJobError(
  userId: string | null | undefined,
  email: string,
  jobId: string,
  niche: string,
  errorMessage: string,
  errorDetails?: ErrorDetails | null
): Promise<void> {
  if (!(await shouldNotifyUser(userId, 'jobError'))) {
    console.log(`[Notification] Skipping failure email for job ${jobId} - disabled by preference`);
    return;
  }
  await sendFailureEmail(email, jobId, niche, errorMessage, errorDetails);
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
  if (!(await shouldNotifyUser(userId, 'solutionsReady'))) {
    console.log(`[Notification] Skipping solutions-ready email for job ${jobId} - disabled by preference`);
    return;
  }
  await sendSolutionsReadyEmail(email, jobId, niche, solutionCount);
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
  if (!(await shouldNotifyUser(userId, 'solutionsReady'))) {
    console.log(`[Notification] Skipping selection reminder email for job ${jobId} - disabled by preference`);
    return;
  }
  await sendSelectionReminderEmail(email, jobId, niche, solutionCount);
}
