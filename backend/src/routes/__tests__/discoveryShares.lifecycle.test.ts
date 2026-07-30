import { beforeEach, describe, expect, it, vi } from 'vitest';
import express, { type Express } from 'express';
import request from 'supertest';

const jobId = '550e8400-e29b-41d4-a716-446655440000';
const userId = 'user-123';
const authHeaders = { 'x-user-id': userId };

const mockTransaction = vi.fn();
const mockQueryRaw = vi.fn();
const mockShareFindUnique = vi.fn();
const mockShareCreate = vi.fn();
const mockShareUpdate = vi.fn();
const mockVoteCount = vi.fn();
const mockVoteDeleteMany = vi.fn();

vi.mock('../../services/db.js', () => ({
  prisma: {
    $transaction: (...args: any[]) => mockTransaction(...args),
    discoveryShare: {
      findUnique: vi.fn(),
      update: vi.fn(),
    },
    discoveryVote: {
      count: vi.fn(),
      groupBy: vi.fn(),
      findMany: vi.fn(),
    },
    jobProgress: { findMany: vi.fn() },
  },
}));

vi.mock('../../services/jobService.js', () => ({
  getJob: vi.fn(),
}));

vi.mock('../../services/assetService.js', () => ({
  getDiscoveryDataForJob: vi.fn(),
  getPreviewReportForJob: vi.fn(),
}));

vi.mock('../../middleware/auth.js', () => ({
  requireInternalAuth: (req: any, res: any, next: any) => {
    const requestUserId = req.headers['x-user-id'];
    if (!requestUserId) return res.status(401).json({ error: 'Unauthorized' });
    req.user = { id: requestUserId };
    next();
  },
  verifyOwnership: (req: any, resourceUserId: string | null | undefined) =>
    req.user?.id === resourceUserId,
  AuthenticatedRequest: {},
}));

vi.mock('../../config.js', () => ({
  CONFIG: { nodeEnv: 'test', ipHashSalt: 'test-salt' },
}));

vi.mock('express-rate-limit', () => ({
  default: () => (_req: any, _res: any, next: any) => next(),
}));

const activeShare = {
  id: 'share-1',
  jobId,
  userId,
  shareToken: 'a'.repeat(22),
  isActive: true,
  viewCount: 3,
};

let app: Express;

beforeEach(async () => {
  vi.clearAllMocks();
  mockQueryRaw.mockResolvedValue([{ userId, status: 'AWAITING_SELECTION' }]);
  mockShareFindUnique.mockResolvedValue(null);
  mockShareCreate.mockResolvedValue(activeShare);
  mockShareUpdate.mockResolvedValue(activeShare);
  mockVoteCount.mockResolvedValue(0);
  mockVoteDeleteMany.mockResolvedValue({ count: 0 });
  mockTransaction.mockImplementation(async (callback: any) => callback({
    $queryRaw: (...args: any[]) => mockQueryRaw(...args),
    discoveryShare: {
      findUnique: (...args: any[]) => mockShareFindUnique(...args),
      create: (...args: any[]) => mockShareCreate(...args),
      update: (...args: any[]) => mockShareUpdate(...args),
    },
    discoveryVote: {
      count: (...args: any[]) => mockVoteCount(...args),
      deleteMany: (...args: any[]) => mockVoteDeleteMany(...args),
    },
  }));

  app = express();
  app.use(express.json());
  const { discoverySharesRouter } = await import('../discoveryShares.js');
  app.use('/api/jobs', discoverySharesRouter);
});

