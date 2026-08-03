import express, { type Express } from 'express';
import { Prisma } from '@prisma/client';
import request from 'supertest';

// These suites exercise route logic, not the decision-tools grant. The grant itself is
// covered in middleware/__tests__/featureAccess.test.ts.
vi.mock('../../middleware/featureAccess.js', () => ({
  requireDecisionToolsAccess: (_req: any, _res: any, next: any) => next(),
}));
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { prepareSelectionChallengeInput } from '../../services/selectionChallengeService.js';
import { candidateSnapshotSha256 } from '../../utils/ideaIdentity.js';

const mocks = vi.hoisted(() => ({
  jobFindFirst: vi.fn(),
  decisionCreate: vi.fn(),
  decisionFindUnique: vi.fn(),
  getReportJsonForJob: vi.fn(),
  getPreviewReportForJob: vi.fn(),
  getDiscoveryDataForJob: vi.fn(),
}));

vi.mock('../../services/db.js', () => ({
  prisma: {
    job: { findFirst: (...args: unknown[]) => mocks.jobFindFirst(...args) },
    selectionFinalDecision: {
      create: (...args: unknown[]) => mocks.decisionCreate(...args),
      findUnique: (...args: unknown[]) => mocks.decisionFindUnique(...args),
    },
  },
}));

vi.mock('../../services/assetService.js', () => ({
  getReportJsonForJob: (...args: unknown[]) => mocks.getReportJsonForJob(...args),
  getPreviewReportForJob: (...args: unknown[]) => mocks.getPreviewReportForJob(...args),
  getDiscoveryDataForJob: (...args: unknown[]) => mocks.getDiscoveryDataForJob(...args),
}));

vi.mock('../../middleware/auth.js', () => ({
  requireInternalAuth: (req: any, _res: any, next: any) => {
    req.user = { id: req.header('X-User-ID') ?? 'owner-1' };
    next();
  },
}));

const JOB_ID = '00000000-0000-0000-0000-000000000001';
const TEST_EXPERIMENT_ID = '00000000-0000-0000-0000-000000000101';
const report = {
  selected_solution_name: 'Signal Desk',
  selection_rationale: 'The strongest balance of demand and feasibility.',
  generated_at: '2026-07-16T10:00:00.000Z',
  selected_solution_details: { solution_name: 'Signal Desk', description: 'Find buyer signals.' },
  alternative_solutions: [{ solution_name: 'Risk Radar', description: 'Watch market risks.' }],
  executive_dashboard: {
    go_no_go_verdict: {
      verdict: 'Conditional',
      rationale: 'Promising if the acquisition assumption holds.',
      risk_level: 'Medium',
      primary_concern: 'Distribution remains unproven.',
    },
  },
};

const frozenFinalists = [
  { idea_id: 'idea-signal', idea_revision: 3, solution_name: 'Signal Desk', value_proposition: 'Find intent.' },
  { idea_id: 'idea-risk', idea_revision: 2, solution_name: 'Risk Radar', value_proposition: 'See risk.' },
];

function exactSelectionRefs(snapshots: Array<Record<string, unknown>> = frozenFinalists) {
  return snapshots.map(snapshot => ({
    ideaId: snapshot.idea_id,
    ideaRevision: snapshot.idea_revision,
    snapshotSha256: candidateSnapshotSha256(snapshot),
  }));
}

function deepResearchDispatch(
  snapshots: Array<Record<string, unknown>> = frozenFinalists,
  refs = exactSelectionRefs(snapshots),
) {
  return {
    requestSnapshot: {
      schemaVersion: 1,
      kind: 'deep_research',
      selectedSolutionRefs: refs,
      selectedSolutionSnapshots: snapshots,
    },
  };
}

