import { beforeEach, describe, expect, it, vi } from 'vitest';
import express from 'express';
import request from 'supertest';

// These suites exercise route logic, not the decision-tools grant. The grant itself is
// covered in middleware/__tests__/featureAccess.test.ts.
vi.mock('../../middleware/featureAccess.js', () => ({
  requireDecisionToolsAccess: (_req: any, _res: any, next: any) => next(),
}));

const mocks = vi.hoisted(() => ({
  findFirst: vi.fn(),
  updateMany: vi.fn(),
  generate: vi.fn(),
  parseCurrent: vi.fn(),
}));

vi.mock('../../services/db.js', () => ({
  prisma: {
    job: {
      findFirst: mocks.findFirst,
      updateMany: mocks.updateMany,
    },
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
vi.mock('../../services/founderFitService.js', () => ({
  founderFitFingerprint: () => 'f'.repeat(64),
  founderFitIdeaSnapshot: (idea: any) => ({
    idea_id: idea.idea_id,
    idea_revision: idea.idea_revision,
    solution_name: idea.solution_name,
  }),
  generateFounderFitArtifact: mocks.generate,
  parseCurrentFounderFitArtifact: mocks.parseCurrent,
}));

import { founderFitRouter } from '../founderFit.js';

const jobId = '11111111-1111-4111-8111-111111111111';
const updatedAt = new Date('2026-07-16T00:00:00.000Z');
const profile = {
  preset: 'solo_bootstrap',
  weeklyTime: 'under_10',
  budget: 'under_1k',
  team: 'solo',
  revenueHorizon: '90_days',
  distributionAdvantages: ['seo'],
  strengths: 'Writing',
  hardConstraints: '',
};
const idea = {
  idea_id: 'idea_signal',
  idea_revision: 2,
  solution_name: 'Signal Desk',
  description: 'Signal tool',
  value_proposition: 'Find demand',
};
const artifact = {
  version: 1,
  inputFingerprint: 'f'.repeat(64),
  profileSnapshot: profile,
  ideaSnapshots: [{ idea_id: idea.idea_id, idea_revision: idea.idea_revision }],
  model: 'gpt-test',
  createdAt: '2026-07-16T00:00:00.000Z',
  results: [],
};

const app = express();
app.use(express.json());
app.use('/api/jobs', founderFitRouter);

function job(overrides: Record<string, unknown> = {}) {
  return {
    id: jobId,
    status: 'AWAITING_SELECTION',
    solutionIdeas: [idea],
    selectionDecisionProfile: profile,
    selectionFounderFit: null,
    updatedAt,
    ...overrides,
  };
}

describe('founder fit owner API', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.updateMany.mockResolvedValue({ count: 1 });
    mocks.generate.mockResolvedValue(artifact);
    mocks.parseCurrent.mockReturnValue(null);
  });

  it('requires a saved founder profile before using the specialist', async () => {
    mocks.findFirst.mockResolvedValue(job({ selectionDecisionProfile: null }));

    const response = await request(app)
      .post(`/api/jobs/${jobId}/founder-fit`)
      .send({ ideas: [{ ideaId: idea.idea_id, ideaRevision: 2 }] });

    expect(response.status).toBe(409);
    expect(response.body.error).toContain('Save your decision context');
    expect(mocks.generate).not.toHaveBeenCalled();
  });

  it('rejects stale or foreign idea revisions before model work', async () => {
    mocks.findFirst.mockResolvedValue(job());

    const response = await request(app)
      .post(`/api/jobs/${jobId}/founder-fit`)
      .send({ ideas: [{ ideaId: idea.idea_id, ideaRevision: 3 }] });

    expect(response.status).toBe(409);
    expect(response.body.error).toContain('idea revisions changed');
    expect(mocks.generate).not.toHaveBeenCalled();
  });

  it('persists only the generated artifact with an optimistic job guard', async () => {
    mocks.findFirst.mockResolvedValue(job());

    const response = await request(app)
      .post(`/api/jobs/${jobId}/founder-fit`)
      .send({ ideas: [{ ideaId: idea.idea_id, ideaRevision: 2 }] });

    expect(response.status).toBe(201);
    expect(mocks.generate).toHaveBeenCalledWith(profile, [expect.objectContaining({ idea_id: idea.idea_id })]);
    expect(mocks.updateMany).toHaveBeenCalledWith(expect.objectContaining({
      where: {
        id: jobId,
        userId: 'user-123',
        status: 'AWAITING_SELECTION',
        updatedAt,
      },
      data: { selectionFounderFit: artifact },
    }));
    expect(response.body.analysis).toEqual(artifact);
  });

  it('reuses an identical persisted analysis without another model call', async () => {
    mocks.findFirst.mockResolvedValue(job({ selectionFounderFit: artifact }));
    mocks.parseCurrent.mockReturnValue(artifact);

    const response = await request(app)
      .post(`/api/jobs/${jobId}/founder-fit`)
      .send({ ideas: [{ ideaId: idea.idea_id, ideaRevision: 2 }] });

    expect(response.status).toBe(200);
    expect(response.body.cached).toBe(true);
    expect(mocks.generate).not.toHaveBeenCalled();
    expect(mocks.updateMany).not.toHaveBeenCalled();
  });

  it('marks a stored artifact stale when its captured profile or ideas no longer match', async () => {
    mocks.findFirst.mockResolvedValue(job({ selectionFounderFit: artifact }));

    const response = await request(app).get(`/api/jobs/${jobId}/founder-fit`);

    expect(response.status).toBe(200);
    expect(response.body).toEqual({ analysis: null, stale: true });
  });
});
