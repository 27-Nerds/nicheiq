import { describe, expect, it } from 'vitest';
import {
  buildSelectionCopilotCatalog,
  matchCurrentSelectionChallengeRows,
  resolveSelectionCopilotAction,
} from '../selectionCopilotActionService.js';

const challengeId = '30000000-0000-0000-0000-000000000001';
const assumptionId = '10000000-0000-0000-0000-000000000001';
const experimentId = '20000000-0000-0000-0000-000000000001';
const evidenceId = '40000000-0000-0000-0000-000000000001';

function challengeArtifact(overrides: Record<string, unknown> = {}) {
  const assessment = {
    questionId: 'pain_is_observed',
    position: 'insufficient',
    summary: 'The captured packet does not directly answer this question.',
    subjectKeys: ['I1'],
    evidenceKeys: [],
    evidenceClass: 'inference',
  };
  const questions = ['pain_is_observed', 'urgency_is_behavioral', 'buyer_will_pay'].map(questionId => ({
    questionId,
    consensus: 'insufficient',
    skeptic: { ...assessment, questionId },
    auditor: { ...assessment, questionId },
  }));
  return {
    version: 1,
    inputFingerprint: 'f'.repeat(64),
    ideaId: 'idea-1',
    ideaRevision: 2,
    ideaTitle: 'Current idea',
    lens: 'demand',
    overall: 'insufficient_evidence',
    ideaSnapshot: { solution_name: 'Current idea' },
    subjectSnapshot: [{ key: 'I1', field: 'solution_name', value: 'Current idea' }],
    evidenceSnapshot: [],
    questions,
    skepticModel: 'model-a',
    auditorModel: 'model-b',
    promptVersion: 1,
    createdAt: '2026-07-16T00:00:00.000Z',
    ...overrides,
  };
}

function catalog() {
  const artifact = challengeArtifact();
  return buildSelectionCopilotCatalog({
    ideas: [
      { idea_id: 'idea-1', idea_revision: 2, solution_name: 'Current idea' },
      { idea_id: 'idea-2', idea_revision: 1, solution_name: 'Second idea' },
    ],
    assumptions: [
      {
        id: assumptionId,
        ideaId: 'idea-1',
        ideaRevision: 2,
        lens: 'DEMAND',
        statement: 'Qualified buyers will pay for same-day alerts.',
        impact: 'DECISIVE',
        ownerState: 'OPEN',
        version: 4,
      },
      {
        id: '10000000-0000-0000-0000-000000000002',
        ideaId: 'idea-1',
        ideaRevision: 1,
        lens: 'DEMAND',
        statement: 'This belongs to a stale idea revision.',
        impact: 'HIGH',
        ownerState: 'OPEN',
        version: 1,
      },
    ],
    experiments: [
      {
        id: experimentId,
        ideaId: 'idea-1',
        ideaRevision: 2,
        status: 'DRAFT',
        assumption: 'Qualified buyers will book a call.',
        method: 'BOOKED_CALL',
        primaryMetric: 'Booked calls',
        passThreshold: 'At least 3',
        failThreshold: 'Fewer than 1',
      },
    ],
    ownerEvidence: [
      {
        id: evidenceId,
        ideaId: 'idea-1',
        ideaRevision: 2,
        lens: 'DEMAND',
        kind: 'CUSTOMER_QUOTE',
        position: 'SUPPORTS',
        title: 'Interview note',
        content: 'A qualified buyer described the alert as urgent.',
        retractedAt: null,
      },
      {
        id: '40000000-0000-0000-0000-000000000002',
        ideaId: 'idea-1',
        ideaRevision: 2,
        lens: 'DEMAND',
        kind: 'NOTE',
        position: 'CONTEXT',
        title: 'Retracted note',
        content: 'No longer applicable.',
        retractedAt: '2026-07-16T01:00:00.000Z',
      },
    ],
    currentChallenges: [{ id: challengeId, artifact }],
    selectionDraftVersion: 7,
  });
}

