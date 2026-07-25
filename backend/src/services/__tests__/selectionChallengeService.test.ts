import { beforeEach, describe, expect, it, vi } from 'vitest';

const { mockChatComplete } = vi.hoisted(() => ({ mockChatComplete: vi.fn() }));

vi.mock('../openai.js', () => ({ chatComplete: mockChatComplete }));
vi.mock('../../config.js', () => ({
  CONFIG: { chatModel: 'gpt-test' },
}));

import {
  generateSelectionChallenge,
  prepareSelectionChallengeInput,
  reduceSelectionChallenge,
} from '../selectionChallengeService.js';

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
  market_fit_score: 0.92,
  technical_feasibility_score: 0.8,
};

const previewReport = {
  audience_mapping: {
    audience_segments: [{
      segment_name: 'Solo SaaS founders',
      payability_class: 'prosumer-wallet',
      where_they_gather: ['founder communities'],
    }],
  },
  market_reality: {
    wallet: { wallet_class: 'prosumer', evidence: 'Some founders already pay for monitoring tools.' },
    incumbents: [{ name: 'Manual search', pricing: '$0', gap: 'Slow and inconsistent' }],
  },
  data_quality_summary: { quality_caveats: ['Payment intent was not directly measured.'] },
};

const discoveryData = {
  quotes: {
    'Teams miss recurring demand signals': [{
      text: 'I keep finding the same request after we already planned the quarter.',
      source_url: 'https://example.com/post/1',
    }],
  },
};

const ownerEvidence = [{
  id: '123e4567-e89b-42d3-a456-426614174000',
  ideaId: idea.idea_id,
  ideaRevision: idea.idea_revision,
  lens: 'DEMAND' as const,
  kind: 'CUSTOMER_QUOTE' as const,
  position: 'SUPPORTS' as const,
  title: 'Interview with an operations lead',
  content: 'I would pay to stop checking five dashboards every morning.',
  sourceUrl: 'https://example.com/interview/42',
  observedAt: new Date('2026-07-15T10:00:00.000Z'),
  createdAt: new Date('2026-07-16T10:00:00.000Z'),
  retractedAt: null,
}];

const originChallengeId = '523e4567-e89b-42d3-a456-426614174000';

function experimentResult(index = 0, overrides: Record<string, unknown> = {}) {
  const experimentId = `623e4567-e89b-42d3-a456-4266141740${String(index).padStart(2, '0')}`;
  const conclusionId = `723e4567-e89b-42d3-a456-4266141740${String(index).padStart(2, '0')}`;
  const sourceType = overrides.sourceType === 'MANUAL' ? 'MANUAL' : 'FIRST_PARTY';
  return {
    id: experimentId,
    ideaId: idea.idea_id,
    ideaRevision: idea.idea_revision,
    originChallengeId,
    originChallenge: {
      id: originChallengeId,
      ideaId: idea.idea_id,
      ideaRevision: idea.idea_revision,
      lens: 'DEMAND' as const,
    },
    conclusion: {
      id: conclusionId,
      createdAt: new Date(`2026-07-${String(10 + index).padStart(2, '0')}T12:00:00.000Z`),
      snapshot: {
        schemaVersion: 1,
        experiment: {
          experimentId,
          ideaId: idea.idea_id,
          ideaRevision: idea.idea_revision,
          originSnapshot: { challengeId: originChallengeId, lens: 'demand' },
        },
        precommitment: {
          primaryMetric: 'Qualified CTA rate',
          passThreshold: 'At least 8%',
          failThreshold: 'Below 3%',
          measurementWindow: '14 days',
          sampleTarget: 100,
        },
        evidence: sourceType === 'FIRST_PARTY' ? {
          source: { sourceType, adapterKey: 'nicheiq-hosted' },
          window: { observedThrough: '2026-07-15T12:00:00.000Z' },
          sample: { observed: 120, target: 100, unit: 'qualified exposures' },
          metrics: [{
            key: 'cta_rate',
            label: 'Qualified CTA rate',
            valueType: 'RATE',
            value: 0.1,
            numerator: 12,
            denominator: 120,
            isPrimary: true,
          }],
          limitations: ['One acquisition channel was tested.'],
        } : {
          source: { sourceType, adapterKey: 'manual' },
          window: { observedThrough: '2026-07-15T00:00:00.000Z' },
          observationSummary: 'Twelve structured interviews were completed.',
          observedMetric: '1 of 12 requested follow-up',
          sample: { observed: 12, target: 12, unit: null },
          limitations: ['One professional community supplied participants.'],
        },
        adjudication: {
          outcome: 'PASS',
          rationale: 'Owner-authored interpretation must not become evidence.',
        },
      },
    },
    ...overrides,
  };
}

