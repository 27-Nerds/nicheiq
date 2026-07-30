import { describe, it, expect, vi, beforeEach } from 'vitest';
import express, { Express } from 'express';
import request from 'supertest';

// ============================================
// Mock functions
// ============================================
const mockGetJob = vi.fn();
const mockGetJobAsset = vi.fn();
const mockFindUniqueShare = vi.fn();
const mockCreateShare = vi.fn();
const mockUpdateShare = vi.fn();

// ============================================
// Mocks
// ============================================

vi.mock('../../services/db.js', () => ({
  prisma: {
    reportShare: {
      findUnique: (...args: any[]) => mockFindUniqueShare(...args),
      create: (...args: any[]) => mockCreateShare(...args),
      update: (...args: any[]) => mockUpdateShare(...args),
    },
  },
}));

vi.mock('../../services/jobService.js', () => ({
  getJob: (...args: any[]) => mockGetJob(...args),
  getJobAsset: (...args: any[]) => mockGetJobAsset(...args),
}));

vi.mock('../../middleware/auth.js', () => ({
  requireInternalAuth: (req: any, res: any, next: any) => {
    const serviceSecret = req.headers['x-internal-service'];
    if (serviceSecret !== 'test-secret') {
      return res.status(401).json({ error: 'Authentication required' });
    }
    const userId = req.headers['x-user-id'];
    if (!userId) {
      return res.status(401).json({ error: 'Authentication required' });
    }
    req.user = {
      id: userId,
      email: req.headers['x-user-email'],
      role: req.headers['x-user-role'],
    };
    next();
  },
  verifyOwnership: (req: any, resourceUserId: string | null | undefined) => {
    if (!req.user) return false;
    return req.user.id === resourceUserId;
  },
  AuthenticatedRequest: {},
}));

vi.mock('../../utils/assetPath.js', () => ({
  resolveAssetPath: () => '/test/path/report.json',
}));

const mockExistsSync = vi.fn().mockReturnValue(true);
const mockReadFileSync = vi.fn().mockReturnValue(
  JSON.stringify({
    niche: 'Test Niche',
    executive_summary: 'Test summary',
    research_metadata: { secret: 'data' },
    seo_calculation_transparency: { internal: 'info' },
    data_quality_summary: {
      overall_data_quality: 'HIGH',
      quality_caveats: ['One source was incomplete.'],
    },
    stage_timing_summary: { total: 120 },
  })
);

vi.mock('fs', () => ({
  existsSync: (...args: any[]) => mockExistsSync(...args),
  readFileSync: (...args: any[]) => mockReadFileSync(...args),
}));

vi.mock('express-rate-limit', () => ({
  default: () => (_req: any, _res: any, next: any) => next(),
}));

vi.mock('../../config.js', () => ({
  CONFIG: {
    nodeEnv: 'test',
    isDev: true,
  },
}));

// ============================================
// Fixtures
// ============================================
const TEST_JOB_ID = '550e8400-e29b-41d4-a716-446655440000';
const TEST_USER_ID = 'user-123';
const OTHER_USER_ID = 'user-999';
const TEST_SHARE_TOKEN = 'abcdefghijklmnopqrstuv'; // 22 chars

const authHeaders = {
  'x-internal-service': 'test-secret',
  'x-user-id': TEST_USER_ID,
  'x-user-role': 'USER',
  'x-user-email': 'user@test.com',
};

const completedJob = {
  id: TEST_JOB_ID,
  userId: TEST_USER_ID,
  status: 'COMPLETED',
  niche: 'Test Niche',
};

const runningJob = {
  id: TEST_JOB_ID,
  userId: TEST_USER_ID,
  status: 'RUNNING',
  niche: 'Test Niche',
};

const otherUserJob = {
  id: TEST_JOB_ID,
  userId: OTHER_USER_ID,
  status: 'COMPLETED',
  niche: 'Test Niche',
};

