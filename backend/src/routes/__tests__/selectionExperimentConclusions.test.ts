import { beforeEach, describe, expect, it, vi } from 'vitest';
import express, { type Express } from 'express';
import request from 'supertest';

// These suites exercise route logic, not the decision-tools grant. The grant itself is
// covered in middleware/__tests__/featureAccess.test.ts.
vi.mock('../../middleware/featureAccess.js', () => ({
  requireDecisionToolsAccess: (_req: any, _res: any, next: any) => next(),
}));

const mockExperimentFindFirst = vi.fn();
const mockConclusionCreate = vi.fn();
const mockConclusionFindUnique = vi.fn();
const mockEventGroupBy = vi.fn();
const mockEventAggregate = vi.fn();
const mockTxExperimentFindUnique = vi.fn();

vi.mock('../../services/db.js', () => ({
  prisma: {
    selectionExperiment: {
      findFirst: (...args: unknown[]) => mockExperimentFindFirst(...args),
    },
    selectionExperimentConclusion: {
      create: (...args: unknown[]) => mockConclusionCreate(...args),
      findUnique: (...args: unknown[]) => mockConclusionFindUnique(...args),
    },
    selectionExperimentEvent: {
      groupBy: (...args: unknown[]) => mockEventGroupBy(...args),
      aggregate: (...args: unknown[]) => mockEventAggregate(...args),
    },
    $transaction: async (callback: (tx: unknown) => unknown) => callback({
      selectionExperiment: {
        findUnique: (...args: unknown[]) => mockTxExperimentFindUnique(...args),
      },
      selectionExperimentConclusion: {
        create: (...args: unknown[]) => mockConclusionCreate(...args),
      },
    }),
  },
}));

vi.mock('../../middleware/auth.js', () => ({
  requireInternalAuth: (req: any, res: any, next: any) => {
    if (!req.headers['x-user-id']) return res.status(401).json({ error: 'Unauthorized' });
    req.user = { id: req.headers['x-user-id'] };
    next();
  },
  AuthenticatedRequest: {},
}));

const JOB_ID = '550e8400-e29b-41d4-a716-446655440000';
const EXPERIMENT_ID = '123e4567-e89b-42d3-a456-426614174000';
const RUN_ID = '223e4567-e89b-42d3-a456-426614174000';
const headers = { 'x-user-id': 'owner-1' };

const lockedExperiment = {
  id: EXPERIMENT_ID,
  jobId: JOB_ID,
  ideaId: 'idea-exact',
  ideaRevision: 4,
  ideaSnapshot: { idea_id: 'idea-exact', idea_revision: 4, solution_name: 'Signal Desk' },
  status: 'LOCKED',
  assumptionType: 'DESIRABILITY',
  assumption: 'Qualified operators will take the next step after seeing the promise.',
  whyCritical: 'Without behavioral interest, this positioning should not advance.',
  currentEvidence: 'Repeated complaints, but no commitment evidence.',
  method: 'CTA_SMOKE_TEST',
  evidenceSignal: 'CTA_INTEREST',
  stimulus: 'One focused offer and CTA.',
  audience: 'Operations leads.',
  channel: 'Two operator communities.',
  primaryMetric: 'Qualified CTA clicks divided by qualified exposures.',
  passThreshold: 'At least 8% after 100 qualified exposures.',
  failThreshold: 'Below 3% after 100 qualified exposures.',
  measurementWindow: '14 days or 100 exposures, whichever is later.',
  sampleTarget: 100,
  costEstimate: 'Under $300',
  passAction: 'Continue to a concierge test.',
  failAction: 'Park this positioning.',
  flatAction: 'Revise the offer once and repeat.',
  invalidAction: 'Repair targeting or instrumentation and rerun.',
  lockedAt: new Date('2026-07-15T10:00:00.000Z'),
  createdAt: new Date('2026-07-15T09:00:00.000Z'),
  updatedAt: new Date('2026-07-15T10:00:00.000Z'),
  job: { status: 'AWAITING_SELECTION' },
  conclusion: null,
  run: null,
  assumptionId: null,
  linkedAssumption: null,
};

const manualInput = {
  evidenceSource: 'MANUAL',
  outcome: 'FAIL',
  ownerRationale: 'Only one of twelve qualified interviewees described an urgent enough workflow to switch tools.',
  observationSummary: 'Twelve structured interviews; one participant requested a follow-up and none asked for access.',
  observedAt: '2026-07-15',
  sampleSize: 12,
  observedMetric: '1 of 12 requested a follow-up',
  sourceReferences: ['Interview notes / July cohort'],
  limitations: ['Recruitment came from one professional community.'],
};

let app: Express;