function lockedExperiment(overrides: Record<string, unknown> = {}) {
  return {
    id: TEST_EXPERIMENT_ID,
    jobId: JOB_ID,
    ideaId: 'idea-signal',
    ideaRevision: 3,
    ideaSnapshot: { idea_id: 'idea-signal', idea_revision: 3, solution_name: 'Signal Desk' },
    originChallengeId: null,
    originQuestionId: null,
    originSnapshot: null,
    status: 'LOCKED',
    assumptionType: 'DESIRABILITY',
    assumption: 'Qualified buyers will make a payment commitment.',
    whyCritical: 'Stated interest is not enough to justify implementation.',
    currentEvidence: 'Interview language shows interest but no commitment.',
    method: 'PREORDER',
    evidenceSignal: 'PAYMENT_INTENT',
    stimulus: 'A priced early-access offer with a refundable deposit.',
    audience: 'Qualified operations leads with an active workflow problem.',
    channel: 'Owner interview follow-ups',
    primaryMetric: 'Refundable deposits from qualified conversations',
    passThreshold: 'At least 3 deposits from 15 qualified conversations.',
    failThreshold: 'No deposits from 15 qualified conversations.',
    measurementWindow: 'Stop after 15 qualified conversations or 21 days.',
    sampleTarget: 15,
    costEstimate: '$150',
    passAction: 'Proceed to implementation planning.',
    failAction: 'Stop or reshape the value proposition.',
    flatAction: 'Run five diagnostic follow-up interviews.',
    invalidAction: 'Repair recruitment criteria and rerun.',
    lockedAt: new Date('2026-07-16T11:00:00.000Z'),
    createdAt: new Date('2026-07-16T10:30:00.000Z'),
    updatedAt: new Date('2026-07-16T11:00:00.000Z'),
    run: null,
    conclusion: null,
    ...overrides,
  };
}

function job(overrides: Record<string, unknown> = {}) {
  return {
    id: JOB_ID,
    status: 'COMPLETED',
    solutionIdeas: [
      { idea_id: 'idea-signal', idea_revision: 3, solution_name: 'Signal Desk', value_proposition: 'Find intent.' },
      { idea_id: 'idea-risk', idea_revision: 2, solution_name: 'Risk Radar', value_proposition: 'See risk.' },
      { idea_id: 'idea-discovery', idea_revision: 1, solution_name: 'Discovery Only' },
    ],
    selectedSolution: 'Signal Desk',
    selectedSolutions: ['Signal Desk', 'Risk Radar'],
    selectedSolutionIds: ['idea-signal', 'idea-risk'],
    selectedSolutionRefs: exactSelectionRefs(),
    dispatches: [deepResearchDispatch()],
    deepResearchRecommendedIdeaId: 'idea-signal',
    deepResearchRecommendedIdeaRevision: 3,
    selectionRationale: 'Owner selected two finalists.',
    selectionDecisionProfile: null,
    selectionFounderFit: null,
    completedAt: new Date('2026-07-16T10:00:00.000Z'),
    selectionFinalDecision: null,
    selectionChallenges: [],
    selectionExperiments: [],
    selectionOwnerEvidence: [],
    selectionAssumptions: [],
    ...overrides,
  };
}

function assumptionRow(overrides: Record<string, unknown> = {}) {
  return {
    id: '30000000-0000-0000-0000-000000000001',
    jobId: JOB_ID,
    ideaId: 'idea-signal',
    ideaRevision: 3,
    lens: 'DEMAND',
    statement: 'Qualified buyers will pay for same-day intent alerts.',
    impactIfFalse: 'The selected idea loses its paid demand wedge.',
    falsificationQuestion: 'Will three qualified buyers place a refundable deposit?',
    impact: 'DECISIVE',
    ownerState: 'ACCEPTED_RISK',
    version: 2,
    originChallengeId: null,
    originQuestionId: null,
    statementFingerprint: 'd'.repeat(64),
    createdByUserId: 'owner-1',
    createdAt: new Date('2026-07-16T09:00:00.000Z'),
    updatedAt: new Date('2026-07-16T10:00:00.000Z'),
    originChallenge: null,
    experiments: [{
      id: TEST_EXPERIMENT_ID,
      status: 'LOCKED',
      conclusion: {
        outcome: 'PASS',
        evidenceSource: 'HOSTED_RUN',
        snapshot: { evidence: { quality: { status: 'VALID' } } },
      },
    }],
    ...overrides,
  };
}

