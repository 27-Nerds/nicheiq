import { beforeEach, describe, expect, it, vi } from 'vitest';
import express, { type Express } from 'express';
import request from 'supertest';

const mockJobFindFirst = vi.fn();
const mockEvidenceFindMany = vi.fn();
const mockEvidenceFindFirst = vi.fn();
const mockEvidenceCreate = vi.fn();
const mockEvidenceCount = vi.fn();
const mockEvidenceUpdateMany = vi.fn();
const mockTransaction = vi.fn();

vi.mock('../../services/db.js', () => ({
  prisma: {
    job: { findFirst: (...args: unknown[]) => mockJobFindFirst(...args) },
    $transaction: (callback: unknown, options: unknown) => mockTransaction(callback, options),
    selectionOwnerEvidence: {
      findMany: (...args: unknown[]) => mockEvidenceFindMany(...args),
      findFirst: (...args: unknown[]) => mockEvidenceFindFirst(...args),
      create: (...args: unknown[]) => mockEvidenceCreate(...args),
      count: (...args: unknown[]) => mockEvidenceCount(...args),
      updateMany: (...args: unknown[]) => mockEvidenceUpdateMany(...args),
    },
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
const EVIDENCE_ID = '123e4567-e89b-42d3-a456-426614174000';
const headers = { 'x-user-id': 'owner-1' };
const input = {
  ideaId: 'idea-exact',
  ideaRevision: 2,
  lens: 'demand',
  kind: 'CUSTOMER_QUOTE',
  position: 'SUPPORTS',
  title: 'Interview with an operations lead',
  content: 'We check five dashboards every morning and still miss recurring signals.',
  sourceUrl: 'https://example.com/interviews/42',
  observedAt: '2026-07-16T10:00:00.000Z',
};

const activeRow = {
  id: EVIDENCE_ID,
  jobId: JOB_ID,
  ideaId: input.ideaId,
  ideaRevision: input.ideaRevision,
  lens: 'DEMAND',
  kind: input.kind,
  position: input.position,
  title: input.title,
  content: input.content,
  sourceUrl: input.sourceUrl,
  observedAt: new Date(input.observedAt),
  inputFingerprint: 'a'.repeat(64),
  createdByUserId: headers['x-user-id'],
  createdAt: new Date('2026-07-16T11:00:00.000Z'),
  retractedAt: null,
  retractionReason: null,
};

function ownedJob(overrides: Record<string, unknown> = {}) {
  return {
    id: JOB_ID,
    status: 'AWAITING_SELECTION',
    solutionIdeas: [{
      idea_id: input.ideaId,
      idea_revision: input.ideaRevision,
      solution_name: 'Signal Desk',
    }],
    selectionFinalDecision: null,
    ...overrides,
  };
}

let app: Express;

beforeEach(async () => {
  vi.clearAllMocks();
  mockJobFindFirst.mockResolvedValue(ownedJob());
  mockEvidenceFindMany.mockResolvedValue([]);
  mockEvidenceFindFirst.mockResolvedValue(null);
  mockEvidenceCount.mockResolvedValue(0);
  mockEvidenceUpdateMany.mockResolvedValue({ count: 1 });
  mockTransaction.mockImplementation(async (callback) => callback({
    job: { findFirst: (...args: unknown[]) => mockJobFindFirst(...args) },
    selectionOwnerEvidence: {
      findFirst: (...args: unknown[]) => mockEvidenceFindFirst(...args),
      count: (...args: unknown[]) => mockEvidenceCount(...args),
      create: (...args: unknown[]) => mockEvidenceCreate(...args),
    },
  }));
  app = express();
  app.use(express.json());
  const { selectionOwnerEvidenceRouter } = await import('../selectionOwnerEvidence.js');
  app.use('/api/jobs', selectionOwnerEvidenceRouter);
});

describe('selection owner evidence API', () => {
  it('creates immutable evidence against the exact idea revision', async () => {
    mockEvidenceCreate.mockImplementation(async ({ data }) => ({
      ...activeRow,
      ...data,
      id: EVIDENCE_ID,
      createdAt: activeRow.createdAt,
      retractedAt: null,
      retractionReason: null,
    }));

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-evidence`)
      .set(headers)
      .send(input);

    expect(response.status).toBe(201);
    expect(response.body.evidence).toMatchObject({
      id: EVIDENCE_ID,
      ideaId: input.ideaId,
      ideaRevision: 2,
      lens: 'demand',
      kind: 'CUSTOMER_QUOTE',
      position: 'SUPPORTS',
    });
    expect(mockEvidenceCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        jobId: JOB_ID,
        ideaId: input.ideaId,
        ideaRevision: 2,
        inputFingerprint: expect.stringMatching(/^[a-f0-9]{64}$/),
        createdByUserId: 'owner-1',
      }),
    });
  });

  it('returns the active duplicate as an idempotent cached result', async () => {
    mockEvidenceFindFirst.mockResolvedValue(activeRow);

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-evidence`)
      .set(headers)
      .send(input);

    expect(response.status).toBe(200);
    expect(response.body.cached).toBe(true);
    expect(response.body.evidence.id).toBe(EVIDENCE_ID);
    expect(mockEvidenceCreate).not.toHaveBeenCalled();
  });

  it('rejects a stale idea revision', async () => {
    mockJobFindFirst.mockResolvedValue(ownedJob({
      solutionIdeas: [{ idea_id: input.ideaId, idea_revision: 3, solution_name: 'Signal Desk' }],
    }));

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-evidence`)
      .set(headers)
      .send(input);

    expect(response.status).toBe(409);
    expect(response.body.error).toContain('revision changed');
    expect(mockEvidenceCreate).not.toHaveBeenCalled();
  });

  it('does not reveal another owner\'s job', async () => {
    mockJobFindFirst.mockResolvedValue(null);

    const response = await request(app)
      .get(`/api/jobs/${JOB_ID}/selection-evidence`)
      .set(headers);

    expect(response.status).toBe(404);
    expect(mockEvidenceFindMany).not.toHaveBeenCalled();
  });

  it('rejects writes once the selection state is no longer editable', async () => {
    mockJobFindFirst.mockResolvedValue(ownedJob({ status: 'REGENERATING' }));

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-evidence`)
      .set(headers)
      .send(input);

    expect(response.status).toBe(409);
    expect(mockEvidenceCreate).not.toHaveBeenCalled();
  });

  it('retracts evidence without deleting it', async () => {
    mockEvidenceFindFirst.mockResolvedValue(activeRow);
    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-evidence/${EVIDENCE_ID}/retract`)
      .set(headers)
      .send({ reason: 'The interview attribution was incorrect.' });

    expect(response.status).toBe(200);
    expect(response.body.cached).toBe(false);
    expect(response.body.evidence.retractedAt).toEqual(expect.any(String));
    expect(mockEvidenceUpdateMany).toHaveBeenCalledWith({
      where: { id: EVIDENCE_ID, jobId: JOB_ID, retractedAt: null },
      data: {
        retractedAt: expect.any(Date),
        retractionReason: 'The interview attribution was incorrect.',
      },
    });
  });

  it('rejects non-HTTP source URLs before accessing the database', async () => {
    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-evidence`)
      .set(headers)
      .send({ ...input, sourceUrl: 'javascript:alert(1)' });

    expect(response.status).toBe(400);
    expect(mockJobFindFirst).not.toHaveBeenCalled();
  });

  it('requires a URL when the evidence kind is link', async () => {
    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-evidence`)
      .set(headers)
      .send({ ...input, kind: 'LINK', sourceUrl: null });

    expect(response.status).toBe(400);
    expect(mockTransaction).not.toHaveBeenCalled();
  });
});