beforeEach(async () => {
  vi.clearAllMocks();
  mockEventGroupBy.mockResolvedValue([]);
  mockEventAggregate.mockResolvedValue({ _min: { receivedAt: null }, _max: { receivedAt: null } });
  mockTxExperimentFindUnique.mockResolvedValue({ assumptionId: null });
  app = express();
  app.use(express.json());
  const { selectionExperimentConclusionsRouter } = await import('../selectionExperimentConclusions.js');
  app.use('/api/jobs', selectionExperimentConclusionsRouter);
});

describe('selection experiment conclusions', () => {
  it('records manual evidence against the exact locked idea and derives the precommitted action', async () => {
    mockExperimentFindFirst.mockResolvedValue(lockedExperiment);
    mockConclusionCreate.mockImplementation(async ({ data }) => ({
      id: 'conclusion-1',
      createdAt: new Date('2026-07-16T00:00:00.000Z'),
      ...data,
    }));

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-experiments/${EXPERIMENT_ID}/conclusion`)
      .set(headers)
      .send(manualInput);

    expect(response.status).toBe(201);
    expect(mockConclusionCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        experimentId: EXPERIMENT_ID,
        ideaId: 'idea-exact',
        ideaRevision: 4,
        evidenceSource: 'MANUAL',
        outcome: 'FAIL',
        nextActionSnapshot: lockedExperiment.failAction,
        concludedByUserId: 'owner-1',
        snapshot: expect.objectContaining({
          schemaVersion: 1,
          experiment: expect.objectContaining({ ideaId: 'idea-exact', ideaRevision: 4 }),
          evidence: expect.objectContaining({ source: expect.objectContaining({ adapterKey: 'manual' }) }),
          adjudication: expect.objectContaining({ basis: 'OWNER_RECORDED' }),
        }),
      }),
    });
    expect(response.body.conclusion.nextActionSnapshot).toBe(lockedExperiment.failAction);
    expect(JSON.stringify(response.body.conclusion)).not.toContain('validated');
  });

  it('snapshots hosted observations only after the run is closed and uses the close time as the cutoff', async () => {
    const closedAt = new Date('2026-07-15T14:00:00.000Z');
    mockExperimentFindFirst.mockResolvedValue({
      ...lockedExperiment,
      run: {
        id: RUN_ID,
        status: 'CLOSED',
        artifact: { version: 1, headline: 'Signal Desk', promise: 'Find buyer signals' },
        briefVersion: 1,
        stimulusVersion: 1,
        launchedAt: new Date('2026-07-15T12:00:00.000Z'),
        closedAt,
      },
    });
    mockEventGroupBy.mockResolvedValue([
      { type: 'STIMULUS_EXPOSED', _count: { _all: 120 } },
      { type: 'CTA_CLICKED', _count: { _all: 11 } },
      { type: 'FAKE_DOOR_DISCLOSED', _count: { _all: 11 } },
    ]);
    mockEventAggregate.mockResolvedValue({
      _min: { receivedAt: new Date('2026-07-15T12:01:00.000Z') },
      _max: { receivedAt: new Date('2026-07-15T13:59:00.000Z') },
    });
    mockConclusionCreate.mockImplementation(async ({ data }) => ({ id: 'conclusion-1', createdAt: new Date(), ...data }));

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-experiments/${EXPERIMENT_ID}/conclusion`)
      .set(headers)
      .send({
        evidenceSource: 'HOSTED_RUN',
        outcome: 'PASS',
        ownerRationale: 'The closed run cleared the written rate and sample rules for this exact offer.',
        limitations: ['One acquisition channel was tested.'],
      });

    expect(response.status).toBe(201);
    expect(mockEventGroupBy).toHaveBeenCalledWith(expect.objectContaining({
      where: { runId: RUN_ID, receivedAt: { lte: closedAt } },
    }));
    const snapshot = mockConclusionCreate.mock.calls[0][0].data.snapshot;
    expect(snapshot.evidence.window.observedThrough).toEqual(closedAt.toISOString());
    expect(snapshot.evidence.metrics).toEqual(expect.arrayContaining([
      expect.objectContaining({ key: 'cta_rate', numerator: 11, denominator: 120, isPrimary: true }),
    ]));
    expect(snapshot.adjudication.nextAction).toBe(lockedExperiment.passAction);
  });

  it('records the linked assumption evidence transition in the immutable conclusion snapshot', async () => {
    const assumptionId = '323e4567-e89b-42d3-a456-426614174000';
    mockExperimentFindFirst.mockResolvedValue({
      ...lockedExperiment,
      assumptionId,
      linkedAssumption: {
        id: assumptionId,
        jobId: JOB_ID,
        ideaId: lockedExperiment.ideaId,
        ideaRevision: lockedExperiment.ideaRevision,
        lens: 'DEMAND',
        statement: 'Qualified operators will take the next step.',
        impactIfFalse: 'The offer should not advance.',
        falsificationQuestion: 'Will qualified operators commit?',
        impact: 'DECISIVE',
        ownerState: 'OPEN',
        version: 2,
        originChallengeId: null,
        originQuestionId: null,
        statementFingerprint: 'f'.repeat(64),
        createdByUserId: 'owner-1',
        createdAt: new Date(),
        updatedAt: new Date(),
        originChallenge: null,
        experiments: [{ id: EXPERIMENT_ID, status: 'LOCKED', conclusion: null }],
      },
    });
    mockTxExperimentFindUnique.mockResolvedValue({ assumptionId });
    mockConclusionCreate.mockImplementation(async ({ data }) => ({ id: 'conclusion-linked', createdAt: new Date(), ...data }));

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-experiments/${EXPERIMENT_ID}/conclusion`)
      .set(headers)
      .send(manualInput);

    expect(response.status).toBe(201);
    expect(response.body.assumptionTransition).toEqual({
      assumptionId,
      before: { direction: 'UNKNOWN', evidenceClass: 'NONE', ownerState: 'OPEN', version: 2 },
      after: { direction: 'CONTRADICTING', evidenceClass: 'PROXY', ownerState: 'OPEN', version: 2 },
    });
    expect(mockConclusionCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        snapshot: expect.objectContaining({
          assumptionTransition: response.body.assumptionTransition,
        }),
      }),
    });
    expect(mockTxExperimentFindUnique).toHaveBeenCalledWith({
      where: { id: EXPERIMENT_ID },
      select: { assumptionId: true },
    });
  });

  it('rejects hosted conclusions while the run is active', async () => {
    mockExperimentFindFirst.mockResolvedValue({
      ...lockedExperiment,
      run: { id: RUN_ID, status: 'ACTIVE', closedAt: null },
    });

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-experiments/${EXPERIMENT_ID}/conclusion`)
      .set(headers)
      .send({
        evidenceSource: 'HOSTED_RUN',
        outcome: 'PASS',
        ownerRationale: 'This should not be accepted while observations are still changing.',
        limitations: [],
      });

    expect(response.status).toBe(409);
    expect(response.body.error).toMatch(/close/i);
    expect(mockConclusionCreate).not.toHaveBeenCalled();
  });

  it('does not allow a partial hosted sample to be labeled pass or fail', async () => {
    mockExperimentFindFirst.mockResolvedValue({
      ...lockedExperiment,
      run: {
        id: RUN_ID,
        status: 'CLOSED',
        artifact: {},
        briefVersion: 1,
        stimulusVersion: 1,
        launchedAt: new Date('2026-07-15T12:00:00.000Z'),
        closedAt: new Date('2026-07-15T13:00:00.000Z'),
      },
    });
    mockEventGroupBy.mockResolvedValue([
      { type: 'STIMULUS_EXPOSED', _count: { _all: 40 } },
      { type: 'CTA_CLICKED', _count: { _all: 5 } },
    ]);

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-experiments/${EXPERIMENT_ID}/conclusion`)
      .set(headers)
      .send({
        evidenceSource: 'HOSTED_RUN',
        outcome: 'PASS',
        ownerRationale: 'The observed rate looks promising but the sample target was not reached.',
        limitations: [],
      });

    expect(response.status).toBe(409);
    expect(response.body.error).toContain('AMBIGUOUS');
    expect(mockConclusionCreate).not.toHaveBeenCalled();
  });

  it('returns the existing conclusion for an exact retry and rejects a conflicting rewrite', async () => {
    mockExperimentFindFirst.mockResolvedValue(lockedExperiment);
    mockConclusionCreate.mockImplementation(async ({ data }) => ({
      id: 'conclusion-1',
      createdAt: new Date(),
      ...data,
    }));
    const created = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-experiments/${EXPERIMENT_ID}/conclusion`)
      .set(headers)
      .send(manualInput);
    expect(created.status).toBe(201);
    const existing = created.body.conclusion;
    mockConclusionCreate.mockClear();
    mockExperimentFindFirst.mockResolvedValue({ ...lockedExperiment, conclusion: existing });

    const exact = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-experiments/${EXPERIMENT_ID}/conclusion`)
      .set(headers)
      .send(manualInput);
    expect(exact.status).toBe(200);

    mockExperimentFindFirst.mockResolvedValue({ ...lockedExperiment, conclusion: existing });
    const conflict = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-experiments/${EXPERIMENT_ID}/conclusion`)
      .set(headers)
      .send({ ...manualInput, ownerRationale: `${manualInput.ownerRationale} Changed.` });
    expect(conflict.status).toBe(409);
    expect(mockConclusionCreate).not.toHaveBeenCalled();
  });

  it('does not reveal another owner’s experiment', async () => {
    mockExperimentFindFirst.mockResolvedValue(null);

    const response = await request(app)
      .get(`/api/jobs/${JOB_ID}/selection-experiments/${EXPERIMENT_ID}/conclusion`)
      .set(headers);

    expect(response.status).toBe(404);
  });
});
