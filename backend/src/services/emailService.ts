import nodemailer from 'nodemailer';
import { CONFIG } from '../config.js';

// Create reusable transporter
const transporter = nodemailer.createTransport({
  host: CONFIG.smtp.host,
  port: CONFIG.smtp.port,
  secure: CONFIG.smtp.port === 465, // true for 465, false for other ports
  auth: CONFIG.smtp.user && CONFIG.smtp.password ? {
    user: CONFIG.smtp.user,
    pass: CONFIG.smtp.password,
  } : undefined,
});

/**
 * Send job completion notification email
 */
export async function sendCompletionEmail(
  to: string,
  jobId: string,
  niche: string
): Promise<void> {
  if (!CONFIG.smtp.host || !CONFIG.smtp.fromEmail) {
    console.log('Email not configured, skipping notification');
    return;
  }

  const statusUrl = `${CONFIG.baseUrl}/jobs/${jobId}`;
  const reportUrl = `${CONFIG.baseUrl}/api/jobs/${jobId}/report`;
  const landingUrl = `${CONFIG.baseUrl}/api/jobs/${jobId}/landing`;

  const htmlContent = `
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Your NicheIQ Research is Ready!</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
  <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px 10px 0 0; text-align: center;">
    <h1 style="color: white; margin: 0; font-size: 28px;">Your Research is Ready!</h1>
  </div>

  <div style="background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; border: 1px solid #eee; border-top: none;">
    <p style="font-size: 16px; margin-bottom: 20px;">
      Great news! Your market research for <strong>"${niche.substring(0, 100)}${niche.length > 100 ? '...' : ''}"</strong> has been completed.
    </p>

    <div style="background: white; border-radius: 8px; padding: 20px; margin-bottom: 25px; border: 1px solid #eee;">
      <h2 style="margin-top: 0; color: #444; font-size: 18px;">What's included:</h2>
      <ul style="padding-left: 20px; color: #555;">
        <li>Comprehensive market research report (JSON)</li>
        <li>Pain point analysis from real user discussions</li>
        <li>Solution recommendations with competitive analysis</li>
        <li>SEO strategy with validated keywords</li>
        <li>Ready-to-use landing page (HTML)</li>
      </ul>
    </div>

    <div style="text-align: center; margin-bottom: 25px;">
      <a href="${statusUrl}" style="display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; text-decoration: none; padding: 14px 32px; border-radius: 6px; font-weight: 600; font-size: 16px;">
        View Your Results
      </a>
    </div>

    <div style="border-top: 1px solid #eee; padding-top: 20px;">
      <p style="font-size: 14px; color: #666; margin-bottom: 10px;">
        <strong>Quick Links:</strong>
      </p>
      <p style="font-size: 14px; margin: 5px 0;">
        <a href="${reportUrl}" style="color: #667eea;">Download Research Report (JSON)</a>
      </p>
      <p style="font-size: 14px; margin: 5px 0;">
        <a href="${landingUrl}" style="color: #667eea;">View Landing Page</a>
      </p>
      <p style="font-size: 14px; margin: 5px 0;">
        <a href="${landingUrl}?download=true" style="color: #667eea;">Download Landing Page (HTML)</a>
      </p>
    </div>
  </div>

  <div style="text-align: center; padding: 20px; color: #888; font-size: 12px;">
    <p>This email was sent by NicheIQ</p>
    <p>Job ID: ${jobId}</p>
  </div>
</body>
</html>
  `;

  const textContent = `
Your NicheIQ Research is Ready!

Great news! Your market research for "${niche.substring(0, 100)}${niche.length > 100 ? '...' : ''}" has been completed.

What's included:
- Comprehensive market research report (JSON)
- Pain point analysis from real user discussions
- Solution recommendations with competitive analysis
- SEO strategy with validated keywords
- Ready-to-use landing page (HTML)

View Your Results: ${statusUrl}

Quick Links:
- Download Research Report: ${reportUrl}
- View Landing Page: ${landingUrl}
- Download Landing Page: ${landingUrl}?download=true

Job ID: ${jobId}
  `;

  try {
    await transporter.sendMail({
      from: CONFIG.smtp.fromEmail,
      to,
      subject: 'Your NicheIQ Research is Ready!',
      text: textContent,
      html: htmlContent,
    });

    console.log(`Completion email sent to ${to} for job ${jobId}`);
  } catch (error) {
    console.error('Failed to send completion email:', error);
    // Don't throw - email failure shouldn't break the flow
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
  if (!CONFIG.smtp.host || !CONFIG.smtp.fromEmail) {
    console.log('Email not configured, skipping notification');
    return;
  }

  const statusUrl = `${CONFIG.baseUrl}/jobs/${jobId}`;

  const htmlContent = `
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>NicheIQ Research Update</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
  <div style="background: #e74c3c; padding: 30px; border-radius: 10px 10px 0 0; text-align: center;">
    <h1 style="color: white; margin: 0; font-size: 28px;">Research Issue</h1>
  </div>

  <div style="background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; border: 1px solid #eee; border-top: none;">
    <p style="font-size: 16px; margin-bottom: 20px;">
      Unfortunately, there was an issue processing your research for <strong>"${niche.substring(0, 100)}${niche.length > 100 ? '...' : ''}"</strong>.
    </p>

    <div style="background: #fff5f5; border-radius: 8px; padding: 15px; margin-bottom: 25px; border: 1px solid #fed7d7;">
      <p style="margin: 0; color: #c53030; font-size: 14px;">
        <strong>Error:</strong> ${errorMessage}
      </p>
    </div>

    <p style="font-size: 14px; color: #666;">
      You can try submitting your research request again. If the problem persists, please contact support.
    </p>

    <div style="text-align: center; margin-top: 25px;">
      <a href="${statusUrl}" style="display: inline-block; background: #e74c3c; color: white; text-decoration: none; padding: 12px 28px; border-radius: 6px; font-weight: 600;">
        View Job Status
      </a>
    </div>
  </div>

  <div style="text-align: center; padding: 20px; color: #888; font-size: 12px;">
    <p>This email was sent by NicheIQ</p>
    <p>Job ID: ${jobId}</p>
  </div>
</body>
</html>
  `;

  const textContent = `
NicheIQ Research Issue

Unfortunately, there was an issue processing your research for "${niche.substring(0, 100)}${niche.length > 100 ? '...' : ''}".

Error: ${errorMessage}

You can try submitting your research request again. If the problem persists, please contact support.

View Job Status: ${statusUrl}

Job ID: ${jobId}
  `;

  try {
    await transporter.sendMail({
      from: CONFIG.smtp.fromEmail,
      to,
      subject: 'NicheIQ Research Issue',
      text: textContent,
      html: htmlContent,
    });

    console.log(`Failure email sent to ${to} for job ${jobId}`);
  } catch (error) {
    console.error('Failed to send failure email:', error);
  }
}

/**
 * Test email configuration
 */
export async function verifyEmailConfig(): Promise<boolean> {
  if (!CONFIG.smtp.host) {
    console.log('SMTP not configured');
    return false;
  }

  try {
    await transporter.verify();
    console.log('Email configuration verified');
    return true;
  } catch (error) {
    console.error('Email configuration error:', error);
    return false;
  }
}
