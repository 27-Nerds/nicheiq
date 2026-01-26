import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Request, Response } from 'express';

// Mock prisma before importing the router
vi.mock('../../services/db.js', () => ({
  prisma: {
    notificationPreferences: {
      findUnique: vi.fn(),
      upsert: vi.fn(),
    },
    user: {
      findUnique: vi.fn(),
    },
  },
}));

// Mock auth middleware
vi.mock('../../middleware/auth.js', () => ({
  requireInternalAuth: (req: any, res: any, next: any) => {
    req.user = { id: 'user-123' };
    next();
  },
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

describe('GET /api/users/:userId/notification-preferences', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns 400 for invalid UUID', async () => {
    const { usersRouter } = await import('../users.js');
    const { req, res } = createMockReqRes({
      params: { userId: 'invalid-uuid' },
    });

    // Find the handler for this route
    const handler = (usersRouter as any).stack.find(
      (layer: any) => layer.route?.path === '/:userId/notification-preferences' && layer.route?.methods?.get
    )?.route?.stack?.[1]?.handle;

    if (handler) {
      await handler(req, res);
      expect(res.status).toHaveBeenCalledWith(400);
      expect(res.json).toHaveBeenCalledWith({ error: 'Invalid user ID format' });
    }
  });

  it('returns 403 when user tries to access another user preferences', async () => {
    const { usersRouter } = await import('../users.js');
    const { req, res } = createMockReqRes({
      params: { userId: '11111111-1111-1111-1111-111111111111' },
      user: { id: 'different-user-id' },
    });

    const handler = (usersRouter as any).stack.find(
      (layer: any) => layer.route?.path === '/:userId/notification-preferences' && layer.route?.methods?.get
    )?.route?.stack?.[1]?.handle;

    if (handler) {
      await handler(req, res);
      expect(res.status).toHaveBeenCalledWith(403);
    }
  });

  it('returns default preferences when none exist', async () => {
    const userId = '11111111-1111-1111-1111-111111111111';
    vi.mocked(prisma.notificationPreferences.findUnique).mockResolvedValue(null);

    const { usersRouter } = await import('../users.js');
    const { req, res } = createMockReqRes({
      params: { userId },
      user: { id: userId },
    });

    const handler = (usersRouter as any).stack.find(
      (layer: any) => layer.route?.path === '/:userId/notification-preferences' && layer.route?.methods?.get
    )?.route?.stack?.[1]?.handle;

    if (handler) {
      await handler(req, res);
      expect(res.json).toHaveBeenCalledWith({
        emailEnabled: true,
        emailOnJobStart: true,
        emailOnJobComplete: true,
        emailOnJobError: true,
      });
    }
  });

  it('returns stored preferences when they exist', async () => {
    const userId = '11111111-1111-1111-1111-111111111111';
    vi.mocked(prisma.notificationPreferences.findUnique).mockResolvedValue({
      id: 'pref-1',
      userId,
      emailEnabled: false,
      emailOnJobStart: false,
      emailOnJobComplete: true,
      emailOnJobError: false,
      createdAt: new Date(),
      updatedAt: new Date(),
    });

    const { usersRouter } = await import('../users.js');
    const { req, res } = createMockReqRes({
      params: { userId },
      user: { id: userId },
    });

    const handler = (usersRouter as any).stack.find(
      (layer: any) => layer.route?.path === '/:userId/notification-preferences' && layer.route?.methods?.get
    )?.route?.stack?.[1]?.handle;

    if (handler) {
      await handler(req, res);
      expect(res.json).toHaveBeenCalledWith({
        emailEnabled: false,
        emailOnJobStart: false,
        emailOnJobComplete: true,
        emailOnJobError: false,
      });
    }
  });
});

describe('PUT /api/users/:userId/notification-preferences', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns 400 when no valid fields provided', async () => {
    const userId = '11111111-1111-1111-1111-111111111111';

    const { usersRouter } = await import('../users.js');
    const { req, res } = createMockReqRes({
      params: { userId },
      user: { id: userId },
      body: { invalidField: true },
    });

    const handler = (usersRouter as any).stack.find(
      (layer: any) => layer.route?.path === '/:userId/notification-preferences' && layer.route?.methods?.put
    )?.route?.stack?.[1]?.handle;

    if (handler) {
      await handler(req, res);
      expect(res.status).toHaveBeenCalledWith(400);
      expect(res.json).toHaveBeenCalledWith({ error: 'No valid preference fields provided' });
    }
  });

  it('upserts preferences successfully', async () => {
    const userId = '11111111-1111-1111-1111-111111111111';
    const updatedPrefs = {
      id: 'pref-1',
      userId,
      emailEnabled: false,
      emailOnJobStart: true,
      emailOnJobComplete: true,
      emailOnJobError: false,
      createdAt: new Date(),
      updatedAt: new Date(),
    };

    vi.mocked(prisma.notificationPreferences.upsert).mockResolvedValue(updatedPrefs);

    const { usersRouter } = await import('../users.js');
    const { req, res } = createMockReqRes({
      params: { userId },
      user: { id: userId },
      body: { emailEnabled: false, emailOnJobError: false },
    });

    const handler = (usersRouter as any).stack.find(
      (layer: any) => layer.route?.path === '/:userId/notification-preferences' && layer.route?.methods?.put
    )?.route?.stack?.[1]?.handle;

    if (handler) {
      await handler(req, res);
      expect(prisma.notificationPreferences.upsert).toHaveBeenCalled();
      expect(res.json).toHaveBeenCalledWith({
        emailEnabled: false,
        emailOnJobStart: true,
        emailOnJobComplete: true,
        emailOnJobError: false,
      });
    }
  });
});
