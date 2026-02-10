import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock prisma
const mockJobFindMany = vi.fn();
const mockJobUpdate = vi.fn();
const mockUserFindUnique = vi.fn();

vi.mock('../db.js', () => ({
  prisma: {
    job: {
      findMany: (...args: any[]) => mockJobFindMany(...args),
      update: (...args: any[]) => mockJobUpdate(...args),
    },
    user: {
      findUnique: (...args: any[]) => mockUserFindUnique(...args),
    },
  },
}));

const mockNotifySelectionReminder = vi.fn();

vi.mock('../notificationService.js', () => ({
  notifySelectionReminder: (...args: any[]) => mockNotifySelectionReminder(...args),
}));

// Import after mocks
import { checkAndSendReminders } from '../selectionReminderService.js';

describe('checkAndSendReminders', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockNotifySelectionReminder.mockResolvedValue(undefined);
    mockJobUpdate.mockResolvedValue({ id: 'job-1' });
  });

  it('queries AWAITING_SELECTION jobs with correct filters', async () => {
    mockJobFindMany.mockResolvedValue([]);

    await checkAndSendReminders();

    expect(mockJobFindMany).toHaveBeenCalledWith({
      where: {
        status: 'AWAITING_SELECTION',
        selectionReminderCount: { lt: 3 },
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
  });

  it('sends 1st reminder after 24h', async () => {
    const job = {
      id: 'job-1',
      niche: 'test niche',
      userId: 'user-1',
      awaitingSelectionAt: new Date(Date.now() - 25 * 60 * 60 * 1000), // 25h ago
      selectionReminderCount: 0,
      lastReminderSentAt: null,
      solutionIdeas: [{ name: 'Sol1' }, { name: 'Sol2' }],
    };
    mockJobFindMany.mockResolvedValue([job]);
    mockUserFindUnique.mockResolvedValue({ email: 'test@test.com' });

    await checkAndSendReminders();

    expect(mockNotifySelectionReminder).toHaveBeenCalledWith(
      'user-1',
      'test@test.com',
      'job-1',
      'test niche',
      2
    );
    expect(mockJobUpdate).toHaveBeenCalledWith({
      where: { id: 'job-1' },
      data: {
        selectionReminderCount: { increment: 1 },
        lastReminderSentAt: expect.any(Date),
      },
    });
  });

  it('sends 2nd reminder after 72h', async () => {
    const job = {
      id: 'job-2',
      niche: 'niche two',
      userId: 'user-2',
      awaitingSelectionAt: new Date(Date.now() - 73 * 60 * 60 * 1000), // 73h ago
      selectionReminderCount: 1,
      lastReminderSentAt: null,
      solutionIdeas: [{ name: 'A' }, { name: 'B' }, { name: 'C' }],
    };
    mockJobFindMany.mockResolvedValue([job]);
    mockUserFindUnique.mockResolvedValue({ email: 'user2@test.com' });

    await checkAndSendReminders();

    expect(mockNotifySelectionReminder).toHaveBeenCalledWith(
      'user-2',
      'user2@test.com',
      'job-2',
      'niche two',
      3
    );
    expect(mockJobUpdate).toHaveBeenCalled();
  });

  it('sends 3rd reminder after 120h', async () => {
    const job = {
      id: 'job-3',
      niche: 'niche three',
      userId: 'user-3',
      awaitingSelectionAt: new Date(Date.now() - 121 * 60 * 60 * 1000), // 121h ago
      selectionReminderCount: 2,
      lastReminderSentAt: null,
      solutionIdeas: [{ name: 'X' }],
    };
    mockJobFindMany.mockResolvedValue([job]);
    mockUserFindUnique.mockResolvedValue({ email: 'user3@test.com' });

    await checkAndSendReminders();

    expect(mockNotifySelectionReminder).toHaveBeenCalledWith(
      'user-3',
      'user3@test.com',
      'job-3',
      'niche three',
      1
    );
    expect(mockJobUpdate).toHaveBeenCalled();
  });

  it('skips jobs not yet at threshold time', async () => {
    const job = {
      id: 'job-4',
      niche: 'early niche',
      userId: 'user-4',
      awaitingSelectionAt: new Date(Date.now() - 23 * 60 * 60 * 1000), // 23h ago, not yet 24h
      selectionReminderCount: 0,
      lastReminderSentAt: null,
      solutionIdeas: [{ name: 'Sol1' }],
    };
    mockJobFindMany.mockResolvedValue([job]);

    await checkAndSendReminders();

    expect(mockNotifySelectionReminder).not.toHaveBeenCalled();
    expect(mockJobUpdate).not.toHaveBeenCalled();
  });

  it('skips when selectionReminderCount >= MAX_REMINDERS', async () => {
    const job = {
      id: 'job-5',
      niche: 'done niche',
      userId: 'user-5',
      awaitingSelectionAt: new Date(Date.now() - 200 * 60 * 60 * 1000),
      selectionReminderCount: 3,
      lastReminderSentAt: null,
      solutionIdeas: [{ name: 'Sol1' }],
    };
    mockJobFindMany.mockResolvedValue([job]);

    await checkAndSendReminders();

    expect(mockNotifySelectionReminder).not.toHaveBeenCalled();
    expect(mockJobUpdate).not.toHaveBeenCalled();
  });

  it('skips when userId is null', async () => {
    const job = {
      id: 'job-6',
      niche: 'no user niche',
      userId: null,
      awaitingSelectionAt: new Date(Date.now() - 25 * 60 * 60 * 1000),
      selectionReminderCount: 0,
      lastReminderSentAt: null,
      solutionIdeas: [{ name: 'Sol1' }],
    };
    mockJobFindMany.mockResolvedValue([job]);

    await checkAndSendReminders();

    expect(mockNotifySelectionReminder).not.toHaveBeenCalled();
    expect(mockJobUpdate).not.toHaveBeenCalled();
  });

  it('skips when user email is not found', async () => {
    const job = {
      id: 'job-7',
      niche: 'no email niche',
      userId: 'user-7',
      awaitingSelectionAt: new Date(Date.now() - 25 * 60 * 60 * 1000),
      selectionReminderCount: 0,
      lastReminderSentAt: null,
      solutionIdeas: [{ name: 'Sol1' }],
    };
    mockJobFindMany.mockResolvedValue([job]);
    mockUserFindUnique.mockResolvedValue(null);

    await checkAndSendReminders();

    expect(mockNotifySelectionReminder).not.toHaveBeenCalled();
    expect(mockJobUpdate).not.toHaveBeenCalled();
  });

  it('increments selectionReminderCount and sets lastReminderSentAt', async () => {
    const job = {
      id: 'job-8',
      niche: 'increment niche',
      userId: 'user-8',
      awaitingSelectionAt: new Date(Date.now() - 25 * 60 * 60 * 1000),
      selectionReminderCount: 0,
      lastReminderSentAt: null,
      solutionIdeas: [{ name: 'Sol1' }, { name: 'Sol2' }, { name: 'Sol3' }],
    };
    mockJobFindMany.mockResolvedValue([job]);
    mockUserFindUnique.mockResolvedValue({ email: 'inc@test.com' });

    await checkAndSendReminders();

    expect(mockJobUpdate).toHaveBeenCalledWith({
      where: { id: 'job-8' },
      data: {
        selectionReminderCount: { increment: 1 },
        lastReminderSentAt: expect.any(Date),
      },
    });
  });

  it('handles notification errors gracefully', async () => {
    const job = {
      id: 'job-9',
      niche: 'error niche',
      userId: 'user-9',
      awaitingSelectionAt: new Date(Date.now() - 25 * 60 * 60 * 1000),
      selectionReminderCount: 0,
      lastReminderSentAt: null,
      solutionIdeas: [{ name: 'Sol1' }],
    };
    mockJobFindMany.mockResolvedValue([job]);
    mockUserFindUnique.mockResolvedValue({ email: 'error@test.com' });
    mockNotifySelectionReminder.mockRejectedValue(new Error('email failed'));

    // Should NOT throw
    await expect(checkAndSendReminders()).resolves.toBeUndefined();

    expect(mockNotifySelectionReminder).toHaveBeenCalled();
    // Job update should NOT have been called since notification failed before it
    expect(mockJobUpdate).not.toHaveBeenCalled();
  });
});
