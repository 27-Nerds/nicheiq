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
  loadSelectionContext: vi.fn(),
  generate: vi.fn(),
  parseCurrentFounderFitArtifact: vi.fn(),
  /** Live row the create-path fingerprint cache should find, or null for a miss. */
  setCachedLive: null as unknown,
  /** Backing store for the mocked Redis single-flight lock. */
  redisStore: new Map<string, string>(),
}));

vi.mock('../../config.js', () => ({ CONFIG: { openaiApiKey: 'test-key', openrouterApiKey: '' } }));
// Real SET NX semantics, so the single-flight lock is exercised rather than failing open.
vi.mock('../../services/redis.js', () => ({
  getRedis: () => ({
    set: async (key: string, value: string, _ex: string, _ttl: number, nx?: string) => {
      if (nx === 'NX' && mocks.redisStore.has(key)) return null;
      mocks.redisStore.set(key, value);
      return 'OK';
    },
    eval: async (_s: string, _n: number, key: string, token: string) => {
      if (mocks.redisStore.get(key) !== token) return 0;
      mocks.redisStore.delete(key);
      return 1;
    },
  }),
}));
vi.mock('../../services/assetService.js', () => ({
  getPreviewReportForJob: mocks.getReport,
}));
vi.mock('../../services/currentSelectionContext.js', () => ({
  loadCurrentSelectionContext: mocks.loadSelectionContext,
}));
vi.mock('../../services/founderFitService.js', () => ({
  parseCurrentFounderFitArtifact: (...args: unknown[]) => mocks.parseCurrentFounderFitArtifact(...args),
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
import type { CandidatePoolVersion } from '../../services/currentSelectionContext.js';

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

function artifact(
  contextOverrides: { founderProfile?: unknown; founderFit?: unknown } = {},
): SelectionConceptSetArtifact {
  const prepared = prepareSelectionConceptSetInput({
    jobId: JOB_ID,
    candidatePoolVersion: 7 as CandidatePoolVersion,
    purpose: 'diverge',
    parents: [parent],
    report,
    founderProfile: null,
    founderFit: null,
    challenges: [],
    conclusions: [],
    ...contextOverrides,
  } as any);
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
    mocks.redisStore.clear();
    const generated = artifact();
    mocks.jobFindFirst.mockResolvedValue(job());
    mocks.loadSelectionContext.mockResolvedValue({
      job: {
        status: 'AWAITING_SELECTION',
        niche: 'test niche',
        gateStage: null,
        activeDispatchId: null,
      },
      canonical: { candidates: [parent], displayedCount: 1, version: 7 },
      runArtifacts: {
        verification: 'verified',
        candidatePoolVersion: 7,
        previewReport: report,
      },
      openingOrigin: 'opening:cv:test',
    });
    mocks.getReport.mockResolvedValue(report);
    mocks.parseCurrentFounderFitArtifact.mockReturnValue(null);
    mocks.challengeFindMany.mockResolvedValue([]);
    mocks.evidenceFindMany.mockResolvedValue([]);
    mocks.conclusionFindMany.mockResolvedValue([]);
    mocks.setFindUnique.mockResolvedValue(null);
    // The create path's cache lookup and the by-id lookups share this mock. Discriminate
    // on the where clause: a fingerprint query is the cache (no live hit by default), an
    // id query is the proposal/archive read.
    mocks.setCachedLive = null;
    mocks.setFindFirst.mockImplementation(async ({ where }: any) =>
      where?.inputFingerprint !== undefined
        ? mocks.setCachedLive
        : { id: SET_ID, artifact: generated, candidatePoolVersion: 7 });
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
      candidatePoolVersion: 7,
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
        candidatePoolVersion: 7,
        inputFingerprint: artifact().inputFingerprint,
      }),
    }));
  });

  it('feeds Concept Forge founder fit through the read-time contract, never the raw artifact', async () => {
    // `founderFit` lands in the prompt payload, so a raw passthrough makes an unvalidated stored
    // artifact into grounding the model reasons from — including one written under a delivery
    // model this profile does not have, or one that predates the current candidate revisions.
    const storedRaw = {
      version: 1,
      inputFingerprint: 'f'.repeat(64),
      results: [{ summary: 'You will build the first release yourself.' }],
    };
    const contracted = {
      version: 1,
      inputFingerprint: 'a'.repeat(64),
      results: [{ summary: 'A contractor will build the software.' }],
    };
    const founderProfile = { team: 'solo', buildModel: 'contractor' };
    mocks.jobFindFirst.mockResolvedValue(job({
      selectionDecisionProfile: founderProfile,
      selectionFounderFit: storedRaw,
    }));
    mocks.parseCurrentFounderFitArtifact.mockReturnValue(contracted);
    mocks.generate.mockResolvedValue({
      candidatePoolVersion: 7,
      artifact: artifact({ founderProfile, founderFit: contracted }),
      costUsd: 0.01,
      usage: { inputTokens: 100, outputTokens: 500, cacheWriteTokens: 0, cacheReadTokens: 0 },
    });

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-concept-sets`)
      .set(headers)
      .send({ purpose: 'diverge', parents: [{ ideaId: 'idea-signal', ideaRevision: 3 }] });

    expect(response.status).toBe(201);
    expect(mocks.parseCurrentFounderFitArtifact).toHaveBeenCalledWith(
      storedRaw,
      founderProfile,
      [parent],
    );
    const sent = mocks.generate.mock.calls[0][0];
    expect(sent.founderFit).toEqual(contracted);
    expect(JSON.stringify(sent)).not.toContain('You will build the first release yourself');
  });

  it('sends no founder fit at all when the stored artifact fails the read-time contract', async () => {
    const founderProfile = { team: 'solo' };
    mocks.jobFindFirst.mockResolvedValue(job({
      selectionDecisionProfile: founderProfile,
      selectionFounderFit: { version: 1, results: [{ summary: 'Written before the contract existed.' }] },
    }));
    mocks.parseCurrentFounderFitArtifact.mockReturnValue(null);
    mocks.generate.mockResolvedValue({
      candidatePoolVersion: 7,
      artifact: artifact({ founderProfile }),
      costUsd: 0.01,
      usage: { inputTokens: 100, outputTokens: 500, cacheWriteTokens: 0, cacheReadTokens: 0 },
    });

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-concept-sets`)
      .set(headers)
      .send({ purpose: 'diverge', parents: [{ ideaId: 'idea-signal', ideaRevision: 3 }] });

    expect(response.status).toBe(201);
    const sent = mocks.generate.mock.calls[0][0];
    expect(sent.founderFit).toBeNull();
    expect(JSON.stringify(sent)).not.toContain('Written before the contract existed');
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

  it('withholds a mismatched preview from Concept Forge input', async () => {
    const stalePreview = { buyer_guidance: 'STALE_PREVIEW_BUYER_GUIDANCE' };
    const verified = await mocks.loadSelectionContext();
    mocks.getReport.mockResolvedValue(stalePreview);
    mocks.loadSelectionContext.mockResolvedValue({
      ...verified,
      runArtifacts: {
        verification: 'untrusted',
        reason: 'version_mismatch',
        candidatePoolVersion: 7,
        artifactPoolVersion: 6,
      },
    });

    await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-concept-sets`)
      .set(headers)
      .send({ purpose: 'diverge', parents: [{ ideaId: 'idea-signal', ideaRevision: 3 }] });

    expect(mocks.generate).toHaveBeenCalledWith(expect.objectContaining({ report: null }));
    expect(
      mocks.getReport,
      'CONCEPT_FORGE_MUST_NOT_BYPASS_CURRENT_SELECTION_CONTEXT_FOR_PREVIEW_DATA',
    ).not.toHaveBeenCalled();
  });

  it('returns the cached set without a model call when the fingerprint matches', async () => {
    mocks.setCachedLive = {
      id: SET_ID,
      artifact: artifact(),
      candidatePoolVersion: 7,
      createdAt: new Date('2026-07-16T12:00:00.000Z'),
    };

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
    mocks.setCachedLive = {
      id: SET_ID,
      artifact: artifact(),
      candidatePoolVersion: 7,
      createdAt: new Date('2026-07-16T12:00:00.000Z'),
    };

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
    const currentContext = await mocks.loadSelectionContext();
    mocks.loadSelectionContext
      .mockResolvedValueOnce(currentContext)
      .mockResolvedValueOnce({
        ...currentContext,
        canonical: {
          candidates: [{ ...parent, idea_revision: 4 }],
          displayedCount: 1,
          version: 8,
        },
      });

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
    mocks.setFindFirst.mockResolvedValue({ id: SET_ID, artifact: current, candidatePoolVersion: 7 });

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
      evaluation: {
        version: 1,
        conceptSetId: SET_ID,
        optionId: current.options[0].optionId,
        inputFingerprint: current.inputFingerprint,
        changedAxes: current.options[0].changedAxes,
        assumptions: current.options[0].assumptions,
        retainedEvidence: current.options[0].retainedEvidence,
        evidenceToRecheck: current.options[0].evidenceToRecheck,
        disqualifiers: current.options[0].disqualifiers,
        suggestedTest: current.options[0].suggestedTest,
      },
    });
    expect(mocks.messageCreate).toHaveBeenCalledWith(expect.objectContaining({
      data: expect.objectContaining({
        origin: 'concept_forge',
        candidatePoolVersion: 7,
      }),
    }));
    expect(mocks.jobUpdate).not.toHaveBeenCalled();
  });

  it('reports a server error when a stored option cannot produce a valid patch', async () => {
    const current = artifact();
    current.options[0].changeSummary = 'x'.repeat(650);
    mocks.setFindFirst.mockResolvedValue({ id: SET_ID, artifact: current, candidatePoolVersion: 7 });
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

  it('does not call a prepared-only concept option evaluated', async () => {
    const stored = artifact();
    mocks.setFindMany.mockResolvedValue([{
      id: SET_ID,
      artifact: stored,
      candidatePoolVersion: 7,
      createdAt: new Date('2026-07-16T12:00:00.000Z'),
    }]);
    mocks.messageFindMany
      .mockResolvedValueOnce([{
        id: 'proposal-message-1',
        operationId: `concept:${SET_ID}:${stored.options[1].optionId}`,
      }])
      .mockResolvedValueOnce([]);

    const response = await request(app)
      .get(`/api/jobs/${JOB_ID}/selection-concept-sets`)
      .set(headers);

    expect(response.status).toBe(200);
    expect(mocks.setFindMany).toHaveBeenCalledWith(expect.objectContaining({
      where: { jobId: JOB_ID, archivedAt: null },
      take: 12,
    }));
    expect(mocks.messageFindMany).toHaveBeenCalledWith({
      where: {
        operationId: {
          in: stored.options.map((option) => `concept:${SET_ID}:${option.optionId}`),
        },
      },
      select: { id: true, operationId: true },
    });
    expect(response.body.sets[0].evaluatedOptionIds).toEqual([]);
  });

  it('marks a persisted artifact from an old pool version as stale, never current', async () => {
    const stored = artifact();
    mocks.setFindMany.mockResolvedValue([{
      id: SET_ID,
      artifact: stored,
      candidatePoolVersion: 6,
      createdAt: new Date('2026-07-16T12:00:00.000Z'),
    }]);

    const response = await request(app)
      .get(`/api/jobs/${JOB_ID}/selection-concept-sets`)
      .set(headers);

    expect(response.status).toBe(200);
    expect(
      response.body.sets[0].stale,
      'OLD_POOL_ARTIFACT_IS_NOT_SERVED_AS_CURRENT',
    ).toBe(true);
  });

  it('marks an option submitted only when a durable seed receipt names its proposal', async () => {
    const stored = artifact();
    mocks.setFindMany.mockResolvedValue([{
      id: SET_ID,
      artifact: stored,
      candidatePoolVersion: 7,
      createdAt: new Date('2026-07-16T12:00:00.000Z'),
    }]);
    mocks.messageFindMany
      .mockResolvedValueOnce([{
        id: 'proposal-message-1',
        operationId: `concept:${SET_ID}:${stored.options[1].optionId}`,
      }])
      .mockResolvedValueOnce([{
        patchJson: {
          kind: 'ledger_event',
          event: 'seed_settled',
          sourceMessageId: 'proposal-message-1',
          outcome: 'demoted',
        },
      }]);

    const response = await request(app)
      .get(`/api/jobs/${JOB_ID}/selection-concept-sets`)
      .set(headers);

    expect(response.status).toBe(200);
    expect(mocks.messageFindMany).toHaveBeenLastCalledWith({
      where: { jobId: JOB_ID, gateStage: 5, role: 'receipt' },
      select: { patchJson: true },
    });
    expect(response.body.sets[0].evaluatedOptionIds).toEqual([stored.options[1].optionId]);
    // The OUTCOME, not just the fact of submission — otherwise reopening the Forge
    // shows a long-settled direction as "Evaluation submitted" forever.
    expect(response.body.sets[0].optionOutcomes).toEqual({
      [stored.options[1].optionId]: 'demoted',
    });
  });

  it('lets a settled receipt win over the submitted receipt for the same proposal', async () => {
    // seed_submitted is never retracted, so preferring it would pin every finished
    // evaluation at "pending" for the life of the job. Ordered submitted-last here
    // precisely because row order must not decide the answer.
    const stored = artifact();
    mocks.setFindMany.mockResolvedValue([{
      id: SET_ID,
      artifact: stored,
      candidatePoolVersion: 7,
      createdAt: new Date('2026-07-16T12:00:00.000Z'),
    }]);
    mocks.messageFindMany
      .mockResolvedValueOnce([{
        id: 'proposal-message-1',
        operationId: `concept:${SET_ID}:${stored.options[0].optionId}`,
      }])
      .mockResolvedValueOnce([
        {
          patchJson: {
            kind: 'ledger_event',
            event: 'seed_settled',
            sourceMessageId: 'proposal-message-1',
            outcome: 'accepted',
          },
        },
        {
          patchJson: {
            kind: 'ledger_event',
            event: 'seed_submitted',
            sourceMessageId: 'proposal-message-1',
          },
        },
      ]);

    const response = await request(app)
      .get(`/api/jobs/${JOB_ID}/selection-concept-sets`)
      .set(headers);

    expect(response.status).toBe(200);
    expect(response.body.sets[0].optionOutcomes).toEqual({
      [stored.options[0].optionId]: 'accepted',
    });
  });

  it('reports a still-running evaluation as pending', async () => {
    const stored = artifact();
    mocks.setFindMany.mockResolvedValue([{
      id: SET_ID,
      artifact: stored,
      candidatePoolVersion: 7,
      createdAt: new Date('2026-07-16T12:00:00.000Z'),
    }]);
    mocks.messageFindMany
      .mockResolvedValueOnce([{
        id: 'proposal-message-1',
        operationId: `concept:${SET_ID}:${stored.options[0].optionId}`,
      }])
      .mockResolvedValueOnce([{
        patchJson: {
          kind: 'ledger_event',
          event: 'seed_submitted',
          sourceMessageId: 'proposal-message-1',
        },
      }]);

    const response = await request(app)
      .get(`/api/jobs/${JOB_ID}/selection-concept-sets`)
      .set(headers);

    expect(response.status).toBe(200);
    expect(response.body.sets[0].optionOutcomes).toEqual({
      [stored.options[0].optionId]: 'pending',
    });
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

  it('generates fresh directions after a discard instead of reviving the old set', async () => {
    // Reviving made "Discard this set" a no-op: asking for the same directions again
    // handed back the artifact the user had just thrown away, with no way to get
    // different ones. The cache reads LIVE rows only, so a discarded set is never found.
    mocks.setCachedLive = null;

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-concept-sets`)
      .set(headers)
      .send({ purpose: 'diverge', parents: [{ ideaId: 'idea-signal', ideaRevision: 3 }] });

    expect(response.status).toBe(201);
    expect(response.body.cached).toBe(false);
    expect(mocks.generate).toHaveBeenCalled();
    expect(mocks.setCreate).toHaveBeenCalled();
    // Nothing un-archives the discarded row; the discard is final.
    expect(mocks.setUpdate).not.toHaveBeenCalled();
  });

  it('only consults LIVE rows for the fingerprint cache', async () => {
    mocks.setCachedLive = {
      id: SET_ID,
      artifact: artifact(),
      candidatePoolVersion: 7,
      createdAt: new Date('2026-07-16T12:00:00.000Z'),
    };

    const response = await request(app)
      .post(`/api/jobs/${JOB_ID}/selection-concept-sets`)
      .set(headers)
      .send({ purpose: 'diverge', parents: [{ ideaId: 'idea-signal', ideaRevision: 3 }] });

    expect(response.status).toBe(200);
    expect(response.body.cached).toBe(true);
    expect(mocks.generate).not.toHaveBeenCalled();
    expect(mocks.setFindFirst).toHaveBeenCalledWith(expect.objectContaining({
      where: expect.objectContaining({ archivedAt: null }),
    }));
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

  describe('single-flight generation', () => {
    it('rejects a second generation while one is already running', async () => {
      mocks.setCachedLive = null;
      // Hold the generation open so the second request arrives mid-flight.
      let finishFirst: (v: unknown) => void = () => {};
      mocks.generate.mockImplementationOnce(() => new Promise((resolve) => { finishFirst = resolve; }));

      // `.then()` is what dispatches a supertest request — without it the call is lazy
      // and the "first" request would not have taken the lock yet.
      const first = request(app)
        .post(`/api/jobs/${JOB_ID}/selection-concept-sets`)
        .set(headers)
        .send({ purpose: 'diverge', parents: [{ ideaId: 'idea-signal', ideaRevision: 3 }] })
        .then((response) => response);
      await new Promise((r) => setTimeout(r, 50));

      const second = await request(app)
        .post(`/api/jobs/${JOB_ID}/selection-concept-sets`)
        .set(headers)
        .send({ purpose: 'diverge', parents: [{ ideaId: 'idea-signal', ideaRevision: 3 }] });

      expect(second.status).toBe(409);
      expect(second.body.code).toBe('CONCEPT_SET_GENERATION_IN_PROGRESS');
      // The whole point: the blocked request cost nothing upstream.
      expect(mocks.generate).toHaveBeenCalledTimes(1);

      finishFirst({ candidatePoolVersion: 7, artifact: artifact(), costUsd: 0.01, usage: {} });
      await first;
    });

    it('serves a repeat of the SAME request from cache without contending for the lock', async () => {
      // Cache read happens before the lock, so a second tab repeating an identical
      // request gets the finished set rather than a "busy" error.
      mocks.redisStore.set(`nicheiq:conceptforge:lock:${JOB_ID}`, 'held-by-another-request');
      mocks.setCachedLive = {
        id: SET_ID,
        artifact: artifact(),
        candidatePoolVersion: 7,
        createdAt: new Date('2026-07-16T12:00:00.000Z'),
      };

      const response = await request(app)
        .post(`/api/jobs/${JOB_ID}/selection-concept-sets`)
        .set(headers)
        .send({ purpose: 'diverge', parents: [{ ideaId: 'idea-signal', ideaRevision: 3 }] });

      expect(response.status).toBe(200);
      expect(response.body.cached).toBe(true);
      expect(mocks.generate).not.toHaveBeenCalled();
    });

    it('releases the lock after a successful generation', async () => {
      mocks.setCachedLive = null;
      await request(app)
        .post(`/api/jobs/${JOB_ID}/selection-concept-sets`)
        .set(headers)
        .send({ purpose: 'diverge', parents: [{ ideaId: 'idea-signal', ideaRevision: 3 }] });

      expect(mocks.redisStore.has(`nicheiq:conceptforge:lock:${JOB_ID}`)).toBe(false);
    });

    it('releases the lock when generation fails, so a retry is not locked out', async () => {
      mocks.setCachedLive = null;
      mocks.generate.mockRejectedValueOnce(new Error('CONCEPT_OPTIONS_NOT_DISTINCT'));

      await request(app)
        .post(`/api/jobs/${JOB_ID}/selection-concept-sets`)
        .set(headers)
        .send({ purpose: 'diverge', parents: [{ ideaId: 'idea-signal', ideaRevision: 3 }] });

      expect(mocks.redisStore.has(`nicheiq:conceptforge:lock:${JOB_ID}`)).toBe(false);
    });

    it('releases the lock when the per-job set cap rejects the request', async () => {
      mocks.setCachedLive = null;
      mocks.setCount.mockResolvedValueOnce(12);

      const response = await request(app)
        .post(`/api/jobs/${JOB_ID}/selection-concept-sets`)
        .set(headers)
        .send({ purpose: 'diverge', parents: [{ ideaId: 'idea-signal', ideaRevision: 3 }] });

      expect(response.status).toBe(409);
      expect(mocks.redisStore.has(`nicheiq:conceptforge:lock:${JOB_ID}`)).toBe(false);
    });

    it('locks per job, so a different job can generate concurrently', async () => {
      mocks.redisStore.set('nicheiq:conceptforge:lock:other-job', 'held');
      mocks.setCachedLive = null;

      const response = await request(app)
        .post(`/api/jobs/${JOB_ID}/selection-concept-sets`)
        .set(headers)
        .send({ purpose: 'diverge', parents: [{ ideaId: 'idea-signal', ideaRevision: 3 }] });

      expect(response.status).toBe(201);
    });
  });
});
