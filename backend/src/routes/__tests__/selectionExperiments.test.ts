import { beforeEach, describe, expect, it, vi } from 'vitest';
import express, { type Express } from 'express';
import request from 'supertest';

// These suites exercise route logic, not the decision-tools grant. The grant itself is
// covered in middleware/__tests__/featureAccess.test.ts.
vi.mock('../../middleware/featureAccess.js', () => ({
  requireDecisionToolsAccess: (_req: any, _res: any, next: any) => next(),
}));

const mockJobFindFirst = vi.fn();
const mockExperimentFindMany = vi.fn();
const mockExperimentCreate = vi.fn();
const mockExperimentFindFirst = vi.fn();
const mockExperimentUpdate = vi.fn();
const mockExperimentUpdateMany = vi.fn();
const mockExperimentDeleteMany = vi.fn();
const mockExperimentFindUnique = vi.fn();
const mockChallengeFindFirst = vi.fn();
const mockOwnerEvidenceFindMany = vi.fn();
const mockAssumptionFindFirst = vi.fn();
const mockPrepareChallengeInput = vi.fn();
const mockPreviewReport = vi.fn();
const mockDiscoveryData = vi.fn();

vi.mock('../../services/db.js', () => ({
  prisma: {
    job: { findFirst: (...args: unknown[]) => mockJobFindFirst(...args) },
    selectionExperiment: {
      findMany: (...args: unknown[]) => mockExperimentFindMany(...args),
      create: (...args: unknown[]) => mockExperimentCreate(...args),
      findFirst: (...args: unknown[]) => mockExperimentFindFirst(...args),
      update: (...args: unknown[]) => mockExperimentUpdate(...args),
      updateMany: (...args: unknown[]) => mockExperimentUpdateMany(...args),
      deleteMany: (...args: unknown[]) => mockExperimentDeleteMany(...args),
      findUnique: (...args: unknown[]) => mockExperimentFindUnique(...args),
    },
    selectionChallenge: { findFirst: (...args: unknown[]) => mockChallengeFindFirst(...args) },
    selectionOwnerEvidence: { findMany: (...args: unknown[]) => mockOwnerEvidenceFindMany(...args) },
    selectionAssumption: { findFirst: (...args: unknown[]) => mockAssumptionFindFirst(...args) },
  },
}));

vi.mock('../../services/assetService.js', () => ({
  getPreviewReportForJob: (...args: unknown[]) => mockPreviewReport(...args),
  getDiscoveryDataForJob: (...args: unknown[]) => mockDiscoveryData(...args),
}));

