import {
  SelectionDecisionHandoffAction,
  type SelectionDecisionHandoff,
} from '@prisma/client';
import { describe, expect, it } from 'vitest';
import type { GithubRepository } from '../githubAppService.js';
import { materializeGithubIssuePreview } from '../selectionHandoffGithubAdapter.js';

const JOB_ID = '20000000-0000-0000-0000-000000000002';
const DECISION_ID = '10000000-0000-0000-0000-000000000001';
const HANDOFF_ID = '30000000-0000-0000-0000-000000000003';
const CONNECTION_ID = '40000000-0000-0000-0000-000000000004';
const TEST_EXPERIMENT_ID = '50000000-0000-0000-0000-000000000005';

function frozenTestBrief() {
  return {
    version: 1,
    experimentId: TEST_EXPERIMENT_ID,
    jobId: JOB_ID,
    lockedAt: '2026-07-16T11:00:00.000Z',
    idea: { ideaId: 'idea-signal', ideaRevision: 3, snapshot: {} },
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
      pass: 'Proceed.',
      fail: 'Stop or reshape.',
      ambiguous: 'Run diagnostic interviews.',
      invalid: 'Repair recruitment and rerun.',
    },
    briefFingerprint: 'e'.repeat(64),
    runStatusAtDecision: null,
  };
}

function frozenPreMortem() {
  return {
    version: 1,
    target: { ideaId: 'idea-signal', ideaRevision: 3 },
    entries: [{
      failureMode: 'The audience does not return after the first useful signal.',
      earlyWarningSignal: 'Fewer than three of ten trial users return within fourteen days.',
      mitigation: 'Interview non-returning users and narrow the recurring workflow before building more.',
      origin: null,
    }],
  };
}

function handoff(
  action: SelectionDecisionHandoffAction = SelectionDecisionHandoffAction.BUILD,
  overrides: Partial<SelectionDecisionHandoff> = {},
): SelectionDecisionHandoff {
  const validate = action === SelectionDecisionHandoffAction.VALIDATE_MORE;
  const dispatchable = action === SelectionDecisionHandoffAction.BUILD || validate;
  return {
    id: HANDOFF_ID,
    finalDecisionId: DECISION_ID,
    action,
    ideaId: dispatchable ? 'idea-signal' : null,
    ideaRevision: dispatchable ? 3 : null,
    inputFingerprint: 'd'.repeat(64),
    artifact: {
      jobId: JOB_ID,
      finalDecisionId: DECISION_ID,
      action,
      target: dispatchable
        ? {
            ideaId: 'idea-signal',
            ideaRevision: 3,
            title: 'Signal Desk',
            problem: 'Founders miss repeated buyer signals.',
            audience: 'Solo SaaS founders',
            valueProposition: 'Collect recurring demand in one place.',
            proposedScope: ['Signal inbox', 'Evidence links'],
            technicalApproach: 'Event ingestion with a searchable evidence store.',
            estimatedBuildTime: '4–6 weeks',
          }
        : null,
      decision: {
        disposition: validate ? 'TEST_FIRST' : action === SelectionDecisionHandoffAction.PARK ? 'PARK' : action === SelectionDecisionHandoffAction.STOP ? 'STOP' : 'PROCEED',
        recommendationRelation: 'FOLLOWED',
        rationale: 'This is the clearest next move for the current audience.',
        acceptedRisks: 'Distribution remains open.',
        changeCriterion: 'Stop if ten qualified calls produce no follow-up requests.',
        overrideReason: null,
        decidedAt: '2026-07-16T12:00:00.000Z',
      },
      evidence: {
        sourceFingerprint: 'b'.repeat(64),
        reportSha256: 'c'.repeat(64),
        recommendationSnapshot: {},
        selectedIdeaSnapshot: dispatchable ? {} : null,
        alternativesSnapshot: {},
        evidenceSnapshot: validate ? { selectedTestBrief: frozenTestBrief() } : {},
      },
      executionPolicy: {
        providerDispatchAllowed: dispatchable,
        allowedOperation: action === SelectionDecisionHandoffAction.BUILD
          ? 'CREATE_IMPLEMENTATION_ISSUE'
          : validate
            ? 'CREATE_VALIDATION_ISSUE'
            : null,
        resumeRequiresNewOwnerDecision: !dispatchable,
        terminal: action === SelectionDecisionHandoffAction.STOP,
      },
      testBrief: validate ? frozenTestBrief() : null,
      preMortem: dispatchable ? frozenPreMortem() : null,
    },
    createdAt: new Date('2026-07-16T12:05:00.000Z'),
    ...overrides,
  };
}

