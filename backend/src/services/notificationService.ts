import { prisma } from './db.js';
import { sendCompletionEmail, sendFailureEmail, sendJobStartEmail } from './emailService.js';

export type NotificationType = 'jobStart' | 'jobComplete' | 'jobError';

const DEFAULT_PREFERENCES = {
  emailEnabled: true,
  emailOnJobStart: true,
  emailOnJobComplete: true,
  emailOnJobError: true,
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
 * Send job failure email if user preferences allow
 */
export async function notifyJobError(
  userId: string | null | undefined,
  email: string,
  jobId: string,
  niche: string,
  errorMessage: string
): Promise<void> {
  if (!(await shouldNotifyUser(userId, 'jobError'))) {
    console.log(`[Notification] Skipping failure email for job ${jobId} - disabled by preference`);
    return;
  }
  await sendFailureEmail(email, jobId, niche, errorMessage);
}
