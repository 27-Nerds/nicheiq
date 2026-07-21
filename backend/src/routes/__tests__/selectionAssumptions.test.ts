import { beforeEach, describe, expect, it, vi } from 'vitest';
import express, { type Express } from 'express';
import request from 'supertest';

const mockJobFindFirst = vi.fn();
const mockAssumptionFindMany = vi.fn();
const mockAssumptionFindFirst = vi.fn();
const mockAssumptionCreate = vi.fn();
const mockAssumptionUpdateMany = vi.fn();
const mockAssumptionFindUniqueOrThrow = vi.fn();
const mockChallengeFindFirst = vi.fn();
const mockOwnerEvidenceFindMany = vi.fn();

vi.mock('../../services/db.js', () => ({
  prisma: {
    job: { findFirst: (...args: unknown[]) => mockJobFindFirst(...args) },
    selectionAssumption: {
      findMany: (...args: unknown[]) => mockAssumptionFindMany(...args),
      findFirst: (...args: unknown[]) => mockAssumptionFindFirst(...args),
      create: (...args: unknown[]) => mockAssumptionCreate(...args),
      updateMany: (...args: unknown[]) => mockAssumptionUpdateMany(...args),
      findUniqueOrThrow: (...args: unknown[]) => mockAssumptionFindUniqueOrThrow(...args),
    },
    selectionChallenge: { findFirst: (...args: unknown[]) => mockChallengeFindFirst(...args) },
    selectionOwnerEvidence: { findMany: (...args: unknown[]) => mockOwnerEvidenceFindMany(...args) },
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
const ASSUMPTION_ID = '123e4567-e89b-42d3-a456-426614174000';
const CHALLENGE_ID = '223e4567-e89b-42d3-a456-426614174000';
const headers = { 'x-user-id': 'owner-1' };

const input = {
  ideaId: 'idea-exact',
  ideaRevision: 2,
  lens: 'demand',
  statement: 'Qualified operators will pay to automate this recurring workflow.',
  impactIfFalse: 'The concept has no credible path to revenue from this audience.',
  falsificationQuestion: 'Will at least five qualified operators make a payment commitment?',
  impact: 'DECISIVE',
};

const assumption = {
  id: ASSUMPTION_ID,
  jobId: JOB_ID,
  ideaId: input.ideaId,
  ideaRevision: input.ideaRevision,
  lens: 'DEMAND',
  statement: input.statement,
  impactIfFalse: input.impactIfFalse,
  falsificationQuestion: input.falsificationQuestion,
  impact: input.impact,
  ownerState: 'OPEN',
  version: 1,
  originChallengeId: null,
  originQuestionId: null,
  statementFingerprint: 'f'.repeat(64),
  createdByUserId: 'owner-1',
  createdAt: new Date('2026-07-16T00:00:00.000Z'),
  updatedAt: new Date('2026-07-16T00:00:00.000Z'),
  originChallenge: null,
  experiments: [],
};

const currentJob = {
  id: JOB_ID,
  status: 'AWAITING_SELECTION',
  solutionIdeas: [{ idea_id: input.ideaId, idea_revision: input.ideaRevision, solution_name: 'Signal Desk' }],
};

let app: Express;

beforeEach(async () => {
  vi.clearAllMocks();
  mockAssumptionFindMany.mockResolvedValue([]);
  mockAssumptionFindFirst.mockResolvedValue(null);
  mockAssumptionUpdateMany.mockResolvedValue({ count: 1 });
  app = express();
  app.use(express.json());
  const { selectionAssumptionsRouter } = await import('../selectionAssumptions.js');
  app.use('/api/jobs', selectionAssumptionsRouter);
});

describe('selection assumption ledger API', () => {
  it('does not reveal another owner’s ledger', async () => {
    mockJobFindFirst.mockResolvedValue(null);
    const response = await request(app)
      .get(`/api/jobs/${JOB_ID}/selection-assumptions`)
      .set(headers);

    expect(response.status).toBe(404);
    expect(mockAssumptionFindMany).not.toHaveBeenCalled();
  });

  it('keeps old revisions visible as stale and ignores unrelated same-lens owner evidence', async () => {
    mockJobFindFirst.mockResolvedValue({
      id: JOB_ID,
      solutionIdeas: [{ idea_id: input.ideaId, idea_revision: 3, solution_name: 'Signal Desk' }],
    });
    mockAssumptionFindMany.mockResolvedValue([assumption]);
    mockOwnerEvidenceFindMany.mockResolvedValue([{ position: 'SUPPORTS', kind: 'ANALYTICS_OBSERVATION' }]);

    const response = await request(app)
      .get(`/api/jobs/${JOB_ID}/selection-assumptions`)
      .set(headers);

    expect(response.status).toBe(200);
    expect(response.body.assumptions[0]).toMatchObject({
      stale: true,
      direction: 'UNKNOWN',
      evidenceClass: 'NONE',
    });
    expect(mockOwnerEvidenceFindMany).not.toHaveBeenCalled();
  });

  it('creates an assumption only for the current exact idea revision', async () => {
    mockJobFindFirst.mockResolvedValue(currentJob);
    mockAssumptionCreate.mockImplementation(async ({ data }) => ({
      ...assumption,
      ...data,
      originChallenge: null,
      experiments: [],
    }));

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-assumptions`)
      .set(headers)
      .send(input);

    expect(response.status).toBe(201);
    expect(response.body.cached).toBe(false);
    expect(response.body.assumption).not.toHaveProperty('statementFingerprint');
    expect(mockAssumptionCreate).toHaveBeenCalledWith(expect.objectContaining({
      data: expect.objectContaining({
        ideaId: input.ideaId,
        ideaRevision: input.ideaRevision,
        lens: 'DEMAND',
        createdByUserId: 'owner-1',
        statementFingerprint: expect.stringMatching(/^[a-f0-9]{64}$/),
      }),
    }));
  });

  it('rejects creation against a stale idea revision', async () => {
    mockJobFindFirst.mockResolvedValue({
      ...currentJob,
      solutionIdeas: [{ idea_id: input.ideaId, idea_revision: 3 }],
    });

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-assumptions`)
      .set(headers)
      .send(input);

    expect(response.status).toBe(409);
    expect(response.body.error).toContain('no longer current');
    expect(mockAssumptionCreate).not.toHaveBeenCalled();
  });

  it('rejects new assumptions once the owner decision is locked', async () => {
    mockJobFindFirst.mockResolvedValue({ ...currentJob, selectionFinalDecision: { id: 'decision-1' } });

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-assumptions`)
      .set(headers)
      .send(input);

    expect(response.status).toBe(409);
    expect(response.body.error).toContain('locked');
    expect(mockAssumptionCreate).not.toHaveBeenCalled();
  });

  it('rejects assumption updates once the owner decision is locked', async () => {
    mockJobFindFirst.mockResolvedValue({ ...currentJob, selectionFinalDecision: { id: 'decision-1' } });
    mockAssumptionFindFirst.mockResolvedValue({
      id: ASSUMPTION_ID,
      ideaId: input.ideaId,
      ideaRevision: input.ideaRevision,
      lens: 'DEMAND',
    });

    const response = await request(app)
      .patch(`/api/jobs/${JOB_ID}/selection-assumptions/${ASSUMPTION_ID}`)
      .set(headers)
      .send({
        expectedVersion: 1,
        ideaId: input.ideaId,
        ideaRevision: input.ideaRevision,
        ownerState: 'ACCEPTED_RISK',
      });

    expect(response.status).toBe(409);
    expect(response.body.error).toContain('locked');
    expect(mockAssumptionUpdateMany).not.toHaveBeenCalled();
  });

  it('returns an exact retry but requires versioned update when duplicate impact differs', async () => {
    mockJobFindFirst.mockResolvedValue(currentJob);
    mockAssumptionFindFirst.mockResolvedValue(assumption);

    const exact = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-assumptions`)
      .set(headers)
      .send(input);
    expect(exact.status).toBe(200);
    expect(exact.body.cached).toBe(true);

    const conflict = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-assumptions`)
      .set(headers)
      .send({ ...input, impact: 'HIGH' });
    expect(conflict.status).toBe(409);
    expect(conflict.body.error).toContain('current version');
    expect(mockAssumptionCreate).not.toHaveBeenCalled();
    expect(mockAssumptionFindFirst.mock.calls.at(-1)?.[0].where).toMatchObject({
      ideaId: input.ideaId,
      ideaRevision: input.ideaRevision,
      lens: 'DEMAND',
    });
    expect(mockAssumptionFindFirst.mock.calls.at(-1)?.[0].where).not.toHaveProperty('impact');
  });

  it('validates exact challenge/question provenance and upserts by that origin', async () => {
    mockJobFindFirst.mockResolvedValue(currentJob);
    mockChallengeFindFirst.mockResolvedValue({
      artifact: {
        version: 1,
        inputFingerprint: 'a'.repeat(64),
        ideaId: input.ideaId,
        ideaRevision: input.ideaRevision,
        ideaTitle: 'Signal Desk',
        lens: 'demand',
        overall: 'insufficient_evidence',
        ideaSnapshot: {},
        subjectSnapshot: [{ key: 'I1', field: 'source_pain', value: 'Manual work repeats weekly.' }],
        evidenceSnapshot: [],
        questions: ['pain_is_observed', 'urgency_is_behavioral', 'buyer_will_pay'].map(questionId => ({
          questionId,
          consensus: 'insufficient',
          skeptic: {
            questionId,
            position: 'insufficient',
            summary: 'No direct evidence yet.',
            subjectKeys: ['I1'],
            evidenceKeys: [],
            evidenceClass: 'inference',
          },
          auditor: {
            questionId,
            position: 'insufficient',
            summary: 'No direct evidence yet.',
            subjectKeys: ['I1'],
            evidenceKeys: [],
            evidenceClass: 'inference',
          },
        })),
        skepticModel: 'test',
        auditorModel: 'test',
        promptVersion: 1,
        createdAt: '2026-07-16T00:00:00.000Z',
      },
    });
    mockAssumptionFindFirst.mockResolvedValue({
      ...assumption,
      originChallengeId: CHALLENGE_ID,
      originQuestionId: 'pain_is_observed',
    });

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-assumptions`)
      .set(headers)
      .send({
        ...input,
        originChallengeId: CHALLENGE_ID,
        originQuestionId: 'pain_is_observed',
      });

    expect(response.status).toBe(200);
    expect(mockChallengeFindFirst).toHaveBeenCalledWith(expect.objectContaining({
      where: expect.objectContaining({
        id: CHALLENGE_ID,
        ideaId: input.ideaId,
        ideaRevision: input.ideaRevision,
        lens: 'DEMAND',
      }),
    }));
    expect(mockAssumptionFindFirst).toHaveBeenCalledWith(expect.objectContaining({
      where: { jobId: JOB_ID, originChallengeId: CHALLENGE_ID, originQuestionId: 'pain_is_observed' },
    }));
  });

  it('uses expectedVersion CAS and rejects stale saves', async () => {
    mockJobFindFirst.mockResolvedValue(currentJob);
    mockAssumptionFindFirst.mockResolvedValue({
      id: ASSUMPTION_ID,
      ideaId: input.ideaId,
      ideaRevision: input.ideaRevision,
    });
    mockAssumptionUpdateMany.mockResolvedValue({ count: 0 });

    const response = await request(app)
      .patch(`/api/jobs/${JOB_ID}/selection-assumptions/${ASSUMPTION_ID}`)
      .set(headers)
      .send({
        expectedVersion: 1,
        ideaId: input.ideaId,
        ideaRevision: input.ideaRevision,
        ownerState: 'ACCEPTED_RISK',
      });

    expect(response.status).toBe(409);
    expect(response.body.error).toContain('reload');
    expect(mockAssumptionUpdateMany).toHaveBeenCalledWith({
      where: expect.objectContaining({ version: 1, ideaId: input.ideaId, ideaRevision: input.ideaRevision }),
      data: { ownerState: 'ACCEPTED_RISK', version: { increment: 1 } },
    });
  });

  it('rejects patching through a stale idea identity even with a current version', async () => {
    mockJobFindFirst.mockResolvedValue(currentJob);
    mockAssumptionFindFirst.mockResolvedValue({
      id: ASSUMPTION_ID,
      ideaId: input.ideaId,
      ideaRevision: input.ideaRevision,
    });

    const response = await request(app)
      .patch(`/api/jobs/${JOB_ID}/selection-assumptions/${ASSUMPTION_ID}`)
      .set(headers)
      .send({
        expectedVersion: 1,
        ideaId: input.ideaId,
        ideaRevision: 3,
        ownerState: 'RETIRED',
      });

    expect(response.status).toBe(409);
    expect(response.body.error).toContain('stale idea revision');
    expect(mockAssumptionUpdateMany).not.toHaveBeenCalled();
  });

  it('rekeys statement identity when an owner edits the assumption', async () => {
    const revisedStatement = 'Qualified operators will prepay for this recurring workflow.';
    mockJobFindFirst.mockResolvedValue(currentJob);
    mockAssumptionFindFirst.mockResolvedValue({
      id: ASSUMPTION_ID,
      ideaId: input.ideaId,
      ideaRevision: input.ideaRevision,
      lens: 'DEMAND',
    });
    mockAssumptionFindUniqueOrThrow.mockResolvedValue({
      ...assumption,
      statement: revisedStatement,
      version: 2,
    });

    const response = await request(app)
      .patch(`/api/jobs/${JOB_ID}/selection-assumptions/${ASSUMPTION_ID}`)
      .set(headers)
      .send({
        expectedVersion: 1,
        ideaId: input.ideaId,
        ideaRevision: input.ideaRevision,
        statement: revisedStatement,
      });

    expect(response.status).toBe(200);
    expect(mockAssumptionUpdateMany).toHaveBeenCalledWith({
      where: expect.objectContaining({ version: 1 }),
      data: {
        statement: revisedStatement,
        statementFingerprint: expect.stringMatching(/^[a-f0-9]{64}$/),
        version: { increment: 1 },
      },
    });
  });
});
