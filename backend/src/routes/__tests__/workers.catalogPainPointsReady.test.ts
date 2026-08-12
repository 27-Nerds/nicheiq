import { describe, it, expect, vi, beforeEach } from 'vitest';
import express, { Express } from 'express';
import request from 'supertest';

// ============================================
// Mocks
// ============================================

// Prisma. Top-level operations on `job` plus a `$transaction` impl that
// invokes the callback with a `tx` shaped like the worker route needs.
const mockJobFindUnique = vi.fn();
const mockTxQueryRaw = vi.fn();
const mockTxPainPointFindMany = vi.fn();
const mockTxCtxFindMany = vi.fn();
const mockTxPainPointUpdate = vi.fn();
const mockTxPainPointFindUnique = vi.fn();
const mockTxPainPointCreate = vi.fn();
const mockTxPainPointUpdateMany = vi.fn();
const mockTxJobUpdateMany = vi.fn();
const mockTxDispatchUpdateMany = vi.fn();
const mockTxIdeaFindMany = vi.fn();
const mockTxIdeaCreate = vi.fn();

let lastTx: unknown;
const buildTx = () => ({
  $queryRaw: (...args: unknown[]) => mockTxQueryRaw(...args),
  catalogPainPoint: {
    findMany: (...args: unknown[]) => mockTxPainPointFindMany(...args),
    update: (...args: unknown[]) => mockTxPainPointUpdate(...args),
    findUnique: (...args: unknown[]) => mockTxPainPointFindUnique(...args),
    create: (...args: unknown[]) => mockTxPainPointCreate(...args),
    updateMany: (...args: unknown[]) => mockTxPainPointUpdateMany(...args),
  },
  catalogResearchContext: {
    findMany: (...args: unknown[]) => mockTxCtxFindMany(...args),
  },
  catalogIdea: {
    findMany: (...args: unknown[]) => mockTxIdeaFindMany(...args),
    create: (...args: unknown[]) => mockTxIdeaCreate(...args),
  },
  job: { updateMany: (...args: unknown[]) => mockTxJobUpdateMany(...args) },
  jobDispatch: { updateMany: (...args: unknown[]) => mockTxDispatchUpdateMany(...args) },
});

vi.mock('../../services/db.js', () => ({
  prisma: {
    job: { findUnique: (...args: unknown[]) => mockJobFindUnique(...args) },
    $transaction: async (cb: (tx: unknown) => Promise<unknown>) => {
      lastTx = buildTx();
      return cb(lastTx);
    },
  },
}));

// Service stubs.
const mockAddJobAsset = vi.fn();
const mockExtractOrCreate = vi.fn();
const mockHasMeaningfulResearchContext = vi.fn();
const mockGeneratePainPointSlug = vi.fn();
const mockGenerateIdeaSlug = vi.fn();
const mockCatalogIdeaFormat = vi.fn();
const mockCatalogIdeaDeliveryFormat = vi.fn();
const mockInvalidateCategoryLanding = vi.fn();
const mockInvalidateCatalogTotals = vi.fn();
const mockInvalidateTopCatalogPainPoints = vi.fn();
const mockBroadcastProgress = vi.fn();