const activeShare = {
  id: 'share-1',
  jobId: TEST_JOB_ID,
  userId: TEST_USER_ID,
  shareToken: TEST_SHARE_TOKEN,
  isActive: true,
  viewCount: 5,
  lastViewedAt: new Date(),
  createdAt: new Date(),
  updatedAt: new Date(),
};

const inactiveShare = {
  ...activeShare,
  isActive: false,
};

// ============================================
// Setup
// ============================================
let app: Express;

beforeEach(async () => {
  vi.clearAllMocks();

  app = express();
  app.use(express.json());

  const { sharesRouter, publicShareRouter } = await import('../shares.js');
  app.use('/api/jobs', sharesRouter);
  app.use('/api/shared', publicShareRouter);
});

// ============================================
// GET /api/jobs/:jobId/share
// ============================================
describe('GET /api/jobs/:jobId/share', () => {
  it('returns isShared false when no share exists', async () => {
    mockGetJob.mockResolvedValue(completedJob);
    mockFindUniqueShare.mockResolvedValue(null);

    const response = await request(app)
      .get(`/api/jobs/${TEST_JOB_ID}/share`)
      .set(authHeaders)
      .expect(200);

    expect(response.body).toEqual({ isShared: false });
  });

  it('returns isShared false when share exists but is inactive', async () => {
    mockGetJob.mockResolvedValue(completedJob);
    mockFindUniqueShare.mockResolvedValue(inactiveShare);

    const response = await request(app)
      .get(`/api/jobs/${TEST_JOB_ID}/share`)
      .set(authHeaders)
      .expect(200);

    expect(response.body).toEqual({ isShared: false });
  });

  it('returns share info when active share exists', async () => {
    mockGetJob.mockResolvedValue(completedJob);
    mockFindUniqueShare.mockResolvedValue(activeShare);

    const response = await request(app)
      .get(`/api/jobs/${TEST_JOB_ID}/share`)
      .set(authHeaders)
      .expect(200);

    expect(response.body).toEqual({
      isShared: true,
      shareToken: TEST_SHARE_TOKEN,
      viewCount: 5,
    });
  });

  it('returns 400 for invalid UUID format', async () => {
    await request(app)
      .get('/api/jobs/not-a-uuid/share')
      .set(authHeaders)
      .expect(400);
  });

  it('returns 404 when job not found', async () => {
    mockGetJob.mockResolvedValue(null);

    await request(app)
      .get(`/api/jobs/${TEST_JOB_ID}/share`)
      .set(authHeaders)
      .expect(404);
  });

  it('returns 403 when user does not own job', async () => {
    mockGetJob.mockResolvedValue(otherUserJob);

    await request(app)
      .get(`/api/jobs/${TEST_JOB_ID}/share`)
      .set(authHeaders)
      .expect(403);
  });
});

