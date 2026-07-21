import { beforeEach, describe, expect, it, vi } from 'vitest';
import express, { type Express } from 'express';
import request from 'supertest';

const mockGetJob = vi.fn();
const mockFindAnnotation = vi.fn();
const mockUpsertAnnotation = vi.fn();
const mockFindShare = vi.fn();

vi.mock('../../services/db.js', () => ({
  prisma: {
    discoveryAnnotationDocument: {
      findUnique: (...args: unknown[]) => mockFindAnnotation(...args),
      upsert: (...args: unknown[]) => mockUpsertAnnotation(...args),
    },
    discoveryShare: {
      findUnique: (...args: unknown[]) => mockFindShare(...args),
    },
  },
}));

vi.mock('../../services/jobService.js', () => ({
  getJob: (...args: unknown[]) => mockGetJob(...args),
}));

vi.mock('../../middleware/auth.js', () => ({
  requireInternalAuth: (req: any, res: any, next: any) => {
    if (req.headers['x-internal-service'] !== 'test-secret' || !req.headers['x-user-id']) {
      return res.status(401).json({ error: 'Authentication required' });
    }
    req.user = { id: req.headers['x-user-id'] };
    next();
  },
  verifyOwnership: (req: any, userId: string) => req.user?.id === userId,
  AuthenticatedRequest: {},
}));

vi.mock('express-rate-limit', () => ({
  default: () => (_req: any, _res: any, next: any) => next(),
}));

vi.mock('../../config.js', () => ({
  CONFIG: { nodeEnv: 'test' },
}));

const JOB_ID = '550e8400-e29b-41d4-a716-446655440000';
const USER_ID = 'user-123';
const SHARE_TOKEN = 'abcdefghijklmnopqrstuv';
const UPDATED_AT = new Date('2026-07-15T12:00:00.000Z');
const headers = {
  'x-internal-service': 'test-secret',
  'x-user-id': USER_ID,
};
const emptyDocument = { version: 1, surfaces: {} };
const validDocument = {
  version: 1,
  surfaces: {
    'research:page': {
      strokes: [{
        id: '123e4567-e89b-42d3-a456-426614174000',
        color: '#dc2626',
        width: 4,
        createdAt: 1,
        anchor: { key: 'research-header', width: 920, height: 140 },
        points: [[0.1, 0.2], [0.4, 0.5]],
      }],
    },
  },
};

let app: Express;

beforeEach(async () => {
  vi.clearAllMocks();
  app = express();
  app.use(express.json());

  const {
    discoveryAnnotationsRouter,
    publicDiscoveryAnnotationsRouter,
  } = await import('../discoveryAnnotations.js');
  app.use('/api/jobs', discoveryAnnotationsRouter);
  app.use('/api/shared/discovery', publicDiscoveryAnnotationsRouter);
});

