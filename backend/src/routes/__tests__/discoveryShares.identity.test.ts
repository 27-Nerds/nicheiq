import express, { type Express } from 'express';
import request from 'supertest';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const shareToken = 'a'.repeat(22);
const viewerToken = '00000000-0000-4000-8000-000000000001';
const jobId = '00000000-0000-0000-0000-000000000001';

const mockShareFindUnique = vi.fn();
const mockShareUpdate = vi.fn();
const mockVoteFindUnique = vi.fn();
const mockVoteCount = vi.fn();
const mockVoteUpsert = vi.fn();
const mockVoteGroupBy = vi.fn();
const mockVoteFindMany = vi.fn();
const mockGetJob = vi.fn();

vi.mock('../../services/db.js', () => ({
  prisma: {
    discoveryShare: {
      findUnique: (...args: any[]) => mockShareFindUnique(...args),
      update: (...args: any[]) => mockShareUpdate(...args),
    },
    discoveryVote: {
      findUnique: (...args: any[]) => mockVoteFindUnique(...args),
      count: (...args: any[]) => mockVoteCount(...args),
      upsert: (...args: any[]) => mockVoteUpsert(...args),
      groupBy: (...args: any[]) => mockVoteGroupBy(...args),
      findMany: (...args: any[]) => mockVoteFindMany(...args),
    },
    jobProgress: { findMany: vi.fn().mockResolvedValue([]) },
  },
}));

vi.mock('../../services/assetService.js', () => ({
  getDiscoveryDataForJob: vi.fn().mockResolvedValue(null),
  getPreviewReportForJob: vi.fn().mockResolvedValue(null),
}));

vi.mock('../../services/jobService.js', () => ({ getJob: (...args: any[]) => mockGetJob(...args) }));
vi.mock('../../middleware/auth.js', () => ({
  requireInternalAuth: (_req: any, _res: any, next: any) => next(),
  verifyOwnership: () => true,
  AuthenticatedRequest: {},
}));
vi.mock('../../config.js', () => ({
  CONFIG: { nodeEnv: 'test', ipHashSalt: 'test-salt' },
}));
vi.mock('express-rate-limit', () => ({
  default: () => (_req: any, _res: any, next: any) => next(),
}));

let app: Express;

const share = (solutions: Array<Record<string, unknown>>) => ({
  id: 'share-1',
  jobId,
  isActive: true,
  allowIndexing: false,
  job: { id: jobId, niche: 'test niche', status: 'AWAITING_SELECTION', solutionIdeas: solutions },
});

beforeEach(async () => {
  vi.clearAllMocks();
  mockShareUpdate.mockResolvedValue({});
  mockVoteFindUnique.mockResolvedValue(null);
  mockVoteCount.mockResolvedValue(0);
  mockVoteUpsert.mockResolvedValue({});
  mockVoteGroupBy.mockResolvedValue([]);
  mockVoteFindMany.mockResolvedValue([]);
  mockGetJob.mockResolvedValue(null);

  app = express();
  app.use(express.json());
  const { discoverySharesRouter, publicDiscoveryShareRouter } = await import('../discoveryShares.js');
  app.use('/api/jobs', discoverySharesRouter);
  app.use('/api/shared/discovery', publicDiscoveryShareRouter);
});