describe('discovery share lifecycle mutations', () => {
  it('locks the Job before enabling a new share', async () => {
    const response = await request(app)
      .post(`/api/jobs/${jobId}/discovery-share`)
      .set(authHeaders);

    expect(response.status).toBe(200);
    expect(response.body).toMatchObject({
      isShared: true,
      shareToken: activeShare.shareToken,
      voteCount: 0,
    });
    expect(mockQueryRaw).toHaveBeenCalledTimes(1);
    expect(mockShareCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        jobId,
        userId,
        isActive: true,
      }),
    });
    expect(mockQueryRaw.mock.invocationCallOrder[0])
      .toBeLessThan(mockShareCreate.mock.invocationCallOrder[0]);
  });

  it('rechecks status after the Job lock and cannot reactivate after Deep Research queues', async () => {
    mockQueryRaw.mockResolvedValue([{ userId, status: 'QUEUED' }]);

    const response = await request(app)
      .post(`/api/jobs/${jobId}/discovery-share`)
      .set(authHeaders);

    expect(response.status).toBe(400);
    expect(response.body.error).toContain('awaiting selection');
    expect(mockShareFindUnique).not.toHaveBeenCalled();
    expect(mockShareCreate).not.toHaveBeenCalled();
    expect(mockShareUpdate).not.toHaveBeenCalled();
  });

  it('checks ownership from the locked Job row', async () => {
    mockQueryRaw.mockResolvedValue([{ userId: 'another-user', status: 'AWAITING_SELECTION' }]);

    const response = await request(app)
      .post(`/api/jobs/${jobId}/discovery-share`)
      .set(authHeaders);

    expect(response.status).toBe(403);
    expect(mockShareCreate).not.toHaveBeenCalled();
  });

  it('regenerates the token and clears votes in one Job-locked transaction', async () => {
    const regeneratedShare = {
      ...activeShare,
      shareToken: 'b'.repeat(22),
      viewCount: 0,
    };
    mockShareFindUnique.mockResolvedValue(activeShare);
    mockShareUpdate.mockResolvedValue(regeneratedShare);
    mockVoteDeleteMany.mockResolvedValue({ count: 4 });

    const response = await request(app)
      .post(`/api/jobs/${jobId}/discovery-share/regenerate`)
      .set(authHeaders);

    expect(response.status).toBe(200);
    expect(response.body).toEqual({
      isShared: true,
      shareToken: regeneratedShare.shareToken,
      viewCount: 0,
      voteCount: 0,
    });
    expect(mockVoteDeleteMany).toHaveBeenCalledWith({ where: { shareId: activeShare.id } });
    expect(mockShareUpdate).toHaveBeenCalledWith({
      where: { jobId },
      data: {
        shareToken: expect.stringMatching(/^[A-Za-z0-9_-]{22}$/),
        viewCount: 0,
        lastViewedAt: null,
        isActive: true,
      },
    });
    expect(mockQueryRaw.mock.invocationCallOrder[0])
      .toBeLessThan(mockVoteDeleteMany.mock.invocationCallOrder[0]);
    expect(mockVoteDeleteMany.mock.invocationCallOrder[0])
      .toBeLessThan(mockShareUpdate.mock.invocationCallOrder[0]);
    expect(mockTransaction).toHaveBeenCalledTimes(1);
  });

  it('does not regenerate or clear votes after Deep Research queues', async () => {
    mockQueryRaw.mockResolvedValue([{ userId, status: 'QUEUED' }]);
    mockShareFindUnique.mockResolvedValue(activeShare);

    const response = await request(app)
      .post(`/api/jobs/${jobId}/discovery-share/regenerate`)
      .set(authHeaders);

    expect(response.status).toBe(400);
    expect(mockShareFindUnique).not.toHaveBeenCalled();
    expect(mockVoteDeleteMany).not.toHaveBeenCalled();
    expect(mockShareUpdate).not.toHaveBeenCalled();
  });

  it('fails the whole token regeneration when its share update fails', async () => {
    mockShareFindUnique.mockResolvedValue(activeShare);
    mockVoteDeleteMany.mockResolvedValue({ count: 2 });
    mockShareUpdate.mockRejectedValue(new Error('database unavailable'));

    const response = await request(app)
      .post(`/api/jobs/${jobId}/discovery-share/regenerate`)
      .set(authHeaders);

    expect(response.status).toBe(500);
    expect(mockVoteDeleteMany).toHaveBeenCalledTimes(1);
    expect(mockShareUpdate).toHaveBeenCalledTimes(1);
  });
});
