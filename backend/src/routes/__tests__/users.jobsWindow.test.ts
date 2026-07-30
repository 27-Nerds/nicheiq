import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock prisma before importing the router
vi.mock('../../services/db.js', () => ({
  prisma: {
    user: {
      findUnique: vi.fn(),
    },
    job: {
      findMany: vi.fn(),
    },
  },
}));

// Mock auth middleware
vi.mock('../../middleware/auth.js', () => ({
  requireInternalAuth: (req: any, _res: any, next: any) => {
    req.user = req.user || { id: '11111111-1111-4111-8111-111111111111' };
    next();
  },
}));

// Mock job formatter — identity-ish so we can assert ids
vi.mock('../../utils/jobFormatter.js', () => ({
  formatJobResponse: vi.fn((job: any) => ({ id: job.id, status: job.status })),
}));

import { prisma } from '../../services/db.js';
import { usersRouter } from '../users.js';
import express from 'express';
import request from 'supertest';

const app = express();
app.use(express.json());
app.use('/api/users', usersRouter);

function job(id: string, status: string) {
  return { id, status, createdAt: new Date().toISOString() };
}

describe('GET /api/users/:userId/jobs — awaiting jobs never fall out of the window', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (prisma.user.findUnique as any).mockResolvedValue({ id: '11111111-1111-4111-8111-111111111111' });
  });

  it('merges awaiting-decision jobs missing from the recent-50 window', async () => {
    const recent = Array.from({ length: 50 }, (_, i) => job(`recent-${i}`, 'COMPLETED'));
    const awaiting = [
      job('recent-0', 'AWAITING_SELECTION'), // duplicate — already in window
      job('old-awaiting-1', 'AWAITING_SELECTION'),
      job('old-awaiting-2', 'AWAITING_GATE'),
    ];
    (prisma.job.findMany as any)
      .mockResolvedValueOnce(recent)
      .mockResolvedValueOnce(awaiting);

    const res = await request(app).get('/api/users/11111111-1111-4111-8111-111111111111/jobs');

    expect(res.status).toBe(200);
    const ids = res.body.jobs.map((j: any) => j.id);
    expect(ids).toHaveLength(52); // 50 recent + 2 unseen awaiting, dupe filtered
    expect(ids).toContain('old-awaiting-1');
    expect(ids).toContain('old-awaiting-2');
    expect(ids.filter((id: string) => id === 'recent-0')).toHaveLength(1);

    // Second query is the unconditional awaiting-status fetch
    const secondCall = (prisma.job.findMany as any).mock.calls[1][0];
    expect(secondCall.where.status).toEqual({ in: ['AWAITING_SELECTION', 'AWAITING_GATE'] });
    expect(secondCall.take).toBeUndefined();
    for (const [query] of (prisma.job.findMany as any).mock.calls) {
      expect(query.include.dispatches).toEqual({
        orderBy: { createdAt: 'desc' },
        take: 1,
        select: {
          id: true,
          kind: true,
          state: true,
          refundedAmount: true,
          refundTransaction: {
            select: { amount: true },
          },
        },
      });
    }
  });
});
