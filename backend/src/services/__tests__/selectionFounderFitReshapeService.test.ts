import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({ chatComplete: vi.fn() }));

vi.mock('../openai.js', () => ({ chatComplete: mocks.chatComplete }));
vi.mock('../../config.js', () => ({ CONFIG: { openaiApiKey: 'test-key' } }));
vi.mock('../analystModelService.js', () => ({
  resolveAnalystModel: vi.fn().mockResolvedValue('gpt-test'),
  normalizeAnalystUsage: vi.fn(() => ({
    inputTokens: 100,
    outputTokens: 50,
    cacheWriteTokens: 0,
    cacheReadTokens: 0,
  })),
  estimateAnalystCostUsd: vi.fn(() => 0.001),
}));

import { generateSelectionFounderFitReshape } from '../selectionFounderFitReshapeService.js';

const profile = {
  preset: 'solo_bootstrap',
  weeklyTime: 'under_10',
  budget: 'under_1k',
  team: 'solo',
  revenueHorizon: '90_days',
  distributionAdvantages: ['seo'],
  strengths: 'Technical writing',
  hardConstraints: '',
};
const parent = {
  idea_id: 'idea-signal',
  idea_revision: 2,
  solution_name: 'Signal Desk',
  source_pain: 'Teams miss recurring demand signals',
  source_segment: 'Solo SaaS founders',
  description: 'A broad always-on monitoring workflow.',
  estimated_development_time: '4-6 weeks',
};
const profileField = {
  time: 'weeklyTime',
  budget: 'budget',
  team: 'team',
  revenue_horizon: 'revenueHorizon',
  distribution: 'distributionAdvantages',
  strengths: 'strengths',
  hard_constraints: 'hardConstraints',
} as const;
const experiment = {
  ideaId: 'idea-signal',
  ideaRevision: 2,
  assumptionType: 'FEASIBILITY',
  assumption: 'A useful first slice fits the available weekly time.',
  whyCritical: 'Otherwise the candidate needs a smaller shape.',
  currentEvidence: 'The current estimate exceeds the founder time budget.',
  method: 'TECHNICAL_SPIKE',
  evidenceSignal: 'USAGE',
  stimulus: 'Build one end-to-end path.',
  audience: 'The founder as operator.',
  channel: 'Private development environment.',
  primaryMetric: 'Hours to a working path.',
  passThreshold: 'Twelve hours or less.',
  failThreshold: 'More than twenty hours.',
  measurementWindow: 'Stop at twenty hours.',
  sampleTarget: 1,
  costEstimate: 'One weekend.',
  passAction: 'Run a customer test.',
  failAction: 'Narrow again.',
  flatAction: 'Remove one feature.',
  invalidAction: 'Document the blocker.',
};
const dimensions = Object.entries(profileField).map(([dimension, field]) => ({
  dimension,
  status: dimension === 'time' ? 'conflict' : dimension === 'hard_constraints' ? 'irrelevant' : 'aligned',
  summary: dimension === 'time'
    ? 'The current build exceeds the available weekly time.'
    : dimension === 'hard_constraints'
      ? 'No hard constraint was supplied.'
      : 'The supplied profile and candidate are aligned here.',
  profileFields: [field],
  ideaFields: dimension === 'hard_constraints' ? [] : ['estimated_development_time'],
}));
const artifact = {
  version: 1,
  inputFingerprint: 'f'.repeat(64),
  profileSnapshot: profile,
  ideaSnapshots: [parent],
  model: 'gpt-fit',
  createdAt: '2026-07-16T00:00:00.000Z',
  results: [{
    ideaId: 'idea-signal',
    ideaRevision: 2,
    ideaTitle: 'Signal Desk',
    verdict: 'needs_reshape',
    summary: 'The first slice is too broad for the available time.',
    strongestAdvantage: 'Technical writing supports the SEO path.',
    blockingConflict: null,
    decisionChangingUnknown: 'Whether one useful workflow fits in a weekend.',
    sensitivity: 'The verdict changes if continuous monitoring is removed.',
    dimensions,
    suggestedExperiment: experiment,
  }],
};

const output = {
  proposedTitle: 'Weekly Signal Brief',
  proposedBrief: 'One weekly renewal-risk review for a single founder workflow.',
  changeSummary: 'Removes continuous monitoring and secondary workflows.',
  rationale: 'The smaller cadence is designed around the recorded time conflict.',
  parentContribution: 'Keep the renewal signal interpretation workflow.',
  evidenceNoLongerTransfers: ['Demand evidence for continuous monitoring'],
  newAssumptions: ['A weekly review is timely enough for this buyer'],
};

describe('selectionFounderFitReshapeService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.chatComplete.mockResolvedValue({
      choices: [{ message: { content: JSON.stringify(output) } }],
      usage: { prompt_tokens: 100, completion_tokens: 50 },
    });
  });

  it('freezes exact fit conflicts and candidate snapshot provenance on one child proposal', async () => {
    const generated = await generateSelectionFounderFitReshape({
      artifact,
      parent: {
        ideaId: 'idea-signal',
        ideaRevision: 2,
        solutionName: 'Signal Desk',
        snapshot: parent,
      },
    });

    expect(generated.patch).toMatchObject({
      operation: 'narrow',
      parents: [{ ideaId: 'idea-signal', ideaRevision: 2 }],
      evidence: {
        sourceAnchors: [{
          ideaId: 'idea-signal',
          ideaRevision: 2,
          candidateSnapshotSha256: expect.stringMatching(/^[a-f0-9]{64}$/),
        }],
        founderFitRef: {
          inputFingerprint: 'f'.repeat(64),
          verdict: 'needs_reshape',
          conflicts: [{ dimension: 'time', profileFields: ['weeklyTime'] }],
        },
      },
    });
    const request = mocks.chatComplete.mock.calls[0][0];
    expect(request.messages[1].content).toContain('UNTRUSTED FOUNDER FIT CONTEXT');
    expect(request.messages[0].content).toContain('scores');
  });

  it('rejects unsupported certainty language instead of saving a polished claim', async () => {
    mocks.chatComplete.mockResolvedValue({
      choices: [{ message: { content: JSON.stringify({ ...output, rationale: 'This is now proven to fit.' }) } }],
    });

    await expect(generateSelectionFounderFitReshape({
      artifact,
      parent: {
        ideaId: 'idea-signal',
        ideaRevision: 2,
        solutionName: 'Signal Desk',
        snapshot: parent,
      },
    })).rejects.toThrow('UNSUPPORTED_FOUNDER_FIT_RESHAPE_CLAIM');
  });

  it('refuses a hard-constraint conflict even if an artifact is mislabeled needs_reshape', async () => {
    const hardBlocked = {
      ...artifact,
      results: [{
        ...artifact.results[0],
        dimensions: dimensions.map((dimension) => dimension.dimension === 'hard_constraints'
          ? { ...dimension, status: 'conflict', summary: 'The product violates the explicit data boundary.' }
          : dimension),
      }],
    };

    await expect(generateSelectionFounderFitReshape({
      artifact: hardBlocked,
      parent: {
        ideaId: 'idea-signal',
        ideaRevision: 2,
        solutionName: 'Signal Desk',
        snapshot: parent,
      },
    })).rejects.toThrow('HARD_CONSTRAINT_BLOCKED');
    expect(mocks.chatComplete).not.toHaveBeenCalled();
  });
});
