import { beforeEach, describe, expect, it, vi } from 'vitest';
import express, { type Express } from 'express';
import request from 'supertest';

// These suites exercise route logic, not the decision-tools grant. The grant itself is
// covered in middleware/__tests__/featureAccess.test.ts.
vi.mock('../../middleware/featureAccess.js', () => ({
  requireDecisionToolsAccess: (_req: any, _res: any, next: any) => next(),
}));
import { Prisma } from '@prisma/client';

const mockExperimentFindFirst = vi.fn();
const mockRunCreate = vi.fn();
const mockRunFindUnique = vi.fn();
const mockRunFindFirst = vi.fn();
const mockRunUpdateMany = vi.fn();
const mockRunFindUniqueOrThrow = vi.fn();
const mockEventFindFirst = vi.fn();
const mockEventCreate = vi.fn();
const mockEventGroupBy = vi.fn();
const mockEventAggregate = vi.fn();

vi.mock('../../services/db.js', () => ({
  prisma: {
    selectionExperiment: {
      findFirst: (...args: unknown[]) => mockExperimentFindFirst(...args),
    },
    selectionExperimentRun: {
      create: (...args: unknown[]) => mockRunCreate(...args),
      findUnique: (...args: unknown[]) => mockRunFindUnique(...args),
      findFirst: (...args: unknown[]) => mockRunFindFirst(...args),
      updateMany: (...args: unknown[]) => mockRunUpdateMany(...args),
      findUniqueOrThrow: (...args: unknown[]) => mockRunFindUniqueOrThrow(...args),
    },
    selectionExperimentEvent: {
      findFirst: (...args: unknown[]) => mockEventFindFirst(...args),
      create: (...args: unknown[]) => mockEventCreate(...args),
      groupBy: (...args: unknown[]) => mockEventGroupBy(...args),
      aggregate: (...args: unknown[]) => mockEventAggregate(...args),
    },
  },
}));

vi.mock('../../middleware/auth.js', () => ({
  requireInternalAuth: (req: any, res: any, next: any) => {
    if (!req.headers['x-user-id']) return res.status(401).json({ error: 'Unauthorized' });
    req.user = { id: req.headers['x-user-id'] };
    next();
  },
  AuthenticatedRequest: {},
}));

const JOB_ID = '550e8400-e29b-41d4-a716-446655440000';
const EXPERIMENT_ID = '123e4567-e89b-42d3-a456-426614174000';
const RUN_ID = '223e4567-e89b-42d3-a456-426614174000';
const EVENT_ID = '323e4567-e89b-42d3-a456-426614174000';
const TOKEN = 'opaque_public_experiment_token_123';
const headers = { 'x-user-id': 'owner-1' };
const launch = {
  headline: 'Signal Desk for operators',
  promise: 'Find recurring buyer signals before your team commits a build cycle.',
  ctaLabel: 'IM_INTERESTED',
};
const run = {
  id: RUN_ID,
  experimentId: EXPERIMENT_ID,
  publicToken: TOKEN,
  status: 'ACTIVE',
  artifact: {
    version: 1,
    headline: launch.headline,
    promise: launch.promise,
    ctaLabel: "I'm interested",
    disclosure: {
      title: 'This is a concept test',
      body: 'This product is not available yet.',
    },
  },
  briefVersion: 1,
  stimulusVersion: 1,
  launchedAt: new Date('2026-07-15T12:00:00.000Z'),
  closedAt: null,
};

let app: Express;

beforeEach(async () => {
  vi.clearAllMocks();
  mockRunUpdateMany.mockResolvedValue({ count: 1 });
  app = express();
  app.use(express.json());
  const {
    selectionExperimentRunsRouter,
    publicSelectionExperimentRunsRouter,
  } = await import('../selectionExperimentRuns.js');
  app.use('/api/jobs', selectionExperimentRunsRouter);
  app.use('/api/public/experiments', publicSelectionExperimentRunsRouter);
});

