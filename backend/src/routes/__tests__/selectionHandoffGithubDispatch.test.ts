import {
  IntegrationProvider,
  SelectionDecisionHandoffAction,
  SelectionHandoffDispatchStatus,
} from '@prisma/client';
import express, { type Express } from 'express';
import request from 'supertest';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  jobFindFirst: vi.fn(),
  connectionFindFirst: vi.fn(),
  dispatchCreate: vi.fn(),
  dispatchFindUnique: vi.fn(),
  dispatchFindFirst: vi.fn(),
  dispatchFindUniqueOrThrow: vi.fn(),
  dispatchUpdate: vi.fn(),
  dispatchUpdateMany: vi.fn(),
  listRepositories: vi.fn(),
  mintToken: vi.fn(),
  createIssue: vi.fn(),
  findMatchingIssues: vi.fn(),
}));

vi.mock('../../services/db.js', () => ({
  prisma: {
    job: { findFirst: (...args: unknown[]) => mocks.jobFindFirst(...args) },
    integrationConnection: {
      findFirst: (...args: unknown[]) => mocks.connectionFindFirst(...args),
    },
    selectionHandoffDispatch: {
      create: (...args: unknown[]) => mocks.dispatchCreate(...args),
      findUnique: (...args: unknown[]) => mocks.dispatchFindUnique(...args),
      findFirst: (...args: unknown[]) => mocks.dispatchFindFirst(...args),
      findUniqueOrThrow: (...args: unknown[]) => mocks.dispatchFindUniqueOrThrow(...args),
      update: (...args: unknown[]) => mocks.dispatchUpdate(...args),
      updateMany: (...args: unknown[]) => mocks.dispatchUpdateMany(...args),
    },
  },
}));

vi.mock('../../services/githubAppService.js', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../services/githubAppService.js')>();
  return {
    ...actual,
    listGithubInstallationRepositories: (...args: unknown[]) => mocks.listRepositories(...args),
    mintGithubInstallationToken: (...args: unknown[]) => mocks.mintToken(...args),
    createGithubIssueWithToken: (...args: unknown[]) => mocks.createIssue(...args),
    findMatchingGithubIssues: (...args: unknown[]) => mocks.findMatchingIssues(...args),
  };
});

vi.mock('../../middleware/auth.js', () => ({
  requireInternalAuth: (req: any, res: any, next: any) => {
    if (!req.headers['x-user-id']) return res.status(401).json({ error: 'Unauthorized' });
    req.user = { id: req.headers['x-user-id'] };
    next();
  },
}));

const JOB_ID = '20000000-0000-0000-0000-000000000002';
const DECISION_ID = '10000000-0000-0000-0000-000000000001';
const HANDOFF_ID = '30000000-0000-0000-0000-000000000003';
const CONNECTION_ID = '40000000-0000-0000-0000-000000000004';
const DISPATCH_ID = '50000000-0000-0000-0000-000000000005';
const TEST_EXPERIMENT_ID = '60000000-0000-0000-0000-000000000006';
const headers = { 'x-user-id': 'owner-1' };

function frozenTestBrief() {
  return {
    version: 1,
    experimentId: TEST_EXPERIMENT_ID,
    jobId: JOB_ID,
    lockedAt: '2026-07-16T11:00:00.000Z',
    idea: { ideaId: 'idea-signal', ideaRevision: 3, snapshot: {} },
    origin: null,
    assumption: {
      type: 'DESIRABILITY',
      statement: 'Qualified buyers will make a payment commitment.',
      whyCritical: 'Interest alone does not justify implementation.',
      currentEvidence: 'Interview language only.',
    },
    testDesign: {
      method: 'PREORDER',
      evidenceSignal: 'PAYMENT_INTENT',
      stimulus: 'A priced early-access offer.',
      audience: 'Qualified operations leads',
      channel: 'Interview follow-ups',
      primaryMetric: 'Refundable deposits',
      passThreshold: 'At least 3 deposits.',
      failThreshold: 'No deposits.',
      measurementWindow: 'Stop after 15 conversations or 21 days.',
      sampleTarget: 15,
      costEstimate: '$150',
    },
    decisionRules: {
      pass: 'Proceed.',
      fail: 'Stop or reshape.',
      ambiguous: 'Run diagnostic interviews.',
      invalid: 'Repair recruitment and rerun.',
    },
    briefFingerprint: 'e'.repeat(64),
    runStatusAtDecision: null,
  };
}