vi.mock('../../services/jobService.js', () => ({
  addJobAsset: (...args: unknown[]) => mockAddJobAsset(...args),
  failJob: vi.fn(),
  updateStageProgress: vi.fn(),
  completeJob: vi.fn(),
  getJob: vi.fn(),
  getJobAsset: vi.fn(),
}));
vi.mock('../../services/researchContextService.js', () => ({
  extractOrCreateResearchContext: (...args: unknown[]) => mockExtractOrCreate(...args),
  hasMeaningfulResearchContext: (...args: unknown[]) =>
    mockHasMeaningfulResearchContext(...args),
  MEANINGFUL_SELECT: {},
}));
vi.mock('../../services/catalogService.js', () => ({
  generatePainPointSlug: (...args: unknown[]) => mockGeneratePainPointSlug(...args),
  generateIdeaSlug: (...args: unknown[]) => mockGenerateIdeaSlug(...args),
  catalogIdeaFormat: (...args: unknown[]) => mockCatalogIdeaFormat(...args),
  catalogIdeaDeliveryFormat: (...args: unknown[]) => mockCatalogIdeaDeliveryFormat(...args),
  invalidateCategoryLanding: (...args: unknown[]) =>
    mockInvalidateCategoryLanding(...args),
  invalidateCatalogTotals: (...args: unknown[]) => mockInvalidateCatalogTotals(...args),
  invalidateTopCatalogPainPoints: (...args: unknown[]) =>
    mockInvalidateTopCatalogPainPoints(...args),
}));
vi.mock('../../services/progressBroadcastService.js', () => ({
  broadcastProgress: (...args: unknown[]) => mockBroadcastProgress(...args),
}));
vi.mock('../../middleware/auth.js', () => ({
  requireInternalService: (_req: unknown, _res: unknown, next: () => void) => next(),
}));
vi.mock('../../services/heartbeatService.js', () => ({
  updateJobHeartbeat: vi.fn(),
  registerWorkerHeartbeat: vi.fn(),
  markWorkerShutdown: vi.fn(),
}));
vi.mock('../../services/notificationService.js', () => ({
  notifyJobStart: vi.fn(),
  notifyJobComplete: vi.fn(),
  notifyJobError: vi.fn(),
  notifySolutionsReady: vi.fn(),
  notifyPhase2Start: vi.fn(),
  notifyRegenerationComplete: vi.fn(),
  notifyLandingPageReady: vi.fn(),
}));
vi.mock('../../services/creditService.js', () => ({
  refundChargeInTx: vi.fn(),
  refundForStage: vi.fn(),
  refundForStageInTx: vi.fn(),
  refundForRegenerationStage: vi.fn(),
  isGuidedSegment: vi.fn(),
}));
vi.mock('../../utils/errorTranslator.js', () => ({
  buildErrorDetails: vi.fn(),
}));
vi.mock('../../utils/phaseContext.js', () => ({
  getPhaseContext: vi.fn(),
}));

// ============================================
// Test app
// ============================================
let app: Express;

const jobId = '00000000-0000-0000-0000-000000000001';
const categoryId = '00000000-0000-0000-0000-000000000010';
const dispatchId = '00000000-0000-0000-0000-000000000020';

beforeEach(async () => {
  vi.clearAllMocks();

  // Default-RUNNING job for the row-lock query.
  mockTxQueryRaw.mockResolvedValue([{ id: jobId, status: 'RUNNING', activeDispatchId: null }]);
  // Reasonable defaults; tests override per-case.
  mockJobFindUnique.mockResolvedValue({ status: 'RUNNING', activeDispatchId: null });
  mockExtractOrCreate.mockResolvedValue({ detailedPainPoints: [{ title: 'x' }] });
  mockHasMeaningfulResearchContext.mockReturnValue(true);
  mockGeneratePainPointSlug.mockResolvedValue('slug');
  mockGenerateIdeaSlug.mockResolvedValue('idea-slug');
  mockCatalogIdeaFormat.mockImplementation(
    (idea: Record<string, unknown>) =>
      String(idea.delivery_format ?? idea.project_type ?? 'saas'),
  );
  mockCatalogIdeaDeliveryFormat.mockImplementation((idea: Record<string, unknown>) => {
    if (typeof idea.delivery_format !== 'string') return null;
    const normalized = idea.delivery_format.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-');
    return ['web-app', 'mobile-app', 'desktop-app', 'browser-extension', 'platform-plugin',
      'api', 'bot-assistant', 'data-product', 'report', 'service', 'physical-product', 'other']
      .includes(normalized) ? normalized : null;
  });
  mockTxPainPointUpdateMany.mockResolvedValue({ count: 0 });
  mockTxJobUpdateMany.mockResolvedValue({ count: 1 });
  mockTxDispatchUpdateMany.mockResolvedValue({ count: 1 });
  mockTxIdeaFindMany.mockResolvedValue([]);

  app = express();
  app.use(express.json());
  const { workersRouter } = await import('../workers.js');
  app.use('/api/workers', workersRouter);
});

function buildPayload(painPoints: Array<Record<string, unknown>> = []) {
  return {
    worker_id: 'w1',
    job_id: jobId,
    category_id: categoryId,
    pain_points: painPoints,
    niche: 'test-niche',
    preview_report_path: '/tmp/preview.json',
  };
}

