import nodemailer from 'nodemailer';
import sgMail from '@sendgrid/mail';
import { readFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { CONFIG } from '../config.js';
import { translateError } from '../utils/errorTranslator.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const TEMPLATES_DIR = join(__dirname, '../templates/email');

// Initialize SendGrid if API key is provided
if (CONFIG.email.sendgrid.apiKey) {
  sgMail.setApiKey(CONFIG.email.sendgrid.apiKey);
}

// Create SMTP transporter (used when provider is 'smtp')
const smtpTransporter = nodemailer.createTransport({
  host: CONFIG.email.smtp.host,
  port: CONFIG.email.smtp.port,
  secure: CONFIG.email.smtp.port === 465,
  auth: CONFIG.email.smtp.user && CONFIG.email.smtp.password ? {
    user: CONFIG.email.smtp.user,
    pass: CONFIG.email.smtp.password,
  } : undefined,
});

// Template cache
const templateCache: Map<string, string> = new Map();

/**
 * Load and cache a template file
 */
function loadTemplate(name: string): string {
  const cached = templateCache.get(name);
  if (cached) return cached;

  const content = readFileSync(join(TEMPLATES_DIR, name), 'utf-8');
  templateCache.set(name, content);
  return content;
}

/**
 * Escape a value for interpolation into HTML template markup. Attribute-safe:
 * several templates place {{NICHE}} inside double quotes, so " and ' are escaped too.
 */
function escapeHtml(value: string): string {
  const map: Record<string, string> = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  };
  return value.replace(/[&<>"']/g, (ch) => map[ch]);
}

/**
 * Replace template placeholders with values.
 *
 * The replacement uses a function form deliberately: with a string replacement,
 * `$&`, `$$`, `` $` `` and `$'` inside the VALUE (e.g. a niche like "saves $$$")
 * are interpreted as replacement patterns and corrupt the output.
 */
function renderTemplate(template: string, vars: Record<string, string>, escapeValues = false): string {
  let result = template;
  for (const [key, value] of Object.entries(vars)) {
    const safe = escapeValues ? escapeHtml(value) : value;
    result = result.replace(new RegExp(`{{${key}}}`, 'g'), () => safe);
  }
  return result;
}

/**
 * Truncate niche string for display
 */
function truncateNiche(niche: string, maxLength = 100): string {
  return niche.length > maxLength ? niche.substring(0, maxLength) + '...' : niche;
}

/**
 * Check if email is configured
 */
function isEmailConfigured(): boolean {
  if (CONFIG.email.provider === 'sendgrid') {
    return !!CONFIG.email.sendgrid.apiKey;
  }
  return !!CONFIG.email.smtp.host;
}

/**
 * Send email using configured provider
 */
async function sendEmail(
  to: string,
  subject: string,
  text: string,
  html: string
): Promise<void> {
  if (!isEmailConfigured()) {
    console.log('Email not configured, skipping notification');
    return;
  }

  const from = CONFIG.email.fromEmail;

  if (CONFIG.email.provider === 'sendgrid') {
    await sgMail.send({
      to,
      from,
      subject,
      text,
      html,
    });
  } else {
    await smtpTransporter.sendMail({
      from,
      to,
      subject,
      text,
      html,
    });
  }
}

/**
 * Send job start notification email
 */
export async function sendJobStartEmail(
  to: string,
  jobId: string,
  niche: string
): Promise<void> {
  const vars = {
    JOB_ID: jobId,
    NICHE: truncateNiche(niche),
    STATUS_URL: `${CONFIG.baseUrl}/jobs/${jobId}`,
  };

  try {
    const html = renderTemplate(loadTemplate('jobStart.html'), vars, true);
    const text = renderTemplate(loadTemplate('jobStart.txt'), vars);

    await sendEmail(to, 'Your NicheIQ Research Has Started!', text, html);
    console.log(`Start email sent to ${to} for job ${jobId}`);
  } catch (error) {
    console.error('Failed to send start email:', error);
  }
}

/**
 * Send job completion notification email
 */
export async function sendCompletionEmail(
  to: string,
  jobId: string,
  niche: string
): Promise<void> {
  const vars = {
    JOB_ID: jobId,
    NICHE: truncateNiche(niche),
    STATUS_URL: `${CONFIG.baseUrl}/jobs/${jobId}`,
    REPORT_URL: `${CONFIG.baseUrl}/api/jobs/${jobId}/report`,
    LANDING_URL: `${CONFIG.baseUrl}/api/jobs/${jobId}/landing`,
  };

  try {
    const html = renderTemplate(loadTemplate('jobComplete.html'), vars, true);
    const text = renderTemplate(loadTemplate('jobComplete.txt'), vars);

    await sendEmail(to, 'Your NicheIQ Research is Ready!', text, html);
    console.log(`Completion email sent to ${to} for job ${jobId}`);
  } catch (error) {
    console.error('Failed to send completion email:', error);
  }
}

/**
 * Send landing page ready notification email
 */
export async function sendLandingPageReadyEmail(
  to: string,
  jobId: string,
  niche: string
): Promise<void> {
  const vars = {
    JOB_ID: jobId,
    NICHE: truncateNiche(niche),
    STATUS_URL: `${CONFIG.baseUrl}/jobs/${jobId}`,
  };

  try {
    const html = renderTemplate(loadTemplate('landingPageReady.html'), vars, true);
    const text = renderTemplate(loadTemplate('landingPageReady.txt'), vars);

    await sendEmail(to, 'Your NicheIQ Landing Page is Ready!', text, html);
    console.log(`Landing page email sent to ${to} for job ${jobId}`);
  } catch (error) {
    console.error('Failed to send landing page email:', error);
  }
}

/**
 * Error details interface for user-friendly error messages
 */
interface ErrorDetails {
  userMessage?: string;
  actionableGuidance?: string;
}

/**
 * Phase context for stage-aware error emails
 */
export interface PhaseContextForEmail {
  phaseLabel: string;
  guidance: string;
}

/**
 * Send job failure notification email
 *
 * @param to - Recipient email
 * @param jobId - The job ID
 * @param niche - The job's niche
 * @param errorMessage - Raw error message (fallback)
 * @param errorDetails - Optional translated error details with user-friendly message
 * @param phaseContext - Optional phase context to enrich error messaging
 */
export async function sendFailureEmail(
  to: string,
  jobId: string,
  niche: string,
  errorMessage: string,
  errorDetails?: ErrorDetails | null,
  phaseContext?: PhaseContextForEmail | null
): Promise<void> {
  // `errorMessage` is the RAW stored job error — worker text, a traceback, or an internal token
  // like `RESUME_NOT_FAILED:QUEUED`. It is a debugging handle, not copy, and echoing it into an
  // email was the leak. Callers that have a translation pass one; the ones that do not (the
  // heartbeat stall path, and the worker `data.error` progress path) used to fall straight
  // through to the raw string.
  //
  // So the fallback is the translator every other error surface already uses, rather than the
  // raw text: unclassifiable input resolves to INTERNAL_ERROR, whose userMessage/guidance are
  // fixed copy. `rawMessage` keeps the original for the debugging channel without rendering it.
  const fallback = translateError('INTERNAL_ERROR', errorMessage);
  let displayMessage = errorDetails?.userMessage || fallback.userMessage;
  let guidance = errorDetails?.actionableGuidance || fallback.actionableGuidance;

  // Enrich with phase context if provided
  if (phaseContext) {
    displayMessage = `${phaseContext.phaseLabel}: ${displayMessage}`;
    guidance = `${guidance} ${phaseContext.guidance}`;
  }

  const vars = {
    JOB_ID: jobId,
    NICHE: truncateNiche(niche),
    STATUS_URL: `${CONFIG.baseUrl}/jobs/${jobId}`,
    ERROR_MESSAGE: displayMessage,
    GUIDANCE: guidance,
  };

  try {
    const html = renderTemplate(loadTemplate('jobError.html'), vars, true);
    const text = renderTemplate(loadTemplate('jobError.txt'), vars);

    await sendEmail(to, 'NicheIQ Research Issue', text, html);
    console.log(`Failure email sent to ${to} for job ${jobId}`);
  } catch (error) {
    console.error('Failed to send failure email:', error);
  }
}

/**
 * What the two AWAITING_SELECTION emails may say about a submitted idea.
 * Resolved by `resolveIdeaCheckEmailContext` (notificationService), which documents the
 * four states and why they mirror `ideaCheckFraming` in routes/chat.ts.
 *
 * `headline` and `nextStep` are read VERBATIM off the persisted artifact, which sources
 * them from `SEED_FAILURE_COPY` (src/nicheiq/report/idea_validation_block.py). No refusal
 * sentence is written in this file: the program has already found four independently
 * authored ones, and a fifth here would be the same defect in the one channel that leaves
 * the product.
 */
export interface IdeaCheckEmailContext {
  state: 'none' | 'evaluated' | 'not_evaluated' | 'unavailable';
  headline?: string | null;
  nextStep?: string | null;
  /** The raw pitch — on a `validate_idea` run `Job.niche` IS what the user submitted. */
  pitch?: string | null;
}

const NO_IDEA_CHECK: IdeaCheckEmailContext = { state: 'none' };

/**
 * S15 — THE CHARGE THAT ALREADY STANDS. Decided 2026-08-15 (owner): a refused idea check
 * keeps the full discovery charge, with disclosure.
 *
 * This is the ONE sentence in this file that is not read off the artifact, and deliberately
 * so. `headline` and `nextStep` describe what happened on one run and are true of it forever,
 * which is why they are persisted and quoted; this states a LIVE commercial policy, and a
 * policy frozen into stored reports would keep being quoted after it changed.
 *
 * The emails need it because they are the only refusal surface that leaves the product: they
 * quote "Run the check again" verbatim from `SEED_FAILURE_COPY`, arrive up to four times over
 * five days, and mention money nowhere — so "the failure is ours" plus "run it again" reads
 * as a run that cost nothing. No page fix reaches an inbox.
 *
 * BYTE-IDENTICAL to `CHARGE_STANDS` in
 * `frontend/src/lib/components/sections/ValidationVerdict.svelte`, pinned by
 * `__tests__/emailService.ideaCheck.test.ts`, which reads both files. Two deployables, one
 * sentence; a second wording would be the independently-authored-refusal-copy defect this
 * program has already found four times.
 *
 * It says NOTHING about what a retry costs. That is a separate fact on a separate line (the
 * page's `rerunPriceRecord`), kept separately replaceable: whether a retry stays a full-price
 * new run is an open question, and this sentence is true either way.
 */
const IDEA_CHECK_CHARGE_NOTE =
  'You were charged in full for this run. Everything else in it completed; the check on '
  + "your idea did not, and we don't refund that charge.";

/**
 * The plain-text refusal note, or '' for every other state.
 *
 * The charge line is UNCONDITIONAL on a refusal: it depends on no artifact field, so a report
 * that carries neither sentence — every refusal materialized before 2026-08-14 — still gets
 * it. The two quoted sentences stay conditional for the reason they always were: the lead
 * already says the check did not happen, and writing a reason here is the copy source this
 * file exists to avoid creating.
 */
function ideaCheckNoteText(ctx: IdeaCheckEmailContext): string {
  if (ctx.state !== 'not_evaluated') return '';
  const lines: string[] = [];
  if (ctx.pitch) lines.push(`Your submission: "${truncateNiche(ctx.pitch)}"`);
  if (ctx.headline) lines.push(`What happened: ${ctx.headline}`);
  if (ctx.nextStep) lines.push(`What to do next: ${ctx.nextStep}`);
  lines.push(`What this cost: ${IDEA_CHECK_CHARGE_NOTE}`);
  return `\n\n${lines.join('\n\n')}`;
}

/** The same note as an HTML block, or '' — inserted UNESCAPED, so every value is escaped here. */
function ideaCheckNoteHtml(ctx: IdeaCheckEmailContext): string {
  if (ctx.state !== 'not_evaluated') return '';
  const rows: string[] = [];
  if (ctx.pitch) rows.push(`Your submission: "${escapeHtml(truncateNiche(ctx.pitch))}"`);
  if (ctx.headline) rows.push(`What happened: ${escapeHtml(ctx.headline)}`);
  if (ctx.nextStep) rows.push(`What to do next: ${escapeHtml(ctx.nextStep)}`);
  rows.push(`What this cost: ${escapeHtml(IDEA_CHECK_CHARGE_NOTE)}`);
  const paragraphs = rows
    .map((row, i) => `      <p style="margin: 0${i === rows.length - 1 ? '' : ' 0 10px'}; color: #52525B;">${row}</p>`)
    .join('\n');
  return [
    '    <div style="background: white; border-radius: 8px; padding: 20px; margin-bottom: 25px; border: 1px solid rgba(0,0,0,0.07);">',
    paragraphs,
    '    </div>',
    '',
  ].join('\n');
}

/**
 * Send solutions ready notification email
 *
 * `ideaCheck` defaults to `none`, the state that renders the pre-2026-08-14 copy verbatim:
 * a caller that cannot resolve the outcome never invents a refusal, and a discovery run is
 * byte-identical to before. Only `not_evaluated` and `unavailable` change anything.
 */
export async function sendSolutionsReadyEmail(
  to: string,
  jobId: string,
  niche: string,
  solutionCount: number,
  ideaCheck: IdeaCheckEmailContext = NO_IDEA_CHECK
): Promise<void> {
  const refused = ideaCheck.state === 'not_evaluated';
  // `unavailable` gets the same wording as a refusal minus the refusal: we cannot read the
  // outcome, so the email reports the pool and asserts nothing about the submitted idea.
  const unclaimed = refused || ideaCheck.state === 'unavailable';
  const count = String(solutionCount);
  const displayNiche = truncateNiche(niche);

  const vars = {
    JOB_ID: jobId,
    NICHE: displayNiche,
    SOLUTION_COUNT: count,
    STATUS_URL: `${CONFIG.baseUrl}/jobs/${jobId}`,
    LEAD: refused
      ? `We've generated ${count} solutions from this run's market evidence. We could not check the idea you submitted — that failure is ours, not a problem with what you wrote.`
      : unclaimed
        ? `We've generated ${count} solutions for your review.`
        : `We've generated ${count} solutions for your research on "${displayNiche}".`,
    // "validation scores" is true of the pool everywhere, but on an idea-check run it lands
    // one line under the user's own pitch and reads as a verdict on it.
    REVIEW_BULLET: unclaimed
      ? 'Review the solutions and their scores'
      : 'Review the solutions and their validation scores',
    IDEA_CHECK_NOTE: ideaCheckNoteText(ideaCheck),
  };
  const htmlVars = {
    LEAD_HTML: refused
      ? `We've generated <strong>${count} solutions</strong> from this run's market evidence. We could not check the idea you submitted — that failure is ours, not a problem with what you wrote.`
      : unclaimed
        ? `We've generated <strong>${count} solutions</strong> for your review.`
        : `We've generated <strong>${count} solutions</strong> for your research on <strong>"${escapeHtml(displayNiche)}"</strong>.`,
    IDEA_CHECK_NOTE_HTML: ideaCheckNoteHtml(ideaCheck),
  };

  try {
    // Markup pass FIRST (its values are escaped at construction), user-value pass SECOND,
    // so nothing a user typed can land in a slot that is later substituted unescaped.
    const html = renderTemplate(
      renderTemplate(loadTemplate('solutionsReady.html'), htmlVars), vars, true,
    );
    const text = renderTemplate(loadTemplate('solutionsReady.txt'), vars);

    await sendEmail(
      to,
      refused
        ? 'Your NicheIQ solutions are ready — we could not check your idea'
        : 'Your NicheIQ Solutions Are Ready for Review!',
      text,
      html,
    );
    console.log(`Solutions ready email sent to ${to} for job ${jobId}`);
  } catch (error) {
    console.error('Failed to send solutions ready email:', error);
  }
}

/**
 * Send guided-mode gate-reached notification email (Phase B — G1/G2 stage gates).
 * Mirrors sendSolutionsReadyEmail: gates wait indefinitely (same semantics as
 * AWAITING_SELECTION), so this email IS the funnel back to a paused run.
 */
export async function sendGateReachedEmail(
  to: string,
  jobId: string,
  niche: string,
  gateStage: 1 | 4
): Promise<void> {
  const vars = {
    JOB_ID: jobId,
    NICHE: truncateNiche(niche),
    GATE_LABEL: gateStage === 1 ? 'niche validation' : 'audience mapping',
    STATUS_URL: `${CONFIG.baseUrl}/jobs/${jobId}`,
  };

  try {
    const html = renderTemplate(loadTemplate('gateReached.html'), vars, true);
    const text = renderTemplate(loadTemplate('gateReached.txt'), vars);

    await sendEmail(to, 'Your NicheIQ Research Is Waiting for You', text, html);
    console.log(`Gate reached email sent to ${to} for job ${jobId} (gate_stage=${gateStage})`);
  } catch (error) {
    console.error('Failed to send gate reached email:', error);
  }
}

/**
 * Send Phase 2 (deep research) start notification email
 */
export async function sendPhase2StartEmail(
  to: string,
  jobId: string,
  niche: string,
  selectedSolutions: string[]
): Promise<void> {
  const vars = {
    JOB_ID: jobId,
    NICHE: truncateNiche(niche),
    STATUS_URL: `${CONFIG.baseUrl}/jobs/${jobId}`,
    SELECTED_SOLUTIONS: selectedSolutions.join(', '),
  };

  try {
    const html = renderTemplate(loadTemplate('phase2Start.html'), vars, true);
    const text = renderTemplate(loadTemplate('phase2Start.txt'), vars);

    await sendEmail(to, 'Your NicheIQ Deep Research Has Begun!', text, html);
    console.log(`Phase 2 start email sent to ${to} for job ${jobId}`);
  } catch (error) {
    console.error('Failed to send phase 2 start email:', error);
  }
}

/**
 * Send regeneration complete notification email
 */
export async function sendRegenerationCompleteEmail(
  to: string,
  jobId: string,
  niche: string,
  newSolutionCount: number,
  totalSolutionCount: number
): Promise<void> {
  const vars = {
    JOB_ID: jobId,
    NICHE: truncateNiche(niche),
    STATUS_URL: `${CONFIG.baseUrl}/jobs/${jobId}`,
    BATCH_RESULT: newSolutionCount > 0
      ? `${newSolutionCount} new candidate${newSolutionCount === 1 ? '' : 's'} cleared the checks and were added. You now have ${totalSolutionCount} candidates to review.`
      : `The batch was evaluated, but no new candidates cleared the checks. Your existing ${totalSolutionCount} candidate${totalSolutionCount === 1 ? ' is' : 's are'} unchanged.`,
    BATCH_GUIDANCE: newSolutionCount > 0
      ? 'Compare the new candidates with the existing leaders. Nothing was added to your shortlist automatically.'
      : 'Review the ruled-out findings before deciding whether a different batch focus is worth trying.',
  };

  try {
    const html = renderTemplate(loadTemplate('regenerationComplete.html'), vars, true);
    const text = renderTemplate(loadTemplate('regenerationComplete.txt'), vars);

    await sendEmail(to, 'Your NicheIQ idea batch is ready', text, html);
    console.log(`Regeneration complete email sent to ${to} for job ${jobId}`);
  } catch (error) {
    console.error('Failed to send regeneration complete email:', error);
  }
}

/**
 * Send selection reminder notification email
 */
export async function sendSelectionReminderEmail(
  to: string,
  jobId: string,
  niche: string,
  solutionCount: number,
  ideaCheck: IdeaCheckEmailContext = NO_IDEA_CHECK
): Promise<void> {
  // THE SHARPEST SENTENCE IN THE PROGRAM. "you have N VALIDATED solutions waiting for your
  // review FOR '{{NICHE}}'" makes the user's own pitch the grammatical object of
  // "validated ... for", and this email is sent at 24h, 72h AND 120h — up to three more
  // assertions after the first one, on a run that refused to grade the pitch.
  const refused = ideaCheck.state === 'not_evaluated';
  const unclaimed = refused || ideaCheck.state === 'unavailable';
  const count = String(solutionCount);
  const displayNiche = truncateNiche(niche);

  const vars = {
    JOB_ID: jobId,
    NICHE: displayNiche,
    SOLUTION_COUNT: count,
    STATUS_URL: `${CONFIG.baseUrl}/jobs/${jobId}`,
    LEAD: refused
      ? `Just a reminder — you have ${count} solutions waiting for your review. This run could not check the idea you submitted; these came from the market evidence and stand on their own.`
      : unclaimed
        ? `Just a reminder — you have ${count} solutions waiting for your review.`
        : `Just a reminder — you have ${count} validated solutions waiting for your review for "${displayNiche}".`,
    IDEA_CHECK_NOTE: ideaCheckNoteText(ideaCheck),
  };
  const htmlVars = {
    LEAD_HTML: refused
      ? `Just a reminder — you have <strong>${count} solutions</strong> waiting for your review. This run could not check the idea you submitted; these came from the market evidence and stand on their own.`
      : unclaimed
        ? `Just a reminder — you have <strong>${count} solutions</strong> waiting for your review.`
        : `Just a reminder — you have <strong>${count} validated solutions</strong> waiting for your review for <strong>"${escapeHtml(displayNiche)}"</strong>.`,
    IDEA_CHECK_NOTE_HTML: ideaCheckNoteHtml(ideaCheck),
  };

  try {
    const html = renderTemplate(
      renderTemplate(loadTemplate('selectionReminder.html'), htmlVars), vars, true,
    );
    const text = renderTemplate(loadTemplate('selectionReminder.txt'), vars);

    await sendEmail(
      to,
      refused
        ? 'Reminder: your NicheIQ solutions are waiting (we could not check your idea)'
        : 'Reminder: Your NicheIQ Solutions Are Waiting',
      text,
      html,
    );
    console.log(`Selection reminder email sent to ${to} for job ${jobId}`);
  } catch (error) {
    console.error('Failed to send selection reminder email:', error);
  }
}

/**
 * Send credit bonus notification email
 */
export async function sendCreditBonusEmail(
  to: string,
  amount: number,
  reason: string,
  newBalance: number
): Promise<void> {
  const vars = {
    AMOUNT: String(amount),
    REASON: reason,
    NEW_BALANCE: String(newBalance),
    DASHBOARD_URL: `${CONFIG.baseUrl}/dashboard`,
  };

  try {
    const html = renderTemplate(loadTemplate('creditBonus.html'), vars, true);
    const text = renderTemplate(loadTemplate('creditBonus.txt'), vars);

    await sendEmail(to, "You've Received NicheIQ Credits!", text, html);
    console.log(`Credit bonus email sent to ${to} for ${amount} credits`);
  } catch (error) {
    console.error('Failed to send credit bonus email:', error);
  }
}

/**
 * Send password reset email with a one-time reset link
 */
export async function sendPasswordResetEmail(
  to: string,
  resetUrl: string
): Promise<void> {
  const vars = {
    RESET_URL: resetUrl,
  };

  try {
    const html = renderTemplate(loadTemplate('passwordReset.html'), vars, true);
    const text = renderTemplate(loadTemplate('passwordReset.txt'), vars);

    await sendEmail(to, 'Reset your NicheIQ password', text, html);
    console.log(`Password reset email sent to ${to}`);
  } catch (error) {
    console.error('Failed to send password reset email:', error);
  }
}

/**
 * Send a reminder that the account uses social sign-in (no password to reset)
 */
export async function sendSocialLoginReminderEmail(
  to: string,
  providerLabel: string,
  loginUrl: string
): Promise<void> {
  const vars = {
    PROVIDER: providerLabel,
    LOGIN_URL: loginUrl,
  };

  try {
    const html = renderTemplate(loadTemplate('socialLoginReminder.html'), vars, true);
    const text = renderTemplate(loadTemplate('socialLoginReminder.txt'), vars);

    await sendEmail(to, 'Sign in to NicheIQ', text, html);
    console.log(`Social login reminder email sent to ${to}`);
  } catch (error) {
    console.error('Failed to send social login reminder email:', error);
  }
}

/**
 * Test email configuration
 */
export async function verifyEmailConfig(): Promise<boolean> {
  if (!isEmailConfigured()) {
    console.log('Email not configured');
    return false;
  }

  try {
    if (CONFIG.email.provider === 'sendgrid') {
      // SendGrid doesn't have a verify method, just check API key exists
      console.log('SendGrid API key configured');
      return true;
    } else {
      await smtpTransporter.verify();
      console.log('SMTP configuration verified');
      return true;
    }
  } catch (error) {
    console.error('Email configuration error:', error);
    return false;
  }
}

/**
 * Get current email provider
 */
export function getEmailProvider(): string {
  return CONFIG.email.provider;
}
