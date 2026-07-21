import { describe, expect, it } from 'vitest';
import {
  deriveSelectionAssumptionEvidence,
  type SelectionAssumptionWithEvidence,
} from '../selectionAssumptionService.js';

function assumption(
  experiments: SelectionAssumptionWithEvidence['experiments'] = [],
): SelectionAssumptionWithEvidence {
  return {
    id: 'assumption-1',
    jobId: 'job-1',
    ideaId: 'idea-1',
    ideaRevision: 1,
    lens: 'DEMAND',
    statement: 'Qualified buyers will commit.',
    impactIfFalse: 'The concept should stop.',
    falsificationQuestion: 'Will buyers make a commitment?',
    impact: 'DECISIVE',
    ownerState: 'OPEN',
    version: 1,
    originChallengeId: null,
    originQuestionId: null,
    statementFingerprint: 'f'.repeat(64),
    createdByUserId: 'owner-1',
    createdAt: new Date(),
    updatedAt: new Date(),
    originChallenge: null,
    experiments,
  } as SelectionAssumptionWithEvidence;
}

describe('selection assumption derived evidence', () => {
  it.each([
    {
      outcome: 'PASS',
      evidenceSource: 'MANUAL',
      snapshot: { evidence: { source: { references: [] }, sample: { observed: null } } },
      expected: { direction: 'SUPPORTING', evidenceClass: 'INFERENCE' },
    },
    {
      outcome: 'FAIL',
      evidenceSource: 'MANUAL',
      snapshot: { evidence: { source: { references: ['Interview notes'] }, sample: { observed: 8 } } },
      expected: { direction: 'CONTRADICTING', evidenceClass: 'PROXY' },
    },
    {
      outcome: 'AMBIGUOUS',
      evidenceSource: 'HOSTED_RUN',
      snapshot: { evidence: { quality: { status: 'PARTIAL' } } },
      expected: { direction: 'MIXED', evidenceClass: 'OBSERVED' },
    },
    {
      outcome: 'INVALID',
      evidenceSource: 'HOSTED_RUN',
      snapshot: { evidence: { quality: { status: 'INVALID' } } },
      expected: { direction: 'UNKNOWN', evidenceClass: 'NONE' },
    },
  ])('derives $outcome conservatively from an explicitly linked conclusion', ({
    outcome,
    evidenceSource,
    snapshot,
    expected,
  }) => {
    const result = deriveSelectionAssumptionEvidence(assumption(), {
      outcome,
      evidenceSource,
      snapshot,
    } as never);
    expect(result).toEqual(expected);
  });

  it('keeps a manual assumption unknown until evidence is explicitly linked', () => {
    expect(deriveSelectionAssumptionEvidence(assumption())).toEqual({
      direction: 'UNKNOWN',
      evidenceClass: 'NONE',
    });
  });
});
