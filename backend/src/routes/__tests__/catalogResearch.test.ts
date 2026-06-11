import { describe, it, expect, vi, beforeEach } from 'vitest';
import express, { Express } from 'express';
import request from 'supertest';

// ── creditService (incl. a real-instanceof InsufficientCreditsError) ──
class InsufficientCreditsError extends Error {
  currentBalance: number;
  required: number;
  constructor(currentBalance = 0, required = 0) {
    super('Insufficient credits');
    this.name = 'InsufficientCreditsError';
    this.currentBalance = currentBalance;
    this.required = required;
  }
}
const mockCreateJobAndChargeDiscovery = vi.fn();
const mockChargeForStageInTx = vi.fn();
const mockRefundForStage = vi.fn();
vi.mock('../../services/creditService.js', () => ({
  createJobAndChargeDiscovery: mockCreateJobAndChargeDiscovery,
  chargeForStageInTx: mockChargeForStageInTx,
  refundForStage: mockRefundForStage,
  InsufficientCreditsError,
}));

// ── catalogService ──
const mockGetPainPointBySlug = vi.fn();
const mockGetIdeaBySlug = vi.fn();
const mockIsEntitledUser = vi.fn().mockResolvedValue(true);
vi.mock('../../services/catalogService.js', () => ({
  getPainPointBySlug: mockGetPainPointBySlug,
  getIdeaBySlug: mockGetIdeaBySlug,
  isEntitledUser: mockIsEntitledUser,
}));

// ── queueService ──
const mockEnqueuePain = vi.fn().mockResolvedValue(undefined);
const mockEnqueueDeepIdea = vi.fn().mockResolvedValue(undefined);
vi.mock('../../services/queueService.js', () => ({
  enqueuePainResearchJob: mockEnqueuePain,
  enqueueDeepIdeaResearchJob: mockEnqueueDeepIdea,
}));

// ── prisma ──
const mockJobUpdate = vi.fn().mockResolvedValue({});
const mockTxJobCreate = vi.fn();
const mockCirFindUnique = vi.fn();
const mockCirCreate = vi.fn().mockResolvedValue({});
const mockCirUpdate = vi.fn().mockResolvedValue({});
const mockCirDelete = vi.fn().mockResolvedValue({});
const mockCatalogIdeaUpdate = vi.fn().mockResolvedValue({});
const mockCatalogIdeaFindUnique = vi.fn();
const mockTransaction = vi.fn();
vi.mock('../../services/db.js', () => ({
  prisma: {
    job: { update: (...a: unknown[]) => mockJobUpdate(...a) },
    catalogIdea: {
      findUnique: (...a: unknown[]) => mockCatalogIdeaFindUnique(...a),
      update: (...a: unknown[]) => mockCatalogIdeaUpdate(...a),
    },
    catalogIdeaResearch: { delete: (...a: unknown[]) => mockCirDelete(...a) },
    // Callback form runs the tx callback; array form (counter rollback) awaits all.
    $transaction: (arg: unknown) =>
      Array.isArray(arg) ? Promise.all(arg) : mockTransaction(arg),
  },
}));

// ── middleware ──
vi.mock('../../middleware/auth.js', () => ({
  requireInternalAuth: (req: any, res: any, next: any) => {
    const userId = req.headers['x-user-id'];
    if (userId) { req.user = { id: userId }; return next(); }
    res.status(401).json({ error: 'Unauthorized' });
  },
  AuthenticatedRequest: {},
}));
vi.mock('../../middleware/rateLimit.js', () => ({
  jobCreationLimiter: (_req: any, _res: any, next: any) => next(),
}));
vi.mock('../../config.js', () => ({ CONFIG: { baseUrl: 'http://test' } }));

function painRecord(over: Record<string, unknown> = {}) {
  return {
    id: 'pp-1', slug: 'manual-invoicing', title: 'Manual invoicing', description: 'desc',
    mentionCount: 5, severityScore: 0.7, willingnessToPayScore: 0.6, opportunityLevel: 'high',
    representativeQuotes: ['q'], sourcePlatforms: ['reddit'], categories: ['billing'],
    affectedSegments: ['freelancers'], solutionApproach: null, themeId: null,
    sourceNiche: 'Freelance tools', ...over,
  };
}
function ideaRecord(over: Record<string, unknown> = {}) {
  return {
    id: 'idea-1', slug: 'invoiceflow', solution_name: 'InvoiceFlow', headline: 'Auto invoicing',
    description: 'A tool', value_proposition: 'Save time', project_type: 'saas',
    core_features: ['a'], target_personas: ['Freelancers'], differentiation_factors: null,
    pricing_strategy: null, technical_approach: null, market_fit_score: 0.7,
    technical_feasibility_score: 0.8, seo_scalability_score: null, organic_discovery_queries: null,
    programmatic_seo_opportunity: null, estimated_cac_organic: null, source_niche: 'Freelance tools',
    addressedPainTitles: ['Manual invoicing'], ...over,
  };
}

