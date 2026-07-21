import { describe, expect, it } from 'vitest';
import {
  IDEA_SYNTHESIS_TEXT_LIMITS,
  IdeaSynthesisPatchSchema,
  normalizeLockedIdeaSynthesisArgs,
} from '../ideaSynthesis.js';

function patch() {
  return {
    kind: 'idea_synthesis',
    operation: 'narrow',
    proposedTitle: 'Weekly Signal Brief',
    proposedBrief: 'One weekly review for a single workflow.',
    changeSummary: 'Removes continuous monitoring.',
    rationale: 'Designed around a recorded constraint.',
    parents: [{
      ideaId: 'idea-parent',
      ideaRevision: 2,
      solutionName: 'Signal Desk',
      contribution: 'Keep signal interpretation.',
    }],
    evidence: {
      sourceAnchors: [{
        ideaId: 'idea-parent',
        ideaRevision: 2,
        candidateSnapshotSha256: 'a'.repeat(64),
      }],
      requiresValidation: ['Recheck demand for the weekly workflow.'],
    },
    newAssumptions: ['A weekly cadence is useful.'],
  };
}

describe('IdeaSynthesisPatchSchema', () => {
  it('requires every source anchor to bind the exact parent revision once', () => {
    const input = patch();
    input.evidence.sourceAnchors[0].ideaRevision = 3;

    expect(IdeaSynthesisPatchSchema.safeParse(input).success).toBe(false);
  });

  it('requires founder-fit provenance to bind the same exact single parent', () => {
    const input = patch() as ReturnType<typeof patch> & {
      evidence: ReturnType<typeof patch>['evidence'] & { founderFitRef: unknown };
    };
    input.evidence.founderFitRef = {
      inputFingerprint: 'f'.repeat(64),
      ideaId: 'different-parent',
      ideaRevision: 2,
      verdict: 'needs_reshape',
      conflicts: [{
        dimension: 'time',
        summary: 'The build exceeds available time.',
        profileFields: ['weeklyTime'],
        ideaFields: ['estimated_development_time'],
      }],
    };

    expect(IdeaSynthesisPatchSchema.safeParse(input).success).toBe(false);
  });
});

describe('normalizeLockedIdeaSynthesisArgs', () => {
  it('keeps server-locked operation and refs while bounding redundant model prose', () => {
    const result = normalizeLockedIdeaSynthesisArgs({
      operation: 'adjacent',
      source_refs: ['R1', 'R9'],
      source_contributions: [
        'Keep the compliance-first trust mechanism. '.repeat(20),
        'A redundant second contribution for the same source.',
      ],
      proposed_title: 'Institutional anti-doping recovery desk',
      proposed_brief: 'Reposition the workflow for athletic departments.',
      change_summary: 'The buyer becomes the institution rather than the athlete.',
      rationale: 'The owner explicitly requested a different buyer.',
      new_assumptions: ['Departments will pay for compliance support.'],
    }, 'reposition', ['R2']);

    expect(result).toMatchObject({
      operation: 'reposition',
      source_refs: ['R2'],
      source_contributions: [expect.any(String)],
    });
    expect(result?.source_contributions).toHaveLength(1);
    expect(result?.source_contributions[0].length).toBeLessThanOrEqual(
      IDEA_SYNTHESIS_TEXT_LIMITS.sourceContribution,
    );
  });
});
