import { describe, it, expect, vi, beforeEach } from 'vitest';
import express, { Express } from 'express';
import request from 'supertest';

// ============================================
// Mock adminService
// ============================================
const mockGetDashboardStats = vi.fn();
const mockGetReportStats = vi.fn();
const mockListPromoCodes = vi.fn();
const mockCreatePromoCode = vi.fn();
const mockUpdatePromoCode = vi.fn();
const mockGetPromoCodeRedemptions = vi.fn();
const mockListUsers = vi.fn();
const mockGetUserDetail = vi.fn();
const mockUpdateUserRole = vi.fn();
const mockListAllPackages = vi.fn();
const mockCreatePackage = vi.fn();
const mockUpdatePackage = vi.fn();

vi.mock('../../services/adminService.js', () => ({
  getDashboardStats: (...args: any[]) => mockGetDashboardStats(...args),
  getReportStats: (...args: any[]) => mockGetReportStats(...args),
  listPromoCodes: (...args: any[]) => mockListPromoCodes(...args),
  createPromoCode: (...args: any[]) => mockCreatePromoCode(...args),
  updatePromoCode: (...args: any[]) => mockUpdatePromoCode(...args),
  getPromoCodeRedemptions: (...args: any[]) => mockGetPromoCodeRedemptions(...args),
  listUsers: (...args: any[]) => mockListUsers(...args),
  getUserDetail: (...args: any[]) => mockGetUserDetail(...args),
  updateUserRole: (...args: any[]) => mockUpdateUserRole(...args),
  listAllPackages: (...args: any[]) => mockListAllPackages(...args),
  createPackage: (...args: any[]) => mockCreatePackage(...args),
  updatePackage: (...args: any[]) => mockUpdatePackage(...args),
}));

// Mock auth middleware
vi.mock('../../middleware/auth.js', () => ({
  requireInternalAdmin: (req: any, res: any, next: any) => {
    const serviceSecret = req.headers['x-internal-service'];
    const userRole = req.headers['x-user-role'];
    const userId = req.headers['x-user-id'];
    if (serviceSecret !== 'test-secret') {
      return res.status(401).json({ error: 'Authentication required' });
    }
    if (!userId) {
      return res.status(401).json({ error: 'Authentication required' });
    }
    if (userRole !== 'ADMIN') {
      return res.status(403).json({ error: 'Admin access required' });
    }
    req.user = { id: userId, email: req.headers['x-user-email'], role: 'ADMIN' };
    next();
  },
  AuthenticatedRequest: {},
}));

// ============================================
// Fixtures
// ============================================
const adminHeaders = {
  'x-internal-service': 'test-secret',
  'x-user-id': 'admin-123',
  'x-user-role': 'ADMIN',
  'x-user-email': 'admin@test.com',
};

const userHeaders = {
  'x-internal-service': 'test-secret',
  'x-user-id': 'user-123',
  'x-user-role': 'USER',
};

const fixtures = {
  dashboardStats: {
    totalUsers: 100,
    totalJobs: 50,
    activeJobs: 5,
    completedJobs: 40,
    failedJobs: 5,
    totalCreditsPurchased: 500,
    totalCreditsUsed: 200,
  },
  reportStats: {
    totalJobs: 50,
    completedJobs: 40,
    failedJobs: 5,
    successRate: 80,
    failureRate: 10,
    avgDurationSeconds: 120,
    failuresByStage: [],
    recentJobs: [],
  },
  promoCodeList: {
    promoCodes: [{ id: 'promo-1', code: 'TEST10', creditAmount: 10, isActive: true }],
    total: 1,
    page: 1,
    limit: 20,
    totalPages: 1,
  },
  createdPromo: { id: 'promo-new', code: 'NEW50', creditAmount: 50, isActive: true },
  usersList: {
    users: [{ id: 'u1', email: 'u@test.com', name: 'Test', role: 'USER', creditBalance: 5, jobCount: 2 }],
    total: 1,
    page: 1,
    limit: 20,
    totalPages: 1,
  },
  userDetail: { id: 'u1', email: 'u@test.com', name: 'Test', role: 'USER', creditBalance: 5, jobCount: 2, recentJobs: [] },
  packagesList: { packages: [{ id: 'pkg-1', name: 'Starter', credits: 5, priceInCents: 999, isActive: true }] },
};

