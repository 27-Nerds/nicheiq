import { describe, it, expect, vi, beforeEach } from 'vitest';
import express, { type Express } from 'express';
import request from 'supertest';

// ============================================
// Mocks (declared before router import so module-load wiring picks them up)
// ============================================

// prisma — only the methods the routes under test reach.
const mockPrisma = {
  catalogPainPoint: { findMany: vi.fn(), groupBy: vi.fn() },
  catalogCategory: { findUnique: vi.fn() },
  catalogIdea: { findMany: vi.fn() },
  catalogResearchContext: { findUnique: vi.fn(), findMany: vi.fn() },
  job: { findFirst: vi.fn(), findMany: vi.fn(), create: vi.fn() },
};
vi.mock('../../services/db.js', () => ({ prisma: mockPrisma }));

// Redis — adminCatalog.ts calls getRedis() at module load. No-op fake.
const fakeRedis = { on: vi.fn(), quit: vi.fn(), duplicate: vi.fn() };
vi.mock('../../services/redis.js', () => ({
  getRedis: () => fakeRedis,
  closeRedis: vi.fn(),
}));

// Queue service — assert enqueue calls.
const mockEnqueueCatalogIdeasJob = vi.fn();
const mockEnqueueCatalogPainPointsJob = vi.fn();
vi.mock('../../services/queueService.js', () => ({
  enqueueCatalogIdeasJob: (...args: unknown[]) => mockEnqueueCatalogIdeasJob(...args),
  enqueueCatalogPainPointsJob: (...args: unknown[]) => mockEnqueueCatalogPainPointsJob(...args),
}));

// Research context service — mock both functions directly. Spreading the
// real module would pull in prisma + filesystem helpers at load time.
const mockExtractOrCreateResearchContext = vi.fn();
const mockHasMeaningfulResearchContext = vi.fn();
vi.mock('../../services/researchContextService.js', () => ({
  extractOrCreateResearchContext: (...args: unknown[]) =>
    mockExtractOrCreateResearchContext(...args),
  hasMeaningfulResearchContext: (...args: unknown[]) =>
    mockHasMeaningfulResearchContext(...args),
  // Spread by callers via `select: { ...MEANINGFUL_SELECT }`. No test asserts
  // the shape, so an empty object suffices.
  MEANINGFUL_SELECT: {},
}));

// Other services adminCatalog imports — stub to no-ops so module load doesn't
// pull external clients (OpenAI etc.).
vi.mock('../../services/catalogService.js', () => ({
  listCategories: vi.fn(),
  createCategory: vi.fn(),
  updateCategory: vi.fn(),
  deleteCategory: vi.fn(),
  listCachedItems: vi.fn(),
  listShareOwners: vi.fn(),
  ensureCachePopulated: vi.fn(),
  publishIdea: vi.fn(),
  publishPainPoint: vi.fn(),
  updateCatalogIdea: vi.fn(),
  updateCatalogPainPoint: vi.fn(),
  depublishIdea: vi.fn(),
  depublishPainPoint: vi.fn(),
  invalidateCategoryLanding: vi.fn(),
}));
vi.mock('../../services/faqGeneratorService.js', () => ({
  generateForCategory: vi.fn(),
  generateForIdea: vi.fn(),
  generateForPainPoint: vi.fn(),
  FaqGenerationError: class FaqGenerationError extends Error {},
}));
vi.mock('../../services/categorizationService.js', () => ({
  categorizeBatch: vi.fn(),
}));
vi.mock('../../services/catalogCollectionService.js', () => ({
  listCollectionsAdmin: vi.fn(),
  getCollectionAdmin: vi.fn(),
  createCollection: vi.fn(),
  updateCollection: vi.fn(),
  deleteCollection: vi.fn(),
  addItemToCollection: vi.fn(),
  removeItemFromCollection: vi.fn(),
  reorderItems: vi.fn(),
}));

// ============================================
// Test app setup
// ============================================
let app: Express;

const categoryId = '11111111-1111-1111-1111-111111111111';
const painPointAId = '22222222-2222-2222-2222-222222222222';
const painPointBId = '33333333-3333-3333-3333-333333333333';
const sourceJobIdMeaningful = '44444444-4444-4444-4444-444444444444';
const parentCategoryId = '55555555-5555-5555-5555-555555555555';
const childCategoryAId = '66666666-6666-6666-6666-666666666666';
const childCategoryBId = '77777777-7777-7777-7777-777777777777';

beforeEach(async () => {
  vi.clearAllMocks();

  // adminCatalogRouter does not apply auth middleware itself (mounted via
  // backend/src/index.ts:73). Inject req.user via a pass-through so the
  // route's req.user!.id reference doesn't throw.
  app = express();
  app.use(express.json());
  app.use((req, _res, next) => {
    (req as express.Request & { user: { id: string; role: string } }).user = {
      id: 'admin-test',
      role: 'ADMIN',
    };
    next();
  });

  const { adminCatalogRouter } = await import('../adminCatalog.js');
  app.use('/api/admin/catalog', adminCatalogRouter);
});