// ============================================
// POST /api/jobs/:jobId/share
// ============================================
describe('POST /api/jobs/:jobId/share', () => {
  it('creates new share for completed job', async () => {
    mockGetJob.mockResolvedValue(completedJob);
    mockFindUniqueShare.mockResolvedValue(null);
    mockCreateShare.mockResolvedValue(activeShare);

    const response = await request(app)
      .post(`/api/jobs/${TEST_JOB_ID}/share`)
      .set(authHeaders)
      .expect(200);

    expect(response.body).toEqual({
      isShared: true,
      shareToken: TEST_SHARE_TOKEN,
      viewCount: 5,
    });
    expect(mockCreateShare).toHaveBeenCalledWith({
      data: expect.objectContaining({
        jobId: TEST_JOB_ID,
        userId: TEST_USER_ID,
        isActive: true,
      }),
    });
  });

  it('reactivates existing inactive share and preserves token', async () => {
    mockGetJob.mockResolvedValue(completedJob);
    mockFindUniqueShare.mockResolvedValue(inactiveShare);
    mockUpdateShare.mockResolvedValue(activeShare);

    const response = await request(app)
      .post(`/api/jobs/${TEST_JOB_ID}/share`)
      .set(authHeaders)
      .expect(200);

    expect(response.body.isShared).toBe(true);
    expect(response.body.shareToken).toBe(TEST_SHARE_TOKEN);
    expect(mockUpdateShare).toHaveBeenCalledWith({
      where: { jobId: TEST_JOB_ID },
      data: { isActive: true },
    });
    expect(mockCreateShare).not.toHaveBeenCalled();
  });

  it('returns 400 when job is not COMPLETED', async () => {
    mockGetJob.mockResolvedValue(runningJob);

    const response = await request(app)
      .post(`/api/jobs/${TEST_JOB_ID}/share`)
      .set(authHeaders)
      .expect(400);

    expect(response.body.error).toBe('Only completed jobs can be shared');
  });

  it('returns 404 when job not found', async () => {
    mockGetJob.mockResolvedValue(null);

    await request(app)
      .post(`/api/jobs/${TEST_JOB_ID}/share`)
      .set(authHeaders)
      .expect(404);
  });

  it('returns 403 when user does not own job', async () => {
    mockGetJob.mockResolvedValue(otherUserJob);

    await request(app)
      .post(`/api/jobs/${TEST_JOB_ID}/share`)
      .set(authHeaders)
      .expect(403);
  });
});

// ============================================
// DELETE /api/jobs/:jobId/share
// ============================================
describe('DELETE /api/jobs/:jobId/share', () => {
  it('sets isActive false on existing share', async () => {
    mockGetJob.mockResolvedValue(completedJob);
    mockFindUniqueShare.mockResolvedValue(activeShare);
    mockUpdateShare.mockResolvedValue(inactiveShare);

    const response = await request(app)
      .delete(`/api/jobs/${TEST_JOB_ID}/share`)
      .set(authHeaders)
      .expect(200);

    expect(response.body).toEqual({ isShared: false });
    expect(mockUpdateShare).toHaveBeenCalledWith({
      where: { jobId: TEST_JOB_ID },
      data: { isActive: false },
    });
  });

  it('returns isShared false gracefully when no share exists', async () => {
    mockGetJob.mockResolvedValue(completedJob);
    mockFindUniqueShare.mockResolvedValue(null);

    const response = await request(app)
      .delete(`/api/jobs/${TEST_JOB_ID}/share`)
      .set(authHeaders)
      .expect(200);

    expect(response.body).toEqual({ isShared: false });
    expect(mockUpdateShare).not.toHaveBeenCalled();
  });

  it('returns 404 when job not found', async () => {
    mockGetJob.mockResolvedValue(null);

    await request(app)
      .delete(`/api/jobs/${TEST_JOB_ID}/share`)
      .set(authHeaders)
      .expect(404);
  });

  it('returns 403 when user does not own job', async () => {
    mockGetJob.mockResolvedValue(otherUserJob);

    await request(app)
      .delete(`/api/jobs/${TEST_JOB_ID}/share`)
      .set(authHeaders)
      .expect(403);
  });
});