// ============================================
// Setup
// ============================================
let app: Express;

beforeEach(async () => {
  vi.clearAllMocks();

  app = express();
  app.use(express.json());

  const { adminRouter } = await import('../admin.js');
  app.use('/api/admin', adminRouter);
});

// ============================================
// Auth enforcement (shared tests)
// ============================================
describe('Admin route auth enforcement', () => {
  it('returns 401 when no internal service header', async () => {
    await request(app).get('/api/admin/dashboard').expect(401);
  });

  it('returns 403 when user role is not ADMIN', async () => {
    await request(app).get('/api/admin/dashboard').set(userHeaders).expect(403);
  });

  it('returns 200 for admin user', async () => {
    mockGetDashboardStats.mockResolvedValue(fixtures.dashboardStats);
    await request(app).get('/api/admin/dashboard').set(adminHeaders).expect(200);
  });
});

// ============================================
// Dashboard
// ============================================
describe('GET /api/admin/dashboard', () => {
  it('returns dashboard stats', async () => {
    mockGetDashboardStats.mockResolvedValue(fixtures.dashboardStats);

    const response = await request(app)
      .get('/api/admin/dashboard')
      .set(adminHeaders)
      .expect(200);

    expect(response.body).toEqual(fixtures.dashboardStats);
    expect(mockGetDashboardStats).toHaveBeenCalled();
  });
});

// ============================================
// Report Stats
// ============================================
describe('GET /api/admin/reports', () => {
  it('returns report stats', async () => {
    mockGetReportStats.mockResolvedValue(fixtures.reportStats);

    const response = await request(app)
      .get('/api/admin/reports')
      .set(adminHeaders)
      .expect(200);

    expect(response.body).toEqual(fixtures.reportStats);
  });
});

// ============================================
// Promo Codes
// ============================================
describe('Promo Codes', () => {
  it('GET /api/admin/promo-codes returns paginated list', async () => {
    mockListPromoCodes.mockResolvedValue(fixtures.promoCodeList);

    const response = await request(app)
      .get('/api/admin/promo-codes')
      .set(adminHeaders)
      .expect(200);

    expect(response.body.promoCodes).toHaveLength(1);
    expect(mockListPromoCodes).toHaveBeenCalledWith(1, 20);
  });

  it('POST /api/admin/promo-codes creates code', async () => {
    mockCreatePromoCode.mockResolvedValue(fixtures.createdPromo);

    const response = await request(app)
      .post('/api/admin/promo-codes')
      .set(adminHeaders)
      .send({ code: 'NEW50', creditAmount: 50 })
      .expect(201);

    expect(response.body.code).toBe('NEW50');
    expect(mockCreatePromoCode).toHaveBeenCalledWith(expect.objectContaining({
      code: 'NEW50',
      creditAmount: 50,
      createdBy: 'admin-123',
    }));
  });

  it('POST /api/admin/promo-codes returns 400 on invalid input', async () => {
    await request(app)
      .post('/api/admin/promo-codes')
      .set(adminHeaders)
      .send({ code: '', creditAmount: -1 })
      .expect(400);
  });

  it('PATCH /api/admin/promo-codes/:id updates code', async () => {
    mockUpdatePromoCode.mockResolvedValue({ id: 'promo-1', isActive: false });

    const response = await request(app)
      .patch('/api/admin/promo-codes/promo-1')
      .set(adminHeaders)
      .send({ isActive: false })
      .expect(200);

    expect(response.body.isActive).toBe(false);
  });

  it('PATCH /api/admin/promo-codes/:id returns 404 if not found', async () => {
    mockUpdatePromoCode.mockRejectedValue({ code: 'P2025' });

    await request(app)
      .patch('/api/admin/promo-codes/nonexistent')
      .set(adminHeaders)
      .send({ isActive: false })
      .expect(404);
  });

  it('GET /api/admin/promo-codes/:id/redemptions returns list', async () => {
    mockGetPromoCodeRedemptions.mockResolvedValue([]);

    const response = await request(app)
      .get('/api/admin/promo-codes/promo-1/redemptions')
      .set(adminHeaders)
      .expect(200);

    expect(response.body.redemptions).toEqual([]);
  });
});

