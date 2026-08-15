import { describe, it, expect, vi, beforeEach } from 'vitest';

/**
 * The wiring half of the seventeenth surface.
 *
 * `POST /api/workers/ideas-ready` registers the PREVIEW_REPORT asset — the artifact that
 * CARRIES `idea_validation.outcome` — twenty lines above the email call, in the same
 * handler. The refusal was in hand and was never consulted, and no layer anywhere between
 * `emailService`, `selectionReminderService` and `notificationService` mentioned
 * `entryMode`, `validate_idea` or `not_evaluated`. These tests pin that it is consulted,
 * on BOTH sends, and that every failure to read it resolves to the state that asserts
 * nothing.
 */

vi.mock('../db.js', () => ({
  prisma: {
    notificationPreferences: { findUnique: vi.fn() },
    job: { findUnique: vi.fn() },
  },
}));
vi.mock('../emailService.js', () => ({
  sendJobStartEmail: vi.fn(),
  sendCompletionEmail: vi.fn(),
  sendFailureEmail: vi.fn(),
  sendSolutionsReadyEmail: vi.fn(),
  sendSelectionReminderEmail: vi.fn(),
  sendPhase2StartEmail: vi.fn(),
  sendRegenerationCompleteEmail: vi.fn(),
  sendLandingPageReadyEmail: vi.fn(),
  sendGateReachedEmail: vi.fn(),
}));
vi.mock('../currentSelectionContext.js', () => ({
  loadCurrentSelectionContext: vi.fn(),
}));

import { prisma } from '../db.js';
import { sendSolutionsReadyEmail, sendSelectionReminderEmail } from '../emailService.js';
import { loadCurrentSelectionContext } from '../currentSelectionContext.js';
import {
  notifySelectionReminder,
  notifySolutionsReady,
  resolveIdeaCheckEmailContext,
} from '../notificationService.js';

const PITCH = 'A scheduling app that lets small vet clinics fill same-day cancellations';

const REFUSED_BLOCK = {
  outcome: 'not_evaluated',
  headline: 'What we built drifted into a different product, so we stopped rather than grade '
    + 'something you did not describe.',
  failure_next_step: 'Your submission is saved. The drift is in our build, not in what you '
    + 'sent, so run it again as it stands — we rebuild your idea from scratch on each run.',
};

function job(entryMode: string | null, niche = PITCH) {
  vi.mocked(prisma.job.findUnique).mockResolvedValue({ entryMode, niche, jobMode: null } as never);
}

function verified(previewReport: Record<string, unknown>) {
  vi.mocked(loadCurrentSelectionContext).mockResolvedValue({
    runArtifacts: { verification: 'verified', previewReport },
  } as never);
}

describe('resolveIdeaCheckEmailContext', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(prisma.notificationPreferences.findUnique).mockResolvedValue(null as never);
  });

  it('is "none" on a discovery run, and never opens the artifact', async () => {
    job('discovery');
    expect(await resolveIdeaCheckEmailContext('job-1')).toEqual({ state: 'none' });
    expect(loadCurrentSelectionContext).not.toHaveBeenCalled();
  });

  it('is "none" when entryMode is absent (legacy one-shot jobs)', async () => {
    job(null);
    expect(await resolveIdeaCheckEmailContext('job-1')).toEqual({ state: 'none' });
  });

  it('carries the refusal, its two artifact sentences, and the pitch', async () => {
    job('validate_idea');
    verified({ idea_validation: REFUSED_BLOCK });
    expect(await resolveIdeaCheckEmailContext('job-1')).toEqual({
      state: 'not_evaluated',
      headline: REFUSED_BLOCK.headline,
      nextStep: REFUSED_BLOCK.failure_next_step,
      pitch: PITCH,
    });
  });

  it('is "evaluated" when the run did grade the idea', async () => {
    job('validate_idea');
    verified({ idea_validation: { outcome: 'promising', headline: 'Worth a test.' } });
    expect(await resolveIdeaCheckEmailContext('job-1')).toEqual({ state: 'evaluated' });
  });

  it('is "unavailable" when the artifact is untrusted, absent, or unreadable', async () => {
    job('validate_idea');

    vi.mocked(loadCurrentSelectionContext).mockResolvedValue({
      runArtifacts: { verification: 'untrusted', reason: 'version_mismatch' },
    } as never);
    expect(await resolveIdeaCheckEmailContext('job-1')).toEqual({ state: 'unavailable' });

    verified({});
    expect(await resolveIdeaCheckEmailContext('job-1')).toEqual({ state: 'unavailable' });

    vi.mocked(loadCurrentSelectionContext).mockResolvedValue(null as never);
    expect(await resolveIdeaCheckEmailContext('job-1')).toEqual({ state: 'unavailable' });
  });

  it('never throws — a notification must not be able to break a run', async () => {
    job('validate_idea');
    vi.mocked(loadCurrentSelectionContext).mockRejectedValue(new Error('disk gone'));
    expect(await resolveIdeaCheckEmailContext('job-1')).toEqual({ state: 'unavailable' });
  });
});

describe('both AWAITING_SELECTION sends consult the outcome', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(prisma.notificationPreferences.findUnique).mockResolvedValue(null as never);
    job('validate_idea');
    verified({ idea_validation: REFUSED_BLOCK });
  });

  it('notifySolutionsReady passes the refusal to the email', async () => {
    await notifySolutionsReady('user-1', 'u@example.com', 'job-1', PITCH, 8);
    expect(sendSolutionsReadyEmail).toHaveBeenCalledWith(
      'u@example.com', 'job-1', PITCH, 8,
      expect.objectContaining({ state: 'not_evaluated', headline: REFUSED_BLOCK.headline }),
    );
  });

  it('notifySelectionReminder does too — at 24h, 72h and 120h', async () => {
    await notifySelectionReminder('user-1', 'u@example.com', 'job-1', PITCH, 8);
    expect(sendSelectionReminderEmail).toHaveBeenCalledWith(
      'u@example.com', 'job-1', PITCH, 8,
      expect.objectContaining({ state: 'not_evaluated', headline: REFUSED_BLOCK.headline }),
    );
  });
});
