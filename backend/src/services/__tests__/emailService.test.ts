import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Mock nodemailer
const mockSendMail = vi.fn();
const mockVerify = vi.fn();
vi.mock('nodemailer', () => ({
  default: {
    createTransport: () => ({
      sendMail: mockSendMail,
      verify: mockVerify,
    }),
  },
}));

// Mock SendGrid
const mockSgSend = vi.fn();
vi.mock('@sendgrid/mail', () => ({
  default: {
    setApiKey: vi.fn(),
    send: mockSgSend,
  },
}));

// Mock fs for templates
vi.mock('fs', () => ({
  readFileSync: vi.fn((path: string) => {
    if (path.includes('jobStart.html')) return '<html>{{NICHE}} started - {{JOB_ID}}</html>';
    if (path.includes('jobStart.txt')) return '{{NICHE}} started - {{JOB_ID}}';
    if (path.includes('jobComplete.html')) return '<html>{{NICHE}} complete - {{JOB_ID}}</html>';
    if (path.includes('jobComplete.txt')) return '{{NICHE}} complete - {{JOB_ID}}';
    if (path.includes('jobError.html')) return '<html>{{NICHE}} error: {{ERROR_MESSAGE}} guidance: {{GUIDANCE}}</html>';
    if (path.includes('jobError.txt')) return '{{NICHE}} error: {{ERROR_MESSAGE}} guidance: {{GUIDANCE}}';
    if (path.includes('phase2Start.html')) return '<html>{{NICHE}} phase2 - {{SELECTED_SOLUTIONS}} - {{JOB_ID}}</html>';
    if (path.includes('phase2Start.txt')) return '{{NICHE}} phase2 - {{SELECTED_SOLUTIONS}} - {{JOB_ID}}';
    if (path.includes('regenerationComplete.html')) return '<html>{{NICHE}} - {{BATCH_RESULT}} - {{BATCH_GUIDANCE}} - {{JOB_ID}}</html>';
    if (path.includes('regenerationComplete.txt')) return '{{NICHE}} - {{BATCH_RESULT}} - {{BATCH_GUIDANCE}} - {{JOB_ID}}';
    return '';
  }),
}));

// Store original env
const originalEnv = { ...process.env };

