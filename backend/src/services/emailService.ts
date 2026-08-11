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
 * Send solutions ready notification email
 */
export async function sendSolutionsReadyEmail(
  to: string,
  jobId: string,
  niche: string,
  solutionCount: number
): Promise<void> {
  const vars = {
    JOB_ID: jobId,
    NICHE: truncateNiche(niche),
    SOLUTION_COUNT: String(solutionCount),
    STATUS_URL: `${CONFIG.baseUrl}/jobs/${jobId}`,
  };

  try {
    const html = renderTemplate(loadTemplate('solutionsReady.html'), vars, true);
    const text = renderTemplate(loadTemplate('solutionsReady.txt'), vars);

    await sendEmail(to, 'Your NicheIQ Solutions Are Ready for Review!', text, html);
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
  solutionCount: number
): Promise<void> {
  const vars = {
    JOB_ID: jobId,
    NICHE: truncateNiche(niche),
    SOLUTION_COUNT: String(solutionCount),
    STATUS_URL: `${CONFIG.baseUrl}/jobs/${jobId}`,
  };

  try {
    const html = renderTemplate(loadTemplate('selectionReminder.html'), vars, true);
    const text = renderTemplate(loadTemplate('selectionReminder.txt'), vars);

    await sendEmail(to, 'Reminder: Your NicheIQ Solutions Are Waiting', text, html);
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