// ============================================
// GET /categories
// ============================================
describe('GET /api/admin/catalog/categories', () => {
  it('returns active jobs and legacy pain-point counts without exposing researchContext', async () => {
    const { listCategories } = await import('../../services/catalogService.js');
    const categories = [
      {
        id: parentCategoryId,
        name: 'Parent',
        slug: 'parent',
        isActive: true,
        children: [
          {
            id: childCategoryAId,
            name: 'Child A',
            slug: 'child-a',
            isActive: true,
            _count: { ideas: 0, painPoints: 2 },
          },
          {
            id: childCategoryBId,
            name: 'Child B',
            slug: 'child-b',
            isActive: true,
            _count: { ideas: 0, painPoints: 1 },
          },
        ],
      },
    ];
    vi.mocked(listCategories).mockResolvedValueOnce(categories as never);
    mockPrisma.job.findMany.mockResolvedValueOnce([
      {
        id: 'job-active',
        catalogCategoryId: childCategoryAId,
        jobMode: 'catalog_pain_points',
        status: 'RUNNING',
      },
    ]);

    // Three CRC rows: one meaningful (job-real), two placeholders (job-a, job-b).
    // The route no longer pulls per-pain-point joins; it pulls CRC once and
    // then asks Postgres for per-category counts of pain points whose
    // sourceJobId is in the placeholder set.
    mockPrisma.catalogResearchContext.findMany.mockResolvedValueOnce([
      { sourceJobId: 'job-real', detailedPainPoints: [{ title: 'real' }] },
      { sourceJobId: 'job-a', detailedPainPoints: [] },
      { sourceJobId: 'job-b', detailedPainPoints: [] },
    ]);
    mockHasMeaningfulResearchContext
      .mockReturnValueOnce(true)
      .mockReturnValueOnce(false)
      .mockReturnValueOnce(false);
    mockPrisma.catalogPainPoint.groupBy.mockResolvedValueOnce([
      { categoryId: childCategoryAId, _count: { _all: 1 } },
      { categoryId: childCategoryBId, _count: { _all: 1 } },
      { categoryId: parentCategoryId, _count: { _all: 1 } },
    ]);

    const res = await request(app)
      .get('/api/admin/catalog/categories')
      .expect(200);

    expect(mockPrisma.job.findMany).toHaveBeenCalledTimes(1);
    expect(mockPrisma.catalogResearchContext.findMany).toHaveBeenCalledWith(
      expect.objectContaining({
        select: expect.objectContaining({ sourceJobId: true }),
      }),
    );
    expect(mockPrisma.catalogPainPoint.groupBy).toHaveBeenCalledWith(
      expect.objectContaining({
        by: ['categoryId'],
        where: expect.objectContaining({
          isActive: true,
          categoryId: { in: expect.arrayContaining([parentCategoryId, childCategoryAId, childCategoryBId]) },
          sourceJobId: { in: expect.arrayContaining(['job-a', 'job-b']) },
        }),
        _count: { _all: true },
      }),
    );

    const [parent] = res.body.categories;
    expect(parent).toMatchObject({
      id: parentCategoryId,
      legacyPainPoints: 3,
    });
    expect(parent).not.toHaveProperty('researchContext');
    expect(parent.children[0]).toMatchObject({
      id: childCategoryAId,
      legacyPainPoints: 1,
      activeJobs: [
        {
          id: 'job-active',
          catalogCategoryId: childCategoryAId,
          jobMode: 'catalog_pain_points',
          status: 'RUNNING',
        },
      ],
    });
    expect(parent.children[0]).not.toHaveProperty('researchContext');
    expect(parent.children[1]).toMatchObject({
      id: childCategoryBId,
      legacyPainPoints: 1,
      activeJobs: [],
    });
    expect(parent.children[1]).not.toHaveProperty('researchContext');
  });
});