function frozenPreMortem() {
  return {
    version: 1,
    target: { ideaId: 'idea-signal', ideaRevision: 3 },
    entries: [{
      failureMode: 'The audience does not return after the first useful signal.',
      earlyWarningSignal: 'Fewer than three of ten trial users return within fourteen days.',
      mitigation: 'Interview non-returning users and narrow the recurring workflow before building more.',
      origin: null,
    }],
  };
}

function handoff(action: SelectionDecisionHandoffAction = SelectionDecisionHandoffAction.BUILD) {
  const validate = action === SelectionDecisionHandoffAction.VALIDATE_MORE;
  const dispatchable = action === SelectionDecisionHandoffAction.BUILD || validate;
  return {
    id: HANDOFF_ID,
    finalDecisionId: DECISION_ID,
    action,
    ideaId: dispatchable ? 'idea-signal' : null,
    ideaRevision: dispatchable ? 3 : null,
    inputFingerprint: 'd'.repeat(64),
    artifact: {
      jobId: JOB_ID,
      finalDecisionId: DECISION_ID,
      action,
      target: dispatchable ? {
        ideaId: 'idea-signal',
        ideaRevision: 3,
        title: 'Signal Desk',
        problem: 'Founders miss repeated buyer signals.',
        audience: 'Solo SaaS founders',
        valueProposition: 'Collect recurring demand in one place.',
        proposedScope: ['Signal inbox'],
        technicalApproach: 'Event ingestion with a searchable evidence store.',
        estimatedBuildTime: '4–6 weeks',
      } : null,
      decision: {
        disposition: validate ? 'TEST_FIRST' : action === SelectionDecisionHandoffAction.PARK ? 'PARK' : action === SelectionDecisionHandoffAction.STOP ? 'STOP' : 'PROCEED',
        recommendationRelation: 'FOLLOWED',
        rationale: 'This is the clearest next move for the current audience.',
        acceptedRisks: 'Distribution remains open.',
        changeCriterion: 'Stop if ten qualified calls produce no follow-up requests.',
        overrideReason: null,
        decidedAt: '2026-07-16T12:00:00.000Z',
      },
      evidence: {
        sourceFingerprint: 'b'.repeat(64),
        reportSha256: 'c'.repeat(64),
        recommendationSnapshot: {},
        selectedIdeaSnapshot: dispatchable ? {} : null,
        alternativesSnapshot: {},
        evidenceSnapshot: validate ? { selectedTestBrief: frozenTestBrief() } : {},
      },
      executionPolicy: {
        providerDispatchAllowed: dispatchable,
        allowedOperation: action === SelectionDecisionHandoffAction.BUILD
          ? 'CREATE_IMPLEMENTATION_ISSUE'
          : validate ? 'CREATE_VALIDATION_ISSUE' : null,
        resumeRequiresNewOwnerDecision: !dispatchable,
        terminal: action === SelectionDecisionHandoffAction.STOP,
      },
      testBrief: validate ? frozenTestBrief() : null,
      preMortem: dispatchable ? frozenPreMortem() : null,
    },
    version: 1,
    createdAt: new Date('2026-07-16T12:05:00.000Z'),
  };
}

function connection(overrides: Record<string, unknown> = {}) {
  return {
    id: CONNECTION_ID,
    userId: 'owner-1',
    provider: IntegrationProvider.GITHUB,
    externalId: '12345',
    accountId: '67890',
    accountLogin: 'nicheiq',
    accountType: 'Organization',
    repositorySelection: 'selected',
    permissions: { issues: 'write' },
    authorizedRepositoryIds: ['987654'],
    status: 'ACTIVE',
    lastVerifiedAt: new Date('2026-07-16T12:00:00.000Z'),
    createdAt: new Date('2026-07-16T12:00:00.000Z'),
    updatedAt: new Date('2026-07-16T12:00:00.000Z'),
    ...overrides,
  };
}

