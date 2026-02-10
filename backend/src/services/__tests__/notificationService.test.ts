import { describe, it, expect, vi, beforeEach } from 'vitest';
import { shouldNotifyUser, notifyJobStart, notifyJobComplete, notifyJobError, notifySolutionsReady, notifySelectionReminder } from '../notificationService.js';

// Mock prisma
vi.mock('../db.js', () => ({
  prisma: {
    notificationPreferences: {
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
}));

import { prisma } from '../db.js';
import { sendJobStartEmail, sendCompletionEmail, sendFailureEmail, sendSolutionsReadyEmail, sendSelectionReminderEmail } from '../emailService.js';

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

      expect(sendFailureEmail).toHaveBeenCalledWith('test@example.com', 'job-456', 'test niche', 'Something went wrong', undefined);
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
      expect(sendSolutionsReadyEmail).toHaveBeenCalledWith('test@example.com', 'job-456', 'test niche', 5);
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
      expect(sendSelectionReminderEmail).toHaveBeenCalledWith('test@example.com', 'job-456', 'test niche', 5);
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
});
