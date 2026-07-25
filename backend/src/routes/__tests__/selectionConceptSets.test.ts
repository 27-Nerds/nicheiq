import { beforeEach, describe, expect, it, vi } from 'vitest';
import express from 'express';
import request from 'supertest';

// These suites exercise route logic, not the decision-tools grant. The grant itself is
// covered in middleware/__tests__/featureAccess.test.ts.
vi.mock('../../middleware/featureAccess.js', () => ({
  requireDecisionToolsAccess: (_req: any, _res: any, next: any) => next(),
}));

const mocks = vi.hoisted(() => ({
  jobFindFirst: vi.fn(),
  jobUpdate: vi.fn(),
  challengeFindMany: vi.fn(),
  evidenceFindMany: vi.fn(),
  conclusionFindMany: vi.fn(),
  setFindUnique: vi.fn(),
  setFindFirst: vi.fn(),
  setFindMany: vi.fn(),
  setCount: vi.fn(),
  setCreate: vi.fn(),
  setUpdate: vi.fn(),
  setUpdateMany: vi.fn(),
  messageFindUnique: vi.fn(),
  messageFindMany: vi.fn(),
  messageCreate: vi.fn(),
  getReport: vi.fn(),
  generate: vi.fn(),
}));

vi.mock('../../config.js', () => ({ CONFIG: { openaiApiKey: 'test-key', openrouterApiKey: '' } }));
vi.mock('../../services/assetService.js', () => ({
  getPreviewReportForJob: mocks.getReport,
}));
vi.mock('../../services/db.js', () => ({
  prisma: {
    job: { findFirst: mocks.jobFindFirst, update: mocks.jobUpdate },
    selectionChallenge: { findMany: mocks.challengeFindMany },
    selectionOwnerEvidence: { findMany: mocks.evidenceFindMany },
    selectionExperimentConclusion: { findMany: mocks.conclusionFindMany },
    selectionConceptSet: {
      findUnique: mocks.setFindUnique,
      findFirst: mocks.setFindFirst,
      findMany: mocks.setFindMany,
      count: mocks.setCount,
      create: mocks.setCreate,
      update: mocks.setUpdate,
      updateMany: mocks.setUpdateMany,
    },
    chatMessage: {
      findUnique: mocks.messageFindUnique,
      findMany: mocks.messageFindMany,
      create: mocks.messageCreate,
    },
  },
}));
vi.mock('../../services/selectionConceptSetService.js', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../services/selectionConceptSetService.js')>();
  return { ...actual, generateSelectionConceptSet: mocks.generate };
});
vi.mock('../../middleware/auth.js', () => ({
  requireInternalAuth: (req: any, res: any, next: any) => {
    if (!req.headers['x-user-id']) return res.status(401).json({ error: 'Unauthorized' });
    req.user = { id: req.headers['x-user-id'] };
    next();
  },
  AuthenticatedRequest: {},
}));

import {
  ConceptSetGenerationError,
  prepareSelectionConceptSetInput,
} from '../../services/selectionConceptSetService.js';
import type { SelectionConceptSetArtifact } from '../../types/selectionConceptSet.js';

const JOB_ID = '550e8400-e29b-41d4-a716-446655440000';
const SET_ID = '660e8400-e29b-41d4-a716-446655440000';
const headers = { 'x-user-id': 'owner-1' };
const parent = {
  idea_id: 'idea-signal',
  idea_revision: 3,
  solution_name: 'Signal Desk',
  source_pain: 'Teams miss recurring demand signals',
  source_segment: 'Solo SaaS founders',
  description: 'A broad monitoring workflow.',
};
const report = { market: 'signal monitoring' };

function job(overrides: Record<string, unknown> = {}) {
  return {
    id: JOB_ID,
    status: 'AWAITING_SELECTION',
    solutionIdeas: [parent],
    selectionDecisionProfile: null,
    selectionFounderFit: null,
    selectionFinalDecision: null,
    ...overrides,
  };
}

