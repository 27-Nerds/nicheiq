import { beforeEach, describe, expect, it, vi } from 'vitest';

const { mockChatCreate, mockChatComplete, mockJobUpdate, mockTransaction } = vi.hoisted(() => ({
  mockChatCreate: vi.fn(),
  mockChatComplete: vi.fn(),
  mockJobUpdate: vi.fn(),
  mockTransaction: vi.fn(),
}));

vi.mock('../db.js', () => ({
  prisma: {
    chatMessage: { create: mockChatCreate, update: vi.fn() },
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
    inputTokens: 0, outputTokens: 0, cacheWriteTokens: 0, cacheReadTokens: 0,
  })),
  resolveAnalystModel: vi.fn(async () => 'gpt-test'),
}));

import { createReportAnalystFollowup } from '../analystFollowupService.js';

/**
 * The completed-report opening quotes `data_quality_summary.quality_caveats[0]` to the owner.
 * That field is producer prose written for the pipeline, and it was being printed verbatim —
 * the same leak the frontend closed for the report and shortlist surfaces, reached through a
 * renderer no frontend module can see (finding D27).
 *
 * A snake_case-token scan passes on most of these inputs even when the whole producer sentence
 * ships, so the assertions are on the PHRASES.
 */
const PRODUCER_PHRASES: [string, RegExp][] = [
  ['Calibration note', /\bCalibration note\b/i],
  ['route verifier', /\broute verifier\b/i],
  ['cites data route', /\bcites? (?:a )?data route\b/i],
  ['as market-fit support', /\bas market-fit support\b/i],
  ['market-fit score', /\bmarket-fit score\b/i],
  ['unverified on the data-route dimension', /\bunverified on the data-route dimension\b/i],
  // Bare, not "Idea-set coverage —": the anchored COVERAGE_NOTE misses a TRUNCATED input, and
  // the blind clause-dash rule then turns the head into "Idea-set coverage." — still the
  // producer's own label, and a dash-suffixed pattern reads 0 on it.
  ['Idea-set coverage', /\bIdea-set coverage\b/i],
  ['Concentration may reflect …', /Concentration may reflect where the real opportunity is/i],
];
const INTERNAL_TOKEN = /\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b|\bWTP\b/;
const CLAUSE_DASH = /\S\s+[—–]+\s+\S/;

/**
 * TWO REAL CAVEATS LONGER THAN THE 280-CHARACTER CLIP, and their length is the point: 43 of
 * the 163 distinct `quality_caveats` values under `output/` are longer than that, so a
 * sanitiser placed AFTER `conciseSentence` reads a cut-off sentence.
 *
 * The coverage note is the sharper of the two. `COVERAGE_NOTE` is anchored `^…$` on the whole
 * producer sentence, so a clipped input does not match it at all: the value falls through to
 * the word rules and the buyer reads "Idea-set coverage. Validated pains with no idea: …" —
 * the producer's own head, with its em dash blindly turned into a full stop.
 */
const LONG_CALIBRATION_CAVEAT =
  'Calibration note for "Signal-to-Reply Watchboard" cites data route "GDELT 2.1 open data files, W3C WebSub Recommendation" as market-fit support, but the route verifier did not confirm it (data_access_model: unverified). Treat the market-fit score as unverified on the data-route dimension.';
const LONG_COVERAGE_CAVEAT =
  'Idea-set coverage — validated pains with no idea: Severe adverse reactions like heart palpitations without emergency guidance; Weight loss stalls for months despite max GLP-1 dose, no clear next step; Risk of adverse interactions when stacking multiple peptides without clinical data; Difficulty sourcing all peptides for a stack from reliable vendors (+3 more). Concentration may reflect where the real opportunity is, not a defect — shown for your judgment.';

async function openingFor(caveat: string): Promise<string> {
  mockChatCreate.mockResolvedValue({ id: 'message-1' });
  await createReportAnalystFollowup({
    jobId: 'job-1',
    operationId: 'dispatch-1',
    niche: 'independent game studios',
    report: {
      selected_solution_name: 'PayoutClarity',
      executive_dashboard: { go_no_go_verdict: { verdict: 'Conditional', risk_level: 'Medium' } },
      data_quality_summary: { quality_caveats: [caveat] },
    },
  });
  return mockChatCreate.mock.calls[0][0].data.content as string;
}

describe('the completed-report opening reads quality_caveats the way the product does', () => {
  beforeEach(() => vi.clearAllMocks());

  it('prints no producer phrase, internal token or clause dash', async () => {
    const caveats = [
      LONG_CALIBRATION_CAVEAT,
      LONG_COVERAGE_CAVEAT,
      'Idea-set coverage — 3 of 5 ideas address "Manual invoicing eats the week". Concentration may reflect where the real opportunity is, not a defect — shown for your judgment.',
      'Core pain point \'title=\'Burnout and Mental Health Struggles\' severity_score=0.9 willingness_to_pay_score=0.6 source_platform=\'Reddit r/gamedev\'\' (the #1 pain point by severity+WTP) is not in the selected solution\'s pain_points_addressed list.',
    ];
    for (const caveat of caveats) {
      vi.clearAllMocks();
      const opening = await openingFor(caveat);
      expect(opening).toContain('Data-quality caveat:');
      for (const [name, pattern] of PRODUCER_PHRASES) {
        expect(opening, `producer phrase reached the owner: ${name}`).not.toMatch(pattern);
      }
      expect(opening, 'internal token reached the owner').not.toMatch(INTERNAL_TOKEN);
      expect(opening, 'clause dash reached the owner').not.toMatch(CLAUSE_DASH);
    }
  });

  it('sanitises BEFORE the 280-character clip, so the stanza rules still see whole sentences', async () => {
    const calibration = await openingFor(LONG_CALIBRATION_CAVEAT);
    expect(calibration).toContain('Research caveat');
    expect(calibration).toContain('Data access: Not verified');
    // The tail of the producer sentence sits past the clip. Clipping first leaves
    // "…as unverified on the data-route…" where the reading should be "not verified for
    // data access".
    expect(calibration).toContain('not verified for data access');
    expect(calibration).not.toMatch(/unverified on the data-route/i);

    vi.clearAllMocks();
    const coverage = await openingFor(LONG_COVERAGE_CAVEAT);
    // Clipping first misses the anchored COVERAGE_NOTE entirely.
    expect(coverage).toContain('validated problems have no matching idea yet');
    expect(coverage).not.toMatch(/Idea-set coverage/i);
  });

  it('keeps a caveat that needs no rewriting exactly as stored', async () => {
    const stored = 'Only 26% of search queries were niche-anchored.';
    expect(await openingFor(stored)).toContain(`Data-quality caveat: ${stored}`);
  });

  it('falls back to the stored caveat rather than dropping the buyer\'s content', async () => {
    // `buyerFacingCoverageNote` returns '' for a blank entry; a caveat of only whitespace is
    // filtered upstream by `textList`, so the opening reports no caveat at all.
    const opening = await openingFor('   ');
    expect(opening).toContain('No solution-specific red-team or data-quality caveat was stored.');
  });
});
