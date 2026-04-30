import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import express from 'express';
import request from 'supertest';
import { requireInternalService } from '../auth.js';

describe('requireInternalService middleware', () => {
  let app: express.Express;
  let originalSecret: string | undefined;

  beforeEach(() => {
    originalSecret = process.env.INTERNAL_SERVICE_SECRET;
    process.env.INTERNAL_SERVICE_SECRET = 'test-service-secret';

    app = express();
    app.get('/protected', requireInternalService, (_req, res) => {
      res.json({ ok: true });
    });
  });

  afterEach(() => {
    if (originalSecret === undefined) {
      delete process.env.INTERNAL_SERVICE_SECRET;
    } else {
      process.env.INTERNAL_SERVICE_SECRET = originalSecret;
    }
  });

  it('passes when the correct service secret is provided', async () => {
    const res = await request(app)
      .get('/protected')
      .set('X-Internal-Service', 'test-service-secret');
    expect(res.status).toBe(200);
    expect(res.body).toEqual({ ok: true });
  });

  it('passes WITHOUT requiring X-User-ID (the contrast with requireInternalAuth)', async () => {
    // requireInternalAuth would 401 here because no X-User-ID is sent.
    const res = await request(app)
      .get('/protected')
      .set('X-Internal-Service', 'test-service-secret');
    // No userId header, but service-only auth should still pass.
    expect(res.status).toBe(200);
  });

  it('rejects with 401 when the secret header is missing', async () => {
    const res = await request(app).get('/protected');
    expect(res.status).toBe(401);
  });

  it('rejects with 401 when the secret is wrong', async () => {
    const res = await request(app)
      .get('/protected')
      .set('X-Internal-Service', 'wrong-secret');
    expect(res.status).toBe(401);
  });

  it('returns 500 when INTERNAL_SERVICE_SECRET is not configured', async () => {
    delete process.env.INTERNAL_SERVICE_SECRET;
    const res = await request(app)
      .get('/protected')
      .set('X-Internal-Service', 'anything');
    expect(res.status).toBe(500);
  });
});
