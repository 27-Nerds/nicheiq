import { beforeEach, describe, expect, it, vi } from 'vitest';
import express from 'express';
import request from 'supertest';

// These suites exercise route logic, not the decision-tools grant. The grant itself is
// covered in middleware/__tests__/featureAccess.test.ts.
vi.mock('../../middleware/featureAccess.js', () => ({
  requireDecisionToolsAccess: (_req: any, _res: any, next: any) => next(),
}));
import { createHash } from 'node:crypto';

const EXPECTED_OPERATION_ID = (() => {
  const raw = `founder-fit-reshape:${'f'.repeat(64)}:idea-parent:3`;
  return `ffr:${createHash('sha256').update(raw).digest('hex').slice(0, 60)}`;
})();

const mocks = vi.hoisted(() => ({
  jobFindFirst: vi.fn(),
  jobUpdate: vi.fn(),
  messageFindUnique: vi.fn(),
  messageFindMany: vi.fn(),
  messageCreate: vi.fn(),
  dispatchFindFirst: vi.fn(),
  parseCurrent: vi.fn(),
  generate: vi.fn(),
}));

vi.mock('../../config.js', () => ({ CONFIG: { openaiApiKey: 'test-key' } }));
vi.mock('../../services/db.js', () => ({
  prisma: {
    job: { findFirst: mocks.jobFindFirst, update: mocks.jobUpdate },
    chatMessage: {
      findUnique: mocks.messageFindUnique,
      findMany: mocks.messageFindMany,
      create: mocks.messageCreate,
    },
    jobDispatch: { findFirst: mocks.dispatchFindFirst },
  },
}));
vi.mock('../../services/founderFitService.js', () => ({
  parseCurrentFounderFitArtifact: mocks.parseCurrent,
}));
vi.mock('../../services/selectionFounderFitReshapeService.js', () => ({
  generateSelectionFounderFitReshape: mocks.generate,
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
const IDEA_ID = 'idea-parent';
const FINGERPRINT = 'f'.repeat(64);
const headers = { 'x-user-id': 'owner-1' };
const parent = {
  idea_id: IDEA_ID,
  idea_revision: 3,
  solution_name: 'Signal Desk',
  source_pain: 'Missed renewal signals',
};
const conflicts = [{
  dimension: 'time',
  status: 'conflict',
  summary: 'The current workflow exceeds the available weekly time.',
  profileFields: ['weeklyTime'],
  ideaFields: ['estimated_development_time'],
}];
const result = {
  ideaId: IDEA_ID,
  ideaRevision: 3,
  ideaTitle: 'Signal Desk',
  verdict: 'needs_reshape',
  dimensions: conflicts,
};
const artifact = {
  inputFingerprint: FINGERPRINT,
  results: [result],
};
const patch = {
  kind: 'idea_synthesis',
  operation: 'narrow',
  proposedTitle: 'Weekly Signal Brief',
  proposedBrief: 'A single weekly review for one renewal-risk workflow.',
  changeSummary: 'Removes continuous monitoring and secondary workflows.',
  rationale: 'The smaller cadence is designed around the recorded time conflict.',
  parents: [{
    ideaId: IDEA_ID,
    ideaRevision: 3,
    solutionName: 'Signal Desk',
    contribution: 'Keep the renewal signal interpretation.',
  }],
  evidence: {
    sourceAnchors: [{
      ideaId: IDEA_ID,
      ideaRevision: 3,
      candidateSnapshotSha256: 'a'.repeat(64),
    }],
    requiresValidation: ['Does not transfer automatically: continuous monitoring demand.'],
    founderFitRef: {
      inputFingerprint: FINGERPRINT,
      ideaId: IDEA_ID,
      ideaRevision: 3,
      verdict: 'needs_reshape',
      conflicts: conflicts.map(({ status: _status, ...conflict }) => conflict),
    },
  },
  newAssumptions: ['A weekly review is timely enough.'],
};

function job(overrides: Record<string, unknown> = {}) {
  return {
    id: JOB_ID,
    status: 'AWAITING_SELECTION',
    solutionIdeas: [parent],
    selectionDecisionProfile: { weeklyTime: 'under_10' },
    selectionFounderFit: artifact,
    selectionFinalDecision: null,
    ...overrides,
  };
}

const app = express();
app.use(express.json());
const { selectionFounderFitReshapeRouter } = await import('../selectionFounderFitReshape.js');
app.use('/api/jobs', selectionFounderFitReshapeRouter);

describe('founder-fit reshape proposals', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.jobFindFirst.mockResolvedValue(job());
    mocks.parseCurrent.mockReturnValue(artifact);
    mocks.messageFindUnique.mockResolvedValue(null);
    mocks.messageFindMany.mockResolvedValue([]);
    mocks.dispatchFindFirst.mockResolvedValue(null);
    mocks.messageCreate.mockImplementation(async ({ data }) => ({
      id: 'reshape-proposal-1',
      content: data.content,
      patchJson: data.patchJson,
      createdAt: new Date('2026-07-16T12:00:00.000Z'),
    }));
    mocks.jobUpdate.mockResolvedValue({});
    mocks.generate.mockResolvedValue({
      patch,
      content: 'One smaller, unevaluated variant.',
      model: 'test-model',
      promptVersion: 'founder-fit-reshape-v1',
      costUsd: 0.001,
      usage: { inputTokens: 100, outputTokens: 50, cacheWriteTokens: 0, cacheReadTokens: 0 },
    });
  });

  it('persists one proposal bound to the exact fit fingerprint and parent revision', async () => {
    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/founder-fit/${IDEA_ID}/3/reshape-proposal`)
      .set(headers)
      .send({});

    expect(response.status).toBe(201);
    expect(mocks.generate).toHaveBeenCalledWith(expect.objectContaining({
      artifact,
      parent: expect.objectContaining({ ideaId: IDEA_ID, ideaRevision: 3 }),
    }));
    expect(mocks.messageCreate).toHaveBeenCalledWith(expect.objectContaining({
      data: expect.objectContaining({
        origin: 'founder_fit_reshape',
        operationId: EXPECTED_OPERATION_ID,
        patchJson: patch,
      }),
    }));
    expect(response.body.settlement.state).toBe('ready');
  });

  it('returns the durable proposal on repeat without another model call', async () => {
    mocks.messageFindUnique.mockResolvedValue({
      id: 'reshape-proposal-1',
      content: 'Saved proposal',
      patchJson: patch,
      createdAt: new Date(),
    });

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/founder-fit/${IDEA_ID}/3/reshape-proposal`)
      .set(headers)
      .send({});

    expect(response.status).toBe(200);
    expect(response.body.cached).toBe(true);
    expect(mocks.generate).not.toHaveBeenCalled();
  });

  it('rejects stale profile/fit changes after generation without saving the proposal', async () => {
    mocks.jobFindFirst
      .mockResolvedValueOnce(job())
      .mockResolvedValueOnce(job({ selectionFounderFit: { inputFingerprint: 'e'.repeat(64) } }));
    mocks.parseCurrent
      .mockReturnValueOnce(artifact)
      .mockReturnValueOnce({ ...artifact, inputFingerprint: 'e'.repeat(64) });

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/founder-fit/${IDEA_ID}/3/reshape-proposal`)
      .set(headers)
      .send({});

    expect(response.status).toBe(409);
    expect(response.body.error).toContain('profile, fit analysis, or idea changed');
    expect(mocks.messageCreate).not.toHaveBeenCalled();
  });

  it('never reshapes a literal hard-constraint blocker', async () => {
    mocks.parseCurrent.mockReturnValue({
      ...artifact,
      results: [{
        ...result,
        dimensions: [{ ...conflicts[0], dimension: 'hard_constraints' }],
      }],
    });

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/founder-fit/${IDEA_ID}/3/reshape-proposal`)
      .set(headers)
      .send({});

    expect(response.status).toBe(409);
    expect(response.body.error).toContain('hard-constraint');
    expect(mocks.generate).not.toHaveBeenCalled();
  });

  it('does not expose another owner\'s job', async () => {
    mocks.jobFindFirst.mockResolvedValue(null);

    const response = await request(app)
      .get(`/api/jobs/${JOB_ID}/founder-fit/${IDEA_ID}/3/reshape-proposal`)
      .set(headers);

    expect(response.status).toBe(404);
  });
});
