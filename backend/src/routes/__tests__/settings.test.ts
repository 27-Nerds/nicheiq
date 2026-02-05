import { describe, it, expect, vi, beforeEach } from 'vitest';
import express, { Express } from 'express';
import request from 'supertest';

// ============================================
// Mock adminService
// ============================================
const mockGetAppSetting = vi.fn();

vi.mock('../../services/adminService.js', () => ({
  getAppSetting: (...args: any[]) => mockGetAppSetting(...args),
}));

// Mock auth middleware
vi.mock('../../middleware/auth.js', () => ({
  requireInternalService: (req: any, res: any, next: any) => {
    const serviceSecret = req.headers['x-internal-service'];
    if (serviceSecret !== 'test-secret') {
      return res.status(401).json({ error: 'Unauthorized' });
    }
    next();
  },
}));

// ============================================
// Fixtures
// ============================================
const internalHeaders = {
  'x-internal-service': 'test-secret',
};

// ============================================
// Setup
// ============================================
let app: Express;

beforeEach(async () => {
  vi.clearAllMocks();

  app = express();
  app.use(express.json());

  const { settingsRouter } = await import('../settings.js');
  app.use('/api/settings', settingsRouter);
});

// ============================================
// Settings Router
// ============================================
describe('GET /api/settings/sample-report-url', () => {
  it('returns URL when setting exists', async () => {
    mockGetAppSetting.mockResolvedValue('/shared/abc123');

    const response = await request(app)
      .get('/api/settings/sample-report-url')
      .set(internalHeaders)
      .expect(200);

    expect(response.body).toEqual({ url: '/shared/abc123' });
    expect(mockGetAppSetting).toHaveBeenCalledWith('sample_report_url');
  });

  it('returns { url: null } when no setting exists', async () => {
    mockGetAppSetting.mockResolvedValue(null);

    const response = await request(app)
      .get('/api/settings/sample-report-url')
      .set(internalHeaders)
      .expect(200);

    expect(response.body).toEqual({ url: null });
  });

  it('returns 401 without internal service header', async () => {
    await request(app)
      .get('/api/settings/sample-report-url')
      .expect(401);
  });

  it('returns { url: null } on DB error', async () => {
    mockGetAppSetting.mockRejectedValue(new Error('DB error'));

    const response = await request(app)
      .get('/api/settings/sample-report-url')
      .set(internalHeaders)
      .expect(200);

    expect(response.body).toEqual({ url: null });
  });
});