describe('selection experiment runs', () => {
  it('publishes one immutable, allowlisted artifact from a locked CTA-interest brief', async () => {
    mockExperimentFindFirst.mockResolvedValue({
      id: EXPERIMENT_ID,
      status: 'LOCKED',
      method: 'CTA_SMOKE_TEST',
      evidenceSignal: 'CTA_INTEREST',
      assumption: 'Internal hypothesis must stay private',
      passThreshold: 'Internal threshold must stay private',
      run: null,
    });
    mockRunCreate.mockResolvedValue(run);

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-experiments/${EXPERIMENT_ID}/run`)
      .set(headers)
      .send(launch);

    expect(response.status).toBe(201);
    const data = mockRunCreate.mock.calls[0][0].data;
    expect(data.artifact).toEqual({
      version: 1,
      headline: launch.headline,
      promise: launch.promise,
      ctaLabel: "I'm interested",
      disclosure: expect.objectContaining({ title: 'This is a concept test' }),
    });
    expect(JSON.stringify(data.artifact)).not.toContain('hypothesis');
    expect(JSON.stringify(data.artifact)).not.toContain('threshold');
  });

  it('rejects drafts and briefs that do not measure CTA interest', async () => {
    mockExperimentFindFirst.mockResolvedValue({
      id: EXPERIMENT_ID,
      status: 'DRAFT',
      method: 'CTA_SMOKE_TEST',
      evidenceSignal: 'CTA_INTEREST',
      run: null,
    });

    const draftResponse = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-experiments/${EXPERIMENT_ID}/run`)
      .set(headers)
      .send(launch);
    expect(draftResponse.status).toBe(409);

    mockExperimentFindFirst.mockResolvedValue({
      id: EXPERIMENT_ID,
      status: 'LOCKED',
      method: 'SURVEY',
      evidenceSignal: 'STATED_PREFERENCE',
      run: null,
    });
    const signalResponse = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-experiments/${EXPERIMENT_ID}/run`)
      .set(headers)
      .send(launch);
    expect(signalResponse.status).toBe(409);
    expect(mockRunCreate).not.toHaveBeenCalled();
  });

  it('does not publish a run after an immutable conclusion exists', async () => {
    mockExperimentFindFirst.mockResolvedValue({
      id: EXPERIMENT_ID,
      status: 'LOCKED',
      method: 'CTA_SMOKE_TEST',
      evidenceSignal: 'CTA_INTEREST',
      run: null,
      conclusion: { id: 'conclusion-1' },
    });

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-experiments/${EXPERIMENT_ID}/run`)
      .set(headers)
      .send(launch);

    expect(response.status).toBe(409);
    expect(mockRunCreate).not.toHaveBeenCalled();
  });

  it('does not reveal another owner\'s experiment', async () => {
    mockExperimentFindFirst.mockResolvedValue(null);

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-experiments/${EXPERIMENT_ID}/run`)
      .set(headers)
      .send(launch);

    expect(response.status).toBe(404);
  });

  it('returns only the public artifact and a signed short-lived view token', async () => {
    mockRunFindFirst.mockResolvedValue({ id: RUN_ID, artifact: run.artifact });

    const response = await request(app).get(`/api/public/experiments/${TOKEN}`);

    expect(response.status).toBe(200);
    expect(response.headers['x-robots-tag']).toBe('noindex, nofollow');
    expect(response.body.test.artifact).toEqual(run.artifact);
    expect(response.body.test.viewToken).toMatch(/^[^.]+\.[^.]+$/);
    expect(response.body.test).not.toHaveProperty('experimentId');
    expect(response.body.test).not.toHaveProperty('results');
  });

  it('records an exposure without persisting the signed token, client IP, or PII', async () => {
    mockRunFindFirst.mockResolvedValue({ id: RUN_ID, artifact: run.artifact });
    const publicPage = await request(app).get(`/api/public/experiments/${TOKEN}`);
    mockEventCreate.mockResolvedValue({ id: 'event-row' });

    const response = await request(app)
      .post(`/api/public/experiments/${TOKEN}/events`)
      .set('x-client-ip', '203.0.113.10')
      .send({
        eventId: EVENT_ID,
        viewToken: publicPage.body.test.viewToken,
        type: 'STIMULUS_EXPOSED',
        occurredAt: new Date().toISOString(),
      });

    expect(response.status).toBe(202);
    expect(mockEventCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        runId: RUN_ID,
        eventId: EVENT_ID,
        type: 'STIMULUS_EXPOSED',
        occurredAt: expect.any(Date),
        viewId: expect.any(String),
      }),
    });
    const stored = mockEventCreate.mock.calls[0][0].data;
    expect(stored).not.toHaveProperty('viewToken');
    expect(stored).not.toHaveProperty('ip');
    expect(stored).not.toHaveProperty('email');
  });

  it('rejects a CTA event without a recorded exposure for the same view', async () => {
    mockRunFindFirst.mockResolvedValue({ id: RUN_ID, artifact: run.artifact });
    const publicPage = await request(app).get(`/api/public/experiments/${TOKEN}`);
    mockEventFindFirst.mockResolvedValue(null);

    const response = await request(app)
      .post(`/api/public/experiments/${TOKEN}/events`)
      .send({
        eventId: EVENT_ID,
        viewToken: publicPage.body.test.viewToken,
        type: 'CTA_CLICKED',
        occurredAt: new Date().toISOString(),
      });

    expect(response.status).toBe(409);
    expect(mockEventCreate).not.toHaveBeenCalled();
  });

  it('accepts duplicate event deliveries idempotently', async () => {
    mockRunFindFirst.mockResolvedValue({ id: RUN_ID, artifact: run.artifact });
    const publicPage = await request(app).get(`/api/public/experiments/${TOKEN}`);
    mockEventCreate.mockRejectedValue(new Prisma.PrismaClientKnownRequestError(
      'Unique constraint',
      { code: 'P2002', clientVersion: '5.22.0' },
    ));

    const response = await request(app)
      .post(`/api/public/experiments/${TOKEN}/events`)
      .send({
        eventId: EVENT_ID,
        viewToken: publicPage.body.test.viewToken,
        type: 'STIMULUS_EXPOSED',
        occurredAt: new Date().toISOString(),
      });

    expect(response.status).toBe(202);
    expect(response.body.accepted).toBe(true);
  });

  it('reports raw numerator and denominator without auto-classifying the idea', async () => {
    mockExperimentFindFirst.mockResolvedValue({
      sampleTarget: 100,
      run,
    });
    mockEventGroupBy.mockResolvedValue([
      { type: 'STIMULUS_EXPOSED', _count: { _all: 40 } },
      { type: 'CTA_CLICKED', _count: { _all: 5 } },
      { type: 'FAKE_DOOR_DISCLOSED', _count: { _all: 5 } },
    ]);
    mockEventAggregate.mockResolvedValue({
      _min: { receivedAt: new Date('2026-07-15T12:00:00.000Z') },
      _max: { receivedAt: new Date('2026-07-15T13:00:00.000Z') },
    });

    const response = await request(app)
      .get(`/api/jobs/${JOB_ID}/selection-experiments/${EXPERIMENT_ID}/results`)
      .set(headers);

    expect(response.status).toBe(200);
    expect(response.body.results).toMatchObject({
      exposures: 40,
      ctaClicks: 5,
      disclosures: 5,
      ctaRate: 0.125,
      sampleProgress: 0.4,
    });
    expect(response.body.results).not.toHaveProperty('outcome');
    expect(response.body.results).not.toHaveProperty('validated');
  });
});
