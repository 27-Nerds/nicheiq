import { beforeEach, describe, expect, it, vi } from 'vitest';

const chatComplete = vi.fn();

vi.mock('../../config.js', () => ({
  CONFIG: { openaiApiKey: 'test-key' },
}));
vi.mock('../openai.js', () => ({
  chatComplete: (...args: unknown[]) => chatComplete(...args),
}));
vi.mock('../analystModelService.js', () => ({
  resolveAnalystModel: vi.fn().mockResolvedValue('test-model'),
  normalizeAnalystUsage: vi.fn().mockReturnValue({
    inputTokens: 100,
    outputTokens: 50,
    cacheWriteTokens: 0,
    cacheReadTokens: 0,
  }),
  estimateAnalystCostUsd: vi.fn().mockReturnValue(0.001),
}));

const JOB_ID = '550e8400-e29b-41d4-a716-446655440000';
const EXPERIMENT_ID = '123e4567-e89b-42d3-a456-426614174000';
const CONCLUSION_ID = '223e4567-e89b-42d3-a456-426614174000';

const conclusionSnapshot = {
  schemaVersion: 1,
  experiment: {
    experimentId: EXPERIMENT_ID,
    jobId: JOB_ID,
    ideaId: 'idea-parent',
    ideaRevision: 3,
    ideaSnapshot: { solution_name: 'Signal Desk' },
    assumptionType: 'DESIRABILITY',
    evidenceSignal: 'STATED_PREFERENCE',
    assumption: 'Operators will pay for a broad signal dashboard.',
  },
  precommitment: {
    primaryMetric: 'Paid pilots',
    passThreshold: '3 pilots',
    failThreshold: '0 pilots',
    measurementWindow: '14 days',
    sampleTarget: 12,
    passAction: 'Build concierge version',
    failAction: 'Narrow to one buyer and workflow',
    ambiguousAction: 'Narrow the promise and repeat',
    invalidAction: 'Repair recruitment',
  },
  evidence: {
    source: {
      sourceType: 'MANUAL',
      adapterKey: 'manual',
      references: ['Interview notes / July cohort'],
    },
    limitations: ['One community'],
  },
  adjudication: {
    outcome: 'FAIL',
    basis: 'OWNER_RECORDED',
    rationale: 'No participant would commit to the broad dashboard.',
    nextAction: 'Narrow to one buyer and workflow',
  },
};

const input = {
  jobId: JOB_ID,
  experimentId: EXPERIMENT_ID,
  conclusionId: CONCLUSION_ID,
  outcome: 'FAIL' as const,
  evidenceSource: 'MANUAL' as const,
  parent: {
    ideaId: 'idea-parent',
    ideaRevision: 3,
    solutionName: 'Signal Desk',
    snapshot: {
      source_pain: 'Operators miss recurring demand signals',
      source_segment: 'Operations leads',
    },
  },
  conclusionSnapshot,
  decisionProfile: { team: 'solo', weeklyTime: '5-10h' },
};

beforeEach(() => {
  vi.clearAllMocks();
  chatComplete.mockResolvedValue({
    choices: [{
      message: {
        content: JSON.stringify({
          proposedTitle: 'Agency Renewal Signal Desk',
          proposedBrief: 'A focused signal desk for small agencies preparing weekly renewal-risk reviews.',
          changeSummary: 'Narrows the buyer and workflow to agency renewal reviews.',
          rationale: 'The broad dashboard failed to earn commitment; one recurring review is easier to test.',
          parentContribution: 'Keep the recurring demand-signal workflow.',
          newAssumptions: ['Agency operators run a weekly renewal review.'],
        }),
      },
    }],
    usage: {},
  });
});

describe('selection idea narrowing service', () => {
  it('lets the model write only the variant while the server binds lineage and immutable evidence', async () => {
    const { generateSelectionIdeaNarrowing } = await import('../selectionIdeaNarrowingService.js');
    const result = await generateSelectionIdeaNarrowing(input);

    expect(result.patch.operation).toBe('narrow');
    expect(result.patch.parents).toEqual([expect.objectContaining({
      ideaId: 'idea-parent',
      ideaRevision: 3,
      solutionName: 'Signal Desk',
    })]);
    expect(result.patch.evidence.experimentConclusionRefs).toEqual([expect.objectContaining({
      conclusionId: CONCLUSION_ID,
      experimentId: EXPERIMENT_ID,
      outcome: 'FAIL',
      evidenceSource: 'MANUAL',
      snapshotSha256: expect.stringMatching(/^[a-f0-9]{64}$/),
      evidenceRefs: [{ adapterKey: 'manual', reference: 'Interview notes / July cohort' }],
    })]);
    expect(result.patch.evidence.requiresValidation).toContain('Narrow to one buyer and workflow');
  });

  it('rejects a model response that turns the child into an unsupported certainty claim', async () => {
    chatComplete.mockResolvedValueOnce({
      choices: [{
        message: {
          content: JSON.stringify({
            proposedTitle: 'Validated Agency Desk',
            proposedBrief: 'A focused signal desk for small agencies preparing weekly renewal-risk reviews.',
            changeSummary: 'Narrows the buyer and workflow to agency renewal reviews.',
            rationale: 'The broad dashboard failed to earn commitment; one recurring review is easier to test.',
            parentContribution: 'Keep the recurring demand-signal workflow.',
            newAssumptions: ['Agency operators run a weekly renewal review.'],
          }),
        },
      }],
      usage: {},
    });
    const { generateSelectionIdeaNarrowing } = await import('../selectionIdeaNarrowingService.js');
    await expect(generateSelectionIdeaNarrowing(input)).rejects.toThrow('UNSUPPORTED_NARROWING_CLAIM');
  });

  it('rejects a conclusion snapshot that no longer names the exact parent revision', async () => {
    const { generateSelectionIdeaNarrowing } = await import('../selectionIdeaNarrowingService.js');
    await expect(generateSelectionIdeaNarrowing({
      ...input,
      conclusionSnapshot: {
        ...conclusionSnapshot,
        experiment: { ...conclusionSnapshot.experiment, ideaRevision: 2 },
      },
    })).rejects.toThrow('STALE_CONCLUSION_SNAPSHOT');
    expect(chatComplete).not.toHaveBeenCalled();
  });
});
