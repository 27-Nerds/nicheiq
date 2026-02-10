/**
 * Selection Reminder Service
 *
 * Monitors jobs in AWAITING_SELECTION state and sends periodic
 * reminder emails to users who haven't selected a solution.
 *
 * Schedule: 24h (1st), 72h (2nd), 120h (3rd) after awaitingSelectionAt
 */

import { prisma } from './db.js';
import { JobStatus } from '@prisma/client';
import { notifySelectionReminder } from './notificationService.js';

const CHECK_INTERVAL_MS = 60 * 60 * 1000; // 1 hour
const MAX_REMINDERS = 3;

// Reminder thresholds in milliseconds
const REMINDER_THRESHOLDS_MS = [
  24 * 60 * 60 * 1000,   // 24h for 1st reminder
  72 * 60 * 60 * 1000,   // 72h for 2nd reminder
  120 * 60 * 60 * 1000,  // 120h for 3rd reminder
];

let checkInterval: NodeJS.Timeout | null = null;
let isRunning = false;

/**
 * Check for jobs needing selection reminders and send them
 */
export async function checkAndSendReminders(): Promise<void> {
  try {
    const jobs = await prisma.job.findMany({
      where: {
        status: JobStatus.AWAITING_SELECTION,
        selectionReminderCount: { lt: MAX_REMINDERS },
        awaitingSelectionAt: { not: null },
      },
      select: {
        id: true,
        niche: true,
        userId: true,
        awaitingSelectionAt: true,
        selectionReminderCount: true,
        lastReminderSentAt: true,
        solutionIdeas: true,
      },
    });

    const now = Date.now();

    for (const job of jobs) {
      if (!job.awaitingSelectionAt || !job.userId) continue;

      const elapsed = now - job.awaitingSelectionAt.getTime();
      const nextReminderIndex = job.selectionReminderCount;

      if (nextReminderIndex >= MAX_REMINDERS) continue;

      const threshold = REMINDER_THRESHOLDS_MS[nextReminderIndex];
      if (elapsed < threshold) continue;

      // Time to send a reminder
      try {
        const user = await prisma.user.findUnique({
          where: { id: job.userId },
          select: { email: true },
        });

        if (user?.email) {
          const solutionCount = Array.isArray(job.solutionIdeas)
            ? (job.solutionIdeas as any[]).length
            : 0;

          await notifySelectionReminder(
            job.userId,
            user.email,
            job.id,
            job.niche,
            solutionCount
          );

          await prisma.job.update({
            where: { id: job.id },
            data: {
              selectionReminderCount: { increment: 1 },
              lastReminderSentAt: new Date(),
            },
          });

          console.log(`[SelectionReminder] Sent reminder #${nextReminderIndex + 1} for job ${job.id}`);
        }
      } catch (err) {
        console.error(`[SelectionReminder] Failed to send reminder for job ${job.id}:`, err);
      }
    }
  } catch (error) {
    console.error('[SelectionReminder] Check error:', error);
  }
}

/**
 * Start the selection reminder monitoring service
 */
export function startSelectionReminderMonitor(): void {
  if (isRunning) {
    console.log('[SelectionReminder] Monitor already running');
    return;
  }

  isRunning = true;
  console.log(`[SelectionReminder] Starting monitor (check interval: ${CHECK_INTERVAL_MS / 1000}s)`);

  // Start periodic checking
  checkInterval = setInterval(async () => {
    await checkAndSendReminders();
  }, CHECK_INTERVAL_MS);
}

/**
 * Stop the selection reminder monitoring service
 */
export function stopSelectionReminderMonitor(): void {
  if (!isRunning) return;

  isRunning = false;
  if (checkInterval) {
    clearInterval(checkInterval);
    checkInterval = null;
  }
  console.log('[SelectionReminder] Monitor stopped');
}