describe('public discovery stable idea identity', () => {
  it('rejects the public URL as soon as its share is inactive', async () => {
    mockShareFindUnique.mockResolvedValue({
      ...share([{ name: 'Legacy idea' }]),
      isActive: false,
    });

    const response = await request(app).get(`/api/shared/discovery/${shareToken}`);

    expect(response.status).toBe(404);
    expect(response.body).toEqual({ error: 'Not found' });
  });

  it('backfills stable IDs in shared discovery responses', async () => {
    mockShareFindUnique.mockResolvedValue(share([{ name: 'Legacy idea' }]));

    const response = await request(app).get(`/api/shared/discovery/${shareToken}`);

    expect(response.status).toBe(200);
    expect(response.body.solutions).toEqual([{
      name: 'Legacy idea',
      idea_id: expect.stringMatching(/^idea_[a-f0-9]{32}$/),
      idea_revision: 1,
    }]);
  });

  it('accepts an ID-only vote and stores the canonical compatibility name', async () => {
    mockShareFindUnique.mockResolvedValue(share([
      { name: 'First idea', idea_id: 'idea_first', idea_revision: 1 },
      { name: 'Second idea', idea_id: 'idea_second', idea_revision: 1 },
    ]));
    mockVoteGroupBy.mockResolvedValue([
      { solutionId: 'idea_second', solutionName: 'Second idea', _count: { id: 1 } },
    ]);

    const response = await request(app)
      .post(`/api/shared/discovery/${shareToken}/vote`)
      .send({ solutionId: 'idea_second', viewerToken });

    expect(response.status).toBe(200);
    expect(mockVoteUpsert).toHaveBeenCalledWith(expect.objectContaining({
      create: expect.objectContaining({ solutionId: 'idea_second', solutionName: 'Second idea' }),
      update: expect.objectContaining({ solutionId: 'idea_second', solutionName: 'Second idea' }),
    }));
    expect(response.body.solutionVotesById).toEqual({ idea_second: 1 });
  });

  it('accepts natural punctuation in a rationale and trims it before storage', async () => {
    mockShareFindUnique.mockResolvedValue(share([
      { name: 'Chosen idea', idea_id: 'idea_chosen', idea_revision: 1 },
    ]));

    const response = await request(app)
      .post(`/api/shared/discovery/${shareToken}/vote`)
      .send({
        solutionId: 'idea_chosen',
        viewerToken,
        comment: `  I'd pay $12/month & call it "useful".  `,
      });

    expect(response.status).toBe(200);
    expect(mockVoteUpsert).toHaveBeenCalledWith(expect.objectContaining({
      create: expect.objectContaining({ comment: `I'd pay $12/month & call it "useful".` }),
    }));
  });

  it('preserves an existing rationale when the viewer changes only their vote', async () => {
    mockShareFindUnique.mockResolvedValue(share([
      { name: 'First idea', idea_id: 'idea_first', idea_revision: 1 },
      { name: 'Second idea', idea_id: 'idea_second', idea_revision: 1 },
    ]));
    mockVoteFindUnique.mockResolvedValue({ id: 'vote-1', comment: 'Keep this note' });

    const response = await request(app)
      .post(`/api/shared/discovery/${shareToken}/vote`)
      .send({ solutionId: 'idea_second', viewerToken });

    expect(response.status).toBe(200);
    const update = mockVoteUpsert.mock.calls[0][0].update;
    expect(update).toMatchObject({ solutionId: 'idea_second', solutionName: 'Second idea' });
    expect(update).not.toHaveProperty('comment');
  });

  it('uses the supplied ID when duplicate ideas share the same name', async () => {
    mockShareFindUnique.mockResolvedValue(share([
      { name: 'Duplicate', idea_id: 'idea_first', idea_revision: 1 },
      { name: 'Duplicate', idea_id: 'idea_second', idea_revision: 1 },
    ]));

    const response = await request(app)
      .post(`/api/shared/discovery/${shareToken}/vote`)
      .send({ solutionId: 'idea_second', solutionName: 'Duplicate', viewerToken });

    expect(response.status).toBe(200);
    expect(mockVoteUpsert).toHaveBeenCalledWith(expect.objectContaining({
      create: expect.objectContaining({ solutionId: 'idea_second' }),
    }));
  });

  it('rejects ambiguous legacy name-only votes', async () => {
    mockShareFindUnique.mockResolvedValue(share([
      { name: 'Duplicate', idea_id: 'idea_first', idea_revision: 1 },
      { name: 'Duplicate', idea_id: 'idea_second', idea_revision: 1 },
    ]));

    const response = await request(app)
      .post(`/api/shared/discovery/${shareToken}/vote`)
      .send({ solutionName: 'Duplicate', viewerToken });

    expect(response.status).toBe(400);
    expect(response.body.error).toContain('ambiguous');
    expect(mockVoteUpsert).not.toHaveBeenCalled();
  });

  it('keeps accepting legacy name-only votes', async () => {
    mockShareFindUnique.mockResolvedValue(share([
      { name: 'Legacy idea', idea_id: 'idea_legacy', idea_revision: 1 },
    ]));

    const response = await request(app)
      .post(`/api/shared/discovery/${shareToken}/vote`)
      .send({ solutionName: 'Legacy idea', viewerToken });

    expect(response.status).toBe(200);
    expect(mockVoteUpsert).toHaveBeenCalledWith(expect.objectContaining({
      create: expect.objectContaining({ solutionName: 'Legacy idea' }),
    }));
  });

  it('rejects solution ID and name values that identify different ideas', async () => {
    mockShareFindUnique.mockResolvedValue(share([
      { name: 'First idea', idea_id: 'idea_first', idea_revision: 1 },
      { name: 'Second idea', idea_id: 'idea_second', idea_revision: 1 },
    ]));

    const response = await request(app)
      .post(`/api/shared/discovery/${shareToken}/vote`)
      .send({ solutionId: 'idea_first', solutionName: 'Second idea', viewerToken });

    expect(response.status).toBe(400);
    expect(response.body.error).toContain('different ideas');
    expect(mockVoteUpsert).not.toHaveBeenCalled();
  });

  it('returns the viewer vote with its stable ID', async () => {
    mockShareFindUnique.mockResolvedValue(share([
      { name: 'Chosen idea', idea_id: 'idea_chosen', idea_revision: 1 },
    ]));
    mockVoteFindUnique.mockResolvedValue({ solutionId: 'idea_chosen', solutionName: 'Chosen idea', comment: null });

    const response = await request(app)
      .get(`/api/shared/discovery/${shareToken}/votes?viewerToken=${viewerToken}`);

    expect(response.status).toBe(200);
    expect(response.body.viewerVote).toEqual({
      solutionId: 'idea_chosen',
      solutionName: 'Chosen idea',
      comment: null,
    });
  });

  it('keeps duplicate-name vote counts separate by stored ID', async () => {
    mockShareFindUnique.mockResolvedValue(share([
      { name: 'Duplicate', idea_id: 'idea_first', idea_revision: 1 },
      { name: 'Duplicate', idea_id: 'idea_second', idea_revision: 1 },
    ]));
    mockVoteGroupBy.mockResolvedValue([
      { solutionId: 'idea_first', solutionName: 'Duplicate', _count: { id: 2 } },
      { solutionId: 'idea_second', solutionName: 'Duplicate', _count: { id: 3 } },
    ]);

    const response = await request(app)
      .get(`/api/shared/discovery/${shareToken}/votes`);

    expect(response.status).toBe(200);
    expect(response.body).toMatchObject({
      totalVotes: 5,
      solutionVotes: { Duplicate: 5 },
      solutionVotesById: { idea_first: 2, idea_second: 3 },
    });
    expect(response.body).not.toHaveProperty('voteRationales');
  });
});

