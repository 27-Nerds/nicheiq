import express, { type Express } from 'express';
import request from 'supertest';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  jobFindFirst: vi.fn(),
  handoffCreate: vi.fn(),
  handoffFindUnique: vi.fn(),
}));

vi.mock('../../services/db.js', () => ({
  prisma: {
    job: { findFirst: (...args: unknown[]) => mocks.jobFindFirst(...args) },
    selectionDecisionHandoff: {
      create: (...args: unknown[]) => mocks.handoffCreate(...args),
      findUnique: (...args: unknown[]) => mocks.handoffFindUnique(...args),
    },
  },
}));

vi.mock('../../middleware/auth.js', () => ({
  requireInternalAuth: (req: any, _res: any, next: any) => {
    req.user = { id: req.header('X-User-ID') ?? 'owner-1' };
    next();
  },
}));

const JOB_ID = '20000000-0000-0000-0000-000000000002';
const DECISION_ID = '10000000-0000-0000-0000-000000000001';

function finalDecision(overrides: Record<string, unknown> = {}) {
  return {
    id: DECISION_ID,
    jobId: JOB_ID,
    disposition: 'PROCEED',
    selectedIdeaId: 'idea-signal',
    selectedIdeaRevision: 3,
    testExperimentId: null,
    testExperimentSnapshot: null,
    preMortemSnapshot: {
      version: 1,
      target: { ideaId: 'idea-signal', ideaRevision: 3 },
      entries: [{
        failureMode: 'The audience does not return after the first useful signal.',
        earlyWarningSignal: 'Fewer than three of ten trial users return within fourteen days.',
        mitigation: 'Interview non-returning users and narrow the recurring workflow before building more.',
        origin: null,
      }],
    },
    recommendationRelation: 'FOLLOWED',
    rationale: 'This is the clearest next move for the current audience.',
    acceptedRisks: 'Distribution remains open.',
    changeCriterion: 'Stop if ten qualified calls produce no follow-up requests.',
    overrideReason: null,
    requestFingerprint: 'a'.repeat(64),
    sourceFingerprint: 'b'.repeat(64),
    recommendationSnapshot: { solutionName: 'Signal Desk' },
    selectedIdeaSnapshot: {
      idea_id: 'idea-signal',
      idea_revision: 3,
      solution_name: 'Signal Desk',
      reportEvidence: { details: { core_features: ['Signal inbox'] } },
    },
    alternativesSnapshot: { deepResearchedFinalists: [] },
    evidenceSnapshot: { experimentConclusions: [] },
    reportSha256: 'c'.repeat(64),
    decidedByUserId: 'owner-1',
    createdAt: new Date('2026-07-16T12:00:00.000Z'),
    decisionHandoff: null,
    ...overrides,
  };
}

function storedHandoff(overrides: Record<string, unknown> = {}) {
  return {
    id: '30000000-0000-0000-0000-000000000003',
    finalDecisionId: DECISION_ID,
    action: 'BUILD',
    ideaId: 'idea-signal',
    ideaRevision: 3,
    inputFingerprint: 'd'.repeat(64),
    artifact: {
      jobId: JOB_ID,
      finalDecisionId: DECISION_ID,
      action: 'BUILD',
      target: { ideaId: 'idea-signal', ideaRevision: 3, title: 'Signal Desk', proposedScope: [] },
      decision: {
        disposition: 'PROCEED',
        recommendationRelation: 'FOLLOWED',
        rationale: 'This is the clearest next move for the current audience.',
        acceptedRisks: '',
        changeCriterion: 'Stop if ten qualified calls produce no follow-up requests.',
        overrideReason: null,
        decidedAt: '2026-07-16T12:00:00.000Z',
      },
      evidence: {},
      executionPolicy: {
        providerDispatchAllowed: true,
        allowedOperation: 'CREATE_IMPLEMENTATION_ISSUE',
        resumeRequiresNewOwnerDecision: false,
        terminal: false,
      },
      testBrief: null,
      preMortem: finalDecision().preMortemSnapshot,
    },
    version: 1,
    createdAt: new Date('2026-07-16T12:05:00.000Z'),
    ...overrides,
  };
}

let app: Express;