// ============================================
// POST /api/jobs/:jobId/share/regenerate
// ============================================
describe('POST /api/jobs/:jobId/share/regenerate', () => {
  it('generates new token and resets viewCount', async () => {
    const newToken = 'ZZZZZZZZZZZZZZZZZZZZZZ';
    mockGetJob.mockResolvedValue(completedJob);
    mockFindUniqueShare.mockResolvedValue(activeShare);
    mockUpdateShare.mockResolvedValue({
      ...activeShare,
      shareToken: newToken,
      viewCount: 0,
      lastViewedAt: null,
    });

    const response = await request(app)
      .post(`/api/jobs/${TEST_JOB_ID}/share/regenerate`)
      .set(authHeaders)
      .expect(200);

    expect(response.body).toEqual({
      isShared: true,
      shareToken: newToken,
      viewCount: 0,
    });
    expect(mockUpdateShare).toHaveBeenCalledWith({
      where: { jobId: TEST_JOB_ID },
      data: expect.objectContaining({
        viewCount: 0,
        lastViewedAt: null,
        isActive: true,
      }),
    });
  });

  it('returns 404 when sharing not enabled', async () => {
    mockGetJob.mockResolvedValue(completedJob);
    mockFindUniqueShare.mockResolvedValue(null);

    const response = await request(app)
      .post(`/api/jobs/${TEST_JOB_ID}/share/regenerate`)
      .set(authHeaders)
      .expect(404);

    expect(response.body.error).toBe('Sharing not enabled for this job');
  });

  it('returns 404 when job not found', async () => {
    mockGetJob.mockResolvedValue(null);

    await request(app)
      .post(`/api/jobs/${TEST_JOB_ID}/share/regenerate`)
      .set(authHeaders)
      .expect(404);
  });

  it('returns 403 when user does not own job', async () => {
    mockGetJob.mockResolvedValue(otherUserJob);

    await request(app)
      .post(`/api/jobs/${TEST_JOB_ID}/share/regenerate`)
      .set(authHeaders)
      .expect(403);
  });
});

