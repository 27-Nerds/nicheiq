import { describe, it, expect, vi, beforeEach } from 'vitest';
import { shouldNotifyUser, notifyJobStart, notifyJobComplete, notifyJobError, notifySolutionsReady, notifySelectionReminder, notifyPhase2Start, notifyRegenerationComplete, notifyLandingPageReady } from '../notificationService.js';

// Mock prisma
vi.mock('../db.js', () => ({
  prisma: {
    notificationPreferences: {
      findUnique: vi.fn(),
    },
    job: {
      findUnique: vi.fn(),
    },
  },
}));

// Mock email service
vi.mock('../emailService.js', () => ({
  sendJobStartEmail: vi.fn(),
  sendCompletionEmail: vi.fn(),
  sendFailureEmail: vi.fn(),
  sendSolutionsReadyEmail: vi.fn(),
  sendSelectionReminderEmail: vi.fn(),
  sendPhase2StartEmail: vi.fn(),
  sendRegenerationCompleteEmail: vi.fn(),
  sendLandingPageReadyEmail: vi.fn(),
}));

import { prisma } from '../db.js';
import { sendJobStartEmail, sendCompletionEmail, sendFailureEmail, sendSolutionsReadyEmail, sendSelectionReminderEmail, sendPhase2StartEmail, sendRegenerationCompleteEmail, sendLandingPageReadyEmail } from '../emailService.js';

