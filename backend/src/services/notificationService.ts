import { prisma } from './db.js';
import { sendCompletionEmail, sendFailureEmail, sendJobStartEmail, sendSolutionsReadyEmail, sendSelectionReminderEmail, sendPhase2StartEmail, sendRegenerationCompleteEmail, sendLandingPageReadyEmail, sendGateReachedEmail } from './emailService.js';
import type { IdeaCheckEmailContext, PhaseContextForEmail } from './emailService.js';
import { loadCurrentSelectionContext } from './currentSelectionContext.js';

export type NotificationType = 'jobStart' | 'jobComplete' | 'jobError' | 'solutionsReady';

/**
 * What an AWAITING_SELECTION email may say about the idea the user submitted.
 *
 * THE SEVENTEENTH SURFACE (2026-08-14). A refused `validate_idea` run is non-fatal by
 * design: Phase 1 finishes, the pool ships, the job reaches AWAITING_SELECTION — and that
 * fires `notifySolutionsReady`, then up to three `notifySelectionReminder` sends at 24h,
 * 72h and 120h. On a `validate_idea` run `Job.niche` IS the user's raw pitch, so the
 * reminder read "you have N VALIDATED solutions waiting for your review FOR '<their own
 * pitch>'" — the most direct assertion in the codebase that their submitted idea was
 * evaluated, arriving up to four times over five days for a run that refused to evaluate
 * it. Sixteen rounds of sweeps missed it because every one of them was applied to a
 * rendered page; this surface leaves the product, and no page fix can reach an inbox.
 *
 * Deliberately the same four states as `ideaCheckFraming` (routes/chat.ts), read from the
 * same artifact field, because both answer the same question: what may we assert about the
 * user's idea? It is not shared code — that function's input is the analyst dossier bundle
 * — but the two must never disagree about the mapping, so the states and their meanings are
 * kept identical on purpose.
 *
 * - `none`          — not an idea-check run. Every email is byte-identical to before.
 * - `evaluated`     — a spec was built and graded. Also byte-identical: the claim is true.
 * - `not_evaluated` — the run refused to grade it (six typed causes, all ours). The email
 *                     says so, in the artifact's own words, and drops every validation claim.
 * - `unavailable`   — an idea-check run whose verified artifact did not load. Asserting
 *                     either of the two states above would be a guess, so the email states
 *                     neither and simply reports the pool. Same doctrine as
 *                     `ResearchProgressScreen`'s "unknown" default.
 */
export type IdeaCheckEmailState = IdeaCheckEmailContext['state'];

/**
 * Resolve what this job's AWAITING_SELECTION emails may claim about the submitted idea.
 *
 * Reads the SAME `PREVIEW_REPORT` artifact the page reads, through the same verifier, so
 * the inbox and the page can never disagree. Any failure resolves to `unavailable`, which
 * asserts nothing — a notification must never block or crash a run.
 */
export async function resolveIdeaCheckEmailContext(
  jobId: string,
): Promise<IdeaCheckEmailContext> {
  try {
    const job = await prisma.job.findUnique({
      where: { id: jobId },
      select: { entryMode: true, niche: true },
    });
    if (job?.entryMode !== 'validate_idea') return { state: 'none' };

    const context = await loadCurrentSelectionContext(prisma, jobId);
    const artifacts = context?.runArtifacts;
    if (!artifacts || artifacts.verification !== 'verified') return { state: 'unavailable' };

    const iv = artifacts.previewReport.idea_validation;
    if (!iv || typeof iv !== 'object' || Array.isArray(iv)) return { state: 'unavailable' };

    const block = iv as Record<string, unknown>;
    if (String(block.outcome ?? '') !== 'not_evaluated') return { state: 'evaluated' };

    // Both sentences come VERBATIM from the artifact, which sources them from
    // `SEED_FAILURE_COPY` (src/nicheiq/report/idea_validation_block.py) — the single
    // source for the failure story. This program has already found a FOURTH
    // independently-authored refusal sentence; a fifth written here would be the same
    // defect. If the artifact carries neither, the email says the check did not complete
    // and stops there rather than inventing a reason.
    return {
      state: 'not_evaluated',
      headline: typeof block.headline === 'string' ? block.headline : null,
      nextStep: typeof block.failure_next_step === 'string' ? block.failure_next_step : null,
      pitch: typeof job.niche === 'string' ? job.niche : null,
    };
  } catch (err) {
    console.error(`[Notification] idea-check state unresolved for job ${jobId}:`, err);
    return { state: 'unavailable' };
  }
}

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
  await sendSolutionsReadyEmail(
    email, jobId, niche, solutionCount, await resolveIdeaCheckEmailContext(jobId),
  );
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
  // Resolved HERE, not passed in by the reminder service: the reminder runs on a schedule
  // off the DB, up to five days after the run ended, so it has no in-memory knowledge of
  // the outcome and must read the persisted artifact like every other consumer.
  await sendSelectionReminderEmail(
    email, jobId, niche, solutionCount, await resolveIdeaCheckEmailContext(jobId),
  );
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