let app: Express;
beforeEach(async () => {
  vi.clearAllMocks();
  mockIsEntitledUser.mockResolvedValue(true);
  mockCreateJobAndChargeDiscovery.mockResolvedValue({ job: { id: 'job-pain' } });
  mockGetPainPointBySlug.mockResolvedValue(painRecord());
  mockGetIdeaBySlug.mockResolvedValue(ideaRecord());
  // idea endpoint: first $transaction creates+charges the job, second runs the counter
  mockTxJobCreate.mockResolvedValue({ id: 'job-idea' });
  mockCirFindUnique.mockResolvedValue(null);
  // Raw row read for the seed (ungated addressedPainTitles — fuller than the
  // display-filtered ideaRecord value).
  mockCatalogIdeaFindUnique.mockResolvedValue({
    addressedPainTitles: ['Manual invoicing', 'Late payments'],
  });
  mockTransaction.mockImplementation(async (cb: (tx: unknown) => unknown) =>
    cb({
      job: { create: (...a: unknown[]) => mockTxJobCreate(...a) },
      catalogIdeaResearch: {
        findUnique: (...a: unknown[]) => mockCirFindUnique(...a),
        create: (...a: unknown[]) => mockCirCreate(...a),
        update: (...a: unknown[]) => mockCirUpdate(...a),
      },
      catalogIdea: { update: (...a: unknown[]) => mockCatalogIdeaUpdate(...a) },
    }),
  );

  app = express();
  app.use(express.json());
  const { catalogResearchRouter } = await import('../catalogResearch.js');
  app.use('/api/catalog', catalogResearchRouter);
});

const AUTH = { 'x-user-id': 'user-1' };

describe('POST /api/catalog/pain-research', () => {
  it('401 without auth', async () => {
    const res = await request(app).post('/api/catalog/pain-research').send({ painSlugs: ['s'] });
    expect(res.status).toBe(401);
  });

  it('single pain → 201 + enqueues one seed + entryMode pain_research', async () => {
    const res = await request(app).post('/api/catalog/pain-research').set(AUTH).send({ painSlugs: ['manual-invoicing'] });
    expect(res.status).toBe(201);
    expect(res.body.id).toBe('job-pain');
    expect(mockEnqueuePain).toHaveBeenCalledOnce();
    expect(mockEnqueuePain.mock.calls[0][1]).toHaveLength(1); // pain_seeds
    expect(mockCreateJobAndChargeDiscovery.mock.calls[0][4]).toBe('pain_research'); // entryMode
  });

  it('remix (3 pains) → 201 + 3 seeds + entryMode pain_remix', async () => {
    const res = await request(app).post('/api/catalog/pain-research').set(AUTH)
      .send({ painSlugs: ['a', 'b', 'c'] });
    expect(res.status).toBe(201);
    expect(mockEnqueuePain.mock.calls[0][1]).toHaveLength(3);
    expect(mockCreateJobAndChargeDiscovery.mock.calls[0][4]).toBe('pain_remix'); // entryMode
  });

  it('403 when a slug is locked', async () => {
    mockGetPainPointBySlug.mockResolvedValueOnce({ locked: true });
    const res = await request(app).post('/api/catalog/pain-research').set(AUTH).send({ painSlugs: ['x'] });
    expect(res.status).toBe(403);
    expect(mockEnqueuePain).not.toHaveBeenCalled();
  });

  it('402 on insufficient credits', async () => {
    mockCreateJobAndChargeDiscovery.mockRejectedValueOnce(new InsufficientCreditsError(2, 5));
    const res = await request(app).post('/api/catalog/pain-research').set(AUTH).send({ painSlugs: ['x'] });
    expect(res.status).toBe(402);
    expect(res.body.code).toBe('INSUFFICIENT_CREDITS');
  });

  it('400 on too many slugs', async () => {
    const res = await request(app).post('/api/catalog/pain-research').set(AUTH)
      .send({ painSlugs: ['a', 'b', 'c', 'd', 'e', 'f'] });
    expect(res.status).toBe(400);
  });

  it('enqueue failure → refund + FAILED', async () => {
    mockEnqueuePain.mockRejectedValueOnce(new Error('redis down'));
    const res = await request(app).post('/api/catalog/pain-research').set(AUTH).send({ painSlugs: ['x'] });
    expect(res.status).toBe(500);
    expect(mockRefundForStage).toHaveBeenCalledWith('job-pain', 'discovery');
    expect(mockJobUpdate).toHaveBeenCalledWith(expect.objectContaining({ data: { status: 'FAILED' } }));
  });

  it('post-enqueue QUEUED update failure → 201 and NO refund (job is on the queue)', async () => {
    mockJobUpdate.mockRejectedValueOnce(new Error('db blip'));
    const res = await request(app).post('/api/catalog/pain-research').set(AUTH).send({ painSlugs: ['x'] });
    expect(res.status).toBe(201);
    expect(mockEnqueuePain).toHaveBeenCalledOnce();
    expect(mockRefundForStage).not.toHaveBeenCalled();
  });

  it('remix with a locked slug mid-batch → 403 naming the slug, nothing charged', async () => {
    mockGetPainPointBySlug
      .mockResolvedValueOnce(painRecord())
      .mockResolvedValueOnce({ locked: true });
    const res = await request(app).post('/api/catalog/pain-research').set(AUTH)
      .send({ painSlugs: ['a-fine-pain', 'locked-pain', 'another-pain'] });
    expect(res.status).toBe(403);
    expect(res.body.slug).toBe('locked-pain');
    expect(mockCreateJobAndChargeDiscovery).not.toHaveBeenCalled();
    expect(mockEnqueuePain).not.toHaveBeenCalled();
  });
});