function repository(overrides: Record<string, unknown> = {}) {
  return {
    id: 987654,
    name: 'signal-desk',
    full_name: 'nicheiq/signal-desk',
    html_url: 'https://github.com/nicheiq/signal-desk',
    has_issues: true,
    private: true,
    ...overrides,
  };
}

function payload() {
  return {
    version: 1,
    destination: {
      repositoryId: '987654',
      owner: 'nicheiq',
      name: 'signal-desk',
      fullName: 'nicheiq/signal-desk',
    },
    request: {
      title: 'Build: Signal Desk',
      body: expect.any(String),
    },
  };
}

function dispatch(overrides: Record<string, unknown> = {}) {
  return {
    id: DISPATCH_ID,
    handoffId: HANDOFF_ID,
    connectionId: CONNECTION_ID,
    provider: IntegrationProvider.GITHUB,
    adapterVersion: 1,
    destinationContainerId: '987654',
    destinationSnapshot: {
      repositoryId: '987654',
      owner: 'nicheiq',
      name: 'signal-desk',
      fullName: 'nicheiq/signal-desk',
    },
    payload: {
      version: 1,
      destination: {
        repositoryId: '987654',
        owner: 'nicheiq',
        name: 'signal-desk',
        fullName: 'nicheiq/signal-desk',
      },
      request: {
        title: 'Build: Signal Desk',
        body: `# Implementation brief\n\n<!-- nicheiq-handoff:${HANDOFF_ID} -->\n`,
      },
    },
    payloadFingerprint: 'e'.repeat(64),
    status: SelectionHandoffDispatchStatus.PENDING,
    confirmedByUserId: 'owner-1',
    attemptCount: 1,
    providerRequestStartedAt: new Date('2026-07-16T12:10:00.000Z'),
    providerResourceId: null,
    providerResourceNodeId: null,
    providerResourceNumber: null,
    providerResourceUrl: null,
    lastErrorClass: null,
    lastErrorCode: null,
    settledAt: null,
    reconciledAt: null,
    reconciledByUserId: null,
    createdAt: new Date('2026-07-16T12:10:00.000Z'),
    updatedAt: new Date('2026-07-16T12:10:00.000Z'),
    ...overrides,
  };
}

const githubIssue = {
  id: 7001,
  node_id: 'I_kwDOExample',
  number: 42,
  html_url: 'https://github.com/nicheiq/signal-desk/issues/42',
  title: 'Build: Signal Desk',
  body: null,
};

let app: Express;

async function preview(action: SelectionDecisionHandoffAction = SelectionDecisionHandoffAction.BUILD) {
  mocks.jobFindFirst.mockResolvedValue({
    selectionFinalDecision: { decisionHandoff: handoff(action) },
  });
  return request(app)
    .post(`/api/jobs/${JOB_ID}/decision-handoff/github/preview`)
    .set(headers)
    .send({ connectionId: CONNECTION_ID, repositoryId: '987654' });
}

beforeEach(async () => {
  vi.clearAllMocks();
  mocks.jobFindFirst.mockResolvedValue({
    selectionFinalDecision: { decisionHandoff: handoff() },
  });
  mocks.connectionFindFirst.mockResolvedValue(connection());
  mocks.listRepositories.mockResolvedValue([repository()]);
  mocks.mintToken.mockResolvedValue('installation-token');
  mocks.createIssue.mockResolvedValue(githubIssue);
  mocks.dispatchFindUnique.mockResolvedValue(null);
  mocks.dispatchUpdateMany.mockResolvedValue({ count: 0 });
  mocks.dispatchCreate.mockImplementation(async ({ data }) => dispatch({
    ...data,
    payload: data.payload,
    destinationSnapshot: data.destinationSnapshot,
    payloadFingerprint: data.payloadFingerprint,
  }));
  mocks.dispatchUpdate.mockImplementation(async ({ data }) => dispatch({
    ...data,
    status: data.status,
  }));
  app = express();
  app.use(express.json());
  const { selectionHandoffGithubDispatchRouter } = await import('../selectionHandoffGithubDispatch.js');
  app.use('/api/jobs', selectionHandoffGithubDispatchRouter);
});