describe('notificationService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('shouldNotifyUser', () => {
    it('returns false when userId is null', async () => {
      const result = await shouldNotifyUser(null, 'jobComplete');
      expect(result).toBe(false);
    });

    it('returns false when userId is undefined', async () => {
      const result = await shouldNotifyUser(undefined, 'jobComplete');
      expect(result).toBe(false);
    });

    it('returns default true for jobComplete when no preferences exist', async () => {
      vi.mocked(prisma.notificationPreferences.findUnique).mockResolvedValue(null);

      const result = await shouldNotifyUser('user-123', 'jobComplete');
      expect(result).toBe(true);
    });

    it('returns default true for jobError when no preferences exist', async () => {
      vi.mocked(prisma.notificationPreferences.findUnique).mockResolvedValue(null);

      const result = await shouldNotifyUser('user-123', 'jobError');
      expect(result).toBe(true);
    });

    it('returns default true for jobStart when no preferences exist', async () => {
      vi.mocked(prisma.notificationPreferences.findUnique).mockResolvedValue(null);

      const result = await shouldNotifyUser('user-123', 'jobStart');
      expect(result).toBe(true);
    });

    it('respects emailEnabled master toggle', async () => {
      vi.mocked(prisma.notificationPreferences.findUnique).mockResolvedValue({
        id: 'pref-1',
        userId: 'user-123',
        emailEnabled: false,
        emailOnJobStart: true,
        emailOnJobComplete: true,
        emailOnJobError: true,
        emailOnSolutionsReady: true,
        createdAt: new Date(),
        updatedAt: new Date(),
      });

      const result = await shouldNotifyUser('user-123', 'jobComplete');
      expect(result).toBe(false);
    });

    it('respects individual preference settings', async () => {
      vi.mocked(prisma.notificationPreferences.findUnique).mockResolvedValue({
        id: 'pref-1',
        userId: 'user-123',
        emailEnabled: true,
        emailOnJobStart: false,
        emailOnJobComplete: true,
        emailOnJobError: false,
        emailOnSolutionsReady: true,
        createdAt: new Date(),
        updatedAt: new Date(),
      });

      expect(await shouldNotifyUser('user-123', 'jobStart')).toBe(false);
      expect(await shouldNotifyUser('user-123', 'jobComplete')).toBe(true);
      expect(await shouldNotifyUser('user-123', 'jobError')).toBe(false);
    });
  });

  describe('notifyJobStart', () => {
    it('sends email when preferences allow', async () => {
      vi.mocked(prisma.notificationPreferences.findUnique).mockResolvedValue(null);

      await notifyJobStart('user-123', 'test@example.com', 'job-456', 'test niche');

      expect(sendJobStartEmail).toHaveBeenCalledWith('test@example.com', 'job-456', 'test niche');
    });

    it('skips email when preferences disable it', async () => {
      vi.mocked(prisma.notificationPreferences.findUnique).mockResolvedValue({
        id: 'pref-1',
        userId: 'user-123',
        emailEnabled: true,
        emailOnJobStart: false,
        emailOnJobComplete: true,
        emailOnJobError: true,
        emailOnSolutionsReady: true,
        createdAt: new Date(),
        updatedAt: new Date(),
      });

      await notifyJobStart('user-123', 'test@example.com', 'job-456', 'test niche');

      expect(sendJobStartEmail).not.toHaveBeenCalled();
    });

    it('skips email when userId is null', async () => {
      await notifyJobStart(null, 'test@example.com', 'job-456', 'test niche');

      expect(sendJobStartEmail).not.toHaveBeenCalled();
    });
  });

  describe('notifyJobComplete', () => {
    it('sends email when preferences allow', async () => {
      vi.mocked(prisma.notificationPreferences.findUnique).mockResolvedValue(null);

      await notifyJobComplete('user-123', 'test@example.com', 'job-456', 'test niche');

      expect(sendCompletionEmail).toHaveBeenCalledWith('test@example.com', 'job-456', 'test niche');
    });

    it('skips email when master toggle is off', async () => {
      vi.mocked(prisma.notificationPreferences.findUnique).mockResolvedValue({
        id: 'pref-1',
        userId: 'user-123',
        emailEnabled: false,
        emailOnJobStart: true,
        emailOnJobComplete: true,
        emailOnJobError: true,
        emailOnSolutionsReady: true,
        createdAt: new Date(),
        updatedAt: new Date(),
      });

      await notifyJobComplete('user-123', 'test@example.com', 'job-456', 'test niche');

      expect(sendCompletionEmail).not.toHaveBeenCalled();
    });
  });

  describe('notifyJobError', () => {
    it('sends email when preferences allow', async () => {
      vi.mocked(prisma.notificationPreferences.findUnique).mockResolvedValue(null);

      await notifyJobError('user-123', 'test@example.com', 'job-456', 'test niche', 'Something went wrong');

      expect(sendFailureEmail).toHaveBeenCalledWith('test@example.com', 'job-456', 'test niche', 'Something went wrong', undefined, undefined);
    });

    it('skips email when emailOnJobError is false', async () => {
      vi.mocked(prisma.notificationPreferences.findUnique).mockResolvedValue({
        id: 'pref-1',
        userId: 'user-123',
        emailEnabled: true,
        emailOnJobStart: true,
        emailOnJobComplete: true,
        emailOnJobError: false,
        emailOnSolutionsReady: true,
        createdAt: new Date(),
        updatedAt: new Date(),
      });

      await notifyJobError('user-123', 'test@example.com', 'job-456', 'test niche', 'Something went wrong');

      expect(sendFailureEmail).not.toHaveBeenCalled();
    });
  });

  describe('notifySolutionsReady', () => {
    it('sends email when preferences allow', async () => {
      vi.mocked(prisma.notificationPreferences.findUnique).mockResolvedValue(null);
      await notifySolutionsReady('user-123', 'test@example.com', 'job-456', 'test niche', 5);
      expect(sendSolutionsReadyEmail).toHaveBeenCalledWith('test@example.com', 'job-456', 'test niche', 5, { state: 'none' });
    });

    it('skips when master emailEnabled is false', async () => {
      vi.mocked(prisma.notificationPreferences.findUnique).mockResolvedValue({
        id: 'pref-1', userId: 'user-123',
        emailEnabled: false, emailOnJobStart: true, emailOnJobComplete: true,
        emailOnJobError: true, emailOnSolutionsReady: true,
        createdAt: new Date(), updatedAt: new Date(),
      });
      await notifySolutionsReady('user-123', 'test@example.com', 'job-456', 'test niche', 5);
      expect(sendSolutionsReadyEmail).not.toHaveBeenCalled();
    });

    it('skips when emailOnSolutionsReady is false', async () => {
      vi.mocked(prisma.notificationPreferences.findUnique).mockResolvedValue({
        id: 'pref-1', userId: 'user-123',
        emailEnabled: true, emailOnJobStart: true, emailOnJobComplete: true,
        emailOnJobError: true, emailOnSolutionsReady: false,
        createdAt: new Date(), updatedAt: new Date(),
      });
      await notifySolutionsReady('user-123', 'test@example.com', 'job-456', 'test niche', 5);
      expect(sendSolutionsReadyEmail).not.toHaveBeenCalled();
    });

    it('skips when userId is null', async () => {
      await notifySolutionsReady(null, 'test@example.com', 'job-456', 'test niche', 5);
      expect(sendSolutionsReadyEmail).not.toHaveBeenCalled();
    });
  });

  describe('notifySelectionReminder', () => {
    it('sends reminder email when preferences allow', async () => {
      vi.mocked(prisma.notificationPreferences.findUnique).mockResolvedValue(null);
      await notifySelectionReminder('user-123', 'test@example.com', 'job-456', 'test niche', 5);
      expect(sendSelectionReminderEmail).toHaveBeenCalledWith('test@example.com', 'job-456', 'test niche', 5, { state: 'none' });
    });

    it('skips when notifications disabled', async () => {
      vi.mocked(prisma.notificationPreferences.findUnique).mockResolvedValue({
        id: 'pref-1', userId: 'user-123',
        emailEnabled: true, emailOnJobStart: true, emailOnJobComplete: true,
        emailOnJobError: true, emailOnSolutionsReady: false,
        createdAt: new Date(), updatedAt: new Date(),
      });
      await notifySelectionReminder('user-123', 'test@example.com', 'job-456', 'test niche', 5);
      expect(sendSelectionReminderEmail).not.toHaveBeenCalled();
    });
  });

  describe('notifyPhase2Start', () => {
    it('sends email when emailOnJobStart is enabled', async () => {
      vi.mocked(prisma.notificationPreferences.findUnique).mockResolvedValue(null);

      await notifyPhase2Start('user-123', 'test@example.com', 'job-456', 'test niche', ['SaaS Tool']);

      expect(sendPhase2StartEmail).toHaveBeenCalledWith('test@example.com', 'job-456', 'test niche', ['SaaS Tool']);
    });

    it('skips when emailOnJobStart is false', async () => {
      vi.mocked(prisma.notificationPreferences.findUnique).mockResolvedValue({
        id: 'pref-1', userId: 'user-123',
        emailEnabled: true, emailOnJobStart: false, emailOnJobComplete: true,
        emailOnJobError: true, emailOnSolutionsReady: true,
        createdAt: new Date(), updatedAt: new Date(),
      });

      await notifyPhase2Start('user-123', 'test@example.com', 'job-456', 'test niche', ['SaaS Tool']);

      expect(sendPhase2StartEmail).not.toHaveBeenCalled();
    });

    it('skips when userId is null', async () => {
      await notifyPhase2Start(null, 'test@example.com', 'job-456', 'test niche', ['SaaS Tool']);

      expect(sendPhase2StartEmail).not.toHaveBeenCalled();
    });
  });

  describe('notifyRegenerationComplete', () => {
    it('sends email when emailOnSolutionsReady is enabled', async () => {
      vi.mocked(prisma.notificationPreferences.findUnique).mockResolvedValue(null);

      await notifyRegenerationComplete('user-123', 'test@example.com', 'job-456', 'test niche', 3, 8);

      expect(sendRegenerationCompleteEmail).toHaveBeenCalledWith('test@example.com', 'job-456', 'test niche', 3, 8);
    });

    it('skips when emailOnSolutionsReady is false', async () => {
      vi.mocked(prisma.notificationPreferences.findUnique).mockResolvedValue({
        id: 'pref-1', userId: 'user-123',
        emailEnabled: true, emailOnJobStart: true, emailOnJobComplete: true,
        emailOnJobError: true, emailOnSolutionsReady: false,
        createdAt: new Date(), updatedAt: new Date(),
      });

      await notifyRegenerationComplete('user-123', 'test@example.com', 'job-456', 'test niche', 3, 8);

      expect(sendRegenerationCompleteEmail).not.toHaveBeenCalled();
    });

    it('skips when userId is null', async () => {
      await notifyRegenerationComplete(null, 'test@example.com', 'job-456', 'test niche', 3, 8);

      expect(sendRegenerationCompleteEmail).not.toHaveBeenCalled();
    });
  });

  describe('notifyJobError with phaseContext', () => {
    it('passes phaseContext through to sendFailureEmail', async () => {
      vi.mocked(prisma.notificationPreferences.findUnique).mockResolvedValue(null);

      const phaseCtx = { phaseLabel: 'During Deep Research Phase', guidance: 'Resume from checkpoint.' };
      await notifyJobError('user-123', 'test@example.com', 'job-456', 'test niche', 'Worker crashed', null, phaseCtx);

      expect(sendFailureEmail).toHaveBeenCalledWith('test@example.com', 'job-456', 'test niche', 'Worker crashed', null, phaseCtx);
    });

    it('passes undefined phaseContext when not provided', async () => {
      vi.mocked(prisma.notificationPreferences.findUnique).mockResolvedValue(null);

      await notifyJobError('user-123', 'test@example.com', 'job-456', 'test niche', 'Error');

      expect(sendFailureEmail).toHaveBeenCalledWith('test@example.com', 'job-456', 'test niche', 'Error', undefined, undefined);
    });
  });

  describe('catalog job email suppression', () => {
    const catalogPainPointsJob = { jobMode: 'catalog_pain_points' };
    const catalogIdeasJob = { jobMode: 'catalog_ideas' };
    const interactiveJob = { jobMode: 'interactive' };
    const nullModeJob = { jobMode: null };

    describe('shouldNotifyUser', () => {
      it('returns false for catalog_pain_points jobs', async () => {
        vi.mocked(prisma.job.findUnique).mockResolvedValue(catalogPainPointsJob as any);

        const result = await shouldNotifyUser('user-123', 'jobComplete', 'job-456');
        expect(result).toBe(false);
        expect(prisma.notificationPreferences.findUnique).not.toHaveBeenCalled();
      });

      it('returns false for catalog_ideas jobs', async () => {
        vi.mocked(prisma.job.findUnique).mockResolvedValue(catalogIdeasJob as any);

        const result = await shouldNotifyUser('user-123', 'jobStart', 'job-456');
        expect(result).toBe(false);
        expect(prisma.notificationPreferences.findUnique).not.toHaveBeenCalled();
      });

      it('proceeds to preference check for interactive jobs', async () => {
        vi.mocked(prisma.job.findUnique).mockResolvedValue(interactiveJob as any);
        vi.mocked(prisma.notificationPreferences.findUnique).mockResolvedValue(null);

        const result = await shouldNotifyUser('user-123', 'jobComplete', 'job-456');
        expect(result).toBe(true);
        expect(prisma.notificationPreferences.findUnique).toHaveBeenCalled();
      });

      it('proceeds to preference check for null jobMode (legacy jobs)', async () => {
        vi.mocked(prisma.job.findUnique).mockResolvedValue(nullModeJob as any);
        vi.mocked(prisma.notificationPreferences.findUnique).mockResolvedValue(null);

        const result = await shouldNotifyUser('user-123', 'jobComplete', 'job-456');
        expect(result).toBe(true);
      });

      it('proceeds to preference check when job not found (deleted)', async () => {
        vi.mocked(prisma.job.findUnique).mockResolvedValue(null);
        vi.mocked(prisma.notificationPreferences.findUnique).mockResolvedValue(null);

        const result = await shouldNotifyUser('user-123', 'jobComplete', 'job-456');
        expect(result).toBe(true);
      });

      it('skips catalog check when jobId is not provided', async () => {
        vi.mocked(prisma.notificationPreferences.findUnique).mockResolvedValue(null);

        const result = await shouldNotifyUser('user-123', 'jobComplete');
        expect(result).toBe(true);
        expect(prisma.job.findUnique).not.toHaveBeenCalled();
      });
    });

    describe('notifyJobStart', () => {
      it('skips email for catalog job', async () => {
        vi.mocked(prisma.job.findUnique).mockResolvedValue(catalogPainPointsJob as any);

        await notifyJobStart('user-123', 'test@example.com', 'job-456', 'test niche');

        expect(sendJobStartEmail).not.toHaveBeenCalled();
      });
    });

    describe('notifyJobComplete', () => {
      it('skips email for catalog job', async () => {
        vi.mocked(prisma.job.findUnique).mockResolvedValue(catalogIdeasJob as any);

        await notifyJobComplete('user-123', 'test@example.com', 'job-456', 'test niche');

        expect(sendCompletionEmail).not.toHaveBeenCalled();
      });
    });

    describe('notifyJobError', () => {
      it('skips email for catalog job', async () => {
        vi.mocked(prisma.job.findUnique).mockResolvedValue(catalogPainPointsJob as any);

        await notifyJobError('user-123', 'test@example.com', 'job-456', 'test niche', 'error');

        expect(sendFailureEmail).not.toHaveBeenCalled();
      });
    });

    describe('notifySolutionsReady', () => {
      it('skips email for catalog job', async () => {
        vi.mocked(prisma.job.findUnique).mockResolvedValue(catalogPainPointsJob as any);

        await notifySolutionsReady('user-123', 'test@example.com', 'job-456', 'test niche', 5);

        expect(sendSolutionsReadyEmail).not.toHaveBeenCalled();
      });
    });

    describe('notifyPhase2Start', () => {
      it('skips email for catalog job', async () => {
        vi.mocked(prisma.job.findUnique).mockResolvedValue(catalogIdeasJob as any);

        await notifyPhase2Start('user-123', 'test@example.com', 'job-456', 'test niche', ['Solution A']);

        expect(sendPhase2StartEmail).not.toHaveBeenCalled();
      });
    });

    describe('notifyRegenerationComplete', () => {
      it('skips email for catalog job', async () => {
        vi.mocked(prisma.job.findUnique).mockResolvedValue(catalogPainPointsJob as any);

        await notifyRegenerationComplete('user-123', 'test@example.com', 'job-456', 'test niche', 3, 8);

        expect(sendRegenerationCompleteEmail).not.toHaveBeenCalled();
      });
    });

    describe('notifySelectionReminder', () => {
      it('skips email for catalog job', async () => {
        vi.mocked(prisma.job.findUnique).mockResolvedValue(catalogIdeasJob as any);

        await notifySelectionReminder('user-123', 'test@example.com', 'job-456', 'test niche', 5);

        expect(sendSelectionReminderEmail).not.toHaveBeenCalled();
      });
    });

    describe('notifyLandingPageReady', () => {
      it('skips email for catalog job', async () => {
        vi.mocked(prisma.job.findUnique).mockResolvedValue(catalogPainPointsJob as any);

        await notifyLandingPageReady('user-123', 'test@example.com', 'job-456', 'test niche');

        expect(sendLandingPageReadyEmail).not.toHaveBeenCalled();
      });

      it('sends email for interactive job', async () => {
        vi.mocked(prisma.job.findUnique).mockResolvedValue(interactiveJob as any);
        vi.mocked(prisma.notificationPreferences.findUnique).mockResolvedValue(null);

        await notifyLandingPageReady('user-123', 'test@example.com', 'job-456', 'test niche');

        expect(sendLandingPageReadyEmail).toHaveBeenCalledWith('test@example.com', 'job-456', 'test niche');
      });
    });
  });
});