describe('POST /api/catalog/ideas/:slug/deep-research', () => {
  it('401 without auth', async () => {
    const res = await request(app).post('/api/catalog/ideas/invoiceflow/deep-research').send({});
    expect(res.status).toBe(401);
  });

  it('success → 201 + first-time counter increment', async () => {
    const res = await request(app).post('/api/catalog/ideas/invoiceflow/deep-research').set(AUTH).send({});
    expect(res.status).toBe(201);
    expect(res.body.id).toBe('job-idea');
    expect(mockCirCreate).toHaveBeenCalledOnce();
    expect(mockCatalogIdeaUpdate).toHaveBeenCalledWith(
      expect.objectContaining({ data: { researchCount: { increment: 1 } } }),
    );
    expect(mockEnqueueDeepIdea).toHaveBeenCalledOnce();
  });

  it('repeat run by same user → no counter increment', async () => {
    mockCirFindUnique.mockResolvedValueOnce({ id: 'existing' });
    const res = await request(app).post('/api/catalog/ideas/invoiceflow/deep-research').set(AUTH).send({});
    expect(res.status).toBe(201);
    expect(mockCirCreate).not.toHaveBeenCalled();
    expect(mockCatalogIdeaUpdate).not.toHaveBeenCalled();
    expect(mockCirUpdate).toHaveBeenCalledOnce(); // jobId updated
  });

  it('403 when idea is locked', async () => {
    mockGetIdeaBySlug.mockResolvedValueOnce({ locked: true });
    const res = await request(app).post('/api/catalog/ideas/invoiceflow/deep-research').set(AUTH).send({});
    expect(res.status).toBe(403);
    expect(mockEnqueueDeepIdea).not.toHaveBeenCalled();
  });

  it('seed carries the ungated addressedPainTitles from the raw row', async () => {
    const res = await request(app).post('/api/catalog/ideas/invoiceflow/deep-research').set(AUTH).send({});
    expect(res.status).toBe(201);
    expect(mockEnqueueDeepIdea.mock.calls[0][1].addressed_pain_titles).toEqual([
      'Manual invoicing',
      'Late payments',
    ]);
  });

  it('422 when the solution name is shorter than 3 chars', async () => {
    mockGetIdeaBySlug.mockResolvedValueOnce(ideaRecord({ solution_name: 'AB' }));
    const res = await request(app).post('/api/catalog/ideas/invoiceflow/deep-research').set(AUTH).send({});
    expect(res.status).toBe(422);
    expect(mockEnqueueDeepIdea).not.toHaveBeenCalled();
  });

  it('counter transaction failure does not block the paid job', async () => {
    mockCirFindUnique.mockRejectedValueOnce(new Error('db down'));
    const res = await request(app).post('/api/catalog/ideas/invoiceflow/deep-research').set(AUTH).send({});
    expect(res.status).toBe(201);
    expect(mockEnqueueDeepIdea).toHaveBeenCalledOnce();
    expect(mockCirCreate).not.toHaveBeenCalled();
  });

  it('deep enqueue failure → refund deep_research + FAILED + counter rollback', async () => {
    mockEnqueueDeepIdea.mockRejectedValueOnce(new Error('redis down'));
    const res = await request(app).post('/api/catalog/ideas/invoiceflow/deep-research').set(AUTH).send({});
    expect(res.status).toBe(500);
    expect(mockRefundForStage).toHaveBeenCalledWith('job-idea', 'deep_research');
    expect(mockJobUpdate).toHaveBeenCalledWith(expect.objectContaining({ data: { status: 'FAILED' } }));
    // First-time counter row created this click → rolled back with the decrement.
    expect(mockCirDelete).toHaveBeenCalledOnce();
    expect(mockCatalogIdeaUpdate).toHaveBeenCalledWith(
      expect.objectContaining({ data: { researchCount: { decrement: 1 } } }),
    );
  });
});
