import {
  SelectionFinalDecisionDisposition,
  SelectionDecisionHandoffAction,
} from '@prisma/client';
import { describe, expect, it } from 'vitest';
import {
  materializeDecisionHandoff,
  renderDecisionHandoffMarkdown,
  serializeDecisionHandoffJson,
  type FinalDecisionHandoffSource,
} from '../selectionDecisionHandoffService.js';

const TEST_EXPERIMENT_ID = '30000000-0000-0000-0000-000000000003';

function frozenTestBrief(overrides: Record<string, unknown> = {}) {
  return {
    version: 1,
    experimentId: TEST_EXPERIMENT_ID,
    jobId: '20000000-0000-0000-0000-000000000002',
    lockedAt: '2026-07-16T11:00:00.000Z',
    idea: {
      ideaId: 'idea-signal',
      ideaRevision: 3,
      snapshot: { idea_id: 'idea-signal', idea_revision: 3, solution_name: 'Signal Desk' },
    },
    origin: null,
    assumption: {
      type: 'DESIRABILITY',
      statement: 'Qualified buyers will make a payment commitment.',
      whyCritical: 'Interest alone does not justify implementation.',
      currentEvidence: 'Interview language only.',
    },
    testDesign: {
      method: 'PREORDER',
      evidenceSignal: 'PAYMENT_INTENT',
      stimulus: 'A priced early-access offer.',
      audience: 'Qualified operations leads',
      channel: 'Interview follow-ups',
      primaryMetric: 'Refundable deposits',
      passThreshold: 'At least 3 deposits.',
      failThreshold: 'No deposits.',
      measurementWindow: 'Stop after 15 conversations or 21 days.',
      sampleTarget: 15,
      costEstimate: '$150',
    },
    decisionRules: {
      pass: 'Proceed to implementation planning.',
      fail: 'Stop or reshape.',
      ambiguous: 'Run diagnostic interviews.',
      invalid: 'Repair recruitment and rerun.',
    },
    briefFingerprint: 'e'.repeat(64),
    runStatusAtDecision: null,
    ...overrides,
  };
}

function frozenPreMortem(overrides: Record<string, unknown> = {}) {
  return {
    version: 1,
    target: { ideaId: 'idea-signal', ideaRevision: 3 },
    entries: [{
      failureMode: 'The audience does not return after the first useful signal.',
      earlyWarningSignal: 'Fewer than three of ten trial users return within fourteen days.',
      mitigation: 'If that happens, interview the non-returning users and narrow the recurring workflow.',
      origin: null,
    }],
    ...overrides,
  };
}

function decision(
  overrides: Partial<FinalDecisionHandoffSource> = {},
): FinalDecisionHandoffSource {
  return {
    id: '10000000-0000-0000-0000-000000000001',
    jobId: '20000000-0000-0000-0000-000000000002',
    disposition: SelectionFinalDecisionDisposition.PROCEED,
    selectedIdeaId: 'idea-signal',
    selectedIdeaRevision: 3,
    testExperimentId: null,
    testExperimentSnapshot: null,
    preMortemSnapshot: frozenPreMortem(),
    recommendationRelation: 'FOLLOWED',
    rationale: 'This is the clearest next move for the current audience.',
    acceptedRisks: 'Distribution remains open.',
    changeCriterion: 'Stop if ten qualified calls produce no follow-up requests.',
    overrideReason: null,
    requestFingerprint: 'a'.repeat(64),
    sourceFingerprint: 'b'.repeat(64),
    recommendationSnapshot: { solutionName: 'Signal Desk', ideaRevision: 3 },
    selectedIdeaSnapshot: {
      idea_id: 'idea-signal',
      idea_revision: 3,
      solution_name: 'Signal Desk',
      source_pain: 'Founders miss repeated buyer signals.',
      source_segment: 'Solo SaaS founders',
      value_proposition: 'Collect recurring demand in one place.',
      reportEvidence: {
        role: 'recommended',
        details: {
          core_features: ['Signal inbox', 'Evidence links'],
          technical_approach: 'Event ingestion with a searchable evidence store.',
          estimated_development_time: '4–6 weeks',
        },
      },
    },
    alternativesSnapshot: { deepResearchedFinalists: [] },
    evidenceSnapshot: { experimentConclusions: [] },
    reportSha256: 'c'.repeat(64),
    decidedByUserId: 'owner-1',
    createdAt: new Date('2026-07-16T12:00:00.000Z'),
    ...overrides,
  };
}