// hasMeaningfulResearchContext is called once for the new job's CRC at the
// outer gate, then once per existing CRC inside the tx. Wire that up via a
// per-row classifier on the existing CRCs.
function wireHasMeaningful(jobIdToMeaningful: Record<string, boolean>) {
  // First call = outer gate for the new job (always true in these tests).
  mockHasMeaningfulResearchContext.mockReset();
  mockHasMeaningfulResearchContext.mockReturnValueOnce(true);
  mockHasMeaningfulResearchContext.mockImplementation((row: { sourceJobId?: string }) => {
    if (!row?.sourceJobId) return true;
    return jobIdToMeaningful[row.sourceJobId] ?? true;
  });
}

describe('POST /api/workers/catalog-pain-points-ready — legacy sweep', () => {
  it('settles the matching modern dispatch atomically with completion', async () => {
    mockJobFindUnique.mockResolvedValue({ status: 'RUNNING', activeDispatchId: dispatchId });
    mockTxQueryRaw.mockResolvedValue([
      { id: jobId, status: 'RUNNING', activeDispatchId: dispatchId },
    ]);
    mockTxPainPointFindMany.mockResolvedValue([]);
    mockTxCtxFindMany.mockResolvedValue([]);

    await request(app)
      .post('/api/workers/catalog-pain-points-ready')
      .send({ ...buildPayload([]), dispatch_id: dispatchId })
      .expect(200);

    expect(mockTxJobUpdateMany).toHaveBeenCalledWith({
      where: {
        id: jobId,
        status: { in: ['RUNNING', 'QUEUED'] },
        activeDispatchId: dispatchId,
      },
      data: expect.objectContaining({ status: 'COMPLETED', activeDispatchId: null }),
    });
    expect(mockTxDispatchUpdateMany).toHaveBeenCalledWith({
      where: {
        id: dispatchId,
        jobId,
        kind: 'CONTINUE',
        state: 'CLAIMED',
        workerId: 'w1',
      },
      data: expect.objectContaining({ state: 'COMPLETED' }),
    });
  });

  it('rejects a stale dispatch before registering the preview asset', async () => {
    mockJobFindUnique.mockResolvedValue({
      status: 'RUNNING',
      activeDispatchId: '00000000-0000-0000-0000-000000000099',
    });

    await request(app)
      .post('/api/workers/catalog-pain-points-ready')
      .send({ ...buildPayload([]), dispatch_id: dispatchId })
      .expect(409);

    expect(mockAddJobAsset).not.toHaveBeenCalled();
    expect(mockTxJobUpdateMany).not.toHaveBeenCalled();
    expect(mockTxDispatchUpdateMany).not.toHaveBeenCalled();
  });

  it('returns a stale-writer conflict when dispatch settlement loses its CAS', async () => {
    mockJobFindUnique.mockResolvedValue({ status: 'RUNNING', activeDispatchId: dispatchId });
    mockTxQueryRaw.mockResolvedValue([
      { id: jobId, status: 'RUNNING', activeDispatchId: dispatchId },
    ]);
    mockTxPainPointFindMany.mockResolvedValue([]);
    mockTxCtxFindMany.mockResolvedValue([]);
    mockTxDispatchUpdateMany.mockResolvedValue({ count: 0 });

    await request(app)
      .post('/api/workers/catalog-pain-points-ready')
      .send({ ...buildPayload([]), dispatch_id: dispatchId })
      .expect(409);
  });

  it('deactivates unmatched legacy rows; merges matched legacy; preserves non-legacy', async () => {
    const existingRows = [
      { id: 'pp-a', sourceJobId: 'legacy-1', title: 'Old A', isActive: true,
        mentionCount: 0, severityScore: 0.1, commercialIntentScore: 0.1,
        representativeQuotes: [], sourcePlatforms: [], affectedSegments: [],
        opportunityLevel: 'low', themeId: null },
      { id: 'pp-b', sourceJobId: 'legacy-2', title: 'Old B', isActive: true,
        mentionCount: 0, severityScore: 0.1, commercialIntentScore: 0.1,
        representativeQuotes: [], sourcePlatforms: [], affectedSegments: [],
        opportunityLevel: 'low', themeId: null },
      { id: 'pp-c', sourceJobId: 'meaningful-x', title: 'Real C', isActive: true,
        mentionCount: 0, severityScore: 0.1, commercialIntentScore: 0.1,
        representativeQuotes: [], sourcePlatforms: [], affectedSegments: [],
        opportunityLevel: 'low', themeId: null },
    ];
    mockTxPainPointFindMany.mockResolvedValue(existingRows);
    mockTxCtxFindMany.mockResolvedValue([
      { sourceJobId: 'legacy-1' },
      { sourceJobId: 'legacy-2' },
      { sourceJobId: 'meaningful-x' },
    ]);
    wireHasMeaningful({
      'legacy-1': false,
      'legacy-2': false,
      'meaningful-x': true,
    });
    mockTxPainPointUpdateMany.mockResolvedValue({ count: 1 });

    // New pain point matches 'Old A' via bigramSimilarity.
    const payload = buildPayload([
      { title: 'Old A', description: 'd', mention_count: 1, severity_score: 0.5,
        commercial_intent: 0.5, opportunity_level: 'high',
        representative_quotes: [], source_platforms: [], categories: [],
        affected_segments: [] },
    ]);

    const res = await request(app)
      .post('/api/workers/catalog-pain-points-ready')
      .send(payload)
      .expect(200);

    // pp-a was updated (lineage advance for the match).
    expect(mockTxPainPointUpdate).toHaveBeenCalledWith(
      expect.objectContaining({ where: { id: 'pp-a' } }),
    );
    // Sweep targets ONLY pp-b (unmatched legacy). pp-c is preserved
    // (unmatched but non-legacy); pp-a is matched.
    expect(mockTxPainPointUpdateMany).toHaveBeenCalledWith({
      where: {
        id: { in: ['pp-b'] },
        categoryId,
        isActive: true,
      },
      data: { isActive: false },
    });
    // total = totalExisting + created - deactivated = 3 + 0 - 1.
    expect(res.body).toEqual({ merged: 1, created: 0, deactivated: 1, total: 2 });
    // Global cache invalidations fire when deactivated > 0.
    expect(mockInvalidateCategoryLanding).toHaveBeenCalledWith(categoryId);
    expect(mockInvalidateCatalogTotals).toHaveBeenCalledOnce();
    expect(mockInvalidateTopCatalogPainPoints).toHaveBeenCalledOnce();
  });

  it('empty pain_points: never sweeps even with all-legacy existing', async () => {
    mockTxPainPointFindMany.mockResolvedValue([
      { id: 'pp-a', sourceJobId: 'legacy-1', title: 'Old A', isActive: true,
        mentionCount: 0, severityScore: 0, commercialIntentScore: 0,
        representativeQuotes: [], sourcePlatforms: [], affectedSegments: [],
        opportunityLevel: 'low', themeId: null },
    ]);
    mockTxCtxFindMany.mockResolvedValue([{ sourceJobId: 'legacy-1' }]);
    wireHasMeaningful({ 'legacy-1': false });

    const res = await request(app)
      .post('/api/workers/catalog-pain-points-ready')
      .send(buildPayload([]))
      .expect(200);

    expect(mockTxPainPointUpdateMany).not.toHaveBeenCalled();
    expect(res.body.deactivated).toBe(0);
    expect(mockInvalidateCatalogTotals).not.toHaveBeenCalled();
  });

  it('all-meaningful existing: no sweep even when some are unmatched', async () => {
    mockTxPainPointFindMany.mockResolvedValue([
      { id: 'pp-c', sourceJobId: 'meaningful-x', title: 'Real C', isActive: true,
        mentionCount: 0, severityScore: 0, commercialIntentScore: 0,
        representativeQuotes: [], sourcePlatforms: [], affectedSegments: [],
        opportunityLevel: 'low', themeId: null },
      { id: 'pp-d', sourceJobId: 'meaningful-y', title: 'Real D', isActive: true,
        mentionCount: 0, severityScore: 0, commercialIntentScore: 0,
        representativeQuotes: [], sourcePlatforms: [], affectedSegments: [],
        opportunityLevel: 'low', themeId: null },
    ]);
    mockTxCtxFindMany.mockResolvedValue([
      { sourceJobId: 'meaningful-x' },
      { sourceJobId: 'meaningful-y' },
    ]);
    wireHasMeaningful({ 'meaningful-x': true, 'meaningful-y': true });

    const payload = buildPayload([
      { title: 'Real C', description: 'd', mention_count: 1, severity_score: 0.5,
        commercial_intent: 0.5, opportunity_level: 'high',
        representative_quotes: [], source_platforms: [], categories: [],
        affected_segments: [] },
    ]);

    const res = await request(app)
      .post('/api/workers/catalog-pain-points-ready')
      .send(payload)
      .expect(200);

    expect(mockTxPainPointUpdateMany).not.toHaveBeenCalled();
    expect(res.body.deactivated).toBe(0);
  });

  it('all-legacy existing, all matched: no sweep (matched IDs filter everything out)', async () => {
    mockTxPainPointFindMany.mockResolvedValue([
      { id: 'pp-a', sourceJobId: 'legacy-1', title: 'Old A', isActive: true,
        mentionCount: 0, severityScore: 0, commercialIntentScore: 0,
        representativeQuotes: [], sourcePlatforms: [], affectedSegments: [],
        opportunityLevel: 'low', themeId: null },
    ]);
    mockTxCtxFindMany.mockResolvedValue([{ sourceJobId: 'legacy-1' }]);
    wireHasMeaningful({ 'legacy-1': false });

    const payload = buildPayload([
      { title: 'Old A', description: 'd', mention_count: 1, severity_score: 0.5,
        commercial_intent: 0.5, opportunity_level: 'high',
        representative_quotes: [], source_platforms: [], categories: [],
        affected_segments: [] },
    ]);

    const res = await request(app)
      .post('/api/workers/catalog-pain-points-ready')
      .send(payload)
      .expect(200);

    expect(mockTxPainPointUpdate).toHaveBeenCalledWith(
      expect.objectContaining({ where: { id: 'pp-a' } }),
    );
    expect(mockTxPainPointUpdateMany).not.toHaveBeenCalled();
    expect(res.body).toEqual({ merged: 1, created: 0, deactivated: 0, total: 1 });
  });
});