// ============================================
// POST /categories/:id/generate-ideas
// ============================================
describe('POST /api/admin/catalog/categories/:id/generate-ideas', () => {
  const validPainPoint = {
    id: painPointAId,
    title: 'Pain A',
    description: 'desc',
    mentionCount: 3,
    severityScore: 0.6,
    willingnessToPayScore: 0.5,
    opportunityLevel: 'medium',
    representativeQuotes: [],
    sourcePlatforms: [],
    categories: [],
    affectedSegments: [],
    sourceJobId: sourceJobIdMeaningful,
    sourceGeneratedAt: new Date('2026-01-01T00:00:00Z'),
    updatedAt: new Date('2026-01-01T00:00:00Z'),
    createdAt: new Date('2026-01-01T00:00:00Z'),
  };

  it('returns 409 with action discriminator when parent context is a placeholder; does not create a job', async () => {
    mockPrisma.catalogPainPoint.findMany.mockResolvedValueOnce([validPainPoint]);
    mockPrisma.catalogCategory.findUnique.mockResolvedValueOnce({
      id: categoryId,
      name: 'Cat',
      description: 'Niche',
      parent: null,
    });
    mockPrisma.job.findFirst.mockResolvedValueOnce(null);
    // Placeholder-shaped context returned from extraction.
    mockExtractOrCreateResearchContext.mockResolvedValueOnce({
      detailedPainPoints: [],
      redditPostsAnalyzed: null,
      contentCategorization: null,
    });
    mockHasMeaningfulResearchContext.mockReturnValueOnce(false);

    const res = await request(app)
      .post(`/api/admin/catalog/categories/${categoryId}/generate-ideas`)
      .send({ painPointIds: [painPointAId] })
      .expect(409);

    expect(res.body).toEqual({
      error: expect.stringContaining('legacy research run'),
      action: 'rerun-pain-points',
      categoryId,
    });

    // Critical: no orphan job created, no LLM-bound enqueue.
    expect(mockPrisma.job.create).not.toHaveBeenCalled();
    expect(mockEnqueueCatalogIdeasJob).not.toHaveBeenCalled();

    // Force-refresh flag is passed to the service.
    expect(mockExtractOrCreateResearchContext).toHaveBeenCalledWith(
      sourceJobIdMeaningful,
      expect.objectContaining({ forceRefreshPlaceholders: true, sourceKind: 'catalog' }),
    );
  });

  it('returns 200 and enqueues when parent context is meaningful', async () => {
    mockPrisma.catalogPainPoint.findMany.mockResolvedValueOnce([validPainPoint]);
    mockPrisma.catalogCategory.findUnique.mockResolvedValueOnce({
      id: categoryId,
      name: 'Cat',
      description: 'Niche',
      parent: { name: 'Parent' },
    });
    mockPrisma.job.findFirst.mockResolvedValueOnce(null);
    mockExtractOrCreateResearchContext.mockResolvedValueOnce({
      detailedPainPoints: [{ title: 'real' }],
      contentCategorization: { themes: ['a'] },
    });
    mockHasMeaningfulResearchContext.mockReturnValueOnce(true);
    mockPrisma.job.create.mockResolvedValueOnce({ id: 'job-new' });
    mockPrisma.catalogIdea.findMany.mockResolvedValueOnce([]);

    const res = await request(app)
      .post(`/api/admin/catalog/categories/${categoryId}/generate-ideas`)
      .send({ painPointIds: [painPointAId] })
      .expect(200);

    expect(res.body).toEqual({ jobId: 'job-new' });
    expect(mockPrisma.job.create).toHaveBeenCalledTimes(1);
    expect(mockEnqueueCatalogIdeasJob).toHaveBeenCalledTimes(1);
    // Parent contentCategorization is forwarded to the enqueue call.
    expect(mockEnqueueCatalogIdeasJob).toHaveBeenCalledWith(
      'job-new',
      categoryId,
      expect.any(Array),
      expect.any(String),
      'Parent',
      expect.any(Array),
      sourceJobIdMeaningful,
      { themes: ['a'] },
    );
  });
});

// ============================================
// GET /categories/:id/pain-points
// ============================================
describe('GET /api/admin/catalog/categories/:id/pain-points', () => {
  it('returns isLegacy per row and strips researchContext from the wire response', async () => {
    const meaningfulCtx = { detailedPainPoints: [{ title: 'x' }] };
    const placeholderCtx = { detailedPainPoints: [] };

    mockPrisma.catalogPainPoint.findMany.mockResolvedValueOnce([
      {
        id: painPointAId,
        title: 'Real pain',
        severityScore: 0.7,
        willingnessToPayScore: 0.6,
        researchContext: meaningfulCtx,
      },
      {
        id: painPointBId,
        title: 'Legacy pain',
        severityScore: 0.4,
        willingnessToPayScore: 0.3,
        researchContext: placeholderCtx,
      },
    ]);
    // First call sees the meaningful context, second sees the placeholder.
    mockHasMeaningfulResearchContext
      .mockReturnValueOnce(true)
      .mockReturnValueOnce(false);

    const res = await request(app)
      .get(`/api/admin/catalog/categories/${categoryId}/pain-points`)
      .expect(200);

    expect(res.body.painPoints).toHaveLength(2);
    expect(res.body.painPoints[0]).toMatchObject({
      id: painPointAId,
      isLegacy: false,
    });
    expect(res.body.painPoints[1]).toMatchObject({
      id: painPointBId,
      isLegacy: true,
    });
    // researchContext payload must not leak to the wire.
    expect(res.body.painPoints[0]).not.toHaveProperty('researchContext');
    expect(res.body.painPoints[1]).not.toHaveProperty('researchContext');
  });
});