describe('selection handoff GitHub dispatch', () => {
  it.each([
    [SelectionDecisionHandoffAction.BUILD, 'Build: Signal Desk'],
    [SelectionDecisionHandoffAction.VALIDATE_MORE, 'Validate: Signal Desk'],
  ])('returns a deterministic %s preview without creating an issue', async (action, title) => {
    const first = await preview(action);
    const second = await preview(action);

    expect(first.status).toBe(200);
    expect(second.body.preview).toEqual(first.body.preview);
    expect(first.body.preview.payload.request.title).toBe(title);
    expect(mocks.createIssue).not.toHaveBeenCalled();
    expect(mocks.dispatchCreate).not.toHaveBeenCalled();
  });

  it.each([
    SelectionDecisionHandoffAction.PARK,
    SelectionDecisionHandoffAction.STOP,
  ])('rejects a %s handoff before persistence or provider access', async (action) => {
    const response = await preview(action);

    expect(response.status).toBe(409);
    expect(mocks.dispatchCreate).not.toHaveBeenCalled();
    expect(mocks.createIssue).not.toHaveBeenCalled();
  });

  it('does not expose another owner\'s handoff', async () => {
    mocks.jobFindFirst.mockResolvedValue(null);

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/decision-handoff/github/preview`)
      .set('x-user-id', 'viewer-2')
      .send({ connectionId: CONNECTION_ID, repositoryId: '987654' });

    expect(response.status).toBe(404);
    expect(mocks.jobFindFirst.mock.calls[0][0].where).toEqual({
      id: JOB_ID,
      userId: 'viewer-2',
    });
    expect(mocks.connectionFindFirst).not.toHaveBeenCalled();
  });

  it('distinguishes an owned job with no handoff from a missing job', async () => {
    mocks.jobFindFirst.mockResolvedValue({ selectionFinalDecision: null });

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/decision-handoff/github/preview`)
      .set(headers)
      .send({ connectionId: CONNECTION_ID, repositoryId: '987654' });

    expect(response.status).toBe(409);
    expect(response.body.error).toBe('Create the decision handoff first');
    expect(mocks.connectionFindFirst).not.toHaveBeenCalled();
  });

  it('requires an active owner connection and a repository in its installation scope', async () => {
    mocks.connectionFindFirst.mockResolvedValueOnce(null);
    const missingConnection = await request(app)
      .post(`/api/jobs/${JOB_ID}/decision-handoff/github/preview`)
      .set(headers)
      .send({ connectionId: CONNECTION_ID, repositoryId: '987654' });
    expect(missingConnection.status).toBe(404);

    mocks.connectionFindFirst.mockResolvedValue(connection({ authorizedRepositoryIds: [] }));
    const unavailableRepository = await request(app)
      .post(`/api/jobs/${JOB_ID}/decision-handoff/github/preview`)
      .set(headers)
      .send({ connectionId: CONNECTION_ID, repositoryId: '987654' });
    expect(unavailableRepository.status).toBe(404);
    expect(mocks.listRepositories).not.toHaveBeenCalled();
    expect(mocks.createIssue).not.toHaveBeenCalled();
  });

  it('rejects a stale preview without creating a receipt or issue', async () => {
    const reviewed = await preview();
    mocks.listRepositories.mockResolvedValue([
      repository({ name: 'renamed', full_name: 'nicheiq/renamed' }),
    ]);

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/decision-handoff/github/dispatch`)
      .set(headers)
      .send({
        connectionId: CONNECTION_ID,
        repositoryId: '987654',
        payloadFingerprint: reviewed.body.preview.payloadFingerprint,
      });

    expect(response.status).toBe(409);
    expect(mocks.dispatchCreate).not.toHaveBeenCalled();
    expect(mocks.createIssue).not.toHaveBeenCalled();
  });

  it('persists PENDING before making the single provider request', async () => {
    const reviewed = await preview();
    const order: string[] = [];
    mocks.dispatchCreate.mockImplementationOnce(async ({ data }) => {
      order.push('receipt');
      return dispatch({ ...data, payload: data.payload, destinationSnapshot: data.destinationSnapshot });
    });
    mocks.createIssue.mockImplementationOnce(async () => {
      order.push('provider');
      return githubIssue;
    });

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/decision-handoff/github/dispatch`)
      .set(headers)
      .send({
        connectionId: CONNECTION_ID,
        repositoryId: '987654',
        payloadFingerprint: reviewed.body.preview.payloadFingerprint,
      });

    expect(response.status).toBe(201);
    expect(order).toEqual(['receipt', 'provider']);
    expect(mocks.dispatchCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        handoffId: HANDOFF_ID,
        payload: expect.objectContaining(payload()),
        payloadFingerprint: reviewed.body.preview.payloadFingerprint,
      }),
    });
    expect(mocks.dispatchCreate.mock.calls[0][0].data).not.toHaveProperty('status');
  });

  it('returns an existing exact receipt without a second provider call', async () => {
    const reviewed = await preview();
    mocks.dispatchFindUnique.mockResolvedValue(dispatch({
      payloadFingerprint: reviewed.body.preview.payloadFingerprint,
      payload: reviewed.body.preview.payload,
      status: SelectionHandoffDispatchStatus.SUCCEEDED,
    }));

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/decision-handoff/github/dispatch`)
      .set(headers)
      .send({
        connectionId: CONNECTION_ID,
        repositoryId: '987654',
        payloadFingerprint: reviewed.body.preview.payloadFingerprint,
      });

    expect(response.status).toBe(200);
    expect(response.body.dispatch.status).toBe('SUCCEEDED');
    expect(mocks.dispatchCreate).not.toHaveBeenCalled();
    expect(mocks.createIssue).not.toHaveBeenCalled();
  });

  it('reclaims a definitively retryable FAILED receipt before one new provider call', async () => {
    const reviewed = await preview();
    const failed = dispatch({
      payloadFingerprint: reviewed.body.preview.payloadFingerprint,
      payload: reviewed.body.preview.payload,
      status: SelectionHandoffDispatchStatus.FAILED,
      lastErrorClass: 'PROVIDER_REJECTED',
      lastErrorCode: 'GITHUB_FORBIDDEN',
      settledAt: new Date('2026-07-16T12:11:00.000Z'),
    });
    mocks.dispatchFindUnique.mockResolvedValue(failed);
    mocks.dispatchUpdateMany
      .mockResolvedValueOnce({ count: 0 })
      .mockResolvedValueOnce({ count: 1 });
    mocks.dispatchFindUniqueOrThrow.mockResolvedValue(dispatch({
      payloadFingerprint: reviewed.body.preview.payloadFingerprint,
      payload: reviewed.body.preview.payload,
      attemptCount: 2,
    }));

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/decision-handoff/github/dispatch`)
      .set(headers)
      .send({
        connectionId: CONNECTION_ID,
        repositoryId: '987654',
        payloadFingerprint: reviewed.body.preview.payloadFingerprint,
      });

    expect(response.status).toBe(201);
    expect(mocks.dispatchUpdateMany).toHaveBeenLastCalledWith({
      where: {
        id: DISPATCH_ID,
        status: SelectionHandoffDispatchStatus.FAILED,
        attemptCount: 1,
        lastErrorCode: {
          in: ['GITHUB_FORBIDDEN', 'GITHUB_REPOSITORY_NOT_FOUND', 'GITHUB_RATE_LIMITED'],
        },
      },
      data: expect.objectContaining({
        status: SelectionHandoffDispatchStatus.PENDING,
        attemptCount: { increment: 1 },
        lastErrorClass: null,
        lastErrorCode: null,
        settledAt: null,
      }),
    });
    expect(mocks.createIssue).toHaveBeenCalledTimes(1);
  });

  it('keeps non-retryable FAILED receipts terminal', async () => {
    const reviewed = await preview();
    mocks.dispatchFindUnique.mockResolvedValue(dispatch({
      payloadFingerprint: reviewed.body.preview.payloadFingerprint,
      payload: reviewed.body.preview.payload,
      status: SelectionHandoffDispatchStatus.FAILED,
      lastErrorClass: 'PROVIDER_REJECTED',
      lastErrorCode: 'GITHUB_ISSUE_REJECTED',
      settledAt: new Date('2026-07-16T12:11:00.000Z'),
    }));

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/decision-handoff/github/dispatch`)
      .set(headers)
      .send({
        connectionId: CONNECTION_ID,
        repositoryId: '987654',
        payloadFingerprint: reviewed.body.preview.payloadFingerprint,
      });

    expect(response.status).toBe(200);
    expect(response.body.dispatch.retryable).toBe(false);
    expect(mocks.mintToken).not.toHaveBeenCalled();
    expect(mocks.createIssue).not.toHaveBeenCalled();
  });

  it('lets only the FAILED-to-PENDING CAS winner call GitHub', async () => {
    const reviewed = await preview();
    mocks.dispatchFindUnique.mockResolvedValue(dispatch({
      payloadFingerprint: reviewed.body.preview.payloadFingerprint,
      payload: reviewed.body.preview.payload,
      status: SelectionHandoffDispatchStatus.FAILED,
      lastErrorClass: 'PROVIDER_REJECTED',
      lastErrorCode: 'GITHUB_RATE_LIMITED',
      settledAt: new Date('2026-07-16T12:11:00.000Z'),
    }));
    mocks.dispatchUpdateMany.mockResolvedValue({ count: 0 });
    mocks.dispatchFindUniqueOrThrow.mockResolvedValue(dispatch({
      payloadFingerprint: reviewed.body.preview.payloadFingerprint,
      payload: reviewed.body.preview.payload,
      status: SelectionHandoffDispatchStatus.PENDING,
      attemptCount: 2,
    }));

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/decision-handoff/github/dispatch`)
      .set(headers)
      .send({
        connectionId: CONNECTION_ID,
        repositoryId: '987654',
        payloadFingerprint: reviewed.body.preview.payloadFingerprint,
      });

    expect(response.status).toBe(200);
    expect(response.body.dispatch.status).toBe('PENDING');
    expect(response.body.dispatch.attemptCount).toBe(2);
    expect(mocks.createIssue).not.toHaveBeenCalled();
  });

  it('records a successful GitHub issue receipt', async () => {
    const reviewed = await preview();
    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/decision-handoff/github/dispatch`)
      .set(headers)
      .send({
        connectionId: CONNECTION_ID,
        repositoryId: '987654',
        payloadFingerprint: reviewed.body.preview.payloadFingerprint,
      });

    expect(response.status).toBe(201);
    expect(mocks.dispatchUpdate).toHaveBeenCalledWith({
      where: { id: DISPATCH_ID },
      data: expect.objectContaining({
        status: SelectionHandoffDispatchStatus.SUCCEEDED,
        providerResourceId: '7001',
        providerResourceNumber: 42,
        providerResourceUrl: githubIssue.html_url,
      }),
    });
  });

  it('classifies a definitive provider rejection as FAILED', async () => {
    const reviewed = await preview();
    const { GithubProviderError } = await import('../../services/githubAppService.js');
    mocks.createIssue.mockRejectedValue(new GithubProviderError(422, 'GITHUB_ISSUE_REJECTED', false));

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/decision-handoff/github/dispatch`)
      .set(headers)
      .send({ connectionId: CONNECTION_ID, repositoryId: '987654', payloadFingerprint: reviewed.body.preview.payloadFingerprint });

    expect(response.status).toBe(201);
    expect(mocks.dispatchUpdate).toHaveBeenCalledWith({
      where: { id: DISPATCH_ID },
      data: expect.objectContaining({
        status: SelectionHandoffDispatchStatus.FAILED,
        lastErrorClass: 'PROVIDER_REJECTED',
        lastErrorCode: 'GITHUB_ISSUE_REJECTED',
      }),
    });
  });

  it('classifies an ambiguous provider outcome as UNKNOWN', async () => {
    const reviewed = await preview();
    mocks.createIssue.mockRejectedValue(new Error('connection reset'));

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/decision-handoff/github/dispatch`)
      .set(headers)
      .send({ connectionId: CONNECTION_ID, repositoryId: '987654', payloadFingerprint: reviewed.body.preview.payloadFingerprint });

    expect(response.status).toBe(201);
    expect(mocks.dispatchUpdate).toHaveBeenCalledWith({
      where: { id: DISPATCH_ID },
      data: expect.objectContaining({
        status: SelectionHandoffDispatchStatus.UNKNOWN,
        lastErrorClass: 'AMBIGUOUS',
        lastErrorCode: 'GITHUB_CREATE_OUTCOME_UNKNOWN',
      }),
    });
  });

  it('recovers stale PENDING receipts as UNKNOWN without calling GitHub', async () => {
    mocks.dispatchFindUnique.mockResolvedValue(dispatch({
      status: SelectionHandoffDispatchStatus.UNKNOWN,
      lastErrorClass: 'AMBIGUOUS',
      lastErrorCode: 'STALE_PENDING',
      settledAt: new Date(),
    }));

    const response = await request(app)
      .get(`/api/jobs/${JOB_ID}/decision-handoff/github/dispatch`)
      .set(headers);

    expect(response.status).toBe(200);
    expect(response.body.dispatch.status).toBe('UNKNOWN');
    expect(mocks.dispatchUpdateMany).toHaveBeenCalledWith({
      where: expect.objectContaining({
        handoffId: HANDOFF_ID,
        provider: IntegrationProvider.GITHUB,
        status: SelectionHandoffDispatchStatus.PENDING,
        updatedAt: { lt: expect.any(Date) },
      }),
      data: expect.objectContaining({
        status: SelectionHandoffDispatchStatus.UNKNOWN,
        lastErrorCode: 'STALE_PENDING',
      }),
    });
    expect(mocks.createIssue).not.toHaveBeenCalled();
  });

  it('reconciles one exact UNKNOWN match to SUCCEEDED without creating another issue', async () => {
    const unknown = dispatch({
      status: SelectionHandoffDispatchStatus.UNKNOWN,
      lastErrorClass: 'AMBIGUOUS',
      lastErrorCode: 'GITHUB_CREATE_OUTCOME_UNKNOWN',
      settledAt: new Date('2026-07-16T12:11:00.000Z'),
    });
    const succeeded = dispatch({
      status: SelectionHandoffDispatchStatus.SUCCEEDED,
      providerResourceId: '7001',
      providerResourceNodeId: githubIssue.node_id,
      providerResourceNumber: 42,
      providerResourceUrl: githubIssue.html_url,
      lastErrorClass: null,
      lastErrorCode: null,
      reconciledAt: new Date('2026-07-16T12:20:00.000Z'),
      reconciledByUserId: 'owner-1',
    });
    mocks.dispatchFindFirst.mockResolvedValue(unknown);
    mocks.findMatchingIssues.mockResolvedValue([githubIssue]);
    mocks.dispatchUpdateMany.mockResolvedValue({ count: 1 });
    mocks.dispatchFindUniqueOrThrow.mockResolvedValue(succeeded);

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/decision-handoff/github/dispatch/${DISPATCH_ID}/reconcile`)
      .set(headers)
      .send({});

    expect(response.status).toBe(200);
    expect(response.body.reconciliation).toBe('matched');
    expect(response.body.dispatch.status).toBe('SUCCEEDED');
    expect(mocks.dispatchUpdateMany).toHaveBeenLastCalledWith({
      where: { id: DISPATCH_ID, status: SelectionHandoffDispatchStatus.UNKNOWN },
      data: expect.objectContaining({
        status: SelectionHandoffDispatchStatus.SUCCEEDED,
        providerResourceId: '7001',
        reconciledByUserId: 'owner-1',
      }),
    });
    expect(mocks.createIssue).not.toHaveBeenCalled();
  });
});
