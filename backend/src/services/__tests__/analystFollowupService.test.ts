import { beforeEach, describe, expect, it, vi } from 'vitest';

const {
  mockChatCreate,
  mockChatComplete,
  mockJobUpdate,
  mockTransaction,
} = vi.hoisted(() => ({
  mockChatCreate: vi.fn(),
  mockChatComplete: vi.fn(),
  mockJobUpdate: vi.fn(),
  mockTransaction: vi.fn(),
}));

vi.mock('../db.js', () => ({
  prisma: {
    chatMessage: {
      create: mockChatCreate,
      update: vi.fn(),
    },
    job: { update: mockJobUpdate },
    $transaction: mockTransaction,
  },
}));

vi.mock('../openai.js', () => ({
  chatComplete: mockChatComplete,
  hasApiKeyForModel: () => true,
}));

vi.mock('../analystModelService.js', () => ({
  estimateAnalystCostUsd: vi.fn(() => 0),
  normalizeAnalystUsage: vi.fn(() => ({
    inputTokens: 0,
    outputTokens: 0,
    cacheWriteTokens: 0,
    cacheReadTokens: 0,
  })),
  resolveAnalystModel: vi.fn(async () => 'gpt-test'),
}));

import {
  createRegenerationAnalystFollowup,
  createReportAnalystFollowup,
  createSeedAnalystFollowup,
} from '../analystFollowupService.js';

/** The internal `red_team_verdict` enum. None of these words is product vocabulary: the
 *  shipped label for `killed` is "Premise unproven", and the other two have never had a
 *  user-facing form at all. */
const INTERNAL_VERDICT_TOKENS = /\b(killed|weakened|survives)\b/i;

describe('createReportAnalystFollowup', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockChatCreate.mockResolvedValue({ id: 'message-1' });
  });

  it('persists a deterministic opening grounded in the nested decision and caveats', async () => {
    await createReportAnalystFollowup({
      jobId: 'job-1',
      operationId: 'dispatch-1',
      niche: 'freelance video editors',
      report: {
        selected_solution_name: 'ScopeShield Post Kit',
        executive_dashboard: {
          go_no_go_verdict: {
            verdict: 'Conditional',
            risk_level: 'Medium',
            primary_concern: 'Standalone willingness to pay remains unvalidated',
          },
        },
        selected_solution_details: {
          red_team_verdict: 'weakened',
          red_team_caveats: [
            'Search evidence did not validate a buyer for a standalone scope tracker.',
          ],
        },
        data_quality_summary: {
          quality_caveats: ['Only 26% of search queries were niche-anchored.'],
        },
      },
    });

    const content = mockChatCreate.mock.calls[0][0].data.content as string;
    expect(content).toContain('**ScopeShield Post Kit**');
    expect(content).toContain('**Conditional**');
    expect(content).toContain('**Medium risk**');
    expect(content).toContain('Standalone willingness to pay remains unvalidated.');
    expect(content).toContain('returned **a decision-critical objection**');
    expect(content).toContain('Search evidence did not validate a buyer');
    expect(content).toContain('Only 26% of search queries were niche-anchored.');
    expect(content).toContain('not confirmation of product-market fit');
    expect(content).toContain('read-only');
    expect(content.toLowerCase()).not.toContain('clear product-market fit');
    expect(mockChatComplete).not.toHaveBeenCalled();
    expect(mockTransaction).not.toHaveBeenCalled();
  });

  it('uses nested snapshot and verdict fallbacks without inventing a positive result', async () => {
    await createReportAnalystFollowup({
      jobId: 'job-2',
      operationId: 'dispatch-2',
      niche: 'test niche',
      report: {
        executive_dashboard: {
          recommended_solution_snapshot: { name: 'Stored Candidate' },
          go_no_go_verdict: { verdict: 'No-Go', risk_level: 'High' },
        },
      },
    });

    const content = mockChatCreate.mock.calls[0][0].data.content as string;
    expect(content).toContain('**Stored Candidate**');
    expect(content).toContain('**No-Go**');
    expect(content).toContain('**High risk**');
    expect(content).toContain('does not record a single primary concern');
    expect(content).not.toContain('clear product-market fit');
    expect(mockChatComplete).not.toHaveBeenCalled();
  });
});

/**
 * `red_team_verdict` reached a user once as "recorded risk: killed" — about an idea that was
 * still live and selectable on the same screen. The enum is a verdict on the PREMISE, it is
 * not a risk, and "killed" is the one word this product deliberately does not use. This is the
 * regression fence for every operation summary the analyst writes.
 */
