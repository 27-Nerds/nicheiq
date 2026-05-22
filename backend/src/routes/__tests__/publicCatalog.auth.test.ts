import { describe, it, expect, vi, beforeAll, afterAll, beforeEach } from 'vitest';
import express, { Express } from 'express';
import request from 'supertest';
import { requireInternalService } from '../../middleware/auth.js';

/**
 * Regression guard for the per-route login gate added to the catalog DETAIL
 * endpoints. Unlike catalog.landing.test.ts / publicCatalog.guardrail.test.ts
 * (which pass-through the auth middleware), this suite mounts the router exactly
 * as production does — under `requireInternalService` — and runs the REAL
 * `requireInternalAuth` so the 401-without-user / 200-with-user behavior is
 * actually exercised. Catches anyone removing the per-route requireInternalAuth.
 */

const SECRET = 'test-internal-secret';

const mockGetIdeaBySlug = vi.fn();
const mockGetPainPointBySlug = vi.fn();
const mockGetCategoryLanding = vi.fn();

// Mock the service-layer DB calls; keep auth real. `isEntitledUser` is stubbed by
// user id (no DB) — entitled = 'admin-1' or 'sub-1' (a fullCatalogAccess user); all
// other ids (e.g. 'user-123') are non-entitled. This deliberately ignores the
// `X-User-Role` header, proving the route relies on the DB-backed helper.
vi.mock('../../services/catalogService.js', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return {
    ...actual,
    getIdeaBySlug: (...a: any[]) => mockGetIdeaBySlug(...a),
    getPainPointBySlug: (...a: any[]) => mockGetPainPointBySlug(...a),
    getCategoryLanding: (...a: any[]) => mockGetCategoryLanding(...a),
    isEntitledUser: (id?: string) => Promise.resolve(id === 'admin-1' || id === 'sub-1'),
    getDiscoverPainPoints: () =>
      Promise.resolve([{ id: 'p1', title: 'X', description: 'Y', severityScore: 0.5, mentionCount: 3 }]),
  };
});

// Bypass the rate limiter (exercised in its own tests).
vi.mock('../../middleware/rateLimit.js', () => ({
  catalogCrawlLimiter: (_req: any, _res: any, next: any) => next(),
}));

let app: Express;
let prevSecret: string | undefined;

beforeAll(() => {
  prevSecret = process.env.INTERNAL_SERVICE_SECRET;
  process.env.INTERNAL_SERVICE_SECRET = SECRET;
});

afterAll(() => {
  if (prevSecret === undefined) delete process.env.INTERNAL_SERVICE_SECRET;
  else process.env.INTERNAL_SERVICE_SECRET = prevSecret;
});

beforeEach(async () => {
  vi.clearAllMocks();
  mockGetIdeaBySlug.mockResolvedValue({ id: 'i1', slug: 'idea-slug', solutionName: 'X' });
  mockGetPainPointBySlug.mockResolvedValue({ id: 'p1', slug: 'pain-slug', title: 'X' });
  mockGetCategoryLanding.mockResolvedValue({ category: { id: 'c1', name: 'X', slug: 'x' } });

  const { publicCatalogRouter } = await import('../publicCatalog.js');
  app = express();
  app.use(express.json());
  // Production-equivalent mount (see backend/src/index.ts).
  app.use('/api/public/catalog', requireInternalService, publicCatalogRouter);
});

describe('public catalog detail endpoints require a logged-in user', () => {
  it('idea-by-slug: 401 with service secret only, 200 with X-User-ID', async () => {
    const noUser = await request(app)
      .get('/api/public/catalog/idea-by-slug/idea-slug')
      .set('X-Internal-Service', SECRET);
    expect(noUser.status).toBe(401);

    const withUser = await request(app)
      .get('/api/public/catalog/idea-by-slug/idea-slug')
      .set('X-Internal-Service', SECRET)
      .set('X-User-ID', 'user-123');
    expect(withUser.status).toBe(200);
    // A non-entitled user must be gated: the service is asked with entitled:false.
    expect(mockGetIdeaBySlug).toHaveBeenLastCalledWith('idea-slug', { entitled: false });
  });

  it('pain-point-by-slug: 401 without X-User-ID, 200 with it', async () => {
    const noUser = await request(app)
      .get('/api/public/catalog/pain-point-by-slug/pain-slug')
      .set('X-Internal-Service', SECRET);
    expect(noUser.status).toBe(401);

    const withUser = await request(app)
      .get('/api/public/catalog/pain-point-by-slug/pain-slug')
      .set('X-Internal-Service', SECRET)
      .set('X-User-ID', 'user-123');
    expect(withUser.status).toBe(200);
  });

  it('landing stays service-only — 200 with secret and no X-User-ID', async () => {
    const res = await request(app)
      .get('/api/public/catalog/landing/x')
      .set('X-Internal-Service', SECRET);
    expect(res.status).toBe(200);
  });

  it('idea-by-slug: a non-featured (locked) item for a non-entitled user → 403', async () => {
    mockGetIdeaBySlug.mockResolvedValueOnce({ locked: true });
    const res = await request(app)
      .get('/api/public/catalog/idea-by-slug/idea-slug')
      .set('X-Internal-Service', SECRET)
      .set('X-User-ID', 'user-123');
    expect(res.status).toBe(403);
  });

  it('pain-point-by-slug: a locked item → 403', async () => {
    mockGetPainPointBySlug.mockResolvedValueOnce({ locked: true });
    const res = await request(app)
      .get('/api/public/catalog/pain-point-by-slug/pain-slug')
      .set('X-Internal-Service', SECRET)
      .set('X-User-ID', 'user-123');
    expect(res.status).toBe(403);
  });

  it('idea-by-slug: an entitled user is gated with entitled:true — WITHOUT X-User-Role', async () => {
    // No X-User-Role header — entitlement comes from the DB-backed isEntitledUser
    // (mocked true for admin-1). Proves the route no longer trusts the header.
    const res = await request(app)
      .get('/api/public/catalog/idea-by-slug/idea-slug')
      .set('X-Internal-Service', SECRET)
      .set('X-User-ID', 'admin-1');
    expect(res.status).toBe(200);
    expect(mockGetIdeaBySlug).toHaveBeenLastCalledWith('idea-slug', { entitled: true });
  });

  it('discover moved here: GET /discover returns { items } (service-only, no user)', async () => {
    const res = await request(app)
      .get('/api/public/catalog/discover')
      .set('X-Internal-Service', SECRET);
    expect(res.status).toBe(200);
    expect(Array.isArray(res.body.items)).toBe(true);
    expect(res.body.items.length).toBeGreaterThan(0);
  });
});
