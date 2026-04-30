import { describe, it, expect, vi, beforeEach } from 'vitest';
import express, { Express } from 'express';
import request from 'supertest';

/**
 * Phase 5.4 — Public catalog runtime is DB-only (architectural invariant).
 *
 * This guardrail test mocks every ingestion-layer side-effect so any
 * accidental call from a public route handler will throw or be detected.
 * Public routes must satisfy: serve requests with mocked DB data ONLY,
 * and never invoke `getJobAsset`, `extractOrCreateResearchContext`,
 * `loadReportJson`, or perform direct filesystem reads.
 *
 * The complementary `.eslintrc.cjs` rule provides the same enforcement
 * at lint-time.
 */

// ─── Mock side-effects so any leak fails the test ────────────────────────
const mockGetJobAsset = vi.fn().mockImplementation(() => {
  throw new Error('GUARDRAIL VIOLATION: getJobAsset called during public catalog request');
});
const mockExtractOrCreate = vi.fn().mockImplementation(() => {
  throw new Error(
    'GUARDRAIL VIOLATION: extractOrCreateResearchContext called during public catalog request',
  );
});
const mockReadFileSync = vi.fn().mockImplementation(() => {
  throw new Error('GUARDRAIL VIOLATION: readFileSync called during public catalog request');
});

// ─── Mock the catalogService public functions to return canned DB data ──
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

vi.mock('../../services/catalogService.js', () => ({
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
}));

// Re-mock the rate limiter to a noop (would otherwise wrap our routes).
vi.mock('../../middleware/rateLimit.js', () => ({
  catalogCrawlLimiter: (_req: any, _res: any, next: any) => next(),
}));

// Mock fs reads — any access during a request fails.
vi.mock('fs', () => ({
  readFileSync: (...args: any[]) => mockReadFileSync(...args),
  existsSync: vi.fn().mockReturnValue(true),
}));

// Mock job/research services so a leak throws.
vi.mock('../../services/jobService.js', () => ({
  getJobAsset: (...args: any[]) => mockGetJobAsset(...args),
}));
vi.mock('../../services/researchContextService.js', () => ({
  extractOrCreateResearchContext: (...args: any[]) => mockExtractOrCreate(...args),
  hasMeaningfulResearchContext: vi.fn().mockReturnValue(true),
  hasProjectedData: vi.fn().mockReturnValue(true),
  isJsonEmpty: vi.fn().mockReturnValue(false),
  rejectIfContainsBannedContent: vi.fn().mockImplementation((v: unknown) => v),
}));

let app: Express;

beforeEach(async () => {
  vi.clearAllMocks();
  // Restore the throwing implementations after clearAllMocks.
  mockGetJobAsset.mockImplementation(() => {
    throw new Error('GUARDRAIL VIOLATION: getJobAsset called during public catalog request');
  });
  mockExtractOrCreate.mockImplementation(() => {
    throw new Error(
      'GUARDRAIL VIOLATION: extractOrCreateResearchContext called during public catalog request',
    );
  });
  mockReadFileSync.mockImplementation(() => {
    throw new Error('GUARDRAIL VIOLATION: readFileSync called during public catalog request');
  });

  // Default DB responses.
  mockGetCategoryLanding.mockResolvedValue({
    category: { id: 'c1', name: 'Sim Racing', slug: 'sim-racing' },
  });
  mockGetIdeaBySlug.mockResolvedValue({
    id: 'i1', slug: 'idea-slug', solutionName: 'Test Idea',
  });
  mockGetPainPointBySlug.mockResolvedValue({
    id: 'p1', slug: 'pain-slug', title: 'Test Pain',
  });
  mockGetCategorySitemapEntries.mockResolvedValue([]);
  mockGetIdeaSitemapEntries.mockResolvedValue([]);
  mockGetPainPointSitemapEntries.mockResolvedValue([]);

  app = express();
  app.use(express.json());

  const { publicCatalogRouter } = await import('../publicCatalog.js');
  app.use('/api/public/catalog', publicCatalogRouter);
});

describe('Phase 5.4 — public catalog runtime guardrail', () => {
  it('GET /landing/:parentSlug does NOT call ingestion helpers', async () => {
    const res = await request(app).get('/api/public/catalog/landing/sim-racing');
    expect(res.status).toBe(200);
    expect(mockGetJobAsset).not.toHaveBeenCalled();
    expect(mockExtractOrCreate).not.toHaveBeenCalled();
    expect(mockReadFileSync).not.toHaveBeenCalled();
  });

  it('GET /landing/:parentSlug/:childSlug does NOT call ingestion helpers', async () => {
    const res = await request(app).get('/api/public/catalog/landing/sim-racing/cockpit-design');
    expect(res.status).toBe(200);
    expect(mockGetJobAsset).not.toHaveBeenCalled();
    expect(mockExtractOrCreate).not.toHaveBeenCalled();
    expect(mockReadFileSync).not.toHaveBeenCalled();
  });

  it('GET /idea-by-slug/:slug does NOT call ingestion helpers', async () => {
    const res = await request(app).get('/api/public/catalog/idea-by-slug/some-idea');
    expect(res.status).toBe(200);
    expect(mockGetJobAsset).not.toHaveBeenCalled();
    expect(mockExtractOrCreate).not.toHaveBeenCalled();
    expect(mockReadFileSync).not.toHaveBeenCalled();
  });

  it('GET /pain-point-by-slug/:slug does NOT call ingestion helpers', async () => {
    const res = await request(app).get('/api/public/catalog/pain-point-by-slug/some-pain');
    expect(res.status).toBe(200);
    expect(mockGetJobAsset).not.toHaveBeenCalled();
    expect(mockExtractOrCreate).not.toHaveBeenCalled();
    expect(mockReadFileSync).not.toHaveBeenCalled();
  });

  it('GET /sitemap does NOT call ingestion helpers', async () => {
    const res = await request(app).get('/api/public/catalog/sitemap');
    expect(res.status).toBe(200);
    expect(mockGetJobAsset).not.toHaveBeenCalled();
    expect(mockExtractOrCreate).not.toHaveBeenCalled();
    expect(mockReadFileSync).not.toHaveBeenCalled();
  });
});