describe('emailService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset module cache to pick up new env vars
    vi.resetModules();
  });

  afterEach(() => {
    // Restore original env
    process.env = { ...originalEnv };
  });

  describe('SMTP provider', () => {
    beforeEach(() => {
      process.env.EMAIL_PROVIDER = 'smtp';
      process.env.SMTP_HOST = 'smtp.test.com';
      process.env.SMTP_PORT = '587';
      process.env.SMTP_USER = 'test@test.com';
      process.env.SMTP_PASSWORD = 'password';
      process.env.FROM_EMAIL = 'noreply@test.com';
    });

    it('sends job start email via SMTP', async () => {
      const { sendJobStartEmail } = await import('../emailService.js');
      mockSendMail.mockResolvedValue({});

      await sendJobStartEmail('user@example.com', 'job-123', 'Test Niche');

      expect(mockSendMail).toHaveBeenCalledWith(
        expect.objectContaining({
          to: 'user@example.com',
          subject: 'Your NicheIQ Research Has Started!',
        })
      );
    });

    it('sends completion email via SMTP', async () => {
      const { sendCompletionEmail } = await import('../emailService.js');
      mockSendMail.mockResolvedValue({});

      await sendCompletionEmail('user@example.com', 'job-123', 'Test Niche');

      expect(mockSendMail).toHaveBeenCalledWith(
        expect.objectContaining({
          to: 'user@example.com',
          subject: 'Your NicheIQ Research is Ready!',
        })
      );
    });

    it('sends failure email via SMTP', async () => {
      const { sendFailureEmail } = await import('../emailService.js');
      mockSendMail.mockResolvedValue({});

      await sendFailureEmail('user@example.com', 'job-123', 'Test Niche', 'Something broke');

      expect(mockSendMail).toHaveBeenCalledWith(
        expect.objectContaining({
          to: 'user@example.com',
          subject: 'NicheIQ Research Issue',
        })
      );
    });

    it('verifies SMTP configuration', async () => {
      const { verifyEmailConfig } = await import('../emailService.js');
      mockVerify.mockResolvedValue(true);

      const result = await verifyEmailConfig();

      expect(result).toBe(true);
      expect(mockVerify).toHaveBeenCalled();
    });

    it('handles SMTP send failure gracefully', async () => {
      const { sendJobStartEmail } = await import('../emailService.js');
      mockSendMail.mockRejectedValue(new Error('SMTP error'));

      // Should not throw
      await sendJobStartEmail('user@example.com', 'job-123', 'Test Niche');

      expect(mockSendMail).toHaveBeenCalled();
    });
  });

  describe('SendGrid provider', () => {
    beforeEach(() => {
      process.env.EMAIL_PROVIDER = 'sendgrid';
      process.env.SENDGRID_API_KEY = 'SG.test-api-key';
      process.env.FROM_EMAIL = 'noreply@test.com';
      // Clear SMTP settings
      delete process.env.SMTP_HOST;
    });

    it('sends job start email via SendGrid', async () => {
      const { sendJobStartEmail } = await import('../emailService.js');
      mockSgSend.mockResolvedValue({});

      await sendJobStartEmail('user@example.com', 'job-123', 'Test Niche');

      expect(mockSgSend).toHaveBeenCalledWith(
        expect.objectContaining({
          to: 'user@example.com',
          from: 'noreply@test.com',
          subject: 'Your NicheIQ Research Has Started!',
        })
      );
    });

    it('sends completion email via SendGrid', async () => {
      const { sendCompletionEmail } = await import('../emailService.js');
      mockSgSend.mockResolvedValue({});

      await sendCompletionEmail('user@example.com', 'job-123', 'Test Niche');

      expect(mockSgSend).toHaveBeenCalledWith(
        expect.objectContaining({
          to: 'user@example.com',
          subject: 'Your NicheIQ Research is Ready!',
        })
      );
    });

    it('sends failure email via SendGrid', async () => {
      const { sendFailureEmail } = await import('../emailService.js');
      mockSgSend.mockResolvedValue({});

      await sendFailureEmail('user@example.com', 'job-123', 'Test Niche', 'Something broke');

      expect(mockSgSend).toHaveBeenCalledWith(
        expect.objectContaining({
          to: 'user@example.com',
          subject: 'NicheIQ Research Issue',
        })
      );
    });

    it('verifies SendGrid configuration', async () => {
      const { verifyEmailConfig } = await import('../emailService.js');

      const result = await verifyEmailConfig();

      expect(result).toBe(true);
    });

    it('handles SendGrid send failure gracefully', async () => {
      const { sendFailureEmail } = await import('../emailService.js');
      mockSgSend.mockRejectedValue(new Error('SendGrid error'));

      // Should not throw
      await sendFailureEmail('user@example.com', 'job-123', 'Test Niche', 'Error');

      expect(mockSgSend).toHaveBeenCalled();
    });
  });

  describe('phase 2 start email', () => {
    beforeEach(() => {
      process.env.EMAIL_PROVIDER = 'smtp';
      process.env.SMTP_HOST = 'smtp.test.com';
      process.env.FROM_EMAIL = 'noreply@test.com';
    });

    it('sends with correct subject and renders solution names', async () => {
      const { sendPhase2StartEmail } = await import('../emailService.js');
      mockSendMail.mockResolvedValue({});

      await sendPhase2StartEmail('user@example.com', 'job-123', 'Test Niche', ['SaaS Dashboard', 'Analytics Tool']);

      expect(mockSendMail).toHaveBeenCalledWith(
        expect.objectContaining({
          to: 'user@example.com',
          subject: 'Your NicheIQ Deep Research Has Begun!',
          html: expect.stringContaining('SaaS Dashboard, Analytics Tool'),
        })
      );
    });
  });

  describe('regeneration complete email', () => {
    beforeEach(() => {
      process.env.EMAIL_PROVIDER = 'smtp';
      process.env.SMTP_HOST = 'smtp.test.com';
      process.env.FROM_EMAIL = 'noreply@test.com';
    });

    it('sends with correct subject and renders the added-candidate result', async () => {
      const { sendRegenerationCompleteEmail } = await import('../emailService.js');
      mockSendMail.mockResolvedValue({});

      await sendRegenerationCompleteEmail('user@example.com', 'job-123', 'Test Niche', 3, 8);

      expect(mockSendMail).toHaveBeenCalledWith(
        expect.objectContaining({
          to: 'user@example.com',
          subject: 'Your NicheIQ idea batch is ready',
          html: expect.stringContaining('3 new candidates'),
          text: expect.stringContaining('8'),
        })
      );
    });

    it('does not claim candidates were added when the batch clears none', async () => {
      const { sendRegenerationCompleteEmail } = await import('../emailService.js');
      mockSendMail.mockResolvedValue({});

      await sendRegenerationCompleteEmail('user@example.com', 'job-123', 'Test Niche', 0, 1);

      const email = mockSendMail.mock.calls.at(-1)?.[0];
      expect(email.text).toContain('no new candidates cleared the checks');
      expect(email.text).toContain('existing 1 candidate is unchanged');
      expect(email.text).not.toContain('0 new');
    });
  });

  describe('failure email with phaseContext', () => {
    beforeEach(() => {
      process.env.EMAIL_PROVIDER = 'smtp';
      process.env.SMTP_HOST = 'smtp.test.com';
      process.env.FROM_EMAIL = 'noreply@test.com';
    });

    it('prepends phase label and appends guidance when phaseContext is provided', async () => {
      const { sendFailureEmail } = await import('../emailService.js');
      mockSendMail.mockResolvedValue({});

      await sendFailureEmail('user@example.com', 'job-123', 'Test Niche', 'Worker crashed', null, {
        phaseLabel: 'During Deep Research Phase',
        guidance: 'Your checkpoint is saved.',
      });

      expect(mockSendMail).toHaveBeenCalledWith(
        expect.objectContaining({
          html: expect.stringContaining('During Deep Research Phase: Worker crashed'),
          text: expect.stringContaining('Your checkpoint is saved.'),
        })
      );
    });

    it('sends normally when phaseContext is null', async () => {
      const { sendFailureEmail } = await import('../emailService.js');
      mockSendMail.mockResolvedValue({});

      await sendFailureEmail('user@example.com', 'job-123', 'Test Niche', 'Something broke', null, null);

      expect(mockSendMail).toHaveBeenCalledWith(
        expect.objectContaining({
          html: expect.stringContaining('Something broke'),
        })
      );
    });
  });

  describe('no email configured', () => {
    beforeEach(() => {
      // Set to empty string instead of deleting — dotenv.config() (called at
      // module load in config.ts) won't overwrite existing keys, but WILL
      // populate deleted keys from the .env file.
      process.env.EMAIL_PROVIDER = '';
      process.env.SMTP_HOST = '';
      process.env.SENDGRID_API_KEY = '';
    });

    it('skips sending when not configured', async () => {
      const { sendJobStartEmail } = await import('../emailService.js');

      await sendJobStartEmail('user@example.com', 'job-123', 'Test Niche');

      expect(mockSendMail).not.toHaveBeenCalled();
      expect(mockSgSend).not.toHaveBeenCalled();
    });

    it('returns false for verify when not configured', async () => {
      const { verifyEmailConfig } = await import('../emailService.js');

      const result = await verifyEmailConfig();

      expect(result).toBe(false);
    });
  });

  describe('template rendering', () => {
    beforeEach(() => {
      process.env.EMAIL_PROVIDER = 'smtp';
      process.env.SMTP_HOST = 'smtp.test.com';
      process.env.FROM_EMAIL = 'noreply@test.com';
    });

    it('truncates long niche names', async () => {
      const { sendJobStartEmail } = await import('../emailService.js');
      mockSendMail.mockResolvedValue({});

      const longNiche = 'A'.repeat(150);
      await sendJobStartEmail('user@example.com', 'job-123', longNiche);

      expect(mockSendMail).toHaveBeenCalledWith(
        expect.objectContaining({
          html: expect.stringContaining('A'.repeat(100) + '...'),
        })
      );
    });

    it('includes job ID in email', async () => {
      const { sendJobStartEmail } = await import('../emailService.js');
      mockSendMail.mockResolvedValue({});

      await sendJobStartEmail('user@example.com', 'job-123', 'Test');

      expect(mockSendMail).toHaveBeenCalledWith(
        expect.objectContaining({
          html: expect.stringContaining('job-123'),
        })
      );
    });
  });

  describe('getEmailProvider', () => {
    it('returns configured provider', async () => {
      process.env.EMAIL_PROVIDER = 'sendgrid';
      const { getEmailProvider } = await import('../emailService.js');

      expect(getEmailProvider()).toBe('sendgrid');
    });

    it('defaults to smtp', async () => {
      process.env.EMAIL_PROVIDER = '';
      const { getEmailProvider } = await import('../emailService.js');

      expect(getEmailProvider()).toBe('smtp');
    });
  });
});