describe('discovery annotation owner API', () => {
  it('returns an empty document when no annotations exist', async () => {
    mockGetJob.mockResolvedValue({
      id: JOB_ID,
      userId: USER_ID,
      status: 'AWAITING_SELECTION',
    });
    mockFindAnnotation.mockResolvedValue(null);

    const response = await request(app)
      .get(`/api/jobs/${JOB_ID}/discovery-annotations`)
      .set(headers)
      .expect(200);

    expect(response.body).toEqual({
      revision: 0,
      document: emptyDocument,
      updatedAt: null,
    });
  });

  it('allows only the owner to read annotations', async () => {
    mockGetJob.mockResolvedValue({
      id: JOB_ID,
      userId: 'another-user',
      status: 'AWAITING_SELECTION',
    });

    await request(app)
      .get(`/api/jobs/${JOB_ID}/discovery-annotations`)
      .set(headers)
      .expect(403);

    expect(mockFindAnnotation).not.toHaveBeenCalled();
  });

  it('saves a valid annotation document during selection', async () => {
    mockGetJob.mockResolvedValue({
      id: JOB_ID,
      userId: USER_ID,
      status: 'AWAITING_SELECTION',
    });
    mockUpsertAnnotation.mockResolvedValue({
      jobId: JOB_ID,
      document: validDocument,
      revision: 3,
      updatedAt: UPDATED_AT,
    });

    const response = await request(app)
      .put(`/api/jobs/${JOB_ID}/discovery-annotations`)
      .set(headers)
      .send({ document: validDocument })
      .expect(200);

    expect(response.body.revision).toBe(3);
    expect(mockUpsertAnnotation).toHaveBeenCalledWith({
      where: { jobId: JOB_ID },
      create: { jobId: JOB_ID, document: validDocument, revision: 1 },
      update: { document: validDocument, revision: { increment: 1 } },
    });
  });

  it('persists per-point region sizes for responsive cross-container strokes', async () => {
    const responsiveDocument = {
      version: 1,
      surfaces: {
        'research:page': {
          strokes: [{
            id: '223e4567-e89b-42d3-a456-426614174000',
            color: '#dc2626',
            width: 4,
            createdAt: 2,
            points: [[0.1, 0.2], [0.4, 0.5]],
            anchors: [
              { key: 'candidate:one', x: 0.2, y: 0.4, width: 720, height: 120 },
              { key: 'candidate:two', x: 0.3, y: 0.5, width: 720, height: 132 },
            ],
          }],
        },
      },
    };
    mockGetJob.mockResolvedValue({
      id: JOB_ID,
      userId: USER_ID,
      status: 'AWAITING_SELECTION',
    });
    mockUpsertAnnotation.mockResolvedValue({
      jobId: JOB_ID,
      document: responsiveDocument,
      revision: 4,
      updatedAt: UPDATED_AT,
    });

    await request(app)
      .put(`/api/jobs/${JOB_ID}/discovery-annotations`)
      .set(headers)
      .send({ document: responsiveDocument })
      .expect(200);

    expect(mockUpsertAnnotation).toHaveBeenCalledWith(expect.objectContaining({
      update: expect.objectContaining({ document: responsiveDocument }),
    }));
  });

  it('rejects assistant annotation surfaces', async () => {
    mockGetJob.mockResolvedValue({
      id: JOB_ID,
      userId: USER_ID,
      status: 'AWAITING_SELECTION',
    });

    await request(app)
      .put(`/api/jobs/${JOB_ID}/discovery-annotations`)
      .set(headers)
      .send({
        document: {
          version: 1,
          surfaces: {
            'assistant:chat': validDocument.surfaces['research:page'],
          },
        },
      })
      .expect(400);

    expect(mockUpsertAnnotation).not.toHaveBeenCalled();
  });

  it('rejects edits outside the selection phase', async () => {
    mockGetJob.mockResolvedValue({
      id: JOB_ID,
      userId: USER_ID,
      status: 'COMPLETED',
    });

    await request(app)
      .put(`/api/jobs/${JOB_ID}/discovery-annotations`)
      .set(headers)
      .send({ document: validDocument })
      .expect(400);

    expect(mockUpsertAnnotation).not.toHaveBeenCalled();
  });
});

describe('discovery annotation public polling API', () => {
  it('returns annotations for an active share', async () => {
    mockFindShare.mockResolvedValue({ jobId: JOB_ID, isActive: true });
    mockFindAnnotation.mockResolvedValue({
      jobId: JOB_ID,
      document: validDocument,
      revision: 3,
      updatedAt: UPDATED_AT,
    });

    const response = await request(app)
      .get(`/api/shared/discovery/${SHARE_TOKEN}/annotations`)
      .expect(200);

    expect(response.body.revision).toBe(3);
    expect(response.body.document).toEqual(validDocument);
    expect(response.headers['cache-control']).toBe('private, no-store');
  });

  it('returns 204 when the viewer already has the latest revision', async () => {
    mockFindShare.mockResolvedValue({ jobId: JOB_ID, isActive: true });
    mockFindAnnotation.mockResolvedValue({
      jobId: JOB_ID,
      document: validDocument,
      revision: 3,
      updatedAt: UPDATED_AT,
    });

    await request(app)
      .get(`/api/shared/discovery/${SHARE_TOKEN}/annotations?sinceRevision=3`)
      .expect(204);
  });

  it('does not expose annotations for an inactive share', async () => {
    mockFindShare.mockResolvedValue({ jobId: JOB_ID, isActive: false });

    await request(app)
      .get(`/api/shared/discovery/${SHARE_TOKEN}/annotations`)
      .expect(404);

    expect(mockFindAnnotation).not.toHaveBeenCalled();
  });
});
