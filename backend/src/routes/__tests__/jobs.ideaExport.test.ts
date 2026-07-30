import { describe, it, expect, vi, beforeEach } from 'vitest';
import express, { Express } from 'express';
import request from 'supertest';

const mockJobFindFirst = vi.fn();

vi.mock('../../services/db.js', () => ({
  prisma: {
    job: {
      findFirst: (...args: any[]) => mockJobFindFirst(...args),
    },
  },
}));

vi.mock('../../services/queueService.js', () => ({
  enqueueJob: vi.fn(),
  enqueueLandingPageJob: vi.fn(),
  enqueuePhase2Job: vi.fn(),
  enqueueRegenerateJob: vi.fn(),
  getQueueStats: vi.fn(),
  getQueueLength: vi.fn(),
}));

vi.mock('../../services/creditService.js', () => ({
  createJobAndChargeDiscovery: vi.fn(),
  createJobAndChargeDiscoveryInTx: vi.fn(),
  InsufficientCreditsError: class extends Error {},
  PriceChangedError: class extends Error {
    expectedCost: number;
    actualCost: number;
    constructor(expectedCost: number, actualCost: number) {
      super('Price changed');
      this.expectedCost = expectedCost;
      this.actualCost = actualCost;
    }
  },
  refundForStage: vi.fn(),
  refundForRegenerationStage: vi.fn(),
  chargeForStageInTx: vi.fn(),
  chargeForStageWithPriceCasInTx: vi.fn(),
  chargeForRegenerationInTx: vi.fn(),
  chargeForResume: vi.fn(),
  segmentForGateContinue: vi.fn(),
  chargeForSeedIdeaInTx: vi.fn(),
  refundChargeInTx: vi.fn(),
  getStageCost: vi.fn(),
}));

vi.mock('../../services/jobService.js', () => ({
  getJob: vi.fn(),
  updateJobStatus: vi.fn(),
  getJobAsset: vi.fn(),
}));

vi.mock('../../middleware/auth.js', () => ({
  requireInternalAuth: (req: any, res: any, next: any) => {
    const userId = req.headers['x-user-id'];
    if (userId) {
      req.user = { id: userId };
      return next();
    }
    res.status(401).json({ error: 'Unauthorized' });
  },
  requireInternalService: (_req: any, _res: any, next: any) => next(),
  verifyOwnership: () => true,
  AuthenticatedRequest: {},
}));

vi.mock('../../middleware/rateLimit.js', () => ({
  jobCreationLimiter: (_req: any, _res: any, next: any) => next(),
}));

vi.mock('../../config.js', () => ({
  CONFIG: { baseUrl: 'http://localhost:3001' },
}));

vi.mock('../../utils/jobFormatter.js', () => ({
  formatJobResponse: vi.fn(),
}));

vi.mock('../../utils/assetPath.js', () => ({
  resolveAssetPath: vi.fn(),
}));

let app: Express;
const authHeaders = { 'x-user-id': 'user-123' };
const jobId = '00000000-0000-0000-0000-000000000001';

const ideas = [
  { solution_name: 'Alpha', idea_id: 'idea-alpha', idea_revision: 1, market_fit_score: 0.5 },
  { solution_name: 'Alpha v2', idea_id: 'idea-alpha', idea_revision: 2, market_fit_score: 0.7 },
  { solution_name: 'Beta', idea_id: 'idea-beta', idea_revision: 1 },
];

beforeEach(async () => {
  vi.clearAllMocks();
  app = express();
  app.use(express.json());
  const { jobsRouter } = await import('../jobs.js');
  app.use('/api/jobs', jobsRouter);
});

describe('GET /api/jobs/:jobId/solutions/:ideaId/export/:format', () => {
  it('exports the exact candidate revision as markdown', async () => {
    mockJobFindFirst.mockResolvedValue({ solutionIdeas: ideas });

    const response = await request(app)
      .get(`/api/jobs/${jobId}/solutions/idea-alpha/export/md?revision=1`)
      .set(authHeaders);

    expect(response.status).toBe(200);
    expect(response.headers['content-type']).toContain('text/markdown');
    expect(response.headers['content-disposition']).toBe(
      'attachment; filename="nicheiq-idea-alpha-r1.md"',
    );
    expect(response.text).toContain('# Alpha');
    expect(response.text).toContain('revision 1');
    expect(response.text).toContain('0.5');
    expect(response.text).not.toContain('# Alpha v2');
  });

  it('exports the current revision as json when no revision is given', async () => {
    mockJobFindFirst.mockResolvedValue({ solutionIdeas: ideas });

    const response = await request(app)
      .get(`/api/jobs/${jobId}/solutions/idea-alpha/export/json`)
      .set(authHeaders);

    expect(response.status).toBe(200);
    expect(response.headers['content-type']).toContain('application/json');
    expect(response.headers['content-disposition']).toBe(
      'attachment; filename="nicheiq-idea-alpha-v2-r2.json"',
    );
    expect(response.body).toEqual(ideas[1]);
  });

  it('404s on an unknown idea or a stale revision', async () => {
    mockJobFindFirst.mockResolvedValue({ solutionIdeas: ideas });

    const unknownIdea = await request(app)
      .get(`/api/jobs/${jobId}/solutions/idea-nope/export/md`)
      .set(authHeaders);
    expect(unknownIdea.status).toBe(404);

    const staleRevision = await request(app)
      .get(`/api/jobs/${jobId}/solutions/idea-alpha/export/md?revision=9`)
      .set(authHeaders);
    expect(staleRevision.status).toBe(404);
  });

  it('400s on an invalid format or revision', async () => {
    mockJobFindFirst.mockResolvedValue({ solutionIdeas: ideas });

    const badFormat = await request(app)
      .get(`/api/jobs/${jobId}/solutions/idea-alpha/export/csv`)
      .set(authHeaders);
    expect(badFormat.status).toBe(400);

    const badRevision = await request(app)
      .get(`/api/jobs/${jobId}/solutions/idea-alpha/export/md?revision=abc`)
      .set(authHeaders);
    expect(badRevision.status).toBe(400);
  });

  it('404s when the job is not owned by the requester', async () => {
    mockJobFindFirst.mockResolvedValue(null);

    const response = await request(app)
      .get(`/api/jobs/${jobId}/solutions/idea-alpha/export/md`)
      .set(authHeaders);
    expect(response.status).toBe(404);
  });

  it('requires authentication', async () => {
    const response = await request(app).get(`/api/jobs/${jobId}/solutions/idea-alpha/export/md`);
    expect(response.status).toBe(401);
  });
});