beforeEach(async () => {
  vi.clearAllMocks();
  mocks.jobFindFirst.mockResolvedValue({ id: JOB_ID, selectionFinalDecision: finalDecision() });
  mocks.handoffCreate.mockImplementation(async ({ data }) => storedHandoff({
    ...data,
    inputFingerprint: data.inputFingerprint,
    artifact: data.artifact,
  }));
  app = express();
  app.use(express.json());
  const { selectionDecisionHandoffsRouter } = await import('../selectionDecisionHandoffs.js');
  app.use('/api/jobs', selectionDecisionHandoffsRouter);
});

describe('selection decision handoffs', () => {
  it('materializes an owner-only handoff without loading mutable report data', async () => {
    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/decision-handoff`)
      .set('X-User-ID', 'owner-1')
      .send({ finalDecisionId: DECISION_ID });

    expect(response.status).toBe(201);
    expect(response.body.handoff).toMatchObject({
      action: 'BUILD',
      ideaId: 'idea-signal',
      ideaRevision: 3,
      artifact: { finalDecisionId: DECISION_ID },
    });
    expect(mocks.handoffCreate).toHaveBeenCalledOnce();
    expect(mocks.jobFindFirst.mock.calls[0][0].where).toEqual({
      id: JOB_ID,
      userId: 'owner-1',
    });
  });

  it('uses one current handoff shape without an unreleased compatibility version', async () => {
    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/decision-handoff`)
      .send({ finalDecisionId: DECISION_ID });

    expect(response.status).toBe(201);
    expect(response.body.handoff).not.toHaveProperty('version');
    expect(mocks.handoffCreate.mock.calls[0][0].data).not.toHaveProperty('version');
  });

  it('does not expose another owner’s handoff', async () => {
    mocks.jobFindFirst.mockResolvedValue(null);
    const response = await request(app)
      .get(`/api/jobs/${JOB_ID}/decision-handoff`)
      .set('X-User-ID', 'viewer-2');

    expect(response.status).toBe(404);
  });

  it('requires the exact immutable decision id', async () => {
    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/decision-handoff`)
      .send({ finalDecisionId: '40000000-0000-0000-0000-000000000004' });

    expect(response.status).toBe(409);
    expect(mocks.handoffCreate).not.toHaveBeenCalled();
  });

  it('requires a recorded final decision', async () => {
    mocks.jobFindFirst.mockResolvedValue({ id: JOB_ID, selectionFinalDecision: null });
    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/decision-handoff`)
      .send({ finalDecisionId: DECISION_ID });

    expect(response.status).toBe(409);
    expect(response.body.error).toMatch(/final owner decision/i);
  });

  it('returns an exact retry without creating another artifact', async () => {
    const first = await request(app)
      .post(`/api/jobs/${JOB_ID}/decision-handoff`)
      .send({ finalDecisionId: DECISION_ID });
    const matching = storedHandoff({
      inputFingerprint: first.body.handoff.inputFingerprint,
      artifact: first.body.handoff.artifact,
    });
    mocks.jobFindFirst.mockResolvedValue({
      id: JOB_ID,
      selectionFinalDecision: finalDecision({ decisionHandoff: matching }),
    });

    const retry = await request(app)
      .post(`/api/jobs/${JOB_ID}/decision-handoff`)
      .send({ finalDecisionId: DECISION_ID });

    expect(retry.status).toBe(200);
    expect(retry.body.handoff.id).toBe(matching.id);
    expect(mocks.handoffCreate).toHaveBeenCalledOnce();
  });

  it('exports the stored artifact as Markdown and JSON', async () => {
    const handoff = storedHandoff();
    mocks.jobFindFirst.mockResolvedValue({
      id: JOB_ID,
      selectionFinalDecision: finalDecision({ decisionHandoff: handoff }),
    });

    const markdown = await request(app)
      .get(`/api/jobs/${JOB_ID}/decision-handoff/export/md`);
    const json = await request(app)
      .get(`/api/jobs/${JOB_ID}/decision-handoff/export/json`);

    expect(markdown.status).toBe(200);
    expect(markdown.headers['content-disposition']).toContain('.md');
    expect(markdown.text).toContain('# Implementation brief');
    expect(json.status).toBe(200);
    expect(json.headers['content-disposition']).toContain('.json');
    expect(JSON.parse(json.text)).toMatchObject({
      inputFingerprint: handoff.inputFingerprint,
      artifact: { finalDecisionId: DECISION_ID },
    });
  });
});