describe('authenticated owner collaborator rationales', () => {
  it('returns exact-ID rationales without viewer or IP identifiers', async () => {
    const solutions = [
      { name: 'Duplicate', idea_id: 'idea_first', idea_revision: 1 },
      { name: 'Duplicate', idea_id: 'idea_second', idea_revision: 1 },
    ];
    mockGetJob.mockResolvedValue({ userId: 'owner-1', solutionIdeas: solutions });
    mockShareFindUnique.mockResolvedValue({
      ...share(solutions),
      shareToken,
      viewCount: 4,
    });
    mockVoteFindMany.mockResolvedValue([
      {
        solutionId: 'idea_second',
        solutionName: 'Duplicate',
        comment: '  The second version fits my workflow.  ',
        viewerToken: 'must-not-leak',
        ipHash: 'must-not-leak',
      },
    ]);

    const response = await request(app).get(`/api/jobs/${jobId}/discovery-share`);

    expect(response.status).toBe(200);
    expect(response.body.voteRationales).toEqual([{
      solutionId: 'idea_second',
      solutionName: 'Duplicate',
      comment: 'The second version fits my workflow.',
    }]);
    expect(JSON.stringify(response.body)).not.toContain('must-not-leak');
    expect(mockVoteFindMany).toHaveBeenCalledWith(expect.objectContaining({
      select: { solutionId: true, solutionName: true, comment: true },
    }));
  });
});