describe('selection copilot action resolution', () => {
  it('publishes only current, active owner-state references', () => {
    const result = catalog();
    expect(result.ideas.map(item => item.ref)).toEqual(['R1', 'R2']);
    expect(result.assumptions.map(item => item.ref)).toEqual(['A1']);
    expect(result.experiments.map(item => item.ref)).toEqual(['X1']);
    expect(result.evidence.map(item => item.ref)).toEqual(['O1']);
    expect(result.questions.map(item => item.ref)).toEqual(['Q1', 'Q2', 'Q3']);
  });

  it('resolves shortlist refs into canonical identities plus the current CAS version', () => {
    expect(resolveSelectionCopilotAction({
      kind: 'shortlist_review',
      idea_refs: ['R2', 'R1'],
      rationale: 'Review these two before saving the shortlist.',
    }, catalog())).toMatchObject({
      kind: 'selection_copilot_action',
      action: 'shortlist_review',
      target: 'shortlist',
      expectedVersion: 7,
      ideas: [
        { ideaId: 'idea-2', ideaRevision: 1, solutionName: 'Second idea' },
        { ideaId: 'idea-1', ideaRevision: 2, solutionName: 'Current idea' },
      ],
    });
  });

  it('resolves a Concept Forge brief to exact current candidate revisions without generating it', () => {
    expect(resolveSelectionCopilotAction({
      kind: 'prefill',
      draft: {
        form: 'concept_forge',
        idea_refs: ['R2', 'R1'],
        values: {
          purpose: 'resolve_tradeoff',
          targetTradeoff: 'Faster launch versus a stronger evidence moat',
        },
      },
      rationale: 'Compare the two current shapes before committing either to paid evaluation.',
      caveats: ['The resulting directions still need independent evaluation.'],
    }, catalog())).toMatchObject({
      action: 'prefill',
      target: 'concept_forge',
      ideas: [
        { ideaId: 'idea-2', ideaRevision: 1, solutionName: 'Second idea' },
        { ideaId: 'idea-1', ideaRevision: 2, solutionName: 'Current idea' },
      ],
      values: {
        purpose: 'resolve_tradeoff',
        targetTradeoff: 'Faster launch versus a stronger evidence moat',
      },
    });
  });

  it('resolves editable records and challenge provenance without accepting model-authored ids', () => {
    const action = resolveSelectionCopilotAction({
      kind: 'prefill',
      draft: {
        form: 'assumption',
        idea_ref: 'R1',
        assumption_ref: 'A1',
        question_ref: 'Q1',
        values: { impactIfFalse: 'The demand wedge would disappear.' },
        grounding: { impactIfFalse: ['R1', 'A1', 'O1', 'Q1'] },
      },
      rationale: 'Turn the current demand gap into an explicit risk.',
      caveats: [],
    }, catalog());

    expect(action).toMatchObject({
      target: 'assumption',
      record: { id: assumptionId, version: 4 },
      origin: { challengeId, questionId: 'pain_is_observed' },
      values: { ideaId: 'idea-1', ideaRevision: 2, lens: 'demand' },
      grounding: {
        impactIfFalse: [
          { ref: 'R1', kind: 'candidate', label: 'Candidate · Current idea' },
          { ref: 'A1', kind: 'assumption', recordId: assumptionId },
          { ref: 'O1', kind: 'owner_evidence', recordId: evidenceId },
          { ref: 'Q1', kind: 'challenge_question', challengeId, questionId: 'pain_is_observed' },
        ],
      },
    });
  });

  it('requires current same-idea grounding and keeps owner judgments out of analyst drafts', () => {
    const current = catalog();
    const base = {
      kind: 'prefill',
      draft: {
        form: 'assumption',
        idea_ref: 'R1',
        lens: 'demand',
        values: { statement: 'Qualified buyers will pay for same-day alerts.' },
      },
      rationale: 'Make the demand hinge explicit for owner review.',
      caveats: [],
    };

    expect(resolveSelectionCopilotAction({
      ...base,
      draft: { ...base.draft, grounding: {} },
    }, current)).toBeNull();
    expect(resolveSelectionCopilotAction({
      ...base,
      draft: { ...base.draft, grounding: { statement: ['R2'] } },
    }, current)).toBeNull();
    expect(resolveSelectionCopilotAction({
      ...base,
      draft: {
        ...base.draft,
        values: { ...base.draft.values, impact: 'DECISIVE' },
        grounding: { statement: ['R1'] },
      },
    }, current)).toBeNull();
    expect(resolveSelectionCopilotAction({
      ...base,
      draft: {
        ...base.draft,
        lens: 'competition',
        grounding: { statement: ['O1'] },
      },
    }, current)).toBeNull();
  });

  it('rejects missing, cross-kind, and mismatched references', () => {
    const current = catalog();
    expect(resolveSelectionCopilotAction({
      kind: 'shortlist_review', idea_refs: ['R99'], rationale: 'Review the missing idea.',
    }, current)).toBeNull();
    expect(resolveSelectionCopilotAction({
      kind: 'open',
      target: 'assumptions',
      idea_refs: ['R1'],
      experiment_ref: 'A1',
      rationale: 'Open this record.',
    }, current)).toBeNull();
    expect(resolveSelectionCopilotAction({
      kind: 'prefill',
      draft: {
        form: 'experiment',
        idea_ref: 'R2',
        experiment_ref: 'X1',
        values: { primaryMetric: 'Qualified replies' },
      },
      rationale: 'Update this test.',
      caveats: [],
    }, current)).toBeNull();
  });

  it('matches challenge row ids only after freshness was established', () => {
    const current = challengeArtifact();
    const stale = challengeArtifact({ inputFingerprint: '0'.repeat(64) });
    expect(matchCurrentSelectionChallengeRows([
      { id: challengeId, artifact: current },
      { id: '30000000-0000-0000-0000-000000000002', artifact: stale },
    ], [current])).toEqual([{ id: challengeId, artifact: current }]);
  });
});