function response(
  questionIds: readonly string[],
  positions: Array<'supports' | 'contradicts' | 'mixed' | 'insufficient'>,
  overrides: Record<string, unknown> = {},
) {
  return {
    choices: [{
      message: {
        content: JSON.stringify({
          assessments: questionIds.map((questionId, index) => ({
            questionId,
            position: positions[index],
            summary: `Assessment ${index + 1} from captured evidence.`,
            subjectKeys: ['I1'],
            evidenceKeys: positions[index] === 'insufficient' ? [] : ['S1'],
            evidenceClass: positions[index] === 'insufficient' ? 'inference' : 'observed',
            ...overrides,
          })),
        }),
      },
    }],
  };
}

describe('selectionChallengeService', () => {
  beforeEach(() => mockChatComplete.mockReset());

  it('runs isolated skeptic and auditor calls over the same bounded evidence without scores or founder context', async () => {
    const questions = ['pain_is_observed', 'urgency_is_behavioral', 'buyer_will_pay'] as const;
    mockChatComplete
      .mockResolvedValueOnce(response(questions, ['contradicts', 'mixed', 'insufficient']))
      .mockResolvedValueOnce(response(questions, ['supports', 'mixed', 'insufficient']));

    const artifact = await generateSelectionChallenge({
      lens: 'demand',
      idea,
      previewReport,
      discoveryData,
    });

    expect(mockChatComplete).toHaveBeenCalledTimes(2);
    const skeptic = mockChatComplete.mock.calls[0][0];
    const auditor = mockChatComplete.mock.calls[1][0];
    expect(skeptic.messages[0].content).toContain('falsification-focused skeptic');
    expect(auditor.messages[0].content).toContain('independent evidence auditor');
    for (const request of [skeptic, auditor]) {
      expect(request.messages[1].content).toContain('I keep finding the same request');
      expect(request.messages[1].content).toContain('pain_is_observed');
      expect(request.messages[1].content).not.toContain('market_fit_score');
      expect(request.messages[1].content).not.toContain('technical_feasibility_score');
      expect(request.messages[1].content).not.toContain('hardConstraints');
      expect(request.messages[1].content).not.toContain('suggestedExperiment');
      expect(request.messages[0].content).toContain('Never fabricate, invent, or guess evidence keys');
      expect(request.messages[1].content).toContain('Available evidence keys: S1');
      expect(request.messages[1].content).toContain('Available subject keys: I1');
    }
    expect(artifact.questions[0].consensus).toBe('disputed');
    expect(artifact.overall).toBe('disputed');
  });

  it('drops hallucinated source keys and downgrades to insufficient instead of failing', async () => {
    const questions = ['pain_is_observed', 'urgency_is_behavioral', 'buyer_will_pay'] as const;
    mockChatComplete
      .mockResolvedValueOnce(response(questions, ['supports', 'supports', 'supports'], { evidenceKeys: ['S99'] }))
      .mockResolvedValueOnce(response(questions, ['supports', 'supports', 'supports'], { evidenceKeys: ['S99'] }));

    const artifact = await generateSelectionChallenge({
      lens: 'demand',
      idea,
      previewReport,
      discoveryData,
    });

    for (const question of artifact.questions) {
      expect(question.skeptic.evidenceKeys).toEqual([]);
      expect(question.skeptic.position).toBe('insufficient');
      expect(question.auditor.evidenceKeys).toEqual([]);
      expect(question.auditor.position).toBe('insufficient');
    }
    expect(artifact.overall).toBe('insufficient_evidence');
  });

  it('keeps valid evidence keys while dropping only hallucinated ones', async () => {
    const questions = ['pain_is_observed', 'urgency_is_behavioral', 'buyer_will_pay'] as const;
    mockChatComplete
      .mockResolvedValueOnce(response(questions, ['supports', 'supports', 'supports'], { evidenceKeys: ['S1', 'S99'] }))
      .mockResolvedValueOnce(response(questions, ['supports', 'supports', 'supports'], { evidenceKeys: ['S1', 'S50'] }));

    const artifact = await generateSelectionChallenge({
      lens: 'demand',
      idea,
      previewReport,
      discoveryData,
    });

    for (const question of artifact.questions) {
      expect(question.skeptic.evidenceKeys).toEqual(['S1']);
      expect(question.auditor.evidenceKeys).toEqual(['S1']);
      expect(question.skeptic.position).toBe('supports');
      expect(question.auditor.position).toBe('supports');
    }
  });

  it('normalizes lowercase and whitespace-padded evidence/subject keys from the LLM', async () => {
    const questions = ['pain_is_observed', 'urgency_is_behavioral', 'buyer_will_pay'] as const;
    mockChatComplete
      .mockResolvedValueOnce(response(questions, ['supports', 'supports', 'insufficient'], {
        evidenceKeys: [' s1 '],
        subjectKeys: ['i1'],
      }))
      .mockResolvedValueOnce(response(questions, ['supports', 'supports', 'insufficient'], {
        evidenceKeys: ['S1'],
        subjectKeys: ['I1'],
      }));

    const artifact = await generateSelectionChallenge({
      lens: 'demand',
      idea,
      previewReport,
      discoveryData,
    });

    expect(artifact.questions[0].skeptic.evidenceKeys).toEqual(['S1']);
    expect(artifact.questions[0].skeptic.subjectKeys).toEqual(['I1']);
    expect(artifact.questions[0].consensus).toBe('supported');
  });

  it('canonically classifies non-quote evidence as proxy even when a model calls it observed', async () => {
    const questions = ['substitutes_are_weak', 'switching_barrier_is_surmountable', 'wedge_is_defensible'] as const;
    mockChatComplete
      .mockResolvedValueOnce(response(questions, ['supports', 'supports', 'supports']))
      .mockResolvedValueOnce(response(questions, ['supports', 'supports', 'supports']));

    const artifact = await generateSelectionChallenge({
      lens: 'competition',
      idea,
      previewReport,
      discoveryData,
    });

    expect(artifact.questions[0].skeptic.evidenceClass).toBe('proxy');
    expect(artifact.questions[0].auditor.evidenceClass).toBe('proxy');
  });

  it('abstains deterministically when no captured evidence can answer the lens', async () => {
    const artifact = await generateSelectionChallenge({
      lens: 'dependencies',
      idea,
      previewReport: null,
      discoveryData: null,
    });

    expect(mockChatComplete).not.toHaveBeenCalled();
    expect(artifact.overall).toBe('insufficient_evidence');
    expect(artifact.questions.every(question => question.consensus === 'insufficient')).toBe(true);
  });

  it('fingerprints only bounded idea subjects and immutable sources', () => {
    const prepared = prepareSelectionChallengeInput({
      lens: 'demand',
      idea: { ...idea, secret_internal_note: 'never expose this' },
      previewReport,
      discoveryData,
    });

    expect(prepared.ideaSnapshot).not.toHaveProperty('secret_internal_note');
    expect(prepared.ideaSnapshot).not.toHaveProperty('market_fit_score');
    expect(prepared.evidenceSnapshot.length).toBeGreaterThan(0);
    expect(prepared.inputFingerprint).toHaveLength(64);
  });

  it('includes only active exact-revision owner evidence and changes the fingerprint', () => {
    const base = prepareSelectionChallengeInput({
      lens: 'demand',
      idea,
      previewReport,
      discoveryData,
    });
    const withOwnerEvidence = prepareSelectionChallengeInput({
      lens: 'demand',
      idea,
      previewReport,
      discoveryData,
      ownerEvidence: [
        ...ownerEvidence,
        { ...ownerEvidence[0], id: '223e4567-e89b-42d3-a456-426614174000', ideaRevision: 1 },
        { ...ownerEvidence[0], id: '323e4567-e89b-42d3-a456-426614174000', lens: 'COMPETITION' as const },
        { ...ownerEvidence[0], id: '423e4567-e89b-42d3-a456-426614174000', retractedAt: new Date() },
      ],
    });

    const ownerSources = withOwnerEvidence.evidenceSnapshot.filter(source => source.kind === 'owner_evidence');
    expect(ownerSources).toHaveLength(1);
    expect(ownerSources[0]).toMatchObject({
      title: 'Owner-provided: Interview with an operations lead',
      provenance: {
        assetType: 'OWNER_EVIDENCE',
        evidenceItemId: ownerEvidence[0].id,
        position: 'SUPPORTS',
        ownerKind: 'CUSTOMER_QUOTE',
      },
    });
    expect(withOwnerEvidence.inputFingerprint).not.toBe(base.inputFingerprint);
  });

  it('turns structured preview evidence into readable cited-source text', () => {
    const prepared = prepareSelectionChallengeInput({
      lens: 'competition',
      idea,
      previewReport,
      discoveryData,
    });

    const competitor = prepared.evidenceSnapshot.find(source => source.kind === 'competitor_fact');
    expect(competitor?.excerpt).toBe('Pricing: $0 · Gap: Slow and inconsistent');
    expect(competitor?.excerpt).not.toContain('{"');
  });

  it('keeps owner-provided evidence unverified and canonically classifies it as proxy', async () => {
    const questions = ['pain_is_observed', 'urgency_is_behavioral', 'buyer_will_pay'] as const;
    mockChatComplete
      .mockResolvedValueOnce(response(questions, ['supports', 'supports', 'supports']))
      .mockResolvedValueOnce(response(questions, ['supports', 'supports', 'supports']));

    const artifact = await generateSelectionChallenge({
      lens: 'demand',
      idea,
      previewReport: null,
      discoveryData: null,
      ownerEvidence,
    });

    const request = mockChatComplete.mock.calls[0][0];
    expect(request.messages[0].content).toContain('unverified owner-provided inputs');
    expect(request.messages[1].content).toContain('I would pay to stop checking five dashboards');
    expect(artifact.questions[0].skeptic.evidenceClass).toBe('proxy');
    expect(artifact.questions[0].auditor.evidenceClass).toBe('proxy');
  });

  it('adds only immutable exact-origin experiment observations and stales only the matching lens', () => {
    const exact = experimentResult();
    const rows = [
      exact,
      experimentResult(1, { ideaRevision: 1 }),
      experimentResult(2, {
        originChallenge: {
          id: originChallengeId,
          ideaId: idea.idea_id,
          ideaRevision: idea.idea_revision,
          lens: 'COMPETITION',
        },
      }),
      experimentResult(3, { conclusion: null }),
    ];
    const demandBefore = prepareSelectionChallengeInput({
      lens: 'demand', idea, previewReport, discoveryData,
    });
    const competitionBefore = prepareSelectionChallengeInput({
      lens: 'competition', idea, previewReport, discoveryData,
    });
    const demandAfter = prepareSelectionChallengeInput({
      lens: 'demand', idea, previewReport, discoveryData, experimentResults: rows,
    });
    const demandRetry = prepareSelectionChallengeInput({
      lens: 'demand', idea, previewReport, discoveryData, experimentResults: rows,
    });
    const competitionAfter = prepareSelectionChallengeInput({
      lens: 'competition', idea, previewReport, discoveryData, experimentResults: rows,
    });

    const sources = demandAfter.evidenceSnapshot.filter(source => source.kind === 'experiment_result');
    expect(sources).toHaveLength(1);
    expect(sources[0]).toMatchObject({
      provenance: {
        assetType: 'EXPERIMENT_RESULT',
        experimentId: exact.id,
        conclusionId: exact.conclusion?.id,
        originChallengeId,
        evidenceClass: 'observed',
        sourceType: 'FIRST_PARTY',
        adapterKey: 'nicheiq-hosted',
        precommitment: {
          primaryMetric: 'Qualified CTA rate',
          passThreshold: 'At least 8%',
          failThreshold: 'Below 3%',
          sampleTarget: 100,
        },
        observation: {
          metrics: [expect.objectContaining({ key: 'cta_rate', value: 0.1 })],
          sample: { observed: 120, target: 100, unit: 'qualified exposures' },
          limitations: ['One acquisition channel was tested.'],
        },
      },
    });
    expect(JSON.stringify(sources[0])).not.toContain('Owner-authored interpretation');
    expect(JSON.stringify(sources[0])).not.toContain('outcome');
    expect(demandAfter.inputFingerprint).not.toBe(demandBefore.inputFingerprint);
    expect(demandRetry.inputFingerprint).toBe(demandAfter.inputFingerprint);
    expect(competitionAfter.inputFingerprint).toBe(competitionBefore.inputFingerprint);
  });

  it('canonically classifies first-party experiment results as observed and manual results as proxy', async () => {
    const questions = ['pain_is_observed', 'urgency_is_behavioral', 'buyer_will_pay'] as const;
    mockChatComplete
      .mockResolvedValueOnce(response(questions, ['supports', 'supports', 'supports']))
      .mockResolvedValueOnce(response(questions, ['supports', 'supports', 'supports']))
      .mockResolvedValueOnce(response(questions, ['supports', 'supports', 'supports']))
      .mockResolvedValueOnce(response(questions, ['supports', 'supports', 'supports']));

    const hosted = await generateSelectionChallenge({
      lens: 'demand',
      idea,
      previewReport: null,
      discoveryData: null,
      experimentResults: [experimentResult()],
    });
    const manual = await generateSelectionChallenge({
      lens: 'demand',
      idea,
      previewReport: null,
      discoveryData: null,
      experimentResults: [experimentResult(1, { sourceType: 'MANUAL' })],
    });

    expect(hosted.questions[0].skeptic.evidenceClass).toBe('observed');
    expect(manual.questions[0].skeptic.evidenceClass).toBe('proxy');
  });

  it('bounds experiment-result evidence before the challenge packet limit', () => {
    const prepared = prepareSelectionChallengeInput({
      lens: 'demand',
      idea,
      previewReport,
      discoveryData,
      experimentResults: Array.from({ length: 10 }, (_, index) => experimentResult(index)),
    });

    expect(prepared.evidenceSnapshot.filter(source => source.kind === 'experiment_result')).toHaveLength(6);
    expect(prepared.evidenceSnapshot.length).toBeLessThanOrEqual(24);
  });

  it('does not hide substantive disagreement behind an averaged result', () => {
    const base = {
      questionId: 'pain_is_observed',
      summary: 'Evidence is contested.',
      subjectKeys: ['I1'],
      evidenceKeys: ['S1'],
      evidenceClass: 'observed' as const,
    };
    expect(reduceSelectionChallenge(
      { ...base, position: 'supports' },
      { ...base, position: 'contradicts' },
    )).toBe('disputed');
  });
});