function artifact(): SelectionConceptSetArtifact {
  const prepared = prepareSelectionConceptSetInput({
    jobId: JOB_ID,
    purpose: 'diverge',
    parents: [parent],
    report,
    founderProfile: null,
    founderFit: null,
    challenges: [],
    conclusions: [],
  });
  const operations = ['narrow', 'reposition', 'adjacent'] as const;
  return {
    inputFingerprint: prepared.inputFingerprint,
    purpose: 'diverge',
    targetTradeoff: null,
    parents: prepared.parents,
    context: prepared.context,
    options: operations.map((operation, index) => {
      const assumptionId = `A${String(index + 1).repeat(10)}`;
      return {
        optionId: `O${String(index + 1).repeat(11)}`,
        operation,
        title: `${operation} direction`,
        brief: `A concrete ${operation} option that changes one product direction.`,
        changeSummary: `Change the ${operation} direction without mutating the source.`,
        rationale: `Expose a distinct decision trade-off for the owner to review.`,
        parentContributions: [{ ...prepared.parents[0], contribution: 'Keep the signal interpretation workflow.' }],
        changedAxes: [{ axis: 'scope', from: 'Broad', to: operation, reason: 'Create a distinct option.' }],
        retainedEvidence: ['The recorded signal pain may still apply.'],
        evidenceToRecheck: ['Demand for the changed workflow must be checked.'],
        assumptions: [{
          assumptionId,
          type: 'demand',
          statement: `Buyers act on the ${operation} workflow.`,
          whyDecisionChanging: 'Without action the option has no demand signal.',
          consequenceIfFalse: 'Park this option.',
        }],
        disqualifiers: ['No qualified buyer commits.'],
        suggestedTest: {
          assumptionId,
          hypothesis: 'Qualified buyers will book a call.',
          method: 'BOOKED_CALL',
          evidenceSignal: 'SMALL_COMMITMENT',
          audience: 'Qualified solo SaaS founders',
          artifact: 'One-page concept with booked-call CTA',
          primaryMetric: 'Qualified booked-call rate',
          passThreshold: 'At least 3 of 20 book',
          failThreshold: 'Zero of 20 book',
          measurementWindow: 'Seven days',
        },
      };
    }),
    model: 'gpt-test',
    promptId: 'selection-concept-forge',
    createdAt: '2026-07-16T12:00:00.000Z',
  };
}

const app = express();
app.use(express.json());
const { selectionConceptSetsRouter } = await import('../selectionConceptSets.js');
app.use('/api/jobs', selectionConceptSetsRouter);

