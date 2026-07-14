import { describe, it, expect, vi, beforeEach } from 'vitest';
import express, { Express } from 'express';
import request from 'supertest';
import { JobStatus } from '@prisma/client';
import { Readable } from 'stream';

// ============================================
// Mock dependencies
// ============================================
const mockJobFindFirst = vi.fn();
const mockJobFindUnique = vi.fn();
const mockJobUpdate = vi.fn();
const mockUpdateMany = vi.fn();
const mockCreditTransactionFindFirst = vi.fn();
const mockCreditTransactionDelete = vi.fn();
const mockUserCreditsFindUnique = vi.fn();
const mockUserCreditsUpdate = vi.fn();
const mockPrismaTransaction = vi.fn();

vi.mock('../../services/db.js', () => ({
  prisma: {
    job: {
      findFirst: (...args: any[]) => mockJobFindFirst(...args),
      findUnique: (...args: any[]) => mockJobFindUnique(...args),
      update: (...args: any[]) => mockJobUpdate(...args),
    },
    jobProgress: {
      updateMany: (...args: any[]) => mockUpdateMany(...args),
    },
    creditTransaction: {
      findFirst: (...args: any[]) => mockCreditTransactionFindFirst(...args),
      delete: (...args: any[]) => mockCreditTransactionDelete(...args),
    },
    userCredits: {
      findUnique: (...args: any[]) => mockUserCreditsFindUnique(...args),
      update: (...args: any[]) => mockUserCreditsUpdate(...args),
    },
    $transaction: (...args: any[]) => mockPrismaTransaction(...args),
  },
}));

const mockGetJob = vi.fn();
const mockGetJobAsset = vi.fn();
const mockUpdateJobStatus = vi.fn();
const mockCancelJob = vi.fn();

vi.mock('../../services/jobService.js', () => ({
  getJob: (...args: any[]) => mockGetJob(...args),
  updateJobStatus: (...args: any[]) => mockUpdateJobStatus(...args),
  getJobAsset: (...args: any[]) => mockGetJobAsset(...args),
  cancelJob: (...args: any[]) => mockCancelJob(...args),
}));

const mockCreateJobAndChargeDiscovery = vi.fn();

vi.mock('../../services/creditService.js', () => ({
  createJobAndChargeDiscovery: (...args: any[]) => mockCreateJobAndChargeDiscovery(...args),
  refundForStage: vi.fn(),
  chargeForResume: vi.fn().mockResolvedValue({ charged: false, amount: 0 }),
  chargeForStageInTx: vi.fn().mockResolvedValue({ cost: 5 }),
  getStageCost: vi.fn().mockResolvedValue(5),
  InsufficientCreditsError: class InsufficientCreditsError extends Error {
    currentBalance: number;
    required: number;
    constructor(currentBalance: number, required: number) {
      super(`Insufficient credits: have ${currentBalance}, need ${required}`);
      this.currentBalance = currentBalance;
      this.required = required;
    }
  },
}));

const mockEnqueueJob = vi.fn();
const mockGetQueueStats = vi.fn();
const mockGetQueueLength = vi.fn();

vi.mock('../../services/queueService.js', () => ({
  enqueueJob: (...args: any[]) => mockEnqueueJob(...args),
  enqueueLandingPageJob: vi.fn(),
  enqueuePhase2Job: vi.fn(),
  enqueueRegenerateJob: vi.fn(),
  getQueueStats: (...args: any[]) => mockGetQueueStats(...args),
  getQueueLength: (...args: any[]) => mockGetQueueLength(...args),
}));

// ============================================
// Auth mocks that enforce the service secret check
// ============================================
const TEST_SERVICE_SECRET = 'test-internal-secret';

