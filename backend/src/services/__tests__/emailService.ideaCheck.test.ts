import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import type { IdeaCheckEmailContext } from '../emailService.js';

/**
 * THE SEVENTEENTH SURFACE — the emails.
 *
 * A refused `validate_idea` run is non-fatal by design: Phase 1 completes, the pool ships,
 * the job reaches AWAITING_SELECTION. That fires `notifySolutionsReady`, and then up to
 * three `notifySelectionReminder` sends at 24h / 72h / 120h. On a `validate_idea` run
 * `Job.niche` IS the user's raw pitch, so the reminder read:
 *
 *   "Just a reminder — you have 8 VALIDATED solutions waiting for your review FOR
 *    '<the user's own pitch>'."
 *
 * — the most direct assertion in the codebase that their submitted idea was evaluated,
 * arriving up to four times over five days for a run that refused to evaluate it. Sixteen
 * rounds of sweeps missed it because every one was applied to a rendered page. This surface
 * leaves the product; no page fix, share gate, tour suppression, chat framing or progress
 * default can reach an inbox.
 *
 * DELIBERATELY DOES NOT MOCK `fs`. `emailService.test.ts` substitutes toy templates, so it
 * proves nothing about what actually ships. Every assertion below renders the REAL
 * `src/templates/email/*` through the real send path.
 */

const mockSendMail = vi.fn();
vi.mock('nodemailer', () => ({
  default: { createTransport: () => ({ sendMail: mockSendMail, verify: vi.fn() }) },
}));
vi.mock('@sendgrid/mail', () => ({ default: { setApiKey: vi.fn(), send: vi.fn() } }));

const originalEnv = { ...process.env };

/** The two sentences a refusal contributes, VERBATIM from `SEED_FAILURE_COPY`. */
const REFUSED: IdeaCheckEmailContext = {
  state: 'not_evaluated',
  headline:
    'Our own check that we were still grading your idea could not run, so we stopped '
    + 'rather than report a verdict we had not verified — a fault on our side, not with '
    + 'your idea.',
  nextStep:
    'Your submission is saved, and nothing in it caused this — there is nothing to change '
    + 'before you retry. Run the check again; if it stops the same way immediately, wait a '
    + 'few minutes first.',
  pitch: PITCH(),
};

function PITCH(): string {
  return 'A scheduling app that lets small vet clinics fill same-day cancellations';
}

const REPO_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..', '..', '..');

/**
 * Read off the source of each deployable, never transcribed — the ledger's G-3 finding was
 * two hand-typed "backend" constants that had both drifted from the sentences the app really
 * ships, so every assertion naming them was about copy no build emits. Concatenated
 * double-quoted / single-quoted literals only; anything else throws rather than silently
 * yielding '' (which `toContain` would accept from every string on earth).
 */