describe('selectionDecisionHandoffService', () => {
  it.each([
    [SelectionFinalDecisionDisposition.PROCEED, SelectionDecisionHandoffAction.BUILD, 'CREATE_IMPLEMENTATION_ISSUE'],
    [SelectionFinalDecisionDisposition.TEST_FIRST, SelectionDecisionHandoffAction.VALIDATE_MORE, 'CREATE_VALIDATION_ISSUE'],
  ])('maps %s to its exact target-bearing action', (disposition, action, operation) => {
    const result = materializeDecisionHandoff(decision({
      disposition,
      ...(disposition === SelectionFinalDecisionDisposition.TEST_FIRST
        ? {
            testExperimentId: TEST_EXPERIMENT_ID,
            testExperimentSnapshot: frozenTestBrief(),
            evidenceSnapshot: { experimentConclusions: [], selectedTestBrief: frozenTestBrief() },
          }
        : {}),
    }));

    expect(result).toMatchObject({
      action,
      ideaId: 'idea-signal',
      ideaRevision: 3,
      artifact: {
        action,
        target: {
          ideaId: 'idea-signal',
          ideaRevision: 3,
          title: 'Signal Desk',
          proposedScope: ['Signal inbox', 'Evidence links'],
        },
        executionPolicy: {
          providerDispatchAllowed: true,
          allowedOperation: operation,
          resumeRequiresNewOwnerDecision: false,
          terminal: false,
        },
      },
    });
    expect(result.artifact).not.toHaveProperty('version');
  });

  it('freezes the exact test plan into a Test first handoff and Markdown export', () => {
    const result = materializeDecisionHandoff(decision({
      disposition: SelectionFinalDecisionDisposition.TEST_FIRST,
      testExperimentId: TEST_EXPERIMENT_ID,
      testExperimentSnapshot: frozenTestBrief(),
      evidenceSnapshot: { selectedTestBrief: frozenTestBrief() },
    }));
    expect(result.artifact).toMatchObject({
      action: 'VALIDATE_MORE',
      testBrief: {
        experimentId: TEST_EXPERIMENT_ID,
        assumption: { statement: 'Qualified buyers will make a payment commitment.' },
      },
    });
    const markdown = renderDecisionHandoffMarkdown(result.artifact, result.inputFingerprint);
    expect(markdown).toContain('# Test handoff');
    expect(markdown).toContain('## Locked test brief');
    expect(markdown).toContain('At least 3 deposits.');
    expect(markdown).toContain(`**Test brief fingerprint:** \`${'e'.repeat(64)}\``);
  });

  it('rejects missing or mismatched test briefs for Test first', () => {
    expect(() => materializeDecisionHandoff(decision({
      disposition: SelectionFinalDecisionDisposition.TEST_FIRST,
    }))).toThrow('HANDOFF_TEST_BRIEF_REQUIRED');
    expect(() => materializeDecisionHandoff(decision({
      disposition: SelectionFinalDecisionDisposition.TEST_FIRST,
      testExperimentId: TEST_EXPERIMENT_ID,
      testExperimentSnapshot: frozenTestBrief({
        idea: { ideaId: 'idea-other', ideaRevision: 3, snapshot: {} },
      }),
    }))).toThrow('HANDOFF_TEST_BRIEF_MISMATCH');
  });

  it('freezes and renders the exact pre-mortem in priority order', () => {
    const result = materializeDecisionHandoff(decision());
    expect(result.artifact.preMortem).toEqual(frozenPreMortem());
    const markdown = renderDecisionHandoffMarkdown(result.artifact, result.inputFingerprint);
    expect(markdown).toContain('## Pre-mortem');
    expect(markdown).toContain('The audience does not return after the first useful signal.');
    expect(markdown).toContain('Fewer than three of ten trial users return within fourteen days.');
    expect(markdown).toContain('interview the non-returning users');
  });

  it('rejects missing or target-mismatched pre-mortems', () => {
    expect(() => materializeDecisionHandoff(decision({
      preMortemSnapshot: null,
    }))).toThrow('HANDOFF_PRE_MORTEM_REQUIRED');
    expect(() => materializeDecisionHandoff(decision({
      preMortemSnapshot: frozenPreMortem({
        target: { ideaId: 'idea-other', ideaRevision: 3 },
      }),
    }))).toThrow('HANDOFF_PRE_MORTEM_MISMATCH');
  });

  it.each([
    [SelectionFinalDecisionDisposition.PARK, SelectionDecisionHandoffAction.PARK, false],
    [SelectionFinalDecisionDisposition.STOP, SelectionDecisionHandoffAction.STOP, true],
  ])('maps %s to a targetless non-dispatch artifact', (disposition, action, terminal) => {
    const result = materializeDecisionHandoff(decision({
      disposition,
      selectedIdeaId: null,
      selectedIdeaRevision: null,
      selectedIdeaSnapshot: null,
      preMortemSnapshot: null,
    }));

    expect(result.action).toBe(action);
    expect(result.ideaId).toBeNull();
    expect(result.ideaRevision).toBeNull();
    expect(result.artifact.target).toBeNull();
    expect(result.artifact.executionPolicy).toEqual({
      providerDispatchAllowed: false,
      allowedOperation: null,
      resumeRequiresNewOwnerDecision: true,
      terminal,
    });
  });

  it('is deterministic across object key order and changes when a frozen decision field changes', () => {
    const first = materializeDecisionHandoff(decision());
    const reordered = materializeDecisionHandoff(decision({
      recommendationSnapshot: { ideaRevision: 3, solutionName: 'Signal Desk' },
    }));
    const changed = materializeDecisionHandoff(decision({
      rationale: 'A materially different owner rationale for taking the next step.',
    }));

    expect(reordered.inputFingerprint).toBe(first.inputFingerprint);
    expect(reordered.artifact).toEqual(first.artifact);
    expect(changed.inputFingerprint).not.toBe(first.inputFingerprint);
  });

  it('rejects mismatched exact idea identity instead of exporting a plausible target', () => {
    expect(() => materializeDecisionHandoff(decision({
      selectedIdeaSnapshot: {
        idea_id: 'another-idea',
        idea_revision: 3,
        solution_name: 'Signal Desk',
      },
    }))).toThrow('HANDOFF_TARGET_MISMATCH');
  });

  it('exports only recorded scope and labels the artifact as an owner decision, not validation', () => {
    const result = materializeDecisionHandoff(decision());
    const markdown = renderDecisionHandoffMarkdown(result.artifact, result.inputFingerprint);
    const json = serializeDecisionHandoffJson(result.artifact, result.inputFingerprint);

    expect(markdown).toContain('# Implementation brief');
    expect(markdown).toContain('- Signal inbox');
    expect(markdown).toContain('does not label the idea validated');
    expect(markdown).not.toContain('Set up CI');
    expect(JSON.parse(json)).toMatchObject({
      inputFingerprint: result.inputFingerprint,
      artifact: { finalDecisionId: decision().id, action: 'BUILD' },
    });
  });
});