vi.mock('../../services/selectionChallengeService.js', () => ({
  prepareSelectionChallengeInput: (...args: unknown[]) => mockPrepareChallengeInput(...args),
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
const CHALLENGE_ID = '223e4567-e89b-42d3-a456-426614174000';
const headers = { 'x-user-id': 'owner-1' };
const draft = {
  ideaId: 'idea-exact',
  ideaRevision: 2,
  assumptionType: 'DESIRABILITY',
  assumption: 'Qualified operators will request early access after seeing the workflow promise.',
  whyCritical: 'Without a behavioral commitment, the concept should not advance.',
  currentEvidence: 'Repeated complaints exist, but no commitment evidence exists yet.',
  method: 'CTA_SMOKE_TEST',
  evidenceSignal: 'CTA_INTEREST',
  stimulus: 'A focused page with one request-access CTA and immediate fake-door disclosure.',
  audience: 'Operations leads at 20–200 person service businesses.',
  channel: 'Two relevant operator communities.',
  primaryMetric: 'Qualified request-access clicks divided by qualified unique visitors.',
  passThreshold: 'At least 8% from 150 qualified visitors.',
  failThreshold: 'Below 3% after 150 qualified visitors.',
  measurementWindow: '14 days or 150 qualified visitors, whichever is later.',
  sampleTarget: 150,
  costEstimate: 'Under $300',
  passAction: 'Interview clickers and continue to a concierge test.',
  failAction: 'Park the current positioning and test the next candidate.',
  flatAction: 'Revise the offer once, then repeat with the same thresholds.',
  invalidAction: 'Repair targeting or instrumentation and rerun without changing thresholds.',
};

const challengeAssessment = {
  questionId: 'pain_is_observed',
  position: 'insufficient',
  summary: 'The packet does not yet establish repeated costly behavior.',
  subjectKeys: ['I1'],
  evidenceKeys: ['S1'],
  evidenceClass: 'observed',
};
const challengeArtifact = {
  version: 1,
  inputFingerprint: 'f'.repeat(64),
  ideaId: draft.ideaId,
  ideaRevision: draft.ideaRevision,
  ideaTitle: 'Signal Desk',
  lens: 'demand',
  overall: 'insufficient_evidence',
  ideaSnapshot: { idea_id: draft.ideaId, idea_revision: draft.ideaRevision, solution_name: 'Signal Desk' },
  subjectSnapshot: [{ key: 'I1', field: 'source_pain', value: 'Operators miss recurring demand signals' }],
  evidenceSnapshot: [{
    key: 'S1',
    kind: 'customer_quote',
    title: 'Operator interview',
    excerpt: 'We check this manually every Monday.',
    url: null,
    capturedAt: '2026-07-15T00:00:00.000Z',
    provenance: { assetType: 'DISCOVERY_DATA', jsonPointer: '/interviews/0' },
  }],
  questions: ['pain_is_observed', 'urgency_is_behavioral', 'buyer_will_pay'].map(questionId => ({
    questionId,
    consensus: 'insufficient',
    skeptic: { ...challengeAssessment, questionId, evidenceKeys: questionId === 'pain_is_observed' ? ['S1'] : [] },
    auditor: { ...challengeAssessment, questionId, evidenceKeys: questionId === 'pain_is_observed' ? ['S1'] : [] },
  })),
  skepticModel: 'gpt-test',
  auditorModel: 'gpt-test',
  promptVersion: 1,
  createdAt: '2026-07-16T00:00:00.000Z',
};

let app: Express;

beforeEach(async () => {
  vi.clearAllMocks();
  mockExperimentUpdateMany.mockResolvedValue({ count: 1 });
  mockExperimentDeleteMany.mockResolvedValue({ count: 1 });
  mockOwnerEvidenceFindMany.mockResolvedValue([]);
  mockPreviewReport.mockResolvedValue(null);
  mockDiscoveryData.mockResolvedValue(null);
  mockPrepareChallengeInput.mockReturnValue({ inputFingerprint: 'f'.repeat(64) });
  mockAssumptionFindFirst.mockResolvedValue(null);
  app = express();
  app.use(express.json());
  const { selectionExperimentsRouter } = await import('../selectionExperiments.js');
  app.use('/api/jobs', selectionExperimentsRouter);
});

describe('selection experiment API', () => {
  it('creates a draft against the exact idea revision and stores an immutable snapshot', async () => {
    mockJobFindFirst.mockResolvedValue({
      id: JOB_ID,
      status: 'AWAITING_SELECTION',
      solutionIdeas: [{
        idea_id: 'idea-exact',
        idea_revision: 2,
        solution_name: 'Signal Desk',
        source_pain: 'Operators miss recurring demand signals',
      }],
    });
    mockExperimentCreate.mockImplementation(async ({ data }) => ({ id: EXPERIMENT_ID, status: 'DRAFT', ...data }));

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-experiments`)
      .set(headers)
      .send(draft);

    expect(response.status).toBe(201);
    expect(mockExperimentCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        jobId: JOB_ID,
        ideaId: 'idea-exact',
        ideaRevision: 2,
        ideaSnapshot: expect.objectContaining({
          idea_id: 'idea-exact',
          idea_revision: 2,
          solution_name: 'Signal Desk',
        }),
      }),
    });
  });

  it('links only an assumption from the same job and exact idea revision', async () => {
    const assumptionId = '323e4567-e89b-42d3-a456-426614174000';
    mockJobFindFirst.mockResolvedValue({
      id: JOB_ID,
      status: 'AWAITING_SELECTION',
      solutionIdeas: [{
        idea_id: draft.ideaId,
        idea_revision: draft.ideaRevision,
        solution_name: 'Signal Desk',
      }],
    });
    mockAssumptionFindFirst.mockResolvedValue({ id: assumptionId });
    mockExperimentCreate.mockImplementation(async ({ data }) => ({ id: EXPERIMENT_ID, status: 'DRAFT', ...data }));

    const linked = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-experiments`)
      .set(headers)
      .send({ ...draft, assumptionId });

    expect(linked.status).toBe(201);
    expect(mockAssumptionFindFirst).toHaveBeenCalledWith({
      where: {
        id: assumptionId,
        jobId: JOB_ID,
        ideaId: draft.ideaId,
        ideaRevision: draft.ideaRevision,
      },
      select: { id: true },
    });
    expect(mockExperimentCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({ assumptionId }),
    });

    mockAssumptionFindFirst.mockResolvedValue(null);
    mockExperimentCreate.mockClear();
    const rejected = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-experiments`)
      .set(headers)
      .send({ ...draft, assumptionId });
    expect(rejected.status).toBe(400);
    expect(rejected.body.error).toContain('exact idea revision');
    expect(mockExperimentCreate).not.toHaveBeenCalled();
  });

  it('verifies a current evidence-check question and stores server-built provenance', async () => {
    mockJobFindFirst.mockResolvedValue({
      id: JOB_ID,
      status: 'AWAITING_SELECTION',
      solutionIdeas: [{
        idea_id: draft.ideaId,
        idea_revision: draft.ideaRevision,
        solution_name: 'Signal Desk',
        source_pain: 'Operators miss recurring demand signals',
      }],
    });
    mockChallengeFindFirst.mockResolvedValue({ artifact: challengeArtifact });
    mockExperimentCreate.mockImplementation(async ({ data }) => ({ id: EXPERIMENT_ID, status: 'DRAFT', ...data }));

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-experiments`)
      .set(headers)
      .send({
        ...draft,
        originChallengeId: CHALLENGE_ID,
        originQuestionId: 'pain_is_observed',
      });

    expect(response.status).toBe(201);
    expect(mockChallengeFindFirst).toHaveBeenCalledWith({
      where: {
        id: CHALLENGE_ID,
        jobId: JOB_ID,
        ideaId: draft.ideaId,
        ideaRevision: draft.ideaRevision,
      },
      select: { artifact: true },
    });
    expect(mockExperimentCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        originChallengeId: CHALLENGE_ID,
        originQuestionId: 'pain_is_observed',
        originSnapshot: expect.objectContaining({
          kind: 'SELECTION_CHALLENGE_QUESTION',
          challengeInputFingerprint: challengeArtifact.inputFingerprint,
          questionId: 'pain_is_observed',
          evidenceKeys: ['S1'],
          citedSources: [challengeArtifact.evidenceSnapshot[0]],
        }),
      }),
    });
  });

  it('rejects an evidence-check origin whose packet has changed', async () => {
    mockJobFindFirst.mockResolvedValue({
      id: JOB_ID,
      status: 'AWAITING_SELECTION',
      solutionIdeas: [{ idea_id: draft.ideaId, idea_revision: draft.ideaRevision, solution_name: 'Signal Desk' }],
    });
    mockChallengeFindFirst.mockResolvedValue({ artifact: challengeArtifact });
    mockPrepareChallengeInput.mockReturnValue({ inputFingerprint: '0'.repeat(64) });

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-experiments`)
      .set(headers)
      .send({
        ...draft,
        originChallengeId: CHALLENGE_ID,
        originQuestionId: 'pain_is_observed',
      });

    expect(response.status).toBe(409);
    expect(response.body.error).toContain('stale');
    expect(mockExperimentCreate).not.toHaveBeenCalled();
  });

  it('requires challenge and question provenance together', async () => {
    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-experiments`)
      .set(headers)
      .send({ ...draft, originChallengeId: CHALLENGE_ID });

    expect(response.status).toBe(400);
    expect(response.body.error).toContain('together');
    expect(mockJobFindFirst).not.toHaveBeenCalled();
  });

  it('rejects an idea revision that is not in the current pool', async () => {
    mockJobFindFirst.mockResolvedValue({
      id: JOB_ID,
      status: 'AWAITING_SELECTION',
      solutionIdeas: [{ idea_id: 'idea-exact', idea_revision: 3, solution_name: 'Signal Desk' }],
    });

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-experiments`)
      .set(headers)
      .send(draft);

    expect(response.status).toBe(400);
    expect(response.body.error).toContain('revision');
    expect(mockExperimentCreate).not.toHaveBeenCalled();
  });

  it('rejects drafting while the candidate pool is regenerating', async () => {
    mockJobFindFirst.mockResolvedValue({
      id: JOB_ID,
      status: 'REGENERATING',
      solutionIdeas: [{
        idea_id: 'idea-exact',
        idea_revision: 2,
        solution_name: 'Signal Desk',
      }],
    });

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-experiments`)
      .set(headers)
      .send(draft);

    expect(response.status).toBe(409);
    expect(mockExperimentCreate).not.toHaveBeenCalled();
  });

  it('does not allow a locked precommitment to be edited', async () => {
    mockExperimentFindFirst.mockResolvedValue({
      ...draft,
      id: EXPERIMENT_ID,
      jobId: JOB_ID,
      ideaId: draft.ideaId,
      ideaRevision: draft.ideaRevision,
      status: 'LOCKED',
      job: { status: 'AWAITING_SELECTION' },
    });

    const response = await request(app)
      .put(`/api/jobs/${JOB_ID}/selection-experiments/${EXPERIMENT_ID}`)
      .set(headers)
      .send(draft);

    expect(response.status).toBe(409);
    expect(response.body.error).toContain('immutable');
    expect(mockExperimentUpdate).not.toHaveBeenCalled();
  });

  it('rejects retargeting a draft to a cross-idea assumption', async () => {
    const assumptionId = '323e4567-e89b-42d3-a456-426614174000';
    mockExperimentFindFirst.mockResolvedValue({
      ...draft,
      id: EXPERIMENT_ID,
      jobId: JOB_ID,
      ideaId: draft.ideaId,
      ideaRevision: draft.ideaRevision,
      status: 'DRAFT',
      originChallengeId: null,
      originQuestionId: null,
      job: { status: 'AWAITING_SELECTION' },
    });
    mockAssumptionFindFirst.mockResolvedValue(null);

    const response = await request(app)
      .put(`/api/jobs/${JOB_ID}/selection-experiments/${EXPERIMENT_ID}`)
      .set(headers)
      .send({ ...draft, assumptionId });

    expect(response.status).toBe(400);
    expect(response.body.error).toContain('exact idea revision');
    expect(mockAssumptionFindFirst).toHaveBeenCalledWith({
      where: {
        id: assumptionId,
        jobId: JOB_ID,
        ideaId: draft.ideaId,
        ideaRevision: draft.ideaRevision,
      },
      select: { id: true },
    });
    expect(mockExperimentUpdate).not.toHaveBeenCalled();
  });

  it('locks a draft with a compare-and-set transition', async () => {
    mockExperimentFindFirst.mockResolvedValue({
      ...draft,
      id: EXPERIMENT_ID,
      status: 'DRAFT',
      job: { status: 'AWAITING_SELECTION' },
    });
    mockExperimentFindUnique.mockResolvedValue({ id: EXPERIMENT_ID, status: 'LOCKED' });

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-experiments/${EXPERIMENT_ID}/lock`)
      .set(headers);

    expect(response.status).toBe(200);
    expect(mockExperimentUpdateMany).toHaveBeenCalledWith({
      where: { id: EXPERIMENT_ID, status: 'DRAFT' },
      data: { status: 'LOCKED', lockedAt: expect.any(Date) },
    });
  });

  it('deletes a draft with a compare-and-set guard', async () => {
    mockExperimentFindFirst.mockResolvedValue({
      ...draft,
      id: EXPERIMENT_ID,
      status: 'DRAFT',
      job: { status: 'AWAITING_SELECTION' },
    });

    const response = await request(app)
      .delete(`/api/jobs/${JOB_ID}/selection-experiments/${EXPERIMENT_ID}`)
      .set(headers);

    expect(response.status).toBe(204);
    expect(mockExperimentDeleteMany).toHaveBeenCalledWith({
      where: { id: EXPERIMENT_ID, status: 'DRAFT' },
    });
  });

  it('never deletes a locked precommitment', async () => {
    mockExperimentFindFirst.mockResolvedValue({
      ...draft,
      id: EXPERIMENT_ID,
      status: 'LOCKED',
      job: { status: 'AWAITING_SELECTION' },
    });

    const response = await request(app)
      .delete(`/api/jobs/${JOB_ID}/selection-experiments/${EXPERIMENT_ID}`)
      .set(headers);

    expect(response.status).toBe(409);
    expect(response.body.error).toContain('locked brief');
    expect(mockExperimentDeleteMany).not.toHaveBeenCalled();
  });

  it('rejects deleting a draft while the job is not in idea selection', async () => {
    mockExperimentFindFirst.mockResolvedValue({
      ...draft,
      id: EXPERIMENT_ID,
      status: 'DRAFT',
      job: { status: 'REGENERATING' },
    });

    const response = await request(app)
      .delete(`/api/jobs/${JOB_ID}/selection-experiments/${EXPERIMENT_ID}`)
      .set(headers);

    expect(response.status).toBe(409);
    expect(mockExperimentDeleteMany).not.toHaveBeenCalled();
  });

  it('does not reveal another owner\'s experiment on delete', async () => {
    mockExperimentFindFirst.mockResolvedValue(null);

    const response = await request(app)
      .delete(`/api/jobs/${JOB_ID}/selection-experiments/${EXPERIMENT_ID}`)
      .set(headers);

    expect(response.status).toBe(404);
    expect(mockExperimentDeleteMany).not.toHaveBeenCalled();
  });

  it('reports a lost delete race instead of claiming success', async () => {
    mockExperimentFindFirst.mockResolvedValue({
      ...draft,
      id: EXPERIMENT_ID,
      status: 'DRAFT',
      job: { status: 'AWAITING_SELECTION' },
    });
    mockExperimentDeleteMany.mockResolvedValue({ count: 0 });

    const response = await request(app)
      .delete(`/api/jobs/${JOB_ID}/selection-experiments/${EXPERIMENT_ID}`)
      .set(headers);

    expect(response.status).toBe(409);
  });

  it('does not reveal another owner\'s experiment', async () => {
    mockExperimentFindFirst.mockResolvedValue(null);

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-experiments/${EXPERIMENT_ID}/lock`)
      .set(headers);

    expect(response.status).toBe(404);
    expect(mockExperimentUpdateMany).not.toHaveBeenCalled();
  });

  it('returns a response when experiment listing fails instead of hanging', async () => {
    mockJobFindFirst.mockResolvedValue({ id: JOB_ID });
    mockExperimentFindMany.mockRejectedValue(new Error('Database unavailable'));

    const response = await request(app)
      .get(`/api/jobs/${JOB_ID}/selection-experiments`)
      .set(headers);

    expect(response.status).toBe(500);
    expect(response.body.error).toBe('Failed to load experiments');
  });

  it('exports a locked provenance-preserving test brief as Markdown', async () => {
    const originSnapshot = {
      version: 1,
      kind: 'SELECTION_CHALLENGE_QUESTION',
      challengeId: CHALLENGE_ID,
      challengeInputFingerprint: challengeArtifact.inputFingerprint,
      questionId: 'pain_is_observed',
      lens: 'demand',
      consensus: 'insufficient',
      evidenceKeys: ['S1'],
      skeptic: challengeArtifact.questions[0].skeptic,
      auditor: challengeArtifact.questions[0].auditor,
      citedSources: challengeArtifact.evidenceSnapshot,
    };
    mockExperimentFindFirst.mockResolvedValue({
      ...draft,
      id: EXPERIMENT_ID,
      jobId: JOB_ID,
      ideaId: draft.ideaId,
      ideaRevision: draft.ideaRevision,
      ideaSnapshot: { solution_name: 'Signal Desk' },
      originChallengeId: CHALLENGE_ID,
      originQuestionId: 'pain_is_observed',
      originSnapshot,
      status: 'LOCKED',
      lockedAt: new Date('2026-07-16T12:00:00.000Z'),
      createdAt: new Date('2026-07-16T11:00:00.000Z'),
      updatedAt: new Date('2026-07-16T12:00:00.000Z'),
    });

    const response = await request(app)
      .get(`/api/jobs/${JOB_ID}/selection-experiments/${EXPERIMENT_ID}/export/md`)
      .set(headers);

    expect(response.status).toBe(200);
    expect(response.headers['content-type']).toContain('text/markdown');
    expect(response.text).toContain('# Test brief: Signal Desk');
    expect(response.text).toContain(`- Challenge: ${CHALLENGE_ID}`);
    expect(response.text).toContain('- Question: pain_is_observed');
    expect(response.text).toContain('This brief records a precommitted test of one assumption');
  });

  it('does not export an unlocked or unowned test brief', async () => {
    mockExperimentFindFirst.mockResolvedValueOnce({
      id: EXPERIMENT_ID,
      status: 'DRAFT',
      lockedAt: null,
    });
    const unlocked = await request(app)
      .get(`/api/jobs/${JOB_ID}/selection-experiments/${EXPERIMENT_ID}/export/json`)
      .set(headers);
    expect(unlocked.status).toBe(409);

    mockExperimentFindFirst.mockResolvedValueOnce(null);
    const unowned = await request(app)
      .get(`/api/jobs/${JOB_ID}/selection-experiments/${EXPERIMENT_ID}/export/json`)
      .set(headers);
    expect(unowned.status).toBe(404);
  });

  it('returns a response when locking fails instead of hanging', async () => {
    mockExperimentFindFirst.mockRejectedValue(new Error('Database unavailable'));

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-experiments/${EXPERIMENT_ID}/lock`)
      .set(headers);

    expect(response.status).toBe(500);
    expect(response.body.error).toBe('Failed to lock experiment');
  });
});