function repository(overrides: Partial<GithubRepository> = {}): GithubRepository {
  return {
    id: 987654,
    name: 'signal-desk',
    full_name: 'nicheiq/signal-desk',
    html_url: 'https://github.com/nicheiq/signal-desk',
    has_issues: true,
    private: true,
    ...overrides,
  };
}

describe('selectionHandoffGithubAdapter', () => {
  it.each([
    [SelectionDecisionHandoffAction.BUILD, 'Build: Signal Desk', 'CREATE_IMPLEMENTATION_ISSUE'],
    [SelectionDecisionHandoffAction.VALIDATE_MORE, 'Validate: Signal Desk', 'CREATE_VALIDATION_ISSUE'],
  ])('materializes a deterministic %s preview', (action, expectedTitle, operation) => {
    const source = handoff(action);
    const first = materializeGithubIssuePreview(source, CONNECTION_ID, repository());
    const second = materializeGithubIssuePreview(source, CONNECTION_ID, repository());

    expect(second).toEqual(first);
    expect(first).toMatchObject({
      provider: 'GITHUB',
      adapterVersion: 1,
      connectionId: CONNECTION_ID,
      payload: {
        version: 1,
        destination: {
          repositoryId: '987654',
          owner: 'nicheiq',
          name: 'signal-desk',
          fullName: 'nicheiq/signal-desk',
        },
        request: { title: expectedTitle },
      },
    });
    expect(first.payload.request.body).toContain(`Decision fingerprint: \`${source.inputFingerprint}\``);
    expect(first.payload.request.body).toContain('The audience does not return after the first useful signal.');
    if (action === SelectionDecisionHandoffAction.VALIDATE_MORE) {
      expect(first.payload.request.body).toContain('Qualified buyers will make a payment commitment.');
      expect(first.payload.request.body).toContain('At least 3 deposits.');
    }
    expect(first.payload.request.body).toContain(`<!-- nicheiq-handoff:${HANDOFF_ID} -->`);
    expect((source.artifact as any).executionPolicy.allowedOperation).toBe(operation);
    expect(first.payloadFingerprint).toMatch(/^[a-f0-9]{64}$/);
  });

  it('rejects missing or mismatched validation handoffs instead of inventing a test plan', () => {
    const missing = handoff(SelectionDecisionHandoffAction.VALIDATE_MORE);
    expect(() => materializeGithubIssuePreview({
      ...missing,
      artifact: { ...(missing.artifact as any), testBrief: null },
    }, CONNECTION_ID, repository()))
      .toThrow('GITHUB_HANDOFF_NOT_DISPATCHABLE');

    const exact = handoff(SelectionDecisionHandoffAction.VALIDATE_MORE);
    const artifact = structuredClone(exact.artifact) as any;
    artifact.testBrief.idea.ideaRevision = 4;
    expect(() => materializeGithubIssuePreview(
      { ...exact, artifact },
      CONNECTION_ID,
      repository(),
    )).toThrow('GITHUB_HANDOFF_NOT_DISPATCHABLE');
  });

  it('rejects a pre-mortem bound to another idea revision', () => {
    const exact = handoff(SelectionDecisionHandoffAction.BUILD);
    const artifact = structuredClone(exact.artifact) as any;
    artifact.preMortem.target.ideaRevision = 4;
    expect(() => materializeGithubIssuePreview(
      { ...exact, artifact },
      CONNECTION_ID,
      repository(),
    )).toThrow('GITHUB_HANDOFF_NOT_DISPATCHABLE');
  });

  it('binds the fingerprint to the connection and exact repository destination', () => {
    const source = handoff();
    const original = materializeGithubIssuePreview(source, CONNECTION_ID, repository());
    const anotherConnection = materializeGithubIssuePreview(
      source,
      '50000000-0000-0000-0000-000000000005',
      repository(),
    );
    const renamedRepository = materializeGithubIssuePreview(
      source,
      CONNECTION_ID,
      repository({ name: 'renamed', full_name: 'nicheiq/renamed' }),
    );

    expect(anotherConnection.payloadFingerprint).not.toBe(original.payloadFingerprint);
    expect(renamedRepository.payloadFingerprint).not.toBe(original.payloadFingerprint);
  });

  it.each([
    SelectionDecisionHandoffAction.PARK,
    SelectionDecisionHandoffAction.STOP,
  ])('rejects the non-dispatchable %s action', (action) => {
    expect(() => materializeGithubIssuePreview(
      handoff(action),
      CONNECTION_ID,
      repository(),
    )).toThrow('GITHUB_HANDOFF_NOT_DISPATCHABLE');
  });
});