function challengeRow(overrides: Record<string, unknown> = {}) {
  const idea = {
    idea_id: 'idea-signal',
    idea_revision: 3,
    solution_name: 'Signal Desk',
    value_proposition: 'Find intent.',
  };
  const prepared = prepareSelectionChallengeInput({
    lens: 'demand',
    idea,
    previewReport: null,
    discoveryData: null,
    ownerEvidence: [],
  });
  const assessment = (questionId: string, position: string, summary: string) => ({
    questionId,
    position,
    summary,
    subjectKeys: prepared.subjectSnapshot.slice(0, 1).map(item => item.key),
    evidenceKeys: [],
    evidenceClass: 'inference',
  });
  const artifact = {
    version: 1,
    inputFingerprint: prepared.inputFingerprint,
    ideaId: 'idea-signal',
    ideaRevision: 3,
    ideaTitle: 'Signal Desk',
    lens: 'demand',
    overall: 'weakened',
    ideaSnapshot: prepared.ideaSnapshot,
    subjectSnapshot: prepared.subjectSnapshot,
    evidenceSnapshot: prepared.evidenceSnapshot,
    questions: [
      {
        questionId: 'buyer_will_pay',
        consensus: 'mixed',
        skeptic: assessment('buyer_will_pay', 'contradicts', 'Payment intent is not observed in the captured evidence.'),
        auditor: assessment('buyer_will_pay', 'mixed', 'Interview language is only a weak proxy for payment intent.'),
      },
      {
        questionId: 'pain_is_observed',
        consensus: 'supported',
        skeptic: assessment('pain_is_observed', 'supports', 'The recurring pain is directly described.'),
        auditor: assessment('pain_is_observed', 'supports', 'The evidence supports a recurring workflow problem.'),
      },
      {
        questionId: 'urgency_is_behavioral',
        consensus: 'supported',
        skeptic: assessment('urgency_is_behavioral', 'supports', 'Workaround behavior shows urgency.'),
        auditor: assessment('urgency_is_behavioral', 'supports', 'Observed behavior supports urgency.'),
      },
    ],
    skepticModel: 'model-skeptic',
    auditorModel: 'model-auditor',
    promptVersion: 1,
    createdAt: '2026-07-16T11:30:00.000Z',
  };
  return {
    id: '00000000-0000-0000-0000-000000000301',
    ideaId: 'idea-signal',
    ideaRevision: 3,
    lens: 'DEMAND',
    inputFingerprint: prepared.inputFingerprint,
    artifact,
    ...overrides,
  };
}

function input(overrides: Record<string, unknown> = {}) {
  return {
    disposition: 'PROCEED',
    ideaId: 'idea-signal',
    ideaRevision: 3,
    preMortem: [{
      failureMode: 'The audience does not return after the first useful signal.',
      earlyWarningSignal: 'Fewer than three of ten trial users return within fourteen days.',
      mitigation: 'Interview non-returning users and narrow the recurring workflow before building more.',
    }],
    rationale: 'This is the clearest next move for the current audience.',
    acceptedRisks: 'Distribution remains open.',
    changeCriterion: 'Stop if ten qualified calls produce no follow-up requests.',
    sourceFingerprint: '',
    ...overrides,
  };
}

let app: Express;

beforeEach(async () => {
  vi.clearAllMocks();
  mocks.jobFindFirst.mockResolvedValue(job());
  mocks.getReportJsonForJob.mockResolvedValue(report);
  mocks.getPreviewReportForJob.mockResolvedValue(null);
  mocks.getDiscoveryDataForJob.mockResolvedValue(null);
  mocks.decisionCreate.mockImplementation(async ({ data }) => ({
    id: 'decision-1',
    createdAt: new Date('2026-07-16T12:00:00.000Z'),
    ...data,
  }));
  app = express();
  app.use(express.json());
  const { selectionFinalDecisionsRouter } = await import('../selectionFinalDecisions.js');
  app.use('/api/jobs', selectionFinalDecisionsRouter);
});

async function sources() {
  const response = await request(app)
    .get(`/api/jobs/${JOB_ID}/final-decision`)
    .set('X-User-ID', 'owner-1');
  expect(response.status).toBe(200);
  return response.body;
}