// ============================================
// Users
// ============================================
describe('Users', () => {
  it('GET /api/admin/users returns paginated list', async () => {
    mockListUsers.mockResolvedValue(fixtures.usersList);

    const response = await request(app)
      .get('/api/admin/users')
      .set(adminHeaders)
      .expect(200);

    expect(response.body.users).toHaveLength(1);
    expect(mockListUsers).toHaveBeenCalledWith(1, 20, undefined);
  });

  it('GET /api/admin/users supports search param', async () => {
    mockListUsers.mockResolvedValue(fixtures.usersList);

    await request(app)
      .get('/api/admin/users?search=test')
      .set(adminHeaders)
      .expect(200);

    expect(mockListUsers).toHaveBeenCalledWith(1, 20, 'test');
  });

  it('GET /api/admin/users/:userId returns user detail', async () => {
    mockGetUserDetail.mockResolvedValue(fixtures.userDetail);

    const response = await request(app)
      .get('/api/admin/users/u1')
      .set(adminHeaders)
      .expect(200);

    expect(response.body.email).toBe('u@test.com');
  });

  it('GET /api/admin/users/:userId returns 404 if not found', async () => {
    mockGetUserDetail.mockResolvedValue(null);

    await request(app)
      .get('/api/admin/users/nonexistent')
      .set(adminHeaders)
      .expect(404);
  });

  it('PATCH /api/admin/users/:userId/role updates role', async () => {
    mockUpdateUserRole.mockResolvedValue({ id: 'u1', email: 'u@test.com', role: 'ADMIN' });

    const response = await request(app)
      .patch('/api/admin/users/u1/role')
      .set(adminHeaders)
      .send({ role: 'ADMIN' })
      .expect(200);

    expect(response.body.role).toBe('ADMIN');
  });

  it('PATCH /api/admin/users/:userId/role validates role value', async () => {
    await request(app)
      .patch('/api/admin/users/u1/role')
      .set(adminHeaders)
      .send({ role: 'SUPERADMIN' })
      .expect(400);
  });
});

// ============================================
// Packages
// ============================================
describe('Packages', () => {
  it('GET /api/admin/packages returns all packages', async () => {
    mockListAllPackages.mockResolvedValue(fixtures.packagesList.packages);

    const response = await request(app)
      .get('/api/admin/packages')
      .set(adminHeaders)
      .expect(200);

    expect(response.body.packages).toHaveLength(1);
  });

  it('POST /api/admin/packages creates package', async () => {
    const newPkg = { id: 'pkg-new', name: 'Pro', credits: 10, priceInCents: 1999, stripePriceId: 'price_test' };
    mockCreatePackage.mockResolvedValue(newPkg);

    const response = await request(app)
      .post('/api/admin/packages')
      .set(adminHeaders)
      .send({ name: 'Pro', credits: 10, priceInCents: 1999, stripePriceId: 'price_test' })
      .expect(201);

    expect(response.body.name).toBe('Pro');
  });

  it('POST /api/admin/packages validates required fields', async () => {
    await request(app)
      .post('/api/admin/packages')
      .set(adminHeaders)
      .send({ name: 'Pro' }) // missing credits, priceInCents, stripePriceId
      .expect(400);
  });

  it('PATCH /api/admin/packages/:id updates package', async () => {
    mockUpdatePackage.mockResolvedValue({ id: 'pkg-1', name: 'Starter', isActive: false });

    const response = await request(app)
      .patch('/api/admin/packages/pkg-1')
      .set(adminHeaders)
      .send({ isActive: false })
      .expect(200);

    expect(response.body.isActive).toBe(false);
  });

  it('PATCH /api/admin/packages/:id returns 404 if not found', async () => {
    mockUpdatePackage.mockRejectedValue({ code: 'P2025' });

    await request(app)
      .patch('/api/admin/packages/nonexistent')
      .set(adminHeaders)
      .send({ isActive: false })
      .expect(404);
  });
});
