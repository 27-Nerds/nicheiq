import { describe, it, expect, vi, beforeEach } from 'vitest';
import express, { Express } from 'express';
import request from 'supertest';

// ============================================
// Mock catalogService — service-layer logic is unit-tested elsewhere; here we
// cover routing, slug-shape validation, status-code semantics, and cache
// headers on the new public-rendering endpoints introduced in Phase 2.
// ============================================
const mockGetCategoryLanding = vi.fn();
const mockGetIdeaBySlug = vi.fn();
const mockGetPainPointBySlug = vi.fn();
const mockGetCategorySitemapEntries = vi.fn();
const mockGetIdeaSitemapEntries = vi.fn();
const mockGetPainPointSitemapEntries = vi.fn();
const mockGetPublicCategoryTree = vi.fn();
const mockResolveLegacyCategory = vi.fn();
const mockResolveLegacyIdea = vi.fn();
const mockResolveLegacyPainPoint = vi.fn();

vi.mock('../../services/catalogService.js', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return {
    ...actual,
    getCategoryLanding: (...args: any[]) => mockGetCategoryLanding(...args),
    getIdeaBySlug: (...args: any[]) => mockGetIdeaBySlug(...args),
    getPainPointBySlug: (...args: any[]) => mockGetPainPointBySlug(...args),
    getCategorySitemapEntries: (...args: any[]) => mockGetCategorySitemapEntries(...args),
    getIdeaSitemapEntries: (...args: any[]) => mockGetIdeaSitemapEntries(...args),
    getPainPointSitemapEntries: (...args: any[]) => mockGetPainPointSitemapEntries(...args),
    getPublicCategoryTree: (...args: any[]) => mockGetPublicCategoryTree(...args),
    resolveLegacyCategory: (...args: any[]) => mockResolveLegacyCategory(...args),
    resolveLegacyIdea: (...args: any[]) => mockResolveLegacyIdea(...args),
    resolveLegacyPainPoint: (...args: any[]) => mockResolveLegacyPainPoint(...args),
    listCategories: vi.fn(),
    getDiscoverPainPoints: vi.fn(),
  };
});

// Bypass the rate limiter in tests (express-rate-limit is exercised in
// dedicated tests; here it just adds noise / 429 flakes).
vi.mock('../../middleware/rateLimit.js', () => ({
  catalogCrawlLimiter: (_req: any, _res: any, next: any) => next(),
  apiLimiter: (_req: any, _res: any, next: any) => next(),
  authLimiter: (_req: any, _res: any, next: any) => next(),
  passwordResetLimiter: (_req: any, _res: any, next: any) => next(),
  jobCreationLimiter: (_req: any, _res: any, next: any) => next(),
}));

// Pass-through the per-route auth gate added to idea-by-slug / pain-point-by-slug.
// This suite mounts the router without the mount-level auth and tests handler
// behavior; the gate itself is covered by publicCatalog.auth.test.ts.
vi.mock('../../middleware/auth.js', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return { ...actual, requireInternalAuth: (_req: any, _res: any, next: any) => next() };
});

let app: Express;

beforeEach(async () => {
  vi.clearAllMocks();

  const { publicCatalogRouter } = await import('../publicCatalog.js');
  app = express();
  app.use(express.json());
  app.use('/api/public/catalog', publicCatalogRouter);
});

describe('GET /api/public/catalog/landing/:parentSlug', () => {
  it('returns 200 with the landing payload for an active top-level category', async () => {
    const payload = { category: { slug: 'saas' }, topIdeas: [], topPainPoints: [] };
    mockGetCategoryLanding.mockResolvedValue(payload);

    const res = await request(app).get('/api/public/catalog/landing/saas');

    expect(res.status).toBe(200);
    expect(res.body).toEqual(payload);
    expect(mockGetCategoryLanding).toHaveBeenCalledWith({ parentSlug: 'saas', entitled: false });
  });

  it('returns 404 for an unknown slug', async () => {
    mockGetCategoryLanding.mockResolvedValue(null);
    const res = await request(app).get('/api/public/catalog/landing/unknown');
    expect(res.status).toBe(404);
  });

  it('returns 410 Gone for an inactive category', async () => {
    mockGetCategoryLanding.mockResolvedValue({ inactive: true });
    const res = await request(app).get('/api/public/catalog/landing/retired');
    expect(res.status).toBe(410);
  });

  it('rejects an invalid slug shape with 400', async () => {
    const res = await request(app).get('/api/public/catalog/landing/Foo%21Bar');
    expect(res.status).toBe(400);
    expect(mockGetCategoryLanding).not.toHaveBeenCalled();
  });
});

describe('GET /api/public/catalog/landing/:parentSlug/:childSlug', () => {
  it('returns 200 with the landing payload for a nested category', async () => {
    const payload = { category: { slug: 'b2b-tools' }, parent: { slug: 'saas' } };
    mockGetCategoryLanding.mockResolvedValue(payload);

    const res = await request(app).get('/api/public/catalog/landing/saas/b2b-tools');

    expect(res.status).toBe(200);
    expect(res.body).toEqual(payload);
    expect(mockGetCategoryLanding).toHaveBeenCalledWith({
      parentSlug: 'saas',
      childSlug: 'b2b-tools',
      entitled: false,
    });
  });

  it('returns 404 when the (parent, child) tuple does not resolve', async () => {
    mockGetCategoryLanding.mockResolvedValue(null);
    const res = await request(app).get('/api/public/catalog/landing/saas/missing');
    expect(res.status).toBe(404);
  });

  it('returns 410 for an inactive nested category', async () => {
    mockGetCategoryLanding.mockResolvedValue({ inactive: true });
    const res = await request(app).get('/api/public/catalog/landing/saas/retired');
    expect(res.status).toBe(410);
  });
});

