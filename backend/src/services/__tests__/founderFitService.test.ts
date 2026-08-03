import { beforeEach, describe, expect, it, vi } from 'vitest';

const { mockChatComplete, mockHasApiKeyForModel } = vi.hoisted(() => ({
  mockChatComplete: vi.fn(),
  mockHasApiKeyForModel: vi.fn(),
}));

vi.mock('../openai.js', () => ({
  chatComplete: mockChatComplete,
  hasApiKeyForModel: mockHasApiKeyForModel,
}));
vi.mock('../../config.js', () => ({
  CONFIG: { founderFitModel: 'gpt-founder-fit-test' },
}));

import {
  founderFitIdeaSnapshot,
  generateFounderFitArtifact,
  parseCurrentFounderFitArtifact,
} from '../founderFitService.js';

const profile = {
  preset: 'solo_bootstrap' as const,
  weeklyTime: 'under_10' as const,
  budget: 'under_1k' as const,
  team: 'solo' as const,
  revenueHorizon: '90_days' as const,
  distributionAdvantages: ['seo' as const],
  strengths: 'Technical writing',
  hardConstraints: '',
};

const idea = {
  idea_id: 'idea_signal',
  idea_revision: 2,
  solution_name: 'Signal Desk',
  description: 'A focused demand signal tool',
  value_proposition: 'Find repeated buyer needs',
  source_pain: 'Teams miss recurring demand signals',
  source_segment: 'Solo SaaS founders',
  target_personas: ['Solo founder'],
  core_features: ['Signal inbox'],
  estimated_development_time: '4-6 weeks',
  technical_feasibility_score: 0.8,
  seo_scalability_score: 0.7,
  tags: { growth_channels: ['seo'], build_complexity: 'medium' },
};

