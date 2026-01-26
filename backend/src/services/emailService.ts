import nodemailer from 'nodemailer';
import sgMail from '@sendgrid/mail';
import { readFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { CONFIG } from '../config.js';

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
 * Replace template placeholders with values
 */
function renderTemplate(template: string, vars: Record<string, string>): string {
  let result = template;
  for (const [key, value] of Object.entries(vars)) {
    result = result.replace(new RegExp(`{{${key}}}`, 'g'), value);
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
    const html = renderTemplate(loadTemplate('jobStart.html'), vars);
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
    const html = renderTemplate(loadTemplate('jobComplete.html'), vars);
    const text = renderTemplate(loadTemplate('jobComplete.txt'), vars);

    await sendEmail(to, 'Your NicheIQ Research is Ready!', text, html);
    console.log(`Completion email sent to ${to} for job ${jobId}`);
  } catch (error) {
    console.error('Failed to send completion email:', error);
  }
}

/**
 * Send job failure notification email
 */
export async function sendFailureEmail(
  to: string,
  jobId: string,
  niche: string,
  errorMessage: string
): Promise<void> {
  const vars = {
    JOB_ID: jobId,
    NICHE: truncateNiche(niche),
    STATUS_URL: `${CONFIG.baseUrl}/jobs/${jobId}`,
    ERROR_MESSAGE: errorMessage,
  };

  try {
    const html = renderTemplate(loadTemplate('jobError.html'), vars);
    const text = renderTemplate(loadTemplate('jobError.txt'), vars);

    await sendEmail(to, 'NicheIQ Research Issue', text, html);
    console.log(`Failure email sent to ${to} for job ${jobId}`);
  } catch (error) {
    console.error('Failed to send failure email:', error);
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
