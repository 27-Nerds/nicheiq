import { beforeEach, describe, expect, it, vi } from 'vitest';
import express, { type Express } from 'express';
import request from 'supertest';

// These suites exercise route logic, not the decision-tools grant. The grant itself is
// covered in middleware/__tests__/featureAccess.test.ts.
vi.mock('../../middleware/featureAccess.js', () => ({
  requireDecisionToolsAccess: (_req: any, _res: any, next: any) => next(),
}));

const experimentFindFirst = vi.fn();
const messageFindUnique = vi.fn();
const messageFindMany = vi.fn();
const messageCreate = vi.fn();
const dispatchFindFirst = vi.fn();
const jobUpdate = vi.fn();
const generate = vi.fn();

vi.mock('../../config.js', () => ({ CONFIG: { openaiApiKey: 'test-key' } }));
vi.mock('../../services/db.js', () => ({
  prisma: {
    selectionExperiment: { findFirst: (...args: unknown[]) => experimentFindFirst(...args) },
    chatMessage: {
      findUnique: (...args: unknown[]) => messageFindUnique(...args),
      findMany: (...args: unknown[]) => messageFindMany(...args),
      create: (...args: unknown[]) => messageCreate(...args),
    },
    jobDispatch: { findFirst: (...args: unknown[]) => dispatchFindFirst(...args) },
    job: { update: (...args: unknown[]) => jobUpdate(...args) },
  },
}));
vi.mock('../../services/selectionIdeaNarrowingService.js', () => ({
  generateSelectionIdeaNarrowing: (...args: unknown[]) => generate(...args),
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
const CONCLUSION_ID = '223e4567-e89b-42d3-a456-426614174000';
const headers = { 'x-user-id': 'owner-1' };
const patch = {
  kind: 'idea_synthesis',
  operation: 'narrow',
  proposedTitle: 'Agency Renewal Signal Desk',
  proposedBrief: 'One weekly renewal-risk review for small agency operators.',
  changeSummary: 'Narrows buyer and workflow.',
  rationale: 'The broad promise did not earn commitment.',
  parents: [{
    ideaId: 'idea-parent',
    ideaRevision: 3,
    solutionName: 'Signal Desk',
    contribution: 'Keep the recurring signal workflow.',
  }],
  evidence: {
    sourceAnchors: [{ ideaId: 'idea-parent', ideaRevision: 3, candidateSnapshotSha256: 'a'.repeat(64), pain: 'Missed demand signals' }],
    requiresValidation: ['Validate the narrower buyer.'],
    experimentConclusionRefs: [{
      conclusionId: CONCLUSION_ID,
      experimentId: EXPERIMENT_ID,
      outcome: 'FAIL',
      evidenceSource: 'MANUAL',
      snapshotSha256: 'a'.repeat(64),
      evidenceRefs: [],
    }],
  },
  newAssumptions: ['Agency operators run this review weekly.'],
};
const baseExperiment = {
  id: EXPERIMENT_ID,
  jobId: JOB_ID,
  ideaId: 'idea-parent',
  ideaRevision: 3,
  conclusion: {
    id: CONCLUSION_ID,
    outcome: 'FAIL',
    evidenceSource: 'MANUAL',
    snapshot: { schemaVersion: 1 },
  },
  job: {
    status: 'AWAITING_SELECTION',
    solutionIdeas: [{
      idea_id: 'idea-parent',
      idea_revision: 3,
      solution_name: 'Signal Desk',
      source_pain: 'Missed demand signals',
    }],
    selectionDecisionProfile: null,
    selectionFinalDecision: null,
  },
};

let app: Express;

beforeEach(async () => {
  vi.clearAllMocks();
  experimentFindFirst.mockResolvedValue(baseExperiment);
  messageFindUnique.mockResolvedValue(null);
  messageFindMany.mockResolvedValue([]);
  dispatchFindFirst.mockResolvedValue(null);
  messageCreate.mockImplementation(async ({ data }) => ({
    id: 'proposal-message-1',
    content: data.content,
    patchJson: data.patchJson,
    createdAt: new Date('2026-07-16T12:00:00.000Z'),
  }));
  jobUpdate.mockResolvedValue({});
  generate.mockResolvedValue({
    patch,
    content: 'One narrowed, unevaluated variant.',
    model: 'test-model',
    promptVersion: 'selection-narrowing-v1',
    costUsd: 0.001,
    usage: { inputTokens: 100, outputTokens: 50, cacheWriteTokens: 0, cacheReadTokens: 0 },
  });
  app = express();
  app.use(express.json());
  const { selectionIdeaNarrowingRouter } = await import('../selectionIdeaNarrowing.js');
  app.use('/api/jobs', selectionIdeaNarrowingRouter);
});

describe('selection idea narrowing proposals', () => {
  it('persists one owner proposal with server-owned operation identity and provenance', async () => {
    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-experiments/${EXPERIMENT_ID}/narrowing-proposal`)
      .set(headers)
      .send({});

    expect(response.status).toBe(201);
    expect(generate).toHaveBeenCalledWith(expect.objectContaining({
      experimentId: EXPERIMENT_ID,
      conclusionId: CONCLUSION_ID,
      parent: expect.objectContaining({ ideaId: 'idea-parent', ideaRevision: 3 }),
    }));
    expect(messageCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        jobId: JOB_ID,
        role: 'assistant',
        origin: 'experiment_narrowing',
        operationId: `narrow:${CONCLUSION_ID}:v1`,
        patchJson: patch,
      }),
      select: expect.any(Object),
    });
    expect(response.body.settlement.state).toBe('ready');
  });

  it('returns the same durable proposal on an exact repeat without another AI call', async () => {
    messageFindUnique.mockResolvedValue({
      id: 'proposal-message-1',
      content: 'Existing proposal',
      patchJson: patch,
      createdAt: new Date(),
    });

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-experiments/${EXPERIMENT_ID}/narrowing-proposal`)
      .set(headers)
      .send({});

    expect(response.status).toBe(200);
    expect(response.body.cached).toBe(true);
    expect(generate).not.toHaveBeenCalled();
    expect(messageCreate).not.toHaveBeenCalled();
  });

  it.each(['PASS', 'INVALID'])('rejects a %s conclusion', async (outcome) => {
    experimentFindFirst.mockResolvedValue({
      ...baseExperiment,
      conclusion: { ...baseExperiment.conclusion, outcome },
    });
    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-experiments/${EXPERIMENT_ID}/narrowing-proposal`)
      .set(headers);
    expect(response.status).toBe(409);
    expect(generate).not.toHaveBeenCalled();
  });

  it('does not reveal another owner\'s experiment', async () => {
    experimentFindFirst.mockResolvedValue(null);
    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-experiments/${EXPERIMENT_ID}/narrowing-proposal`)
      .set(headers);
    expect(response.status).toBe(404);
  });

  it('does not persist a proposal if the exact parent disappears during generation', async () => {
    experimentFindFirst
      .mockResolvedValueOnce(baseExperiment)
      .mockResolvedValueOnce({
        ...baseExperiment,
        job: { ...baseExperiment.job, solutionIdeas: [] },
      });
    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-experiments/${EXPERIMENT_ID}/narrowing-proposal`)
      .set(headers);
    expect(response.status).toBe(409);
    expect(messageCreate).not.toHaveBeenCalled();
  });

  it('restores a settled receipt for the exact proposal message', async () => {
    messageFindUnique.mockResolvedValue({
      id: 'proposal-message-1',
      content: 'Existing proposal',
      patchJson: patch,
      createdAt: new Date(),
    });
    dispatchFindFirst.mockResolvedValue({ state: 'SETTLED' });
    messageFindMany.mockResolvedValue([{
      patchJson: {
        kind: 'ledger_event',
        sourceMessageId: 'proposal-message-1',
        outcome: 'accepted',
        idea: {
          solution_name: 'Agency Renewal Signal Desk',
          idea_id: 'idea-child',
          idea_revision: 1,
          synthesis_operation: 'narrow',
          synthesized_from: [{
            idea_id: 'idea-parent',
            idea_revision: 3,
            solution_name: 'Signal Desk',
            contribution: 'Keep the recurring signal workflow.',
          }],
          synthesis_source_message_id: 'proposal-message-1',
        },
      },
    }]);

    const response = await request(app)
      .get(`/api/jobs/${JOB_ID}/selection-experiments/${EXPERIMENT_ID}/narrowing-proposal`)
      .set(headers);
    expect(response.status).toBe(200);
    expect(response.body.settlement).toEqual({
      state: 'accepted',
      idea: {
        solution_name: 'Agency Renewal Signal Desk',
        idea_id: 'idea-child',
        idea_revision: 1,
        synthesis_operation: 'narrow',
        synthesized_from: [{
          idea_id: 'idea-parent',
          idea_revision: 3,
          solution_name: 'Signal Desk',
          contribution: 'Keep the recurring signal workflow.',
        }],
        synthesis_source_message_id: 'proposal-message-1',
      },
    });
  });
});