describe('GET /api/public/catalog/idea-by-slug/:slug', () => {
  it('returns 200 with the idea preview', async () => {
    mockGetIdeaBySlug.mockResolvedValue({ id: 'i1', solution_name: 'Test' });
    const res = await request(app).get('/api/public/catalog/idea-by-slug/ai-invoice-parser-saas');
    expect(res.status).toBe(200);
    expect(res.body.id).toBe('i1');
  });

  it('returns 404 for unknown slug', async () => {
    mockGetIdeaBySlug.mockResolvedValue(null);
    const res = await request(app).get('/api/public/catalog/idea-by-slug/missing-slug');
    expect(res.status).toBe(404);
  });

  it('rejects an invalid slug shape', async () => {
    const res = await request(app).get('/api/public/catalog/idea-by-slug/Foo%20Bar');
    expect(res.status).toBe(400);
    expect(mockGetIdeaBySlug).not.toHaveBeenCalled();
  });
});

describe('GET /api/public/catalog/pain-point-by-slug/:slug', () => {
  it('returns 200 with the pain-point detail', async () => {
    mockGetPainPointBySlug.mockResolvedValue({ id: 'p1', title: 'Test pain' });
    const res = await request(app).get('/api/public/catalog/pain-point-by-slug/missing-tooling-saas');
    expect(res.status).toBe(200);
    expect(res.body.id).toBe('p1');
  });

  it('returns 404 for unknown slug', async () => {
    mockGetPainPointBySlug.mockResolvedValue(null);
    const res = await request(app).get('/api/public/catalog/pain-point-by-slug/no-such-pain');
    expect(res.status).toBe(404);
  });
});

describe('GET /api/public/catalog/legacy-redirect', () => {
  it('returns category target on hit', async () => {
    mockResolveLegacyCategory.mockResolvedValue('/ideas/saas/b2b-tools');
    const res = await request(app)
      .get('/api/public/catalog/legacy-redirect')
      .query({ kind: 'category', key: 'saas-b2b-tools' });
    expect(res.status).toBe(200);
    expect(res.body).toEqual({ target: '/ideas/saas/b2b-tools' });
    expect(mockResolveLegacyCategory).toHaveBeenCalledWith('saas-b2b-tools');
  });

  it('returns null target on miss', async () => {
    mockResolveLegacyCategory.mockResolvedValue(null);
    const res = await request(app)
      .get('/api/public/catalog/legacy-redirect')
      .query({ kind: 'category', key: 'unknown-slug' });
    expect(res.status).toBe(200);
    expect(res.body).toEqual({ target: null });
  });

  it('returns idea target on hit', async () => {
    mockResolveLegacyIdea.mockResolvedValue('/idea/ai-invoice-parser-saas');
    const res = await request(app)
      .get('/api/public/catalog/legacy-redirect')
      .query({ kind: 'idea', key: 'ai-invoice-parser-saas' });
    expect(res.status).toBe(200);
    expect(res.body.target).toBe('/idea/ai-invoice-parser-saas');
  });

  it('returns pain-point target on hit', async () => {
    mockResolveLegacyPainPoint.mockResolvedValue('/pain-point/missing-tooling-saas');
    const res = await request(app)
      .get('/api/public/catalog/legacy-redirect')
      .query({ kind: 'pain-point', key: 'missing-tooling-saas' });
    expect(res.status).toBe(200);
    expect(res.body.target).toBe('/pain-point/missing-tooling-saas');
  });

  it('rejects invalid kind', async () => {
    const res = await request(app)
      .get('/api/public/catalog/legacy-redirect')
      .query({ kind: 'category-bad', key: 'foo' });
    expect(res.status).toBe(400);
  });

  it('rejects key that fails slug regex', async () => {
    const res = await request(app)
      .get('/api/public/catalog/legacy-redirect')
      .query({ kind: 'category', key: 'Foo Bar!' });
    expect(res.status).toBe(400);
  });
});

describe('GET /api/public/catalog/sitemap', () => {
  it('returns 200 with categories/ideas/painPoints arrays and a cache header', async () => {
    mockGetCategorySitemapEntries.mockResolvedValue([
      { slug: 'saas', parentSlug: null, updatedAt: '2026-04-27T00:00:00.000Z', ideaCount: 12, painPointCount: 4 },
    ]);
    mockGetIdeaSitemapEntries.mockResolvedValue([
      { slug: 'ai-invoice-parser-saas', updatedAt: '2026-04-27T00:00:00.000Z' },
    ]);
    mockGetPainPointSitemapEntries.mockResolvedValue([
      { slug: 'missing-tooling-saas', updatedAt: '2026-04-27T00:00:00.000Z' },
    ]);

    const res = await request(app).get('/api/public/catalog/sitemap');

    expect(res.status).toBe(200);
    expect(res.body.categories).toHaveLength(1);
    expect(res.body.ideas).toHaveLength(1);
    expect(res.body.painPoints).toHaveLength(1);
    expect(res.headers['cache-control']).toBe('public, max-age=300');
  });
});