function stringLiteral(file: string, name: string): string {
  const src = readFileSync(resolve(REPO_ROOT, file), 'utf8');
  const decl = src.match(new RegExp(`const ${name}\\s*=\\s*([\\s\\S]*?);\\n`));
  if (!decl) throw new Error(`${file} no longer declares ${name}`);
  const parts = [...decl[1].matchAll(/(["'])((?:[^\\]|\\.)*?)\1/g)].map((m) => m[2]);
  if (!parts.length) throw new Error(`${name} is no longer a plain string literal`);
  return parts.join('').replace(/\\(['"])/g, '$1');
}

/** The page is where this sentence is authored; the email carries the same fact. */
const CHARGE_STANDS = stringLiteral(
  'frontend/src/lib/components/sections/ValidationVerdict.svelte',
  'CHARGE_STANDS',
);

async function send(
  which: 'solutions' | 'reminder',
  ideaCheck?: IdeaCheckEmailContext,
): Promise<{ subject: string; text: string; html: string }> {
  const mod = await import('../emailService.js');
  mockSendMail.mockResolvedValue({});
  if (which === 'solutions') {
    await mod.sendSolutionsReadyEmail('u@example.com', 'job-1', PITCH(), 8, ideaCheck);
  } else {
    await mod.sendSelectionReminderEmail('u@example.com', 'job-1', PITCH(), 8, ideaCheck);
  }
  expect(mockSendMail).toHaveBeenCalledTimes(1);
  const call = mockSendMail.mock.calls[0][0];
  return { subject: call.subject, text: call.text, html: call.html };
}

describe('AWAITING_SELECTION emails · a refused idea check', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
    process.env.EMAIL_PROVIDER = 'smtp';
    process.env.SMTP_HOST = 'smtp.test.com';
    process.env.SMTP_PORT = '587';
    process.env.FROM_EMAIL = 'noreply@test.com';
    process.env.BASE_URL = 'http://localhost:3000';
  });
  afterEach(() => {
    process.env = { ...originalEnv };
  });

  it('solutionsReady claims no validation of the submitted idea, in text or HTML', async () => {
    const { subject, text, html } = await send('solutions', REFUSED);

    for (const body of [text, html]) {
      expect(body).not.toContain('validation scores');
      // The pitch is never the object of a research/validation claim.
      expect(body).not.toContain(`for your research on`);
      expect(body).toContain('We could not check the idea you submitted');
    }
    // The failure story is the artifact's, verbatim — no sentence authored in the backend.
    expect(text).toContain(REFUSED.headline);
    expect(text).toContain(REFUSED.nextStep);
    expect(html).toContain('could not run, so we stopped');
    expect(subject).toBe('Your NicheIQ solutions are ready — we could not check your idea');
    // The pool is real and was paid for: the email still delivers it.
    expect(text).toContain('8 solutions');
    expect(text).toContain('/jobs/job-1');
  });

  it('selectionReminder never calls the solutions "validated ... for <their pitch>"', async () => {
    const { subject, text, html } = await send('reminder', REFUSED);

    for (const body of [text, html]) {
      expect(body).not.toContain('validated solutions');
      expect(body).not.toMatch(/waiting for your review for/);
      expect(body).toContain('could not check the idea you submitted');
    }
    expect(text).toContain(REFUSED.headline);
    expect(subject).toBe(
      'Reminder: your NicheIQ solutions are waiting (we could not check your idea)',
    );
  });

  it('states neither outcome when the artifact cannot be read', async () => {
    // Same doctrine as ResearchProgressScreen's "unknown" default: a surface that cannot
    // read the outcome asserts neither one. `unavailable` must not print the refusal
    // either — that would be inventing a failure we did not verify.
    for (const which of ['solutions', 'reminder'] as const) {
      vi.clearAllMocks();
      const { text, html, subject } = await send(which, { state: 'unavailable' });
      for (const body of [text, html]) {
        expect(body).not.toContain('validated solutions');
        expect(body).not.toContain('validation scores');
        expect(body).not.toContain('could not check the idea you submitted');
        expect(body).not.toContain(PITCH());
      }
      expect(subject).not.toContain('could not check');
    }
  });

  /**
   * S15 — THE CHARGE THAT ALREADY STANDS (owner decision 2026-08-15: Option B, no refund).
   *
   * A refused run keeps the full discovery charge — taken at job creation
   * (`creditService.ts:906`), never refunded on the AWAITING_SELECTION path, pinned by
   * `refusedRunCharge.test.ts`. These emails quote "Run the check again" from the artifact,
   * arrive up to four times over five days, and said nothing about money in either
   * direction, so the honest half of the message ("that failure is ours") was doing the work
   * of implying the run was free. This is the surface that leaves the product: no page fix
   * reaches it.
   */
  it('carries the SAME sentence the page does, and it is not empty', () => {
    // The two deployables cannot share a module, so the guard is that neither may drift: if
    // the policy changes, one edit fails this and the other must follow.
    expect(CHARGE_STANDS.length).toBeGreaterThan(40);
    expect(CHARGE_STANDS).toMatch(/charged/i);
    expect(CHARGE_STANDS).toMatch(/refund/i);
    // …and it prices nothing. The retry's cost is a separate, separately-replaceable line
    // (the page's `rerunPriceRecord`), because whether a retry stays a full-price new run is
    // an open question and this sentence is true either way.
    expect(CHARGE_STANDS).not.toMatch(/credits|balance|new check|paid check/i);
    expect(
      stringLiteral('backend/src/services/emailService.ts', 'IDEA_CHECK_CHARGE_NOTE'),
    ).toBe(CHARGE_STANDS);
  });

  it('discloses the standing charge in both emails, in text and HTML', async () => {
    for (const which of ['solutions', 'reminder'] as const) {
      vi.clearAllMocks();
      const { text, html } = await send(which, REFUSED);
      expect(text, which).toContain(CHARGE_STANDS);
      // The HTML block escapes every row, so the apostrophe arrives as an entity.
      expect(html, which).toContain(CHARGE_STANDS.replace(/'/g, '&#39;'));
    }
  });

  it('discloses it even when the artifact carries neither sentence', async () => {
    // Every refusal materialized before 2026-08-14 is this shape. The charge fact depends on
    // no artifact field, so it must not inherit the reasons the other two rows are withheld —
    // a disclosure that fails OPEN on old data is the defect, not the safe default.
    vi.clearAllMocks();
    const { text, html } = await send('solutions', { state: 'not_evaluated' });
    expect(text).toContain(CHARGE_STANDS);
    expect(html).toContain(CHARGE_STANDS.replace(/'/g, '&#39;'));
  });

  it('says nothing about the charge when the outcome could not be read', async () => {
    // `unavailable` asserts neither outcome; asserting a kept charge would assert one.
    for (const which of ['solutions', 'reminder'] as const) {
      vi.clearAllMocks();
      const { text, html } = await send(which, { state: 'unavailable' });
      for (const body of [text, html]) {
        expect(body).not.toContain('What this cost');
        expect(body).not.toMatch(/refund/i);
      }
    }
  });

  it('escapes the pitch in the HTML refusal note', async () => {
    vi.clearAllMocks();
    const mod = await import('../emailService.js');
    mockSendMail.mockResolvedValue({});
    await mod.sendSelectionReminderEmail('u@example.com', 'job-1', 'n', 3, {
      ...REFUSED,
      pitch: '<script>alert(1)</script>',
    });
    const html = mockSendMail.mock.calls[0][0].html as string;
    expect(html).not.toContain('<script>');
    expect(html).toContain('&lt;script&gt;');
  });
});

describe('AWAITING_SELECTION emails · the controls (withheld, not rewritten)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
    process.env.EMAIL_PROVIDER = 'smtp';
    process.env.SMTP_HOST = 'smtp.test.com';
    process.env.SMTP_PORT = '587';
    process.env.FROM_EMAIL = 'noreply@test.com';
    process.env.BASE_URL = 'http://localhost:3000';
  });
  afterEach(() => {
    process.env = { ...originalEnv };
  });

  /**
   * A discovery run and a GRADED idea check both keep the pre-2026-08-14 copy exactly.
   * Byte-for-byte, because "we only changed the refused branch" is a claim about a diff,
   * and this program has twice found that claim false when measured.
   */
  it('a discovery run and a graded check are byte-identical to the shipped copy', async () => {
    const expectedSolutions =
      'Your NicheIQ Solutions Are Ready for Review!\n'
      + '\n'
      + `We've generated 8 solutions for your research on "${PITCH()}".\n`
      + '\n'
      + "What's next:\n"
      + '- Review the solutions and their validation scores\n'
      + '- Select the solution you want to investigate further\n'
      + "- We'll run a deep analysis on your chosen solution\n"
      + '\n'
      + 'Review Solutions: http://localhost:3000/jobs/job-1\n'
      + '\n'
      + 'Job ID: job-1\n';
    const expectedReminder =
      'Reminder: Your NicheIQ Solutions Are Waiting\n'
      + '\n'
      + `Just a reminder — you have 8 validated solutions waiting for your review for "${PITCH()}".\n`
      + '\n'
      + 'Select a solution to continue with a deep analysis including SEO strategy, market sizing, and a full research report.\n'
      + '\n'
      + 'Review Solutions: http://localhost:3000/jobs/job-1\n'
      + '\n'
      + 'Job ID: job-1\n';

    for (const ctx of [undefined, { state: 'none' } as const, { state: 'evaluated' } as const]) {
      vi.clearAllMocks();
      const solutions = await send('solutions', ctx);
      expect(solutions.text).toBe(expectedSolutions);
      expect(solutions.subject).toBe('Your NicheIQ Solutions Are Ready for Review!');
      expect(solutions.html).toContain(
        `We've generated <strong>8 solutions</strong> for your research on <strong>"${PITCH()}"</strong>.`,
      );
      expect(solutions.html).toContain('<li>Review the solutions and their validation scores</li>');

      vi.clearAllMocks();
      const reminder = await send('reminder', ctx);
      expect(reminder.text).toBe(expectedReminder);
      expect(reminder.subject).toBe('Reminder: Your NicheIQ Solutions Are Waiting');
      expect(reminder.html).toContain(
        `you have <strong>8 validated solutions</strong> waiting for your review for <strong>"${PITCH()}"</strong>.`,
      );
    }
  });

  it('leaves no unsubstituted placeholder in any state', async () => {
    for (const which of ['solutions', 'reminder'] as const) {
      for (const ctx of [
        undefined,
        { state: 'evaluated' } as const,
        { state: 'unavailable' } as const,
        REFUSED,
      ]) {
        vi.clearAllMocks();
        const { text, html } = await send(which, ctx);
        expect(text).not.toMatch(/\{\{[A-Z_]+\}\}/);
        expect(html).not.toMatch(/\{\{[A-Z_]+\}\}/);
      }
    }
  });
});