describe('selection final decisions', () => {
  it('returns an exact research recommendation separately from an owner decision', async () => {
    const body = await sources();
    expect(body.decision).toBeNull();
    expect(body.recommendation).toMatchObject({
      ideaId: 'idea-signal',
      ideaRevision: 3,
      solutionName: 'Signal Desk',
      identityResolution: 'exact',
    });
    expect(body.finalists).toHaveLength(2);
    expect(body.lockedTestBriefs).toEqual([]);
  });

  it('uses frozen finalist snapshots when the current pool contains a newer revision', async () => {
    mocks.jobFindFirst.mockResolvedValue(job({
      solutionIdeas: [
        { idea_id: 'idea-signal', idea_revision: 4, solution_name: 'Signal Desk v4', value_proposition: 'Current pool value.' },
        { idea_id: 'idea-risk', idea_revision: 2, solution_name: 'Risk Radar', value_proposition: 'See risk.' },
      ],
    }));

    const loaded = await sources();
    expect(loaded.recommendation).toMatchObject({
      ideaId: 'idea-signal',
      ideaRevision: 3,
      solutionName: 'Signal Desk',
      identityResolution: 'exact',
    });

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/final-decision`)
      .send(input({ sourceFingerprint: loaded.sourceFingerprint }));
    expect(response.status).toBe(201);
    expect(mocks.decisionCreate.mock.calls[0][0].data.selectedIdeaSnapshot).toMatchObject({
      idea_id: 'idea-signal',
      idea_revision: 3,
      solution_name: 'Signal Desk',
      value_proposition: 'Find intent.',
    });
  });

  it('rejects a frozen finalist whose snapshot does not match its immutable hash', async () => {
    const refs = exactSelectionRefs();
    refs[0] = { ...refs[0], snapshotSha256: 'f'.repeat(64) };
    mocks.jobFindFirst.mockResolvedValue(job({
      selectedSolutionRefs: refs,
      dispatches: [deepResearchDispatch(frozenFinalists, refs)],
    }));

    const response = await request(app).get(`/api/jobs/${JOB_ID}/final-decision`);
    expect(response.status).toBe(409);
    expect(response.body.error).toMatch(/finalist identities/i);
  });

  it('returns only current unresolved challenge prompts for exact finalist revisions', async () => {
    mocks.jobFindFirst.mockResolvedValue(job({ selectionChallenges: [challengeRow()] }));
    const body = await sources();
    expect(body.riskPrompts).toEqual([expect.objectContaining({
      challengeId: '00000000-0000-0000-0000-000000000301',
      ideaId: 'idea-signal',
      ideaRevision: 3,
      lens: 'demand',
      questionId: 'buyer_will_pay',
      consensus: 'mixed',
    })]);
    expect(body.riskPrompts[0].challengeArtifactFingerprint).toMatch(/^[a-f0-9]{64}$/);
  });

  it('freezes exact current challenge provenance without private evidence excerpts', async () => {
    const challenge = challengeRow();
    mocks.jobFindFirst.mockResolvedValue(job({ selectionChallenges: [challenge] }));
    const loaded = await sources();
    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/final-decision`)
      .send(input({
        sourceFingerprint: loaded.sourceFingerprint,
        preMortem: [{
          failureMode: 'Qualified buyers never make a concrete payment commitment.',
          earlyWarningSignal: 'No qualified buyer places a deposit in the first fifteen conversations.',
          mitigation: 'Stop implementation and reshape the paid outcome before collecting more demand.',
          origin: {
            challengeId: challenge.id,
            questionId: 'buyer_will_pay',
          },
        }],
      }));

    expect(response.status).toBe(201);
    const snapshot = mocks.decisionCreate.mock.calls[0][0].data.preMortemSnapshot;
    expect(snapshot.entries[0].origin).toMatchObject({
      kind: 'SELECTION_CHALLENGE_QUESTION',
      challengeId: challenge.id,
      questionId: 'buyer_will_pay',
      lens: 'demand',
      consensus: 'mixed',
      skeptic: { position: 'contradicts' },
      auditor: { position: 'mixed' },
    });
    expect(JSON.stringify(snapshot)).not.toContain('excerpt');
    expect(JSON.stringify(snapshot)).not.toContain('sourceUrl');
  });

  it('requires a complete pre-mortem for target decisions and rejects it for targetless decisions', async () => {
    const loaded = await sources();
    const missing = await request(app)
      .post(`/api/jobs/${JOB_ID}/final-decision`)
      .send(input({ sourceFingerprint: loaded.sourceFingerprint, preMortem: undefined }));
    expect(missing.status).toBe(400);

    const targetless = await request(app)
      .post(`/api/jobs/${JOB_ID}/final-decision`)
      .send(input({
        disposition: 'PARK',
        ideaId: undefined,
        ideaRevision: undefined,
        sourceFingerprint: loaded.sourceFingerprint,
      }));
    expect(targetless.status).toBe(400);
  });

  it('rejects stale or cross-target saved-risk origins', async () => {
    const challenge = challengeRow();
    mocks.jobFindFirst.mockResolvedValue(job({ selectionChallenges: [challenge] }));
    const current = await sources();
    const origin = { challengeId: challenge.id, questionId: 'buyer_will_pay' };

    const crossTarget = await request(app)
      .post(`/api/jobs/${JOB_ID}/final-decision`)
      .send(input({
        ideaId: 'idea-risk',
        ideaRevision: 2,
        overrideReason: 'The founder already owns the distribution path for this finalist.',
        sourceFingerprint: current.sourceFingerprint,
        preMortem: [{
          failureMode: 'The buyer never changes their current market-risk workflow.',
          earlyWarningSignal: 'No qualified user imports data during the first fourteen days.',
          mitigation: 'Stop implementation and test the switching wedge with five buyers.',
          origin,
        }],
      }));
    expect(crossTarget.status).toBe(409);
    expect(crossTarget.body.error).toMatch(/saved risk changed/i);

    mocks.jobFindFirst.mockResolvedValue(job({
      selectionChallenges: [challengeRow({ inputFingerprint: 'f'.repeat(64) })],
    }));
    const staleSources = await sources();
    const stale = await request(app)
      .post(`/api/jobs/${JOB_ID}/final-decision`)
      .send(input({
        sourceFingerprint: staleSources.sourceFingerprint,
        preMortem: [{
          failureMode: 'Qualified buyers never make a concrete payment commitment.',
          earlyWarningSignal: 'No qualified buyer places a deposit in the first fifteen conversations.',
          mitigation: 'Stop implementation and reshape the paid outcome before collecting more demand.',
          origin,
        }],
      }));
    expect(stale.status).toBe(409);
    expect(stale.body.error).toMatch(/saved risk changed/i);
  });

  it('returns only locked, unconcluded test briefs for exact finalist revisions', async () => {
    mocks.jobFindFirst.mockResolvedValue(job({
      selectionExperiments: [
        lockedExperiment(),
        lockedExperiment({ id: '00000000-0000-0000-0000-000000000102', ideaRevision: 2 }),
        lockedExperiment({
          id: '00000000-0000-0000-0000-000000000103',
          conclusion: {
            id: '00000000-0000-0000-0000-000000000201',
            ideaId: 'idea-signal',
            ideaRevision: 3,
            outcome: 'PASS',
            nextActionSnapshot: 'Proceed.',
            ownerRationale: 'The pass rule was met.',
            createdAt: new Date('2026-07-16T12:00:00.000Z'),
            snapshot: {},
          },
        }),
      ],
    }));

    const body = await sources();
    expect(body.lockedTestBriefs).toHaveLength(1);
    expect(body.lockedTestBriefs[0]).toMatchObject({
      experimentId: TEST_EXPERIMENT_ID,
      idea: { ideaId: 'idea-signal', ideaRevision: 3 },
      assumption: { statement: 'Qualified buyers will make a payment commitment.' },
      runStatus: null,
      conclusionId: null,
    });
    expect(body.conclusions).toHaveLength(1);
  });

  it('records a followed recommendation with server-built snapshots', async () => {
    const loaded = await sources();
    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/final-decision`)
      .set('X-User-ID', 'owner-1')
      .send(input({ sourceFingerprint: loaded.sourceFingerprint }));

    expect(response.status).toBe(201);
    expect(response.body.decision.recommendationRelation).toBe('FOLLOWED');
    expect(response.body.decision.selectedIdeaId).toBe('idea-signal');
    const data = mocks.decisionCreate.mock.calls[0][0].data;
    expect(data.selectedIdeaSnapshot.solution_name).toBe('Signal Desk');
    expect(data.alternativesSnapshot.discoveryOnlyAlternatives[0].solution_name).toBe('Discovery Only');
    expect(data.reportSha256).toMatch(/^[a-f0-9]{64}$/);
    expect(data.testExperimentId).toBeNull();
    expect(data.testExperimentSnapshot).toBe(Prisma.DbNull);
    expect(data.preMortemSnapshot).toMatchObject({
      version: 1,
      target: { ideaId: 'idea-signal', ideaRevision: 3 },
      entries: [{ origin: null }],
    });
  });

  it('requires and freezes the exact locked test brief for Test first', async () => {
    mocks.jobFindFirst.mockResolvedValue(job({ selectionExperiments: [lockedExperiment()] }));
    const loaded = await sources();
    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/final-decision`)
      .send(input({
        disposition: 'TEST_FIRST',
        testExperimentId: TEST_EXPERIMENT_ID,
        sourceFingerprint: loaded.sourceFingerprint,
      }));

    expect(response.status).toBe(201);
    const data = mocks.decisionCreate.mock.calls[0][0].data;
    expect(data).toMatchObject({
      disposition: 'TEST_FIRST',
      testExperimentId: TEST_EXPERIMENT_ID,
      testExperimentSnapshot: {
        experimentId: TEST_EXPERIMENT_ID,
        idea: { ideaId: 'idea-signal', ideaRevision: 3 },
        assumption: { statement: 'Qualified buyers will make a payment commitment.' },
        runStatusAtDecision: null,
      },
    });
    expect(data.testExperimentSnapshot.briefFingerprint).toMatch(/^[a-f0-9]{64}$/);
    expect(data.evidenceSnapshot.selectedTestBrief).toEqual(data.testExperimentSnapshot);
  });

  it('rejects Test first without an exact eligible brief', async () => {
    const loaded = await sources();
    const missing = await request(app)
      .post(`/api/jobs/${JOB_ID}/final-decision`)
      .send(input({ disposition: 'TEST_FIRST', sourceFingerprint: loaded.sourceFingerprint }));
    expect(missing.status).toBe(400);

    mocks.jobFindFirst.mockResolvedValue(job({ selectionExperiments: [lockedExperiment()] }));
    const withBrief = await sources();
    const wrong = await request(app)
      .post(`/api/jobs/${JOB_ID}/final-decision`)
      .send(input({
        disposition: 'TEST_FIRST',
        testExperimentId: '00000000-0000-0000-0000-000000000999',
        sourceFingerprint: withBrief.sourceFingerprint,
      }));
    expect(wrong.status).toBe(409);
    expect(wrong.body.error).toMatch(/no longer eligible/i);
    expect(mocks.decisionCreate).not.toHaveBeenCalled();
  });

  it('rejects a locked test brief from another finalist revision', async () => {
    mocks.jobFindFirst.mockResolvedValue(job({ selectionExperiments: [lockedExperiment()] }));
    const loaded = await sources();
    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/final-decision`)
      .send(input({
        disposition: 'TEST_FIRST',
        ideaId: 'idea-risk',
        ideaRevision: 2,
        testExperimentId: TEST_EXPERIMENT_ID,
        overrideReason: 'The founder already owns this candidate distribution channel.',
        sourceFingerprint: loaded.sourceFingerprint,
      }));

    expect(response.status).toBe(409);
    expect(response.body.error).toMatch(/different candidate revision/i);
  });

  it('changes the source fingerprint when an eligible locked plan changes', async () => {
    mocks.jobFindFirst.mockResolvedValue(job({ selectionExperiments: [lockedExperiment()] }));
    const first = await sources();
    mocks.jobFindFirst.mockResolvedValue(job({
      selectionExperiments: [lockedExperiment({ passThreshold: 'At least 5 deposits.' })],
    }));
    const changed = await sources();
    expect(changed.sourceFingerprint).not.toBe(first.sourceFingerprint);
  });

  it('fingerprints safe owner-evidence metadata without exposing private content', async () => {
    const evidence = {
      id: '123e4567-e89b-42d3-a456-426614174000',
      ideaId: 'idea-signal',
      ideaRevision: 3,
      lens: 'DEMAND',
      kind: 'CUSTOMER_QUOTE',
      position: 'SUPPORTS',
      title: 'Interview with an operations lead',
      content: 'Private interview transcript must not leave the owner ledger.',
      sourceUrl: null,
      observedAt: new Date('2026-07-15T10:00:00.000Z'),
      inputFingerprint: 'b'.repeat(64),
      createdAt: new Date('2026-07-16T09:00:00.000Z'),
      retractedAt: null,
    };
    mocks.jobFindFirst.mockResolvedValue(job({ selectionOwnerEvidence: [
      evidence,
      { ...evidence, id: '223e4567-e89b-42d3-a456-426614174000', ideaId: 'idea-discovery' },
    ] }));

    const first = await sources();
    expect(first.ownerEvidence).toEqual([expect.objectContaining({
      id: evidence.id,
      ideaId: 'idea-signal',
      recordFingerprint: evidence.inputFingerprint,
    })]);
    expect(JSON.stringify(first.ownerEvidence)).not.toContain('Private interview transcript');

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/final-decision`)
      .send(input({ sourceFingerprint: first.sourceFingerprint }));
    expect(response.status).toBe(201);
    const snapshot = mocks.decisionCreate.mock.calls[0][0].data.evidenceSnapshot;
    expect(snapshot.ownerEvidence).toEqual(first.ownerEvidence);
    expect(JSON.stringify(snapshot)).not.toContain('Private interview transcript');

    mocks.jobFindFirst.mockResolvedValue(job({
      selectionOwnerEvidence: [{ ...evidence, inputFingerprint: 'c'.repeat(64) }],
    }));
    const changed = await sources();
    expect(changed.sourceFingerprint).not.toBe(first.sourceFingerprint);
  });

  it('reviews current finalist assumptions and freezes only the selected exact revision', async () => {
    const selectedAssumption = assumptionRow();
    const otherFinalistAssumption = assumptionRow({
      id: '30000000-0000-0000-0000-000000000002',
      ideaId: 'idea-risk',
      ideaRevision: 2,
      statement: 'Risk Radar can reach compliance teams through the founder network.',
      impact: 'DECISIVE',
      ownerState: 'OPEN',
      experiments: [],
    });
    mocks.jobFindFirst.mockResolvedValue(job({
      selectionAssumptions: [
        selectedAssumption,
        otherFinalistAssumption,
        assumptionRow({
          id: '30000000-0000-0000-0000-000000000003',
          ideaRevision: 2,
        }),
        assumptionRow({
          id: '30000000-0000-0000-0000-000000000004',
          ownerState: 'RETIRED',
        }),
      ],
    }));

    const loaded = await sources();
    expect(loaded.assumptions).toHaveLength(2);
    expect(loaded.assumptions).toEqual(expect.arrayContaining([
      expect.objectContaining({
        id: selectedAssumption.id,
        ideaId: 'idea-signal',
        ideaRevision: 3,
        impact: 'DECISIVE',
        ownerState: 'ACCEPTED_RISK',
        direction: 'SUPPORTING',
        evidenceClass: 'OBSERVED',
        falsificationQuestion: selectedAssumption.falsificationQuestion,
        linkedTests: [{ id: TEST_EXPERIMENT_ID, status: 'LOCKED', outcome: 'PASS' }],
      }),
      expect.objectContaining({
        id: otherFinalistAssumption.id,
        impact: 'DECISIVE',
        ownerState: 'OPEN',
      }),
    ]));

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/final-decision`)
      .send(input({ sourceFingerprint: loaded.sourceFingerprint }));

    expect(response.status).toBe(201);
    const snapshot = mocks.decisionCreate.mock.calls[0][0].data.evidenceSnapshot.assumptions;
    expect(snapshot).toEqual([expect.objectContaining({
      id: selectedAssumption.id,
      ideaId: 'idea-signal',
      ideaRevision: 3,
      ownerState: 'ACCEPTED_RISK',
      direction: 'SUPPORTING',
      linkedTests: [{ id: TEST_EXPERIMENT_ID, status: 'LOCKED', outcome: 'PASS' }],
    })]);
  });

  it('invalidates a reviewed source when a linked assumption test outcome changes', async () => {
    mocks.jobFindFirst.mockResolvedValue(job({ selectionAssumptions: [assumptionRow()] }));
    const first = await sources();

    mocks.jobFindFirst.mockResolvedValue(job({
      selectionAssumptions: [assumptionRow({
        experiments: [{
          id: TEST_EXPERIMENT_ID,
          status: 'LOCKED',
          conclusion: {
            outcome: 'FAIL',
            evidenceSource: 'HOSTED_RUN',
            snapshot: { evidence: { quality: { status: 'VALID' } } },
          },
        }],
      })],
    }));
    const changed = await sources();
    expect(changed.sourceFingerprint).not.toBe(first.sourceFingerprint);
    expect(changed.assumptions[0]).toMatchObject({
      direction: 'CONTRADICTING',
      linkedTests: [{ outcome: 'FAIL' }],
    });

    const stale = await request(app)
      .post(`/api/jobs/${JOB_ID}/final-decision`)
      .send(input({ sourceFingerprint: first.sourceFingerprint }));
    expect(stale.status).toBe(409);
    expect(stale.body.error).toMatch(/inputs changed/i);
    expect(mocks.decisionCreate).not.toHaveBeenCalled();
  });

  it('requires an explicit reason when overriding the recommendation', async () => {
    const loaded = await sources();
    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/final-decision`)
      .send(input({
        sourceFingerprint: loaded.sourceFingerprint,
        ideaId: 'idea-risk',
        ideaRevision: 2,
      }));

    expect(response.status).toBe(400);
    expect(response.body.error).toMatch(/overriding/i);
    expect(mocks.decisionCreate).not.toHaveBeenCalled();
  });

  it('rejects stale decision sources before writing', async () => {
    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/final-decision`)
      .send(input({ sourceFingerprint: 'a'.repeat(64) }));

    expect(response.status).toBe(409);
    expect(response.body.error).toMatch(/inputs changed/i);
  });

  it('records Park without attaching an idea identity', async () => {
    const loaded = await sources();
    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/final-decision`)
      .send(input({
        disposition: 'PARK',
        sourceFingerprint: loaded.sourceFingerprint,
        ideaId: undefined,
        ideaRevision: undefined,
        preMortem: undefined,
      }));

    expect(response.status).toBe(201);
    expect(response.body.decision).toMatchObject({
      disposition: 'PARK',
      selectedIdeaId: null,
      selectedIdeaRevision: null,
      recommendationRelation: 'DEFERRED',
    });
  });

  it('returns an exact retry and rejects a conflicting immutable decision', async () => {
    const loaded = await sources();
    const firstInput = input({ sourceFingerprint: loaded.sourceFingerprint });
    const first = await request(app).post(`/api/jobs/${JOB_ID}/final-decision`).send(firstInput);
    expect(first.status).toBe(201);

    mocks.jobFindFirst.mockResolvedValue(job({ selectionFinalDecision: first.body.decision }));
    const retry = await request(app).post(`/api/jobs/${JOB_ID}/final-decision`).send(firstInput);
    expect(retry.status).toBe(200);
    const conflict = await request(app).post(`/api/jobs/${JOB_ID}/final-decision`).send({
      ...firstInput,
      rationale: 'A different immutable decision rationale that conflicts.',
    });
    expect(conflict.status).toBe(409);
  });

  it('does not resolve an ambiguous legacy recommendation name', async () => {
    mocks.jobFindFirst.mockResolvedValue(job({
      selectedSolutionRefs: null,
      dispatches: [],
      deepResearchRecommendedIdeaId: null,
      deepResearchRecommendedIdeaRevision: null,
      selectedSolution: 'Signal Desk',
      selectedSolutions: ['Signal Desk', 'Signal Desk'],
      solutionIdeas: [
        { idea_id: 'idea-signal', idea_revision: 3, solution_name: 'Signal Desk' },
        { idea_id: 'idea-risk', idea_revision: 2, solution_name: 'Signal Desk' },
      ],
    }));
    const response = await request(app).get(`/api/jobs/${JOB_ID}/final-decision`);
    expect(response.status).toBe(409);
    expect(response.body.error).toMatch(/recommendation/i);
  });

  it('recovers exact legacy finalist identities only from unique names', async () => {
    mocks.jobFindFirst.mockResolvedValue(job({
      selectedSolutionRefs: null,
      dispatches: [],
      selectedSolutionIds: [],
      deepResearchRecommendedIdeaId: null,
      deepResearchRecommendedIdeaRevision: null,
    }));
    const response = await request(app).get(`/api/jobs/${JOB_ID}/final-decision`);
    expect(response.status).toBe(200);
    expect(response.body.recommendation).toMatchObject({
      ideaId: 'idea-signal',
      ideaRevision: 3,
      identityResolution: 'legacy_unique_name',
    });
  });
});
