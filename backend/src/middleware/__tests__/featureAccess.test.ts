import { beforeEach, describe, expect, it, vi } from 'vitest';
import express from 'express';
import request from 'supertest';

const mocks = vi.hoisted(() => ({
  userFindUnique: vi.fn(),
  isEntitledUser: vi.fn(),
}));

vi.mock('../../services/db.js', () => ({
  prisma: { user: { findUnique: (...a: unknown[]) => mocks.userFindUnique(...a) } },
}));

vi.mock('../../services/catalogService.js', () => ({
  isEntitledUser: (...a: unknown[]) => mocks.isEntitledUser(...a),
}));

const { requireDecisionToolsAccess } = await import('../featureAccess.js');
const { hasAnalystAccess, hasDecisionToolsAccess, getFeatureAccess } =
  await import('../../services/featureAccess.js');

function appWithGuard() {
  const app = express();
  app.get(
    '/thing',
    (req, _res, next) => {
      const userId = req.headers['x-user-id'] as string | undefined;
      if (userId) (req as { user?: { id: string } }).user = { id: userId };
      next();
    },
    requireDecisionToolsAccess,
    (_req, res) => { res.json({ ok: true }); },
  );
  return app;
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.isEntitledUser.mockResolvedValue(false);
});

describe('hasDecisionToolsAccess', () => {
  it('is false without a user id, without a DB round trip', async () => {
    expect(await hasDecisionToolsAccess(undefined)).toBe(false);
    expect(mocks.userFindUnique).not.toHaveBeenCalled();
  });

  it('is false when the user no longer exists', async () => {
    mocks.userFindUnique.mockResolvedValue(null);
    expect(await hasDecisionToolsAccess('gone')).toBe(false);
  });

  it('grants ADMIN by role even without the flag', async () => {
    mocks.userFindUnique.mockResolvedValue({ role: 'ADMIN', decisionToolsAccess: false });
    expect(await hasDecisionToolsAccess('u1')).toBe(true);
  });

  it('grants a plain user holding the flag', async () => {
    mocks.userFindUnique.mockResolvedValue({ role: 'USER', decisionToolsAccess: true });
    expect(await hasDecisionToolsAccess('u1')).toBe(true);
  });

  it('denies a plain user without the flag', async () => {
    mocks.userFindUnique.mockResolvedValue({ role: 'USER', decisionToolsAccess: false });
    expect(await hasDecisionToolsAccess('u1')).toBe(false);
  });

  it('is not implied by a subscription — the grant is not billing-derived', async () => {
    mocks.isEntitledUser.mockResolvedValue(true);
    mocks.userFindUnique.mockResolvedValue({ role: 'USER', decisionToolsAccess: false });
    expect(await hasDecisionToolsAccess('u1')).toBe(false);
  });
});

describe('hasAnalystAccess', () => {
  it('is additive: an entitled user passes without reading the grant', async () => {
    mocks.isEntitledUser.mockResolvedValue(true);
    expect(await hasAnalystAccess('u1')).toBe(true);
    expect(mocks.userFindUnique).not.toHaveBeenCalled();
  });

  it('grants an unentitled user holding chatAnalystAccess', async () => {
    mocks.userFindUnique.mockResolvedValue({ chatAnalystAccess: true });
    expect(await hasAnalystAccess('u1')).toBe(true);
  });

  it('denies an unentitled user without the grant', async () => {
    mocks.userFindUnique.mockResolvedValue({ chatAnalystAccess: false });
    expect(await hasAnalystAccess('u1')).toBe(false);
  });

  it('is false without a user id', async () => {
    expect(await hasAnalystAccess(undefined)).toBe(false);
  });
});

describe('getFeatureAccess', () => {
  it('reports the two grants independently', async () => {
    mocks.isEntitledUser.mockResolvedValue(false);
    mocks.userFindUnique.mockResolvedValue({
      role: 'USER',
      chatAnalystAccess: false,
      decisionToolsAccess: true,
    });
    expect(await getFeatureAccess('u1')).toEqual({ analyst: false, decisionTools: true });
  });
});

describe('requireDecisionToolsAccess', () => {
  it('passes a granted user through to the handler', async () => {
    mocks.userFindUnique.mockResolvedValue({ role: 'USER', decisionToolsAccess: true });
    const res = await request(appWithGuard()).get('/thing').set('x-user-id', 'u1');
    expect(res.status).toBe(200);
    expect(res.body).toEqual({ ok: true });
  });

  it('403s FEATURE_NOT_ENABLED without the grant', async () => {
    mocks.userFindUnique.mockResolvedValue({ role: 'USER', decisionToolsAccess: false });
    const res = await request(appWithGuard()).get('/thing').set('x-user-id', 'u1');
    expect(res.status).toBe(403);
    expect(res.body.code).toBe('FEATURE_NOT_ENABLED');
  });

  it('403s when no authenticated user reached the guard', async () => {
    const res = await request(appWithGuard()).get('/thing');
    expect(res.status).toBe(403);
    expect(mocks.userFindUnique).not.toHaveBeenCalled();
  });
});