const secondIdea = {
  ...idea,
  idea_id: 'idea_brief',
  idea_revision: 4,
  solution_name: 'Brief Builder',
  headline: 'Turn demand signals into briefs',
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

function modelResult(overrides: Record<string, unknown> = {}) {
  return {
    ideaRef: 'R1',
    verdict: 'needs_reshape',
    summary: 'Promising, but the time constraint needs a smaller first slice.',
    strongestAdvantage: 'The founder can use technical writing through SEO.',
    blockingConflict: null,
    decisionChangingUnknown: 'Whether a useful first slice fits under ten hours per week.',
    sensitivity: 'This fits if the first release can ship in two weeks of part-time work.',
    dimensions: Object.entries(profileField).map(([dimension, field]) => ({
      dimension,
      status: dimension === 'hard_constraints' ? 'irrelevant' : 'unknown',
      summary: dimension === 'hard_constraints' ? 'No hard constraint was supplied.' : 'The supplied data does not prove this fit.',
      profileFields: [field],
      ideaFields: dimension === 'hard_constraints' ? [] : ['estimated_development_time'],
    })),
    suggestedExperiment: {
      assumptionType: 'FEASIBILITY',
      assumption: 'A useful first slice can be built within the available weekly time.',
      whyCritical: 'If not, the idea must be narrowed before validation.',
      currentEvidence: 'The report estimates four to six weeks but does not define a thin slice.',
      method: 'TECHNICAL_SPIKE',
      evidenceSignal: 'USAGE',
      stimulus: 'Build the smallest end-to-end signal inbox path.',
      audience: 'The founder as the initial operator.',
      channel: 'Private development environment.',
      primaryMetric: 'Hours required for one working end-to-end path.',
      passThreshold: 'Complete the path in 12 hours or less.',
      failThreshold: 'More than 20 hours without a working path.',
      measurementWindow: 'Stop after 20 hours or one working path.',
      sampleTarget: 1,
      costEstimate: 'One focused weekend.',
      passAction: 'Proceed to a customer-facing test.',
      failAction: 'Narrow the product mechanism.',
      flatAction: 'Remove one more feature and repeat once.',
      invalidAction: 'Document the blocker and rerun with stable dependencies.',
    },
    ...overrides,
  };
}

describe('founderFitService', () => {
  beforeEach(() => {
    mockChatComplete.mockReset();
    mockHasApiKeyForModel.mockReset();
    mockHasApiKeyForModel.mockReturnValue(true);
  });

  it('refuses generation when the configured model provider has no API key', async () => {
    mockHasApiKeyForModel.mockReturnValue(false);

    await expect(generateFounderFitArtifact(profile, [idea])).rejects.toMatchObject({
      failureCause: 'upstream',
    });
    expect(mockHasApiKeyForModel).toHaveBeenCalledWith('gpt-founder-fit-test');
    expect(mockChatComplete).not.toHaveBeenCalled();
  });

  it('maps temporary model references to canonical idea revisions and fences founder text', async () => {
    mockChatComplete.mockResolvedValue({
      choices: [{ message: { content: JSON.stringify({ results: [modelResult()] }) } }],
    });

    const artifact = await generateFounderFitArtifact(profile, [idea]);

    expect(artifact.results[0]).toMatchObject({
      ideaId: 'idea_signal',
      ideaRevision: 2,
      ideaTitle: 'Signal Desk',
      verdict: 'needs_reshape',
      suggestedExperiment: { ideaId: 'idea_signal', ideaRevision: 2 },
    });
    const request = mockChatComplete.mock.calls[0][0];
    expect(request.messages[1].content).toContain('BEGIN_UNTRUSTED_FOUNDER_CONTEXT');
    expect(request.messages[1].content).toContain('"ideaRef":"R1"');
    expect(request.messages[0].content).toContain('Do not rank ideas');
    expect(request.messages[0].content).toContain('Available idea references (ideaRef): R1');
    expect(request.messages[1].content).toContain('Available idea references: R1');
    expect(request.model).toBe('gpt-founder-fit-test');
    expect(artifact.model).toBe('gpt-founder-fit-test');
  });

  it('maps an exact two-idea response by temporary reference, independent of response order', async () => {
    mockChatComplete.mockResolvedValue({
      choices: [{
        message: {
          content: JSON.stringify({
            results: [modelResult({ ideaRef: 'R2', verdict: 'fits' }), modelResult()],
          }),
        },
      }],
    });

    const artifact = await generateFounderFitArtifact(profile, [idea, secondIdea]);

    expect(artifact.results.map(result => ({
      ideaId: result.ideaId,
      ideaRevision: result.ideaRevision,
      ideaTitle: result.ideaTitle,
    }))).toEqual([
      { ideaId: 'idea_signal', ideaRevision: 2, ideaTitle: 'Signal Desk' },
      { ideaId: 'idea_brief', ideaRevision: 4, ideaTitle: 'Turn demand signals into briefs' },
    ]);
    expect(mockChatComplete.mock.calls[0][0].messages[0].content).toContain(
      'Available idea references (ideaRef): R1, R2',
    );
  });

  it('rejects a model that softens an explicit hard-constraint conflict', async () => {
    const constrained = { ...profile, hardConstraints: 'No customer data may leave the EU.' };
    const result = modelResult({ verdict: 'needs_reshape' }) as any;
    result.dimensions = result.dimensions.map((dimension: any) =>
      dimension.dimension === 'hard_constraints'
        ? { ...dimension, status: 'conflict', summary: 'The required data flow conflicts with the EU-only rule.' }
        : dimension
    );
    mockChatComplete.mockResolvedValue({
      choices: [{ message: { content: JSON.stringify({ results: [result] }) } }],
    });

    await expect(generateFounderFitArtifact(constrained, [idea])).rejects.toMatchObject({
      name: 'FounderFitGenerationError',
      failureCause: 'schema_mismatch',
    });
  });

  it('invalidates a persisted artifact when the profile or exact idea revision changes', async () => {
    mockChatComplete.mockResolvedValue({
      choices: [{ message: { content: JSON.stringify({ results: [modelResult()] }) } }],
    });
    const artifact = await generateFounderFitArtifact(profile, [idea]);

    expect(parseCurrentFounderFitArtifact(artifact, profile, [idea])).not.toBeNull();
    expect(parseCurrentFounderFitArtifact(
      artifact,
      { ...profile, budget: '1k_5k' },
      [idea],
    )).toBeNull();
    expect(parseCurrentFounderFitArtifact(
      artifact,
      profile,
      [{ ...idea, idea_revision: 3 }],
    )).toBeNull();
  });

  it('snapshots only the bounded fields used by the specialist', () => {
    const snapshot = founderFitIdeaSnapshot({
      ...idea,
      secret_internal_note: 'do not expose',
      tags: {
        ...idea.tags,
        strengths: ['market-fit'],
        primary_strength: 'market-fit',
        rationale: 'Generated before final score calibration.',
      },
    });

    expect(snapshot).not.toHaveProperty('secret_internal_note');
    expect(snapshot.tags).toEqual({
      build_complexity: 'medium',
      data_access: null,
      growth_channels: ['seo'],
    });
  });

  it('drops hallucinated ideaFields and injects required profileFields instead of failing', async () => {
    const result = modelResult() as any;
    result.dimensions = result.dimensions.map((dimension: any) => {
      if (dimension.dimension === 'distribution') {
        return { ...dimension, ideaFields: ['tags', 'monetization', 'seo_scalability_score'] };
      }
      if (dimension.dimension === 'time') {
        return { ...dimension, profileFields: ['inventedField', 'weeklyTime'] };
      }
      return dimension;
    });
    mockChatComplete.mockResolvedValue({
      choices: [{ message: { content: JSON.stringify({ results: [result] }) } }],
    });

    const artifact = await generateFounderFitArtifact(profile, [idea]);

    const distribution = artifact.results[0].dimensions.find((d) => d.dimension === 'distribution')!;
    expect(distribution.ideaFields).toEqual(['seo_scalability_score']);
    const time = artifact.results[0].dimensions.find((d) => d.dimension === 'time')!;
    expect(time.profileFields).toContain('weeklyTime');
    expect(time.profileFields).not.toContain('inventedField');
  });

  it('enumerates allowed idea and profile fields in the system prompt', async () => {
    mockChatComplete.mockResolvedValue({
      choices: [{ message: { content: JSON.stringify({ results: [modelResult()] }) } }],
    });
    await generateFounderFitArtifact(profile, [idea]);
    const systemContent = mockChatComplete.mock.calls[0][0].messages[0].content as string;
    expect(systemContent).toContain('tags.build_complexity');
    expect(systemContent).toContain('tags.growth_channels');
    expect(systemContent).toContain('Allowed profileFields');
    expect(systemContent).toContain('Allowed ideaFields');
  });

  it('forces hard_constraints to irrelevant when profile has no hard constraints', async () => {
    const result = modelResult() as any;
    result.dimensions = result.dimensions.map((dimension: any) =>
      dimension.dimension === 'hard_constraints'
        ? { ...dimension, status: 'unknown', ideaFields: ['critic_concern'] }
        : dimension
    );
    mockChatComplete.mockResolvedValue({
      choices: [{ message: { content: JSON.stringify({ results: [result] }) } }],
    });

    const artifact = await generateFounderFitArtifact(profile, [idea]);

    const hardConstraints = artifact.results[0].dimensions.find((d) => d.dimension === 'hard_constraints')!;
    expect(hardConstraints.status).toBe('irrelevant');
    expect(hardConstraints.ideaFields).toEqual([]);
  });

  it('classifies timeout, empty, JSON, schema, and two-idea coverage failures', async () => {
    const timeout = Object.assign(new Error('request timed out'), { name: 'TimeoutError' });
    mockChatComplete.mockRejectedValueOnce(timeout);
    await expect(generateFounderFitArtifact(profile, [idea])).rejects.toMatchObject({
      failureCause: 'timeout',
    });

    mockChatComplete.mockResolvedValueOnce({ choices: [{ message: { content: '' } }] });
    await expect(generateFounderFitArtifact(profile, [idea])).rejects.toMatchObject({
      failureCause: 'no_content',
    });

    mockChatComplete.mockResolvedValueOnce({ choices: [{ message: { content: '{not-json' } }] });
    await expect(generateFounderFitArtifact(profile, [idea])).rejects.toMatchObject({
      failureCause: 'bad_json',
    });

    mockChatComplete.mockResolvedValueOnce({
      choices: [{ message: { content: JSON.stringify({ results: [{ ideaRef: 'R1' }] }) } }],
    });
    await expect(generateFounderFitArtifact(profile, [idea])).rejects.toMatchObject({
      failureCause: 'schema_mismatch',
    });

    mockChatComplete.mockResolvedValueOnce({
      choices: [{ message: { content: JSON.stringify({ results: [modelResult()] }) } }],
    });
    await expect(generateFounderFitArtifact(profile, [idea, secondIdea])).rejects.toMatchObject({
      failureCause: 'coverage_mismatch',
    });
  });

  it('classifies non-timeout provider failures as upstream', async () => {
    mockChatComplete.mockRejectedValueOnce(new Error('provider unavailable'));

    await expect(generateFounderFitArtifact(profile, [idea])).rejects.toMatchObject({
      failureCause: 'upstream',
    });
  });
});
