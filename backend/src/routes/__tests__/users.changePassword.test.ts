import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Request, Response } from 'express';
import bcrypt from 'bcryptjs';

// Mock bcrypt
vi.mock('bcryptjs', () => ({
  default: {
    compare: vi.fn(),
    hash: vi.fn(),
  },
}));

// Mock prisma before importing the router
vi.mock('../../services/db.js', () => ({
  prisma: {
    user: {
      findUnique: vi.fn(),
      update: vi.fn(),
    },
    notificationPreferences: {
      findUnique: vi.fn(),
      upsert: vi.fn(),
    },
  },
}));

// Mock auth middleware
vi.mock('../../middleware/auth.js', () => ({
  requireInternalAuth: (req: any, _res: any, next: any) => {
    req.user = req.user || { id: 'user-123' };
    next();
  },
}));

// Mock job formatter
vi.mock('../../utils/jobFormatter.js', () => ({
  formatJobResponse: vi.fn(),
}));

import { prisma } from '../../services/db.js';

// Helper to create mock request/response
function createMockReqRes(overrides: {
  params?: Record<string, string>;
  body?: Record<string, unknown>;
  user?: { id: string };
}) {
  const req = {
    params: overrides.params || {},
    body: overrides.body || {},
    user: overrides.user || { id: 'user-123' },
  } as unknown as Request & { user: { id: string } };

  const res = {
    status: vi.fn().mockReturnThis(),
    json: vi.fn().mockReturnThis(),
  } as unknown as Response;

  return { req, res };
}

// Helper to get route handler
async function getChangePasswordHandler() {
  const { usersRouter } = await import('../users.js');
  const handler = (usersRouter as any).stack.find(
    (layer: any) => layer.route?.path === '/:userId/change-password' && layer.route?.methods?.post
  )?.route?.stack?.[1]?.handle;
  return handler;
}

describe('POST /api/users/:userId/change-password', () => {
  const validUserId = '11111111-1111-1111-1111-111111111111';

  beforeEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
  });

  it('returns 400 for invalid UUID format', async () => {
    const handler = await getChangePasswordHandler();
    const { req, res } = createMockReqRes({
      params: { userId: 'invalid-uuid' },
      body: { currentPassword: 'old123456', newPassword: 'new123456' },
    });

    if (handler) {
      await handler(req, res);
      expect(res.status).toHaveBeenCalledWith(400);
      expect(res.json).toHaveBeenCalledWith({ error: 'Invalid user ID format' });
    }
  });

  it('returns 403 when user tries to change another user password', async () => {
    const handler = await getChangePasswordHandler();
    const { req, res } = createMockReqRes({
      params: { userId: validUserId },
      user: { id: 'different-user-id' },
      body: { currentPassword: 'old123456', newPassword: 'new123456' },
    });

    if (handler) {
      await handler(req, res);
      expect(res.status).toHaveBeenCalledWith(403);
      expect(res.json).toHaveBeenCalledWith({ error: 'Not authorized to change this password' });
    }
  });

  it('returns 400 when current password is missing', async () => {
    const handler = await getChangePasswordHandler();
    const { req, res } = createMockReqRes({
      params: { userId: validUserId },
      user: { id: validUserId },
      body: { newPassword: 'new123456' },
    });

    if (handler) {
      await handler(req, res);
      expect(res.status).toHaveBeenCalledWith(400);
      expect(res.json).toHaveBeenCalledWith(
        expect.objectContaining({ error: 'Validation error' })
      );
    }
  });

  it('returns 400 when new password is too short', async () => {
    const handler = await getChangePasswordHandler();
    const { req, res } = createMockReqRes({
      params: { userId: validUserId },
      user: { id: validUserId },
      body: { currentPassword: 'old123456', newPassword: 'short' },
    });

    if (handler) {
      await handler(req, res);
      expect(res.status).toHaveBeenCalledWith(400);
      expect(res.json).toHaveBeenCalledWith(
        expect.objectContaining({ error: 'Validation error' })
      );
    }
  });

  it('returns 404 when user not found', async () => {
    vi.mocked(prisma.user.findUnique).mockResolvedValue(null);

    const handler = await getChangePasswordHandler();
    const { req, res } = createMockReqRes({
      params: { userId: validUserId },
      user: { id: validUserId },
      body: { currentPassword: 'old123456', newPassword: 'new123456' },
    });

    if (handler) {
      await handler(req, res);
      expect(res.status).toHaveBeenCalledWith(404);
      expect(res.json).toHaveBeenCalledWith({ error: 'User not found' });
    }
  });

  it('returns 400 for OAuth user without password', async () => {
    vi.mocked(prisma.user.findUnique).mockResolvedValue({
      passwordHash: null, // OAuth user - no password
    } as any);

    const handler = await getChangePasswordHandler();
    const { req, res } = createMockReqRes({
      params: { userId: validUserId },
      user: { id: validUserId },
      body: { currentPassword: 'old123456', newPassword: 'new123456' },
    });

    if (handler) {
      await handler(req, res);
      expect(res.status).toHaveBeenCalledWith(400);
      expect(res.json).toHaveBeenCalledWith({
        error: 'Account uses OAuth login. Password cannot be changed.',
      });
    }
  });

  it('returns 401 when current password is incorrect', async () => {
    vi.mocked(prisma.user.findUnique).mockResolvedValue({
      passwordHash: 'hashed-old-password',
    } as any);
    vi.mocked(bcrypt.compare).mockResolvedValue(false as never);

    const handler = await getChangePasswordHandler();
    const { req, res } = createMockReqRes({
      params: { userId: validUserId },
      user: { id: validUserId },
      body: { currentPassword: 'wrong-password', newPassword: 'new123456' },
    });

    if (handler) {
      await handler(req, res);
      expect(bcrypt.compare).toHaveBeenCalledWith('wrong-password', 'hashed-old-password');
      expect(res.status).toHaveBeenCalledWith(401);
      expect(res.json).toHaveBeenCalledWith({ error: 'Current password is incorrect' });
    }
  });

  it('successfully changes password', async () => {
    vi.mocked(prisma.user.findUnique).mockResolvedValue({
      passwordHash: 'hashed-old-password',
    } as any);
    vi.mocked(bcrypt.compare).mockResolvedValue(true as never);
    vi.mocked(bcrypt.hash).mockResolvedValue('hashed-new-password' as never);
    vi.mocked(prisma.user.update).mockResolvedValue({} as any);

    const handler = await getChangePasswordHandler();
    const { req, res } = createMockReqRes({
      params: { userId: validUserId },
      user: { id: validUserId },
      body: { currentPassword: 'old123456', newPassword: 'new123456' },
    });

    if (handler) {
      await handler(req, res);
      expect(bcrypt.compare).toHaveBeenCalledWith('old123456', 'hashed-old-password');
      expect(bcrypt.hash).toHaveBeenCalledWith('new123456', 12);
      expect(prisma.user.update).toHaveBeenCalledWith({
        where: { id: validUserId },
        data: { passwordHash: 'hashed-new-password' },
      });
      expect(res.json).toHaveBeenCalledWith({ message: 'Password changed successfully' });
    }
  });
});
