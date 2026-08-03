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
const mockGlobalVoteCount = vi.fn();
const mockGlobalVoteUpsert = vi.fn();
const mockGlobalVoteGroupBy = vi.fn();
const mockGetJob = vi.fn();
const mockTransaction = vi.fn();
const mockQueryRaw = vi.fn();
const mockJobFindUnique = vi.fn();

vi.mock('../../services/db.js', () => ({
  prisma: {
    $transaction: (...args: any[]) => mockTransaction(...args),
    job: {
      findUnique: (...args: any[]) => mockJobFindUnique(...args),
    },
    discoveryShare: {
      findUnique: (...args: any[]) => mockShareFindUnique(...args),
      update: (...args: any[]) => mockShareUpdate(...args),
    },
    discoveryVote: {
      findUnique: (...args: any[]) => mockVoteFindUnique(...args),
      count: (...args: any[]) => mockGlobalVoteCount(...args),
      upsert: (...args: any[]) => mockGlobalVoteUpsert(...args),
      groupBy: (...args: any[]) => mockGlobalVoteGroupBy(...args),
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
  job: {
    id: jobId,
    niche: 'test niche',
    status: 'AWAITING_SELECTION',
    activeDispatchId: null,
    dispatches: [],
    solutionIdeas: solutions,
  },
});

const ownerJob = (solutions: Array<Record<string, unknown>>) => ({
  userId: 'owner-1',
  status: 'AWAITING_SELECTION',
  activeDispatchId: null,
  dispatches: [],
  solutionIdeas: solutions,
});

beforeEach(async () => {
  vi.clearAllMocks();
  mockShareUpdate.mockResolvedValue({});
  mockVoteFindUnique.mockResolvedValue(null);
  mockVoteCount.mockResolvedValue(0);
  mockVoteUpsert.mockResolvedValue({});
  mockVoteGroupBy.mockResolvedValue([]);
  mockVoteFindMany.mockResolvedValue([]);
  mockGlobalVoteCount.mockResolvedValue(0);
  mockGlobalVoteUpsert.mockResolvedValue({});
  mockGlobalVoteGroupBy.mockResolvedValue([]);
  mockGetJob.mockResolvedValue(null);
  mockQueryRaw.mockResolvedValue([{
    userId: 'owner-1',
    status: 'AWAITING_SELECTION',
    activeDispatchKind: null,
  }]);
  mockJobFindUnique.mockResolvedValue({ solutionIdeas: [] });
  mockTransaction.mockImplementation(async (callback: any) => callback({
    $queryRaw: (...args: any[]) => mockQueryRaw(...args),
    job: {
      findUnique: (...args: any[]) => mockJobFindUnique(...args),
    },
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
  }));

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

  it('serves the public dossier while an append-only seed is running', async () => {
    const activeShare = share([{ name: 'Seed-safe idea' }]);
    mockShareFindUnique.mockResolvedValue({
      ...activeShare,
      job: {
        ...activeShare.job,
        status: 'RUNNING',
        activeDispatchId: 'seed-dispatch',
        dispatches: [{ id: 'seed-dispatch', kind: 'SEED_IDEA' }],
      },
    });

    const response = await request(app).get(`/api/shared/discovery/${shareToken}`);

    expect(response.status).toBe(200);
  });

  it('rejects a stale active dossier after Deep Research starts', async () => {
    const activeShare = share([{ name: 'No longer public' }]);
    mockShareFindUnique.mockResolvedValue({
      ...activeShare,
      job: {
        ...activeShare.job,
        status: 'RUNNING_PHASE2',
        activeDispatchId: 'deep-dispatch',
        dispatches: [{ id: 'deep-dispatch', kind: 'DEEP_RESEARCH' }],
      },
    });

    const response = await request(app).get(`/api/shared/discovery/${shareToken}`);

    expect(response.status).toBe(404);
    expect(mockShareUpdate).not.toHaveBeenCalled();
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

  it('locks the Job before re-reading the current token and writing the vote', async () => {
    mockShareFindUnique.mockResolvedValue(share([
      { name: 'Chosen idea', idea_id: 'idea_chosen', idea_revision: 1 },
    ]));

    const response = await request(app)
      .post(`/api/shared/discovery/${shareToken}/vote`)
      .send({ solutionId: 'idea_chosen', viewerToken });

    expect(response.status).toBe(200);
    expect(mockTransaction).toHaveBeenCalledTimes(1);
    expect(mockShareFindUnique).toHaveBeenCalledTimes(2);
    expect(mockShareFindUnique.mock.calls[0][0]).toEqual({
      where: { shareToken },
      select: { jobId: true },
    });
    expect(mockShareFindUnique.mock.calls[1][0]).toEqual({
      where: { shareToken },
      include: { job: { select: { solutionIdeas: true } } },
    });
    expect(mockShareFindUnique.mock.invocationCallOrder[0])
      .toBeLessThan(mockQueryRaw.mock.invocationCallOrder[0]);
    expect(mockQueryRaw.mock.invocationCallOrder[0])
      .toBeLessThan(mockShareFindUnique.mock.invocationCallOrder[1]);
    expect(mockShareFindUnique.mock.invocationCallOrder[1])
      .toBeLessThan(mockVoteUpsert.mock.invocationCallOrder[0]);
    expect(mockVoteUpsert.mock.invocationCallOrder[0])
      .toBeLessThan(mockVoteGroupBy.mock.invocationCallOrder[0]);
    expect(mockGlobalVoteCount).not.toHaveBeenCalled();
    expect(mockGlobalVoteUpsert).not.toHaveBeenCalled();
    expect(mockGlobalVoteGroupBy).not.toHaveBeenCalled();
  });

  it('rejects an old token that is gone by the authoritative post-lock re-read', async () => {
    mockShareFindUnique
      .mockResolvedValueOnce({ jobId })
      .mockResolvedValueOnce(null);

    const response = await request(app)
      .post(`/api/shared/discovery/${shareToken}/vote`)
      .send({ solutionId: 'idea_chosen', viewerToken });

    expect(response.status).toBe(404);
    expect(mockQueryRaw).toHaveBeenCalledTimes(1);
    expect(mockShareFindUnique).toHaveBeenCalledTimes(2);
    expect(mockVoteUpsert).not.toHaveBeenCalled();
  });

  it('rejects a share disabled while the vote waited for the Job lock', async () => {
    mockShareFindUnique
      .mockResolvedValueOnce({ jobId })
      .mockResolvedValueOnce({
        ...share([{ name: 'Chosen idea', idea_id: 'idea_chosen', idea_revision: 1 }]),
        isActive: false,
      });

    const response = await request(app)
      .post(`/api/shared/discovery/${shareToken}/vote`)
      .send({ solutionId: 'idea_chosen', viewerToken });

    expect(response.status).toBe(404);
    expect(mockVoteUpsert).not.toHaveBeenCalled();
  });

  it('rejects a vote after Deep Research changed the locked Job status', async () => {
    mockShareFindUnique.mockResolvedValueOnce({ jobId });
    mockQueryRaw.mockResolvedValue([{
      userId: 'owner-1',
      status: 'QUEUED',
      activeDispatchKind: 'DEEP_RESEARCH',
    }]);

    const response = await request(app)
      .post(`/api/shared/discovery/${shareToken}/vote`)
      .send({ solutionId: 'idea_chosen', viewerToken });

    expect(response.status).toBe(404);
    expect(mockShareFindUnique).toHaveBeenCalledTimes(1);
    expect(mockVoteUpsert).not.toHaveBeenCalled();
  });

  it('accepts a vote while an append-only seed is running', async () => {
    mockShareFindUnique.mockResolvedValue(share([
      { name: 'Chosen idea', idea_id: 'idea_chosen', idea_revision: 1 },
    ]));
    mockQueryRaw.mockResolvedValue([{
      userId: 'owner-1',
      status: 'RUNNING',
      activeDispatchKind: 'SEED_IDEA',
    }]);

    const response = await request(app)
      .post(`/api/shared/discovery/${shareToken}/vote`)
      .send({ solutionId: 'idea_chosen', viewerToken });

    expect(response.status).toBe(200);
    expect(mockVoteUpsert).toHaveBeenCalledTimes(1);
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
    mockGlobalVoteGroupBy.mockResolvedValue([
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

  it('rejects public vote summaries after selection closes even if the share flag is stale', async () => {
    const activeShare = share([
      { name: 'Chosen idea', idea_id: 'idea_chosen', idea_revision: 1 },
    ]);
    mockShareFindUnique.mockResolvedValue({
      ...activeShare,
      job: {
        ...activeShare.job,
        status: 'COMPLETED',
      },
    });

    const response = await request(app).get(`/api/shared/discovery/${shareToken}/votes`);

    expect(response.status).toBe(404);
    expect(mockGlobalVoteGroupBy).not.toHaveBeenCalled();
  });
});

describe('authenticated owner collaborator rationales', () => {
  it('returns exact-ID rationales without viewer or IP identifiers', async () => {
    const solutions = [
      { name: 'Duplicate', idea_id: 'idea_first', idea_revision: 1 },
      { name: 'Duplicate', idea_id: 'idea_second', idea_revision: 1 },
    ];
    mockGetJob.mockResolvedValue(ownerJob(solutions));
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

  it('keeps historical votes available to the owner after the public link is disabled', async () => {
    const solutions = [
      { name: 'Chosen idea', idea_id: 'idea_chosen', idea_revision: 1 },
    ];
    mockGetJob.mockResolvedValue(ownerJob(solutions));
    mockShareFindUnique.mockResolvedValue({
      ...share(solutions),
      shareToken,
      isActive: false,
      viewCount: 6,
    });
    mockGlobalVoteGroupBy.mockResolvedValue([
      { solutionId: 'idea_chosen', solutionName: 'Chosen idea', _count: { id: 2 } },
    ]);
    mockVoteFindMany.mockResolvedValue([{
      solutionId: 'idea_chosen',
      solutionName: 'Chosen idea',
      comment: 'This fits the workflow.',
    }]);

    const response = await request(app).get(`/api/jobs/${jobId}/discovery-share`);

    expect(response.status).toBe(200);
    expect(response.body).toMatchObject({
      isShared: false,
      viewCount: 6,
      voteCount: 2,
      solutionVotesById: { idea_chosen: 2 },
      voteRationales: [{
        solutionId: 'idea_chosen',
        solutionName: 'Chosen idea',
        comment: 'This fits the workflow.',
      }],
    });
    expect(response.body).not.toHaveProperty('shareToken');
  });

  it('returns the preserved feedback record when the owner disables sharing', async () => {
    const solutions = [
      { name: 'Chosen idea', idea_id: 'idea_chosen', idea_revision: 1 },
    ];
    mockGetJob.mockResolvedValue(ownerJob(solutions));
    mockJobFindUnique.mockResolvedValue({ solutionIdeas: solutions });
    mockShareFindUnique.mockResolvedValue({
      ...share(solutions),
      shareToken,
      viewCount: 5,
    });
    mockVoteGroupBy.mockResolvedValue([
      { solutionId: 'idea_chosen', solutionName: 'Chosen idea', _count: { id: 1 } },
    ]);
    mockVoteFindMany.mockResolvedValue([{
      solutionId: 'idea_chosen',
      solutionName: 'Chosen idea',
      comment: 'Keep this feedback.',
    }]);

    const response = await request(app).delete(`/api/jobs/${jobId}/discovery-share`);

    expect(response.status).toBe(200);
    expect(response.body).toMatchObject({
      isShared: false,
      voteCount: 1,
      solutionVotesById: { idea_chosen: 1 },
      voteRationales: [{ comment: 'Keep this feedback.' }],
    });
    expect(response.body).not.toHaveProperty('shareToken');
    expect(mockTransaction).toHaveBeenCalledTimes(1);
    expect(mockShareUpdate).toHaveBeenCalledWith({
      where: { jobId },
      data: { isActive: false },
    });
    expect(mockQueryRaw.mock.invocationCallOrder[0])
      .toBeLessThan(mockJobFindUnique.mock.invocationCallOrder[0]);
    expect(mockQueryRaw.mock.invocationCallOrder[0])
      .toBeLessThan(mockShareFindUnique.mock.invocationCallOrder[0]);
    expect(mockShareFindUnique.mock.invocationCallOrder[0])
      .toBeLessThan(mockShareUpdate.mock.invocationCallOrder[0]);
  });
});