describe('adversarial-review vocabulary', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockChatCreate.mockResolvedValue({ id: 'message-1' });
    mockChatComplete.mockResolvedValue({
      choices: [{ message: { content: 'enriched note' } }],
      usage: {},
    });
    mockTransaction.mockResolvedValue([]);
  });

  const committedContent = () => mockChatCreate.mock.calls[0][0].data.content as string;

  it.each(['killed', 'weakened', 'survives'])(
    'never emits the raw "%s" verdict in a seed summary',
    async (verdict) => {
      await createSeedAnalystFollowup({
        jobId: 'job-1',
        dispatchId: 'dispatch-1',
        niche: 'test niche',
        outcome: 'accepted',
        idea: {
          solution_name: 'Stored Candidate',
          technical_feasibility_score: 0.85,
          market_fit_score: 0.45,
          red_team_verdict: verdict,
        },
      });

      expect(committedContent()).not.toMatch(INTERNAL_VERDICT_TOKENS);
    },
  );

  it('names the killed verdict the way the owner\'s screen does', async () => {
    await createSeedAnalystFollowup({
      jobId: 'job-1',
      dispatchId: 'dispatch-1',
      niche: 'test niche',
      outcome: 'accepted',
      idea: { solution_name: 'Stored Candidate', red_team_verdict: 'killed' },
    });

    const content = committedContent();
    expect(content).toContain('adversarial review: Premise unproven');
    expect(content).not.toContain('recorded risk');
  });

  it('prefers the stored risk prose and does not restate the verdict as a risk', async () => {
    await createSeedAnalystFollowup({
      jobId: 'job-1',
      dispatchId: 'dispatch-1',
      niche: 'test niche',
      outcome: 'demoted',
      idea: {
        solution_name: 'Stored Candidate',
        key_risk: 'No reachable buyer was found for this workflow.',
        red_team_verdict: 'killed',
      },
    });

    const content = committedContent();
    expect(content).toContain('recorded risk: No reachable buyer was found for this workflow.');
    expect(content).not.toContain('adversarial review');
    expect(content).not.toMatch(INTERNAL_VERDICT_TOKENS);
  });

  it('drops an unrecognised verdict rather than echoing it', async () => {
    await createSeedAnalystFollowup({
      jobId: 'job-1',
      dispatchId: 'dispatch-1',
      niche: 'test niche',
      outcome: 'accepted',
      idea: { solution_name: 'Stored Candidate', red_team_verdict: 'obliterated' },
    });

    expect(committedContent()).not.toContain('obliterated');
  });

  it('never emits the raw verdict in a report summary', async () => {
    await createReportAnalystFollowup({
      jobId: 'job-1',
      operationId: 'dispatch-1',
      niche: 'test niche',
      report: {
        selected_solution_name: 'Stored Candidate',
        executive_dashboard: { go_no_go_verdict: { verdict: 'Conditional', risk_level: 'Medium' } },
        selected_solution_details: {
          red_team_verdict: 'killed',
          red_team_caveats: ['No reachable buyer was found for this workflow.'],
        },
      },
    });

    const content = committedContent();
    expect(content).toContain('returned **Premise unproven**');
    expect(content).not.toMatch(INTERNAL_VERDICT_TOKENS);
  });

  // The enriched note replaces the deterministic one, and a model repeats the vocabulary it
  // is handed — so the committed result the analyst reads must not carry the enum either.
  it.each(['killed', 'weakened', 'survives'])(
    'hands the analyst no raw "%s" token to parrot',
    async (verdict) => {
      await createSeedAnalystFollowup({
        jobId: 'job-1',
        dispatchId: 'dispatch-1',
        niche: 'test niche',
        outcome: 'accepted',
        idea: { solution_name: 'Stored Candidate', red_team_verdict: verdict },
      });
      await vi.waitFor(() => expect(mockChatComplete).toHaveBeenCalled());

      const payload = mockChatComplete.mock.calls[0][0].messages[1].content as string;
      expect(payload).not.toMatch(INTERNAL_VERDICT_TOKENS);
    },
  );

  it('strips the enum from the regeneration payload too', async () => {
    await createRegenerationAnalystFollowup({
      jobId: 'job-1',
      dispatchId: 'dispatch-1',
      niche: 'test niche',
      ideas: [{ solution_name: 'Stored Candidate', red_team_verdict: 'killed' }],
    });
    await vi.waitFor(() => expect(mockChatComplete).toHaveBeenCalled());

    expect(committedContent()).not.toMatch(INTERNAL_VERDICT_TOKENS);
    const payload = mockChatComplete.mock.calls[0][0].messages[1].content as string;
    expect(payload).not.toMatch(INTERNAL_VERDICT_TOKENS);
    expect(payload).toContain('Premise unproven');
  });
});
