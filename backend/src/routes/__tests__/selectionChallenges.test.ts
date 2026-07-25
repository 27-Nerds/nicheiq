import { beforeEach, describe, expect, it, vi } from 'vitest';
import express from 'express';
import request from 'supertest';

// These suites exercise route logic, not the decision-tools grant. The grant itself is
// covered in middleware/__tests__/featureAccess.test.ts.
vi.mock('../../middleware/featureAccess.js', () => ({
  requireDecisionToolsAccess: (_req: any, _res: any, next: any) => next(),
}));

const mocks = vi.hoisted(() => ({
  jobFindFirst: vi.fn(),
  challengeFindFirst: vi.fn(),
  challengeFindMany: vi.fn(),
  challengeCreate: vi.fn(),
  ownerEvidenceFindMany: vi.fn(),
  experimentFindMany: vi.fn(),
  generate: vi.fn(),
  prepare: vi.fn(),
  preview: vi.fn(),
  discovery: vi.fn(),
}));

vi.mock('../../services/db.js', () => ({
  prisma: {
    job: { findFirst: mocks.jobFindFirst },
    selectionChallenge: {
      findFirst: mocks.challengeFindFirst,
      findMany: mocks.challengeFindMany,
      create: mocks.challengeCreate,
    },
    selectionOwnerEvidence: { findMany: mocks.ownerEvidenceFindMany },
    selectionExperiment: { findMany: mocks.experimentFindMany },
  },
}));
vi.mock('../../middleware/auth.js', () => ({
  requireInternalAuth: (req: any, _res: any, next: any) => {
    req.user = { id: 'user-123' };
    next();
  },
}));
vi.mock('../../config.js', () => ({
  CONFIG: { openaiApiKey: 'test-key', openrouterApiKey: '', chatModel: 'gpt-test' },
}));
vi.mock('../../services/assetService.js', () => ({
  getPreviewReportForJob: mocks.preview,
  getDiscoveryDataForJob: mocks.discovery,
}));
vi.mock('../../services/selectionChallengeService.js', () => ({
  generateSelectionChallenge: mocks.generate,
  prepareSelectionChallengeInput: mocks.prepare,
}));

import { selectionChallengesRouter } from '../selectionChallenges.js';

const jobId = '11111111-1111-4111-8111-111111111111';
const idea = {
  idea_id: 'idea_signal',
  idea_revision: 2,
  solution_name: 'Signal Desk',
  description: 'Signal tool',
};
const assessment = {
  questionId: 'pain_is_observed',
  position: 'insufficient',
  summary: 'The packet does not directly answer this question.',
  subjectKeys: ['I1'],
  evidenceKeys: [],
  evidenceClass: 'inference',
};
const questions = ['pain_is_observed', 'urgency_is_behavioral', 'buyer_will_pay'].map(questionId => ({
  questionId,
  consensus: 'insufficient',
  skeptic: { ...assessment, questionId },
  auditor: { ...assessment, questionId },
}));
const artifact = {
  version: 1,
  inputFingerprint: 'f'.repeat(64),
  ideaId: idea.idea_id,
  ideaRevision: idea.idea_revision,
  ideaTitle: idea.solution_name,
  lens: 'demand',
  overall: 'insufficient_evidence',
  ideaSnapshot: { idea_id: idea.idea_id, idea_revision: idea.idea_revision, solution_name: idea.solution_name },
  subjectSnapshot: [{ key: 'I1', field: 'solution_name', value: idea.solution_name }],
  evidenceSnapshot: [],
  questions,
  skepticModel: 'deterministic-empty-evidence',
  auditorModel: 'deterministic-empty-evidence',
  promptVersion: 1,
  createdAt: '2026-07-16T00:00:00.000Z',
};
const row = {
  id: 'challenge-1',
  jobId,
  ideaId: idea.idea_id,
  ideaRevision: idea.idea_revision,
  lens: 'DEMAND',
  inputFingerprint: artifact.inputFingerprint,
  ideaSnapshot: artifact.ideaSnapshot,
  evidenceSnapshot: artifact.evidenceSnapshot,
  artifact,
  skepticModel: artifact.skepticModel,
  auditorModel: artifact.auditorModel,
  promptVersion: 1,
  createdAt: new Date(artifact.createdAt),
};

const app = express();
app.use(express.json());
app.use('/api/jobs', selectionChallengesRouter);

function job(overrides: Record<string, unknown> = {}) {
  return {
    id: jobId,
    status: 'AWAITING_SELECTION',
    solutionIdeas: [idea],
    ...overrides,
  };
}