// ============================================
// GET /api/shared/:shareToken (public)
// ============================================
describe('GET /api/shared/:shareToken', () => {
  it('returns sanitized report for valid active token', async () => {
    mockFindUniqueShare.mockResolvedValue({
      ...activeShare,
      job: completedJob,
    });
    mockGetJobAsset.mockResolvedValue({ filePath: 'output/report.json' });
    // fire-and-forget update — resolve silently
    mockUpdateShare.mockResolvedValue({});

    const response = await request(app)
      .get(`/api/shared/${TEST_SHARE_TOKEN}`)
      .expect(200);

    expect(response.body).toEqual({
      niche: 'Test Niche',
      executive_summary: 'Test summary',
      research_metadata: { secret: 'data' },
      seo_calculation_transparency: { internal: 'info' },
      data_quality_summary: {
        overall_data_quality: 'HIGH',
        quality_caveats: ['One source was incomplete.'],
      },
    });
  });

  it('keeps research quality and strips only execution timing from shared reports', async () => {
    mockFindUniqueShare.mockResolvedValue({
      ...activeShare,
      job: completedJob,
    });
    mockGetJobAsset.mockResolvedValue({ filePath: 'output/report.json' });
    mockUpdateShare.mockResolvedValue({});

    const response = await request(app)
      .get(`/api/shared/${TEST_SHARE_TOKEN}`)
      .expect(200);

    expect(response.body).toHaveProperty('research_metadata');
    expect(response.body).toHaveProperty('seo_calculation_transparency');
    expect(response.body).toEqual(expect.objectContaining({
      data_quality_summary: {
        overall_data_quality: 'HIGH',
        quality_caveats: ['One source was incomplete.'],
      },
    }));
    expect(response.body).not.toHaveProperty('stage_timing_summary');
  });

  it('sets X-Robots-Tag header', async () => {
    mockFindUniqueShare.mockResolvedValue({
      ...activeShare,
      job: completedJob,
    });
    mockGetJobAsset.mockResolvedValue({ filePath: 'output/report.json' });
    mockUpdateShare.mockResolvedValue({});

    const response = await request(app)
      .get(`/api/shared/${TEST_SHARE_TOKEN}`)
      .expect(200);

    expect(response.headers['x-robots-tag']).toBe('noindex, nofollow');
  });

  it('sets Cache-Control header', async () => {
    mockFindUniqueShare.mockResolvedValue({
      ...activeShare,
      job: completedJob,
    });
    mockGetJobAsset.mockResolvedValue({ filePath: 'output/report.json' });
    mockUpdateShare.mockResolvedValue({});

    const response = await request(app)
      .get(`/api/shared/${TEST_SHARE_TOKEN}`)
      .expect(200);

    expect(response.headers['cache-control']).toBe('private, no-store');
  });

  it('sets Referrer-Policy header', async () => {
    mockFindUniqueShare.mockResolvedValue({
      ...activeShare,
      job: completedJob,
    });
    mockGetJobAsset.mockResolvedValue({ filePath: 'output/report.json' });
    mockUpdateShare.mockResolvedValue({});

    const response = await request(app)
      .get(`/api/shared/${TEST_SHARE_TOKEN}`)
      .expect(200);

    expect(response.headers['referrer-policy']).toBe('no-referrer');
  });

  it('increments viewCount (fire-and-forget)', async () => {
    mockFindUniqueShare.mockResolvedValue({
      ...activeShare,
      job: completedJob,
    });
    mockGetJobAsset.mockResolvedValue({ filePath: 'output/report.json' });
    mockUpdateShare.mockResolvedValue({});

    await request(app)
      .get(`/api/shared/${TEST_SHARE_TOKEN}`)
      .expect(200);

    expect(mockUpdateShare).toHaveBeenCalledWith({
      where: { id: activeShare.id },
      data: expect.objectContaining({
        viewCount: { increment: 1 },
      }),
    });
  });

  it('returns 404 for invalid token format (not 22 chars)', async () => {
    const response = await request(app)
      .get('/api/shared/tooshort')
      .expect(404);

    expect(response.body).toEqual({ error: 'Not found' });
  });

  it('returns 404 for non-existent token', async () => {
    mockFindUniqueShare.mockResolvedValue(null);

    const response = await request(app)
      .get(`/api/shared/${TEST_SHARE_TOKEN}`)
      .expect(404);

    expect(response.body).toEqual({ error: 'Not found' });
  });

  it('returns 404 for inactive share', async () => {
    mockFindUniqueShare.mockResolvedValue({
      ...inactiveShare,
      job: completedJob,
    });

    const response = await request(app)
      .get(`/api/shared/${TEST_SHARE_TOKEN}`)
      .expect(404);

    expect(response.body).toEqual({ error: 'Not found' });
  });

  it('returns 404 for non-COMPLETED job', async () => {
    mockFindUniqueShare.mockResolvedValue({
      ...activeShare,
      job: runningJob,
    });

    const response = await request(app)
      .get(`/api/shared/${TEST_SHARE_TOKEN}`)
      .expect(404);

    expect(response.body).toEqual({ error: 'Not found' });
  });

  it('returns 404 when report file does not exist', async () => {
    mockExistsSync.mockReturnValueOnce(false);

    mockFindUniqueShare.mockResolvedValue({
      ...activeShare,
      job: completedJob,
    });
    mockGetJobAsset.mockResolvedValue({ filePath: 'output/report.json' });

    const response = await request(app)
      .get(`/api/shared/${TEST_SHARE_TOKEN}`)
      .expect(404);

    expect(response.body).toEqual({ error: 'Not found' });
  });

  it('all 404 responses have identical body for anti-enumeration', async () => {
    const expectedBody = { error: 'Not found' };

    // Invalid format
    const r1 = await request(app).get('/api/shared/short').expect(404);
    expect(r1.body).toEqual(expectedBody);

    // Non-existent token
    mockFindUniqueShare.mockResolvedValue(null);
    const r2 = await request(app).get(`/api/shared/${TEST_SHARE_TOKEN}`).expect(404);
    expect(r2.body).toEqual(expectedBody);

    // Inactive share
    mockFindUniqueShare.mockResolvedValue({
      ...inactiveShare,
      job: completedJob,
    });
    const r3 = await request(app).get(`/api/shared/${TEST_SHARE_TOKEN}`).expect(404);
    expect(r3.body).toEqual(expectedBody);
  });
});