vi.mock('../../middleware/auth.js', () => ({
  requireInternalAuth: (req: any, res: any, next: any) => {
    if (req.headers['x-internal-service'] !== TEST_SERVICE_SECRET) {
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
  requireInternalService: (req: any, res: any, next: any) => {
    if (req.headers['x-internal-service'] !== TEST_SERVICE_SECRET) {
      return res.status(401).json({ error: 'Unauthorized' });
    }
    next();
  },
  verifyOwnership: (req: any, resourceUserId: string) => {
    return req.user?.id === resourceUserId;
  },
  AuthenticatedRequest: {},
}));

vi.mock('../../middleware/rateLimit.js', () => ({
  jobCreationLimiter: (_req: any, _res: any, next: any) => next(),
}));

const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

vi.mock('../../middleware/validation.js', () => ({
  validateJobId: (req: any, res: any, next: any) => {
    const { jobId } = req.params;
    if (!jobId || !UUID_REGEX.test(jobId)) {
      return res.status(400).json({ error: 'Invalid job ID format' });
    }
    next();
  },
}));

vi.mock('../../config.js', () => ({
  CONFIG: { baseUrl: 'http://localhost:3001' },
}));

vi.mock('../../utils/jobFormatter.js', () => ({
  formatJobResponse: (job: any) => job,
}));

// Mock FS for path traversal tests
const mockExistsSync = vi.fn();
const mockCreateReadStream = vi.fn();
const mockStatSync = vi.fn();

vi.mock('fs', () => ({
  existsSync: (...args: any[]) => mockExistsSync(...args),
  createReadStream: (...args: any[]) => mockCreateReadStream(...args),
  statSync: (...args: any[]) => mockStatSync(...args),
}));

// SECURITY FINDING: resolveAssetPath has no path traversal protection.
// It passes through relative paths (including ../) and absolute paths unchanged.
vi.mock('../../utils/assetPath.js', () => ({
  resolveAssetPath: (p: string) => p,
}));

// ============================================
// Setup Express App
// ============================================
let app: Express;

const validUserHeaders = {
  'x-user-id': 'user-123',
  'x-internal-service': TEST_SERVICE_SECRET,
};

const attackerHeaders = {
  'x-user-id': 'attacker-456',
  'x-internal-service': TEST_SERVICE_SECRET,
};

const serviceHeaders = {
  'x-internal-service': TEST_SERVICE_SECRET,
};

beforeEach(async () => {
  vi.clearAllMocks();

  app = express();
  app.use(express.json());

  const { jobsRouter } = await import('../jobs.js');
  app.use('/api/jobs', jobsRouter);

  // Default mocks — use Readable.from() for a properly-ending stream
  mockCreateReadStream.mockImplementation(() => {
    return Readable.from(Buffer.from('mock-content'));
  });
  mockStatSync.mockReturnValue({ size: 12 });
  mockGetQueueLength.mockResolvedValue(0);
  mockGetQueueStats.mockResolvedValue({ position: 1, aheadCount: 0, totalQueued: 1 });
  mockCancelJob.mockResolvedValue({ cancelled: true, creditRefunded: 0 });
});

// ============================================
// Security Tests
// ============================================
describe('Security Audit: Jobs API', () => {
  const targetJobId = '00000000-0000-0000-0000-000000000001';
  const targetUserId = 'user-123';

  // ==========================================
  // Category 1: Authentication
  // ==========================================
  describe('Authentication', () => {
    it('GET /:jobId — no headers → 401', async () => {
      const res = await request(app).get(`/api/jobs/${targetJobId}`);
      expect(res.status).toBe(401);
    });

    it('GET /:jobId/reportjson — no headers → 401', async () => {
      const res = await request(app).get(`/api/jobs/${targetJobId}/reportjson`);
      expect(res.status).toBe(401);
    });

    it('GET /:jobId/landingpage — no headers → 401', async () => {
      const res = await request(app).get(`/api/jobs/${targetJobId}/landingpage`);
      expect(res.status).toBe(401);
    });

    it('DELETE /:jobId — no headers → 401', async () => {
      const res = await request(app).delete(`/api/jobs/${targetJobId}`);
      expect(res.status).toBe(401);
    });

    it('POST /:jobId/cancel — no headers → 401', async () => {
      const res = await request(app).post(`/api/jobs/${targetJobId}/cancel`);
      expect(res.status).toBe(401);
    });

    it('POST /:jobId/resume — no headers → 401', async () => {
      const res = await request(app).post(`/api/jobs/${targetJobId}/resume`);
      expect(res.status).toBe(401);
    });

    it('PATCH /:jobId/status — no headers → 401', async () => {
      const res = await request(app)
        .patch(`/api/jobs/${targetJobId}/status`)
        .send({ status: 'RUNNING' });
      expect(res.status).toBe(401);
    });

    it('POST / — no headers → 401', async () => {
      const res = await request(app)
        .post('/api/jobs')
        .send({ niche: 'Some niche description for testing' });
      expect(res.status).toBe(401);
    });

    it('GET /:jobId/queue-position — no headers → 401', async () => {
      const res = await request(app).get(`/api/jobs/${targetJobId}/queue-position`);
      expect(res.status).toBe(401);
    });

    it('wrong service secret with valid x-user-id → 401', async () => {
      const res = await request(app)
        .get(`/api/jobs/${targetJobId}`)
        .set({ 'x-user-id': 'user-123', 'x-internal-service': 'wrong-secret' });
      expect(res.status).toBe(401);
    });

    it('x-user-id present but no service secret → 401', async () => {
      const res = await request(app)
        .get(`/api/jobs/${targetJobId}`)
        .set({ 'x-user-id': 'user-123' });
      expect(res.status).toBe(401);
    });
  });

  // ==========================================
  // Category 2: Authorization / IDOR
  // ==========================================
  describe('Authorization (IDOR)', () => {
    beforeEach(() => {
      mockGetJob.mockResolvedValue({
        id: targetJobId,
        userId: targetUserId,
        status: JobStatus.COMPLETED,
        niche: 'test niche description',
      });
    });

    it('GET /:jobId — attacker gets 404 (no existence leakage)', async () => {
      const res = await request(app)
        .get(`/api/jobs/${targetJobId}`)
        .set(attackerHeaders);
      expect(res.status).toBe(404);
      expect(res.body.error).toBe('Job not found');
    });

    it('GET /:jobId/reportjson — attacker gets 404', async () => {
      const res = await request(app)
        .get(`/api/jobs/${targetJobId}/reportjson`)
        .set(attackerHeaders);
      expect(res.status).toBe(404);
    });

    it('GET /:jobId/landingpage — attacker gets 404', async () => {
      const res = await request(app)
        .get(`/api/jobs/${targetJobId}/landingpage`)
        .set(attackerHeaders);
      expect(res.status).toBe(404);
    });

    it('DELETE /:jobId — attacker gets 404', async () => {
      mockGetJob.mockResolvedValue({
        id: targetJobId,
        userId: targetUserId,
        status: JobStatus.RUNNING,
      });

      const res = await request(app)
        .delete(`/api/jobs/${targetJobId}`)
        .set(attackerHeaders);
      expect(res.status).toBe(404);
      expect(res.body.error).toBe('Job not found');
    });

    it('GET /:jobId/queue-position — attacker gets 404', async () => {
      mockGetJob.mockResolvedValue({
        id: targetJobId,
        userId: targetUserId,
        status: JobStatus.QUEUED,
      });

      const res = await request(app)
        .get(`/api/jobs/${targetJobId}/queue-position`)
        .set(attackerHeaders);
      expect(res.status).toBe(404);
    });

    it('POST /:jobId/cancel — attacker gets 404 (findFirst pattern)', async () => {
      // The cancel endpoint queries with both jobId AND userId,
      // so an attacker's userId won't match → findFirst returns null → 404
      mockJobFindFirst.mockImplementation(({ where }: any) => {
        if (where.userId === attackerHeaders['x-user-id']) return null;
        return { id: targetJobId, userId: targetUserId, status: JobStatus.RUNNING };
      });

      const res = await request(app)
        .post(`/api/jobs/${targetJobId}/cancel`)
        .set(attackerHeaders);

      // SECURITY FINDING: IDOR response inconsistency — GET endpoints return 403 revealing
      // the job exists, while POST /cancel returns 404 hiding existence. This inconsistency
      // means GET /:jobId can be used to probe for job existence.
      expect(res.status).toBe(404);
    });

    it('POST /:jobId/resume — attacker gets 404 (findFirst pattern)', async () => {
      mockJobFindFirst.mockImplementation(({ where }: any) => {
        if (where.userId === attackerHeaders['x-user-id']) return null;
        return { id: targetJobId, userId: targetUserId, status: JobStatus.FAILED };
      });

      const res = await request(app)
        .post(`/api/jobs/${targetJobId}/resume`)
        .set(attackerHeaders);
      expect(res.status).toBe(404);
    });

    it('POST / uses req.user.id, not body userId', async () => {
      mockCreateJobAndChargeDiscovery.mockResolvedValue({
        job: { id: 'new-job-id' },
        transaction: {},
      });
      mockEnqueueJob.mockResolvedValue(undefined);
      mockJobUpdate.mockResolvedValue({ id: 'new-job-id', status: JobStatus.QUEUED });

      const res = await request(app)
        .post('/api/jobs')
        .set(validUserHeaders)
        .send({
          niche: 'A niche long enough to pass validation',
          userId: 'attacker-injected-id', // should be ignored
        });

      expect(res.status).toBe(201);
      // createJobAndChargeDiscovery should receive the authenticated user's ID
      expect(mockCreateJobAndChargeDiscovery).toHaveBeenCalledWith(
        'user-123', // from auth, not from body
        expect.any(String),
        undefined,
        'interactive', // jobMode
        undefined, // entryMode
        undefined, // ideaFocus (persisted on the Job row since the resume-completeness fix)
        false // chatMode (Phase B: entitlement-coerced server-side, false when not requested)
      );
    });

    it('nonexistent job returns identical 404 for both owner and attacker', async () => {
      mockGetJob.mockResolvedValue(null);

      const ownerRes = await request(app)
        .get(`/api/jobs/${targetJobId}`)
        .set(validUserHeaders);
      const attackerRes = await request(app)
        .get(`/api/jobs/${targetJobId}`)
        .set(attackerHeaders);

      expect(ownerRes.status).toBe(404);
      expect(attackerRes.status).toBe(404);
      expect(ownerRes.body).toEqual(attackerRes.body);
    });

    it('verifyOwnership returns false when req.user is undefined', async () => {
      // Import the mock to test directly
      const { verifyOwnership } = await import('../../middleware/auth.js');
      const result = verifyOwnership({} as any, 'some-user-id');
      expect(result).toBe(false);
    });
  });

  // ==========================================
  // Category 3: Input Validation
  // ==========================================
  describe('Input Validation', () => {
    describe('UUID validation', () => {
      it('malformed ID rejected with 400 on GET /:jobId', async () => {
        const res = await request(app)
          .get('/api/jobs/not-a-uuid')
          .set(validUserHeaders);
        expect(res.status).toBe(400);
        expect(res.body.error).toMatch(/invalid job id/i);
      });

      it('SQL injection string as jobId → 400', async () => {
        const res = await request(app)
          .get("/api/jobs/'; DROP TABLE jobs; --")
          .set(validUserHeaders);
        expect(res.status).toBe(400);
      });

      // SECURITY FINDING: Path traversal in URL params is resolved by Express's router
      // before reaching the handler. ../../etc/passwd resolves to a different route entirely,
      // returning 404 rather than hitting UUID validation.
      it('path traversal string as jobId → does not reach handler', async () => {
        const res = await request(app)
          .get('/api/jobs/..%2F..%2Fetc%2Fpasswd')
          .set(validUserHeaders);
        // URL-encoded traversal still doesn't match UUID format
        expect(res.status).toBe(400);
      });

      it('valid UUID format accepted', async () => {
        mockGetJob.mockResolvedValue(null);

        const res = await request(app)
          .get(`/api/jobs/${targetJobId}`)
          .set(validUserHeaders);
        // UUID passes validation, then gets 404 since job doesn't exist
        expect(res.status).toBe(404);
      });

      it('all endpoints now validate UUID format (reportjson)', async () => {
        const res = await request(app)
          .get('/api/jobs/not-a-uuid/reportjson')
          .set(validUserHeaders);
        expect(res.status).toBe(400);
        expect(res.body.error).toMatch(/invalid job id/i);
      });
    });

    describe('Zod validation for POST /', () => {
      it('missing niche → 400', async () => {
        const res = await request(app)
          .post('/api/jobs')
          .set(validUserHeaders)
          .send({});
        expect(res.status).toBe(400);
        expect(res.body.error).toBe('Validation error');
      });

      it('niche too short (<10 chars) → 400', async () => {
        const res = await request(app)
          .post('/api/jobs')
          .set(validUserHeaders)
          .send({ niche: 'short' });
        expect(res.status).toBe(400);
        expect(res.body.details).toBeDefined();
      });

      it('niche too long (>500 chars) → 400', async () => {
        const res = await request(app)
          .post('/api/jobs')
          .set(validUserHeaders)
          .send({ niche: 'x'.repeat(501) });
        expect(res.status).toBe(400);
      });

      it('non-string niche → 400', async () => {
        const res = await request(app)
          .post('/api/jobs')
          .set(validUserHeaders)
          .send({ niche: 12345 });
        expect(res.status).toBe(400);
      });

      it('valid minimum-length niche → 201', async () => {
        mockCreateJobAndChargeDiscovery.mockResolvedValue({
          job: { id: 'new-job-id' },
          transaction: {},
        });
        mockEnqueueJob.mockResolvedValue(undefined);
        mockJobUpdate.mockResolvedValue({ id: 'new-job-id', status: JobStatus.QUEUED });

        const res = await request(app)
          .post('/api/jobs')
          .set(validUserHeaders)
          .send({ niche: 'Exactly 10' }); // 10 chars
        expect(res.status).toBe(201);
      });

      it('extra fields are stripped by Zod', async () => {
        mockCreateJobAndChargeDiscovery.mockResolvedValue({
          job: { id: 'new-job-id' },
          transaction: {},
        });
        mockEnqueueJob.mockResolvedValue(undefined);
        mockJobUpdate.mockResolvedValue({ id: 'new-job-id', status: JobStatus.QUEUED });

        const res = await request(app)
          .post('/api/jobs')
          .set(validUserHeaders)
          .send({
            niche: 'A valid niche that passes validation',
            malicious: '<script>alert(1)</script>',
          });
        expect(res.status).toBe(201);
        // The malicious field should not reach createJobAndChargeDiscovery
        const callArgs = mockCreateJobAndChargeDiscovery.mock.calls[0];
        expect(callArgs[1]).toBe('A valid niche that passes validation');
      });

      it('allowedProjectTypes with injection strings rejected', async () => {
        const res = await request(app)
          .post('/api/jobs')
          .set(validUserHeaders)
          .send({
            niche: 'A valid niche for testing injection',
            allowedProjectTypes: ["'; DROP TABLE jobs; --", '<script>alert(1)</script>'],
          });

        expect(res.status).toBe(400);
        expect(res.body.error).toBe('Validation error');
      });

      it('allowedProjectTypes with valid enum values accepted', async () => {
        mockCreateJobAndChargeDiscovery.mockResolvedValue({
          job: { id: 'new-job-id' },
          transaction: {},
        });
        mockEnqueueJob.mockResolvedValue(undefined);
        mockJobUpdate.mockResolvedValue({ id: 'new-job-id', status: JobStatus.QUEUED });

        const res = await request(app)
          .post('/api/jobs')
          .set(validUserHeaders)
          .send({
            niche: 'A valid niche for testing project types',
            allowedProjectTypes: ['saas', 'directory'],
          });

        expect(res.status).toBe(201);
      });
    });

    // SECURITY FINDING: The niche field has no pattern validation.
    // Prompt injection payloads pass Zod's min/max length check unfiltered.
    // This is a risk since niche is fed directly to LLM agents in the pipeline.
  });

  // ==========================================
  // Category 4: Path Traversal & Asset Security
  // ==========================================
  describe('Path Traversal & Asset Security', () => {
    beforeEach(() => {
      mockGetJob.mockResolvedValue({
        id: targetJobId,
        userId: targetUserId,
        status: JobStatus.COMPLETED,
      });
      mockExistsSync.mockReturnValue(true);
    });

    // SECURITY FINDING: resolveAssetPath has no traversal protection.
    // It resolves relative paths against the project root and passes absolute paths
    // through unchanged. If an attacker can control the stored filePath in the DB,
    // they can read arbitrary files from the filesystem.

    it('reportjson — stored path with ../ traversal is served without sanitization', async () => {
      mockGetJobAsset.mockResolvedValue({
        filePath: '../../../etc/passwd',
      });

      const res = await request(app)
        .get(`/api/jobs/${targetJobId}/reportjson`)
        .set(validUserHeaders)
        .buffer(true)
        .parse((res, cb) => {
          let data = '';
          res.on('data', (chunk: any) => { data += chunk; });
          res.on('end', () => cb(null, data));
        });

      // The file is served — resolveAssetPath does not block traversal
      expect(res.status).toBe(200);
      expect(mockExistsSync).toHaveBeenCalledWith('../../../etc/passwd');
    });

    it('reportjson — URL-encoded traversal %2e%2e%2f in stored path', async () => {
      // URL encoding is decoded before storage, so this tests if the stored value is malicious
      mockGetJobAsset.mockResolvedValue({
        filePath: '%2e%2e%2fetc/passwd',
      });

      const res = await request(app)
        .get(`/api/jobs/${targetJobId}/reportjson`)
        .set(validUserHeaders)
        .buffer(true)
        .parse((res, cb) => {
          let data = '';
          res.on('data', (chunk: any) => { data += chunk; });
          res.on('end', () => cb(null, data));
        });

      // Path is passed through as-is (the literal %2e%2e%2f string)
      expect(res.status).toBe(200);
      expect(mockExistsSync).toHaveBeenCalledWith('%2e%2e%2fetc/passwd');
    });

    it('reportjson — null byte injection in stored path', async () => {
      mockGetJobAsset.mockResolvedValue({
        filePath: 'report.json\x00.html',
      });

      const res = await request(app)
        .get(`/api/jobs/${targetJobId}/reportjson`)
        .set(validUserHeaders)
        .buffer(true)
        .parse((res, cb) => {
          let data = '';
          res.on('data', (chunk: any) => { data += chunk; });
          res.on('end', () => cb(null, data));
        });

      expect(res.status).toBe(200);
    });

    it('reportjson — absolute path /etc/shadow passes through unchanged', async () => {
      mockGetJobAsset.mockResolvedValue({
        filePath: '/etc/shadow',
      });

      const res = await request(app)
        .get(`/api/jobs/${targetJobId}/reportjson`)
        .set(validUserHeaders)
        .buffer(true)
        .parse((res, cb) => {
          let data = '';
          res.on('data', (chunk: any) => { data += chunk; });
          res.on('end', () => cb(null, data));
        });

      expect(res.status).toBe(200);
      // resolveAssetPath returns absolute paths as-is
      expect(mockExistsSync).toHaveBeenCalledWith('/etc/shadow');
    });

    it('landingpage — stored path with ../ traversal is served without sanitization', async () => {
      mockGetJobAsset.mockResolvedValue({
        filePath: '../../../etc/passwd',
      });

      const res = await request(app)
        .get(`/api/jobs/${targetJobId}/landingpage`)
        .set(validUserHeaders);

      expect(res.status).toBe(200);
      expect(mockExistsSync).toHaveBeenCalledWith('../../../etc/passwd');
    });

    it('landingpage — absolute path passes through unchanged', async () => {
      mockGetJobAsset.mockResolvedValue({
        filePath: '/etc/shadow',
      });

      const res = await request(app)
        .get(`/api/jobs/${targetJobId}/landingpage`)
        .set(validUserHeaders);

      expect(res.status).toBe(200);
      expect(mockExistsSync).toHaveBeenCalledWith('/etc/shadow');
    });

    it('legitimate path resolves safely', async () => {
      mockGetJobAsset.mockResolvedValue({
        filePath: 'outputs/job-123/report.json',
      });

      const res = await request(app)
        .get(`/api/jobs/${targetJobId}/reportjson`)
        .set(validUserHeaders)
        .buffer(true)
        .parse((res, cb) => {
          let data = '';
          res.on('data', (chunk: any) => { data += chunk; });
          res.on('end', () => cb(null, data));
        });

      expect(res.status).toBe(200);
      expect(mockExistsSync).toHaveBeenCalledWith('outputs/job-123/report.json');
    });

    it('asset not found returns 404', async () => {
      mockGetJobAsset.mockResolvedValue(null);

      const res = await request(app)
        .get(`/api/jobs/${targetJobId}/reportjson`)
        .set(validUserHeaders);

      expect(res.status).toBe(404);
      expect(res.body.error).toMatch(/not found/i);
    });
  });

  // ==========================================
  // Category 5: Internal Service Endpoints
  // ==========================================
  describe('Internal Service Endpoints (PATCH /:jobId/status)', () => {
    it('no headers → 401', async () => {
      const res = await request(app)
        .patch(`/api/jobs/${targetJobId}/status`)
        .send({ status: 'RUNNING' });
      expect(res.status).toBe(401);
    });

    it('wrong service secret → 401', async () => {
      const res = await request(app)
        .patch(`/api/jobs/${targetJobId}/status`)
        .set({ 'x-internal-service': 'wrong-secret' })
        .send({ status: 'RUNNING' });
      expect(res.status).toBe(401);
    });

    it('user auth headers without service secret → 401', async () => {
      // User-style headers (x-user-id) should not grant access to service endpoints
      const res = await request(app)
        .patch(`/api/jobs/${targetJobId}/status`)
        .set({ 'x-user-id': 'user-123' })
        .send({ status: 'RUNNING' });
      expect(res.status).toBe(401);
    });

    it('valid service secret → allowed (processes request)', async () => {
      mockGetJob.mockResolvedValue({
        id: targetJobId,
        userId: targetUserId,
        status: JobStatus.QUEUED,
        currentStage: 0,
      });
      mockJobUpdate.mockResolvedValue({
        id: targetJobId,
        status: JobStatus.RUNNING,
        currentStage: 0,
      });

      const res = await request(app)
        .patch(`/api/jobs/${targetJobId}/status`)
        .set(serviceHeaders)
        .send({ status: 'RUNNING' });

      expect(res.status).toBe(200);
      expect(res.body.status).toBe(JobStatus.RUNNING);
    });

    it('only RUNNING status accepted, others rejected with 400', async () => {
      mockGetJob.mockResolvedValue({
        id: targetJobId,
        userId: targetUserId,
        status: JobStatus.QUEUED,
      });

      const res = await request(app)
        .patch(`/api/jobs/${targetJobId}/status`)
        .set(serviceHeaders)
        .send({ status: 'COMPLETED' });

      expect(res.status).toBe(400);
      expect(res.body.error).toMatch(/only running/i);
    });
  });

  // ==========================================
  // Category 6: Information Leakage
  // ==========================================
  describe('Information Leakage', () => {
    it('404 body identical for nonexistent jobs regardless of requester', async () => {
      mockGetJob.mockResolvedValue(null);

      const ownerRes = await request(app)
        .get(`/api/jobs/${targetJobId}`)
        .set(validUserHeaders);
      const attackerRes = await request(app)
        .get(`/api/jobs/${targetJobId}`)
        .set(attackerHeaders);

      expect(ownerRes.status).toBe(404);
      expect(attackerRes.status).toBe(404);
      // Bodies must be structurally identical — no user-specific info leaked
      expect(JSON.stringify(ownerRes.body)).toBe(JSON.stringify(attackerRes.body));
    });

    it('IDOR response is identical to nonexistent job (no existence leakage)', async () => {
      // Attacker hits an existing job owned by someone else
      mockGetJob.mockResolvedValue({
        id: targetJobId,
        userId: targetUserId,
        status: JobStatus.COMPLETED,
      });

      const idorRes = await request(app)
        .get(`/api/jobs/${targetJobId}`)
        .set(attackerHeaders);

      // Now simulate nonexistent job
      mockGetJob.mockResolvedValue(null);
      const notFoundRes = await request(app)
        .get(`/api/jobs/${targetJobId}`)
        .set(attackerHeaders);

      // Both must be identical 404 — attacker cannot distinguish
      expect(idorRes.status).toBe(404);
      expect(notFoundRes.status).toBe(404);
      expect(JSON.stringify(idorRes.body)).toBe(JSON.stringify(notFoundRes.body));
    });

    it('Zod errors include field names but not full schema', async () => {
      const res = await request(app)
        .post('/api/jobs')
        .set(validUserHeaders)
        .send({});

      expect(res.status).toBe(400);
      expect(res.body.error).toBe('Validation error');
      expect(res.body.details).toBeDefined();
      // Should include field-level errors but not leak internal schema details
      const detailsStr = JSON.stringify(res.body.details);
      expect(detailsStr).toContain('niche');
    });

    it('500 errors return generic message, no stack traces', async () => {
      mockGetJob.mockRejectedValue(new Error('DB connection failed'));

      const res = await request(app)
        .get(`/api/jobs/${targetJobId}`)
        .set(validUserHeaders);

      expect(res.status).toBe(500);
      expect(res.body.error).toBe('Failed to get job status');
      // No stack trace or internal details
      expect(res.body.stack).toBeUndefined();
      expect(res.body.message).toBeUndefined();
    });

    it('POST /:jobId/cancel error exposes status field', async () => {
      mockJobFindFirst.mockResolvedValue({
        id: targetJobId,
        userId: targetUserId,
        status: JobStatus.COMPLETED,
      });
      mockCancelJob.mockResolvedValue({ cancelled: false, reason: 'not_cancellable', status: JobStatus.COMPLETED });

      const res = await request(app)
        .post(`/api/jobs/${targetJobId}/cancel`)
        .set(validUserHeaders);

      expect(res.status).toBe(400);
      // SECURITY FINDING: The cancel endpoint exposes the job's current status
      // in the error response. This is a deliberate UX choice but could leak info.
      expect(res.body.status).toBe(JobStatus.COMPLETED);
      expect(res.body.error).toBe('Job already finished');
    });
  });

  // ==========================================
  // Category 7: Business Logic
  // ==========================================
  describe('Business Logic', () => {
    it('DELETE /:jobId rejects COMPLETED jobs with 400', async () => {
      mockGetJob.mockResolvedValue({
        id: targetJobId,
        userId: targetUserId,
        status: JobStatus.COMPLETED,
      });
      mockCancelJob.mockResolvedValue({ cancelled: false, reason: 'not_cancellable', status: JobStatus.COMPLETED });

      const res = await request(app)
        .delete(`/api/jobs/${targetJobId}`)
        .set(validUserHeaders);

      expect(res.status).toBe(400);
      expect(res.body.error).toMatch(/cannot cancel a completed job/i);
    });

    it('DELETE /:jobId rejects CANCELLED jobs with 400', async () => {
      mockGetJob.mockResolvedValue({
        id: targetJobId,
        userId: targetUserId,
        status: JobStatus.CANCELLED,
      });
      mockCancelJob.mockResolvedValue({ cancelled: false, reason: 'not_cancellable', status: JobStatus.CANCELLED });

      const res = await request(app)
        .delete(`/api/jobs/${targetJobId}`)
        .set(validUserHeaders);

      expect(res.status).toBe(400);
      expect(res.body.error).toMatch(/already cancelled/i);
    });

    it('POST /:jobId/cancel rejects COMPLETED jobs', async () => {
      mockJobFindFirst.mockResolvedValue({
        id: targetJobId,
        userId: targetUserId,
        status: JobStatus.COMPLETED,
      });
      mockCancelJob.mockResolvedValue({ cancelled: false, reason: 'not_cancellable', status: JobStatus.COMPLETED });

      const res = await request(app)
        .post(`/api/jobs/${targetJobId}/cancel`)
        .set(validUserHeaders);

      expect(res.status).toBe(400);
      expect(res.body.error).toBe('Job already finished');
    });

    it('POST /:jobId/cancel rejects FAILED jobs', async () => {
      mockJobFindFirst.mockResolvedValue({
        id: targetJobId,
        userId: targetUserId,
        status: JobStatus.FAILED,
      });
      mockCancelJob.mockResolvedValue({ cancelled: false, reason: 'not_cancellable', status: JobStatus.FAILED });

      const res = await request(app)
        .post(`/api/jobs/${targetJobId}/cancel`)
        .set(validUserHeaders);

      expect(res.status).toBe(400);
      expect(res.body.error).toBe('Job already finished');
    });

    it('POST /:jobId/resume only works on FAILED jobs, rejects RUNNING', async () => {
      mockJobFindFirst.mockResolvedValue({
        id: targetJobId,
        userId: targetUserId,
        status: JobStatus.RUNNING,
      });

      const res = await request(app)
        .post(`/api/jobs/${targetJobId}/resume`)
        .set(validUserHeaders);

      expect(res.status).toBe(400);
      expect(res.body.error).toMatch(/only failed jobs/i);
    });

    it('POST /:jobId/resume succeeds on FAILED jobs (no prior refund)', async () => {
      mockJobFindFirst.mockResolvedValue({
        id: targetJobId,
        userId: targetUserId,
        status: JobStatus.FAILED,
        niche: 'test niche description',
      });
      mockCreditTransactionFindFirst.mockResolvedValue(null); // no refund
      mockJobUpdate.mockResolvedValue({
        id: targetJobId,
        status: JobStatus.QUEUED,
      });
      mockEnqueueJob.mockResolvedValue(undefined);

      const res = await request(app)
        .post(`/api/jobs/${targetJobId}/resume`)
        .set(validUserHeaders);

      expect(res.status).toBe(200);
      expect(res.body.status).toBe('queued');
      expect(res.body.creditCharged).toBe(0);
    });

    it('PATCH /:jobId/status only transitions from QUEUED', async () => {
      // Already RUNNING — should return current state without error
      mockGetJob.mockResolvedValue({
        id: targetJobId,
        userId: targetUserId,
        status: JobStatus.RUNNING,
        currentStage: 3,
      });

      const res = await request(app)
        .patch(`/api/jobs/${targetJobId}/status`)
        .set(serviceHeaders)
        .send({ status: 'RUNNING' });

      // Returns 200 with current state (no-op, not an error)
      expect(res.status).toBe(200);
      expect(res.body.status).toBe(JobStatus.RUNNING);
      // Should NOT have called prisma.job.update
      expect(mockJobUpdate).not.toHaveBeenCalled();
    });

    it('GET /:jobId/reportjson rejects non-COMPLETED jobs without report asset', async () => {
      mockGetJob.mockResolvedValue({
        id: targetJobId,
        userId: targetUserId,
        status: JobStatus.RUNNING,
      });
      mockGetJobAsset.mockResolvedValue(null); // No report asset

      const res = await request(app)
        .get(`/api/jobs/${targetJobId}/reportjson`)
        .set(validUserHeaders);

      expect(res.status).toBe(400);
      expect(res.body.error).toMatch(/not ready/i);
    });
  });
});

// SECURITY FINDING SUMMARY:
// 1. resolveAssetPath has no path traversal protection — stored filePaths with ../ or absolute paths are served directly
// 2. UUID validation only on GET /:jobId, not other endpoints
// 3. allowedProjectTypes has no item-level validation — arbitrary strings including injection payloads accepted
// 4. niche field has no pattern validation — prompt injection risk since it feeds into LLM agents
// 5. IDOR response inconsistency: GET endpoints return 403 (reveals job existence), POST /cancel returns 404
// 6. requireInternalAuth trusts x-user-id/x-user-email/x-user-role headers after secret validation — full impersonation if secret leaks