describe('selection challenge owner API', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.jobFindFirst.mockResolvedValue(job());
    mocks.challengeFindFirst.mockResolvedValue(null);
    mocks.challengeFindMany.mockResolvedValue([]);
    mocks.ownerEvidenceFindMany.mockResolvedValue([]);
    mocks.experimentFindMany.mockResolvedValue([]);
    mocks.preview.mockResolvedValue(null);
    mocks.discovery.mockResolvedValue(null);
    mocks.prepare.mockReturnValue({
      ideaSnapshot: artifact.ideaSnapshot,
      subjectSnapshot: artifact.subjectSnapshot,
      evidenceSnapshot: artifact.evidenceSnapshot,
      inputFingerprint: artifact.inputFingerprint,
    });
    mocks.generate.mockResolvedValue(artifact);
    mocks.challengeCreate.mockResolvedValue(row);
  });

  it('includes active owner evidence in the current challenge fingerprint input', async () => {
    const ownerEvidence = [{
      id: '123e4567-e89b-42d3-a456-426614174000',
      jobId,
      ideaId: idea.idea_id,
      ideaRevision: idea.idea_revision,
      lens: 'DEMAND',
      kind: 'CUSTOMER_QUOTE',
      position: 'SUPPORTS',
      title: 'Founder interview',
      content: 'I would pay to stop doing this manually.',
      sourceUrl: null,
      observedAt: null,
      createdAt: new Date(),
      retractedAt: null,
    }];
    mocks.ownerEvidenceFindMany.mockResolvedValue(ownerEvidence);

    const response = await request(app)
      .post(`/api/jobs/${jobId}/selection-challenges`)
      .send({ ideaId: idea.idea_id, ideaRevision: 2, lens: 'demand' });

    expect(response.status).toBe(201);
    expect(mocks.prepare).toHaveBeenCalledWith(expect.objectContaining({ ownerEvidence }));
    expect(mocks.generate).toHaveBeenCalledWith(expect.objectContaining({ ownerEvidence }));
  });

  it('loads only immutable challenge-origin experiment conclusions into fingerprint input', async () => {
    const experimentResults = [{
      id: '623e4567-e89b-42d3-a456-426614174000',
      ideaId: idea.idea_id,
      ideaRevision: idea.idea_revision,
      originChallengeId: '523e4567-e89b-42d3-a456-426614174000',
      originChallenge: {
        id: '523e4567-e89b-42d3-a456-426614174000',
        ideaId: idea.idea_id,
        ideaRevision: idea.idea_revision,
        lens: 'DEMAND',
      },
      conclusion: {
        id: '723e4567-e89b-42d3-a456-426614174000',
        createdAt: new Date('2026-07-16T10:00:00.000Z'),
        snapshot: {},
      },
    }];
    mocks.experimentFindMany.mockResolvedValue(experimentResults);

    const response = await request(app)
      .post(`/api/jobs/${jobId}/selection-challenges`)
      .send({ ideaId: idea.idea_id, ideaRevision: 2, lens: 'demand' });

    expect(response.status).toBe(201);
    expect(mocks.experimentFindMany).toHaveBeenCalledWith(expect.objectContaining({
      where: {
        jobId,
        originChallengeId: { not: null },
        conclusion: { isNot: null },
      },
    }));
    expect(mocks.prepare).toHaveBeenCalledWith(expect.objectContaining({ experimentResults }));
    expect(mocks.generate).toHaveBeenCalledWith(expect.objectContaining({ experimentResults }));
  });

  it('rejects a stale or foreign idea revision before model work', async () => {
    const response = await request(app)
      .post(`/api/jobs/${jobId}/selection-challenges`)
      .send({ ideaId: idea.idea_id, ideaRevision: 3, lens: 'demand' });

    expect(response.status).toBe(409);
    expect(response.body.error).toContain('revision changed');
    expect(mocks.generate).not.toHaveBeenCalled();
  });

  it('persists one immutable completed artifact without mutating the Job', async () => {
    const response = await request(app)
      .post(`/api/jobs/${jobId}/selection-challenges`)
      .send({ ideaId: idea.idea_id, ideaRevision: 2, lens: 'demand' });

    expect(response.status).toBe(201);
    expect(mocks.generate).toHaveBeenCalledWith(expect.objectContaining({
      lens: 'demand',
      idea: expect.objectContaining({ idea_id: idea.idea_id, idea_revision: 2 }),
    }));
    expect(mocks.challengeCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        jobId,
        ideaId: idea.idea_id,
        ideaRevision: 2,
        lens: 'DEMAND',
        inputFingerprint: artifact.inputFingerprint,
        artifact,
      }),
    });
    expect(response.body.challenge.id).toBe('challenge-1');
  });

  it('returns an identical cached artifact without another model call', async () => {
    mocks.challengeFindFirst.mockResolvedValue(row);

    const response = await request(app)
      .post(`/api/jobs/${jobId}/selection-challenges`)
      .send({ ideaId: idea.idea_id, ideaRevision: 2, lens: 'demand' });

    expect(response.status).toBe(200);
    expect(response.body.cached).toBe(true);
    expect(mocks.generate).not.toHaveBeenCalled();
    expect(mocks.challengeCreate).not.toHaveBeenCalled();
  });

  it('does not persist a result if the evidence changes during model work', async () => {
    mocks.prepare
      .mockReturnValueOnce({
        ideaSnapshot: artifact.ideaSnapshot,
        subjectSnapshot: artifact.subjectSnapshot,
        evidenceSnapshot: [],
        inputFingerprint: artifact.inputFingerprint,
      })
      .mockReturnValueOnce({
        ideaSnapshot: artifact.ideaSnapshot,
        subjectSnapshot: artifact.subjectSnapshot,
        evidenceSnapshot: [{ key: 'S1' }],
        inputFingerprint: 'a'.repeat(64),
      });

    const response = await request(app)
      .post(`/api/jobs/${jobId}/selection-challenges`)
      .send({ ideaId: idea.idea_id, ideaRevision: 2, lens: 'demand' });

    expect(response.status).toBe(409);
    expect(response.body.error).toContain('evidence changed');
    expect(mocks.challengeCreate).not.toHaveBeenCalled();
  });

  it('returns only current-fingerprint artifacts and marks prior evidence stale', async () => {
    mocks.challengeFindMany.mockResolvedValue([
      row,
      { ...row, id: 'old-competition', lens: 'COMPETITION', inputFingerprint: '0'.repeat(64) },
    ]);

    const response = await request(app).get(`/api/jobs/${jobId}/selection-challenges`);

    expect(response.status).toBe(200);
    expect(response.body.challenges).toHaveLength(1);
    expect(response.body.challenges[0].id).toBe('challenge-1');
    expect(response.body.stale).toContainEqual({
      ideaId: idea.idea_id,
      ideaRevision: 2,
      lens: 'competition',
    });
  });

  it('marks only the origin-matching challenge stale after experiment evidence arrives', async () => {
    const competitionArtifact = {
      ...artifact,
      inputFingerprint: 'c'.repeat(64),
      lens: 'competition',
      questions: ['substitutes_are_weak', 'switching_barrier_is_surmountable', 'wedge_is_defensible']
        .map(questionId => ({
          questionId,
          consensus: 'insufficient',
          skeptic: { ...assessment, questionId },
          auditor: { ...assessment, questionId },
        })),
    };
    mocks.experimentFindMany.mockResolvedValue([{ id: 'experiment-result' }]);
    mocks.challengeFindMany.mockResolvedValue([
      row,
      {
        ...row,
        id: 'challenge-competition',
        lens: 'COMPETITION',
        inputFingerprint: competitionArtifact.inputFingerprint,
        artifact: competitionArtifact,
      },
    ]);
    mocks.prepare.mockImplementation(({ lens, experimentResults }) => ({
      ideaSnapshot: artifact.ideaSnapshot,
      subjectSnapshot: artifact.subjectSnapshot,
      evidenceSnapshot: [],
      inputFingerprint: lens === 'demand' && experimentResults.length
        ? 'a'.repeat(64)
        : lens === 'competition'
          ? competitionArtifact.inputFingerprint
          : artifact.inputFingerprint,
    }));

    const response = await request(app).get(`/api/jobs/${jobId}/selection-challenges`);

    expect(response.status).toBe(200);
    expect(response.body.challenges.map((challenge: { id: string }) => challenge.id))
      .toEqual(['challenge-competition']);
    expect(response.body.stale).toEqual([{
      ideaId: idea.idea_id,
      ideaRevision: 2,
      lens: 'demand',
    }]);
  });

  it('keeps challenge data owner-only', async () => {
    mocks.jobFindFirst.mockResolvedValue(null);

    const response = await request(app).get(`/api/jobs/${jobId}/selection-challenges`);

    expect(response.status).toBe(404);
    expect(mocks.challengeFindMany).not.toHaveBeenCalled();
  });
});