describe('selection concept sets', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    const generated = artifact();
    mocks.jobFindFirst.mockResolvedValue(job());
    mocks.getReport.mockResolvedValue(report);
    mocks.challengeFindMany.mockResolvedValue([]);
    mocks.evidenceFindMany.mockResolvedValue([]);
    mocks.conclusionFindMany.mockResolvedValue([]);
    mocks.setFindUnique.mockResolvedValue(null);
    mocks.setFindFirst.mockResolvedValue({ id: SET_ID, artifact: generated });
    mocks.setFindMany.mockResolvedValue([]);
    mocks.setCount.mockResolvedValue(0);
    mocks.setCreate.mockImplementation(async ({ data }) => ({
      id: SET_ID,
      artifact: data.artifact,
      createdAt: new Date('2026-07-16T12:00:00.000Z'),
    }));
    mocks.messageFindUnique.mockResolvedValue(null);
    mocks.messageFindMany.mockResolvedValue([]);
    mocks.setUpdate.mockResolvedValue({});
    mocks.setUpdateMany.mockResolvedValue({ count: 1 });
    mocks.messageCreate.mockImplementation(async ({ data }) => ({ id: 'proposal-message-1', patchJson: data.patchJson }));
    mocks.jobUpdate.mockResolvedValue({});
    mocks.generate.mockResolvedValue({
      artifact: generated,
      costUsd: 0.01,
      usage: { inputTokens: 100, outputTokens: 500, cacheWriteTokens: 0, cacheReadTokens: 0 },
    });
  });

  it('persists three current options without an unreleased artifact version', async () => {
    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-concept-sets`)
      .set(headers)
      .send({ purpose: 'diverge', parents: [{ ideaId: 'idea-signal', ideaRevision: 3 }] });

    expect(response.status).toBe(201);
    expect(response.body.set.artifact.options).toHaveLength(3);
    expect(response.body.set.artifact).not.toHaveProperty('version');
    expect(mocks.setCreate).toHaveBeenCalledWith(expect.objectContaining({
      data: expect.objectContaining({
        jobId: JOB_ID,
        inputFingerprint: artifact().inputFingerprint,
      }),
    }));
  });

  it('rejects a parent revision that is no longer current before generation', async () => {
    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-concept-sets`)
      .set(headers)
      .send({ purpose: 'diverge', parents: [{ ideaId: 'idea-signal', ideaRevision: 2 }] });

    expect(response.status).toBe(409);
    expect(mocks.generate).not.toHaveBeenCalled();
    expect(mocks.setCreate).not.toHaveBeenCalled();
  });

  it('returns the cached set without a model call when the fingerprint matches', async () => {
    mocks.setFindUnique.mockResolvedValue({
      id: SET_ID,
      artifact: artifact(),
      createdAt: new Date('2026-07-16T12:00:00.000Z'),
    });

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-concept-sets`)
      .set(headers)
      .send({ purpose: 'diverge', parents: [{ ideaId: 'idea-signal', ideaRevision: 3 }] });

    expect(response.status).toBe(200);
    expect(response.body.cached).toBe(true);
    expect(response.body.set.id).toBe(SET_ID);
    expect(mocks.generate).not.toHaveBeenCalled();
    expect(mocks.setCreate).not.toHaveBeenCalled();
  });

  it('refuses new generation once the job reached the concept-set cap', async () => {
    mocks.setCount.mockResolvedValue(12);

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-concept-sets`)
      .set(headers)
      .send({ purpose: 'diverge', parents: [{ ideaId: 'idea-signal', ideaRevision: 3 }] });

    expect(response.status).toBe(409);
    expect(response.body.error).toContain('limit');
    expect(mocks.generate).not.toHaveBeenCalled();
    expect(mocks.setCreate).not.toHaveBeenCalled();
  });

  it('still serves a cache hit when the job is at the concept-set cap', async () => {
    mocks.setCount.mockResolvedValue(12);
    mocks.setFindUnique.mockResolvedValue({
      id: SET_ID,
      artifact: artifact(),
      createdAt: new Date('2026-07-16T12:00:00.000Z'),
    });

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-concept-sets`)
      .set(headers)
      .send({ purpose: 'diverge', parents: [{ ideaId: 'idea-signal', ideaRevision: 3 }] });

    expect(response.status).toBe(200);
    expect(response.body.cached).toBe(true);
    expect(mocks.generate).not.toHaveBeenCalled();
  });

  it('surfaces a structured guardrail code and bills the spend when generation fails', async () => {
    mocks.generate.mockRejectedValue(new ConceptSetGenerationError(
      'COMBINED_CONCEPT_OPTION_REQUIRED',
      0.02,
      { inputTokens: 400, outputTokens: 900, cacheWriteTokens: 0, cacheReadTokens: 0 },
    ));

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-concept-sets`)
      .set(headers)
      .send({ purpose: 'diverge', parents: [{ ideaId: 'idea-signal', ideaRevision: 3 }] });

    expect(response.status).toBe(502);
    expect(response.body.code).toBe('COMBINED_CONCEPT_OPTION_REQUIRED');
    expect(response.body.error).toContain('combine');
    expect(mocks.setCreate).not.toHaveBeenCalled();
    expect(mocks.jobUpdate).toHaveBeenCalledWith({
      where: { id: JOB_ID },
      data: { chatCostUsd: { increment: 0.02 } },
    });
  });

  it('does not write a zero-cost charge when a failed generation spent nothing', async () => {
    mocks.generate.mockRejectedValue(new ConceptSetGenerationError(
      'INVALID_CONCEPT_SET_OUTPUT',
      0,
      { inputTokens: 0, outputTokens: 0, cacheWriteTokens: 0, cacheReadTokens: 0 },
    ));

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-concept-sets`)
      .set(headers)
      .send({ purpose: 'diverge', parents: [{ ideaId: 'idea-signal', ideaRevision: 3 }] });

    expect(response.status).toBe(502);
    expect(response.body.code).toBe('INVALID_CONCEPT_SET_OUTPUT');
    expect(mocks.jobUpdate).not.toHaveBeenCalled();
  });

  it('maps a plain guardrail error to the same structured envelope', async () => {
    mocks.generate.mockRejectedValue(new Error('CONCEPT_OPTIONS_NOT_DISTINCT'));

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-concept-sets`)
      .set(headers)
      .send({ purpose: 'diverge', parents: [{ ideaId: 'idea-signal', ideaRevision: 3 }] });

    expect(response.status).toBe(502);
    expect(response.body.code).toBe('CONCEPT_OPTIONS_NOT_DISTINCT');
    expect(response.body.error).toContain('too similar');
  });

  it('rejects persisting when the shortlist changed while options were generated', async () => {
    mocks.jobFindFirst
      .mockResolvedValueOnce(job())
      .mockResolvedValueOnce(job({ solutionIdeas: [{ ...parent, idea_revision: 4 }] }));

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-concept-sets`)
      .set(headers)
      .send({ purpose: 'diverge', parents: [{ ideaId: 'idea-signal', ideaRevision: 3 }] });

    expect(response.status).toBe(409);
    expect(response.body.error).toContain('changed while options were being prepared');
    expect(mocks.generate).toHaveBeenCalledTimes(1);
    expect(mocks.setCreate).not.toHaveBeenCalled();
  });

  it('prepares one exact option as an unevaluated synthesis proposal without charging', async () => {
    const current = artifact();
    mocks.setFindFirst.mockResolvedValue({ id: SET_ID, artifact: current });

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-concept-sets/${SET_ID}/options/${current.options[0].optionId}/proposal`)
      .set(headers)
      .send({ expectedInputFingerprint: current.inputFingerprint });

    expect(response.status).toBe(201);
    expect(response.body.sourceMessageId).toBe('proposal-message-1');
    expect(response.body.patch).toMatchObject({
      kind: 'idea_synthesis',
      operation: 'narrow',
      parents: [{ ideaId: 'idea-signal', ideaRevision: 3 }],
      evidence: { sourceAnchors: [{ candidateSnapshotSha256: current.parents[0].candidateSnapshotSha256 }] },
    });
    expect(mocks.messageCreate).toHaveBeenCalledWith(expect.objectContaining({
      data: expect.objectContaining({ origin: 'concept_forge' }),
    }));
    expect(mocks.jobUpdate).not.toHaveBeenCalled();
  });

  it('reports a server error when a stored option cannot produce a valid patch', async () => {
    const current = artifact();
    current.options[0].changeSummary = 'x'.repeat(650);
    mocks.setFindFirst.mockResolvedValue({ id: SET_ID, artifact: current });
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-concept-sets/${SET_ID}/options/${current.options[0].optionId}/proposal`)
      .set(headers)
      .send({ expectedInputFingerprint: current.inputFingerprint });

    expect(response.status).toBe(500);
    expect(response.body.error).toBe('Failed to prepare concept option');
    expect(mocks.messageCreate).not.toHaveBeenCalled();
    expect(consoleError).toHaveBeenCalledWith(expect.stringContaining(SET_ID), expect.anything());
    consoleError.mockRestore();
  });

  it('lists only unarchived sets and stamps evaluated options from proposal records', async () => {
    const stored = artifact();
    mocks.setFindMany.mockResolvedValue([{
      id: SET_ID,
      artifact: stored,
      createdAt: new Date('2026-07-16T12:00:00.000Z'),
    }]);
    mocks.messageFindMany.mockResolvedValue([
      { operationId: `concept:${SET_ID}:${stored.options[1].optionId}` },
    ]);

    const response = await request(app)
      .get(`/api/jobs/${JOB_ID}/selection-concept-sets`)
      .set(headers);

    expect(response.status).toBe(200);
    expect(mocks.setFindMany).toHaveBeenCalledWith(expect.objectContaining({
      where: { jobId: JOB_ID, archivedAt: null },
    }));
    expect(mocks.messageFindMany).toHaveBeenCalledWith({
      where: {
        operationId: {
          in: stored.options.map((option) => `concept:${SET_ID}:${option.optionId}`),
        },
      },
      select: { operationId: true },
    });
    expect(response.body.sets[0].evaluatedOptionIds).toEqual([stored.options[1].optionId]);
  });

  it('excludes archived sets from the cap and points the cap message at discarding', async () => {
    mocks.setCount.mockResolvedValue(12);

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-concept-sets`)
      .set(headers)
      .send({ purpose: 'diverge', parents: [{ ideaId: 'idea-signal', ideaRevision: 3 }] });

    expect(response.status).toBe(409);
    expect(response.body.error).toContain('discard a saved set');
    expect(mocks.setCount).toHaveBeenCalledWith({
      where: { jobId: JOB_ID, archivedAt: null },
    });
  });

  it('revives an archived set on a matching fingerprint instead of regenerating', async () => {
    mocks.setFindUnique.mockResolvedValue({
      id: SET_ID,
      artifact: artifact(),
      createdAt: new Date('2026-07-16T12:00:00.000Z'),
      archivedAt: new Date('2026-07-17T12:00:00.000Z'),
    });

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-concept-sets`)
      .set(headers)
      .send({ purpose: 'diverge', parents: [{ ideaId: 'idea-signal', ideaRevision: 3 }] });

    expect(response.status).toBe(200);
    expect(response.body.cached).toBe(true);
    expect(mocks.setUpdate).toHaveBeenCalledWith({
      where: { id: SET_ID },
      data: { archivedAt: null },
    });
    expect(mocks.generate).not.toHaveBeenCalled();
  });

  it('archives an owned set with a timestamp and stays idempotent', async () => {
    mocks.setFindFirst.mockResolvedValue({ id: SET_ID, archivedAt: null });

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-concept-sets/${SET_ID}/archive`)
      .set(headers);

    expect(response.status).toBe(204);
    expect(mocks.setUpdateMany).toHaveBeenCalledWith({
      where: { id: SET_ID, archivedAt: null },
      data: { archivedAt: expect.any(Date) },
    });

    mocks.setUpdateMany.mockClear();
    mocks.setFindFirst.mockResolvedValue({ id: SET_ID, archivedAt: new Date() });
    const repeat = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-concept-sets/${SET_ID}/archive`)
      .set(headers);
    expect(repeat.status).toBe(204);
    expect(mocks.setUpdateMany).not.toHaveBeenCalled();
  });

  it('refuses archiving an unknown set or one on a locked decision', async () => {
    mocks.setFindFirst.mockResolvedValue(null);
    const missing = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-concept-sets/${SET_ID}/archive`)
      .set(headers);
    expect(missing.status).toBe(404);

    mocks.jobFindFirst.mockResolvedValue(job({ selectionFinalDecision: { id: 'decision-1' } }));
    const locked = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-concept-sets/${SET_ID}/archive`)
      .set(headers);
    expect(locked.status).toBe(409);
    expect(mocks.setUpdateMany).not.toHaveBeenCalled();
  });

  it('hides an archived set from proposal preparation', async () => {
    const current = artifact();
    mocks.setFindFirst.mockResolvedValue(null);

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-concept-sets/${SET_ID}/options/${current.options[0].optionId}/proposal`)
      .set(headers)
      .send({ expectedInputFingerprint: current.inputFingerprint });

    expect(response.status).toBe(404);
    expect(mocks.setFindFirst).toHaveBeenCalledWith(expect.objectContaining({
      where: expect.objectContaining({ archivedAt: null }),
    }));
    expect(mocks.messageCreate).not.toHaveBeenCalled();
  });

  it('refuses proposal preparation when the owner reviewed a different fingerprint', async () => {
    const current = artifact();
    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-concept-sets/${SET_ID}/options/${current.options[0].optionId}/proposal`)
      .set(headers)
      .send({ expectedInputFingerprint: 'e'.repeat(64) });

    expect(response.status).toBe(409);
    expect(mocks.messageCreate).not.toHaveBeenCalled();
  });
});
