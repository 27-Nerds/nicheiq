import { describe, it, expect, vi, beforeEach } from 'vitest';
import express, { Express } from 'express';
import request from 'supertest';

// Mock environment variable
vi.stubEnv('INTERNAL_SERVICE_SECRET', 'test-secret');

let app: Express;

beforeEach(async () => {
  vi.clearAllMocks();

  app = express();
  app.use(express.json());

  const { requireInternalAdmin } = await import('../auth.js');
  app.get('/test', requireInternalAdmin, (req: any, res) => {
    res.json({ ok: true, user: req.user });
  });
});

describe('requireInternalAdmin', () => {
  it('returns 401 when no x-internal-service header', async () => {
    const response = await request(app)
      .get('/test')
      .expect(401);

    expect(response.body.error).toBe('Authentication required');
  });

  it('returns 401 when wrong service secret', async () => {
    const response = await request(app)
      .get('/test')
      .set('x-internal-service', 'wrong-secret')
      .expect(401);

    expect(response.body.error).toBe('Authentication required');
  });

  it('returns 401 when no x-user-id header', async () => {
    const response = await request(app)
      .get('/test')
      .set('x-internal-service', 'test-secret')
      .expect(401);

    expect(response.body.error).toBe('Authentication required');
  });

  it('returns 403 when x-user-role is USER', async () => {
    const response = await request(app)
      .get('/test')
      .set('x-internal-service', 'test-secret')
      .set('x-user-id', 'user-123')
      .set('x-user-role', 'USER')
      .expect(403);

    expect(response.body.error).toBe('Admin access required');
  });

  it('returns 403 when x-user-role header is missing', async () => {
    const response = await request(app)
      .get('/test')
      .set('x-internal-service', 'test-secret')
      .set('x-user-id', 'user-123')
      .expect(403);

    expect(response.body.error).toBe('Admin access required');
  });

  it('passes when valid service secret + user-id + ADMIN role', async () => {
    const response = await request(app)
      .get('/test')
      .set('x-internal-service', 'test-secret')
      .set('x-user-id', 'admin-123')
      .set('x-user-role', 'ADMIN')
      .set('x-user-email', 'admin@test.com')
      .expect(200);

    expect(response.body.ok).toBe(true);
    expect(response.body.user).toEqual({
      id: 'admin-123',
      email: 'admin@test.com',
      role: 'ADMIN',
    });
  });
});