describe('POST /api/workers/catalog-ideas-ready — dispatch settlement', () => {
  it('stores delivery format separately from project type', async () => {
    await request(app)
      .post('/api/workers/catalog-ideas-ready')
      .send({
        worker_id: 'w1',
        job_id: jobId,
        category_id: categoryId,
        ideas: [{
          solution_name: 'Reply Draft',
          description: 'Drafts support replies.',
          delivery_format: 'browser-extension',
          project_type: 'saas',
        }],
        niche: 'test-niche',
      })
      .expect(200);

    expect(mockGenerateIdeaSlug).toHaveBeenCalledWith(
      expect.objectContaining({ format: 'browser-extension' }),
      expect.any(Object),
    );
    expect(mockTxIdeaCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        format: 'browser-extension',
        deliveryFormat: 'browser-extension',
        projectType: 'saas',
      }),
    });
  });

  it('keeps delivery format null for a legacy-shaped idea', async () => {
    await request(app)
      .post('/api/workers/catalog-ideas-ready')
      .send({
        worker_id: 'w1',
        job_id: jobId,
        category_id: categoryId,
        ideas: [{
          solution_name: 'Legacy SaaS',
          description: 'A legacy-shaped payload.',
          project_type: 'saas',
        }],
        niche: 'test-niche',
      })
      .expect(200);

    expect(mockTxIdeaCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        format: 'saas',
        deliveryFormat: null,
        projectType: 'saas',
      }),
    });
  });

  it('settles the matching modern dispatch for an empty successful batch', async () => {
    mockJobFindUnique.mockResolvedValue({ status: 'RUNNING', activeDispatchId: dispatchId });
    mockTxQueryRaw.mockResolvedValue([
      { id: jobId, status: 'RUNNING', activeDispatchId: dispatchId },
    ]);

    await request(app)
      .post('/api/workers/catalog-ideas-ready')
      .send({
        worker_id: 'w1',
        job_id: jobId,
        dispatch_id: dispatchId,
        category_id: categoryId,
        ideas: [],
        niche: 'test-niche',
      })
      .expect(200);

    expect(mockTxDispatchUpdateMany).toHaveBeenCalledWith({
      where: {
        id: dispatchId,
        jobId,
        kind: 'CONTINUE',
        state: 'CLAIMED',
        workerId: 'w1',
      },
      data: expect.objectContaining({ state: 'COMPLETED' }),
    });
  });
});
