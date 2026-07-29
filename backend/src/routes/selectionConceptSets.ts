import { JobStatus, Prisma } from '@prisma/client';
import { Router, type Response } from 'express';
import { z } from 'zod';
import { CONFIG } from '../config.js';
import { requireInternalAuth, type AuthenticatedRequest } from '../middleware/auth.js';
import { requireDecisionToolsAccess } from '../middleware/featureAccess.js';
import { getPreviewReportForJob } from '../services/assetService.js';
import { acquireGenerationLock } from '../services/selectionGenerationLock.js';
import { prisma } from '../services/db.js';
import {
  ConceptSetGenerationError,
  ConceptSetTimeoutError,
  generateSelectionConceptSet,
  prepareSelectionConceptSetInput,
  type ConceptSetGuardrailCode,
  type SelectionConceptSetInput,
} from '../services/selectionConceptSetService.js';
import {
  findOwnedSelectionWorkspaceJob as ownedJob,
  type SelectionWorkspaceJob as ConceptJob,
} from '../services/selectionOwnedJobService.js';
import {
  PrepareSelectionConceptOptionSchema,
  SelectionConceptSetArtifactSchema,
  SelectionConceptSetRequestSchema,
  type SelectionConceptSetArtifact,
  type SelectionConceptSetRequest,
} from '../types/selectionConceptSet.js';
import { IdeaSynthesisPatchSchema } from '../types/ideaSynthesis.js';
import { ensureIdeaIdentities, type IdeaRecord } from '../utils/ideaIdentity.js';

export const selectionConceptSetsRouter = Router();

const MAX_CONCEPT_SETS_PER_JOB = 12;

/** User-facing message per Concept Forge guardrail: names the cause and a recovery step. */
const GUARDRAIL_MESSAGES: Record<ConceptSetGuardrailCode, string> = {
  INVALID_CONCEPT_SET_OUTPUT:
    'Concept Forge returned a reply that did not match the required structure. This is usually transient — try again.',
  UNSUPPORTED_CONCEPT_SET_CLAIM:
    'Concept Forge overstated certainty (words like "proven" or "validated"), so the options were discarded. Try again.',
  CONCEPT_OPTIONS_NOT_DISTINCT:
    'The options came back too similar to each other. Try again with a sharper tension, or pick a different pair of candidates.',
  INVALID_CONCEPT_OPTION_LANES:
    'The options did not cover the required narrow, reposition, and adjacent directions. Try again.',
  COMBINED_CONCEPT_OPTION_REQUIRED:
    'With two candidates, one option must combine them, and the reply skipped it. Try again, or branch from a single candidate instead.',
  INVALID_CONCEPT_SOURCE:
    'An option pointed at a candidate outside your selection. Try again.',
  DUPLICATE_CONCEPT_SOURCE:
    'An option referenced the same candidate twice. Try again.',
  INVALID_CONCEPT_SOURCE_COUNT:
    'An option did not map cleanly onto your selected candidates. Try again.',
  INVALID_CONCEPT_TEST_ASSUMPTION:
    'A suggested test did not target one of its own assumptions. Try again.',
  CONCEPT_OPTIONS_IGNORE_BUYER_EVIDENCE:
    'This research has already ruled out ideas in this audience because it does not pay for tooling, and every option came back aimed at that same audience. Try again — one direction needs to move to a buyer with budget.',
  CONCEPT_OPTIONS_COLLAPSE_ON_BUYER:
    'Every option came back changing the same thing about who pays, so the three directions only ask one question. Try again — one of them should leave that alone and change the product instead.',
  CONCEPT_BUYER_MOVE_STAYS_IN_DEAD_SEGMENT:
    'The direction that changed the buyer moved it to an audience this research already ruled out for not paying. Try again.',
  CONCEPT_TEST_WINDOW_INCONSISTENT:
    'A suggested test came back measuring two different time windows at once, so its result would be unreadable. Try again.',
  CONCEPT_TEST_BANDS_INVERTED:
    'A suggested test came back with a pass bar that is not above its fail bar. Try again.',
  CONCEPT_TEST_THRESHOLD_IMPLAUSIBLE:
    'A suggested test set a pass bar that cold outreach does not reach, so a promising direction would fail it. Try again.',
};

async function recordForgeCost(jobId: string, costUsd: number): Promise<void> {
  if (costUsd <= 0) return;
  await prisma.job.update({
    where: { id: jobId },
    data: { chatCostUsd: { increment: costUsd } },
  }).catch((error) => console.error('Failed to record Concept Forge cost:', error));
}

const JobParamsSchema = z.object({ jobId: z.string().uuid() });
const OptionParamsSchema = JobParamsSchema.extend({
  setId: z.string().uuid(),
  optionId: z.string().regex(/^O[a-f0-9]{11}$/),
});

function exactParents(job: ConceptJob, request: SelectionConceptSetRequest): IdeaRecord[] | null {
  const pool = ensureIdeaIdentities(job.id, job.solutionIdeas);
  const parents = request.parents.map((ref) => pool.find((idea) =>
    idea.idea_id === ref.ideaId && idea.idea_revision === ref.ideaRevision
  ));
  return parents.some((parent) => !parent) ? null : parents as IdeaRecord[];
}

async function loadContextInput(
  job: ConceptJob,
  request: SelectionConceptSetRequest,
): Promise<SelectionConceptSetInput | null> {
  const parents = exactParents(job, request);
  if (!parents) return null;
  const exactPairs = request.parents.map((parent) => ({
    ideaId: parent.ideaId,
    ideaRevision: parent.ideaRevision,
  }));
  const [report, challenges, ownerEvidence, conclusions] = await Promise.all([
    getPreviewReportForJob(job.id).catch(() => null),
    prisma.selectionChallenge.findMany({
      where: { jobId: job.id, OR: exactPairs },
      orderBy: { createdAt: 'desc' },
      take: 24,
      select: { artifact: true },
    }),
    prisma.selectionOwnerEvidence.findMany({
      where: { jobId: job.id, retractedAt: null, OR: exactPairs },
      orderBy: { createdAt: 'desc' },
      take: 24,
    }),
    prisma.selectionExperimentConclusion.findMany({
      where: {
        experiment: { jobId: job.id },
        OR: exactPairs,
      },
      orderBy: { createdAt: 'desc' },
      take: 12,
      select: {
        id: true,
        ideaId: true,
        ideaRevision: true,
        outcome: true,
        evidenceSource: true,
        requestFingerprint: true,
        snapshot: true,
      },
    }),
  ]);
  return {
    jobId: job.id,
    purpose: request.purpose,
    targetTradeoff: request.targetTradeoff,
    parents,
    report,
    founderProfile: job.selectionDecisionProfile,
    founderFit: job.selectionFounderFit,
    challenges: [
      ...challenges.map((row) => row.artifact),
      ...ownerEvidence.map((row) => ({
        kind: 'owner_evidence',
        id: row.id,
        ideaId: row.ideaId,
        ideaRevision: row.ideaRevision,
        lens: row.lens,
        evidenceKind: row.kind,
        position: row.position,
        title: row.title,
        content: row.content,
        sourceUrl: row.sourceUrl,
        observedAt: row.observedAt?.toISOString() ?? null,
        inputFingerprint: row.inputFingerprint,
      })),
    ],
    conclusions,
  };
}

function requestFromArtifact(artifact: SelectionConceptSetArtifact): SelectionConceptSetRequest {
  return {
    purpose: artifact.purpose,
    targetTradeoff: artifact.targetTradeoff ?? undefined,
    parents: artifact.parents.map((parent) => ({
      ideaId: parent.ideaId,
      ideaRevision: parent.ideaRevision,
    })),
  };
}

function parentRevisionStale(job: ConceptJob, artifact: SelectionConceptSetArtifact): boolean {
  const parents = exactParents(job, requestFromArtifact(artifact));
  if (!parents) return true;
  return parents.some((parent, index) => {
    const prepared = prepareSelectionConceptSetInput({
      jobId: job.id,
      purpose: artifact.purpose,
      targetTradeoff: artifact.targetTradeoff ?? undefined,
      parents: [parent],
      report: null,
      founderProfile: null,
      founderFit: null,
      challenges: [],
      conclusions: [],
    });
    return prepared.parents[0].candidateSnapshotSha256 !== artifact.parents[index].candidateSnapshotSha256;
  });
}

function publicSet(
  row: { id: string; artifact: unknown; createdAt: Date },
  stale: boolean,
  optionOutcomes: Record<string, ConceptOptionOutcome> = {},
) {
  return {
    id: row.id,
    artifact: SelectionConceptSetArtifactSchema.parse(row.artifact),
    stale,
    createdAt: row.createdAt,
    evaluatedOptionIds: Object.keys(optionOutcomes),
    // The OUTCOME, not just the fact of submission. Reopening the Forge used to show
    // a long-settled direction as "Evaluation submitted" forever, because the only
    // signal was a boolean that never advanced past "was sent".
    optionOutcomes,
  };
}

function operationIdFor(setId: string, optionId: string): string {
  return `concept:${setId}:${optionId}`;
}

export type ConceptOptionOutcome =
  'pending' | 'accepted' | 'demoted' | 'failed' | 'refunded';

/** Outcome per option that actually entered paid evaluation.
 *
 * A concept proposal row is free preparation, not an evaluation. Only expose an
 * option once a durable seed receipt points back to that proposal message. This
 * keeps a prepared-but-never-confirmed direction from rendering as "Evaluated" and
 * prevents a settled option from re-arming after a reload. No schema change: both
 * sides already live in the analyst ledger.
 *
 * `seed_settled` always wins over `seed_submitted` for the same proposal — the
 * submitted receipt is never retracted, so preferring it would pin a finished
 * evaluation at "pending" for the life of the job. */
async function evaluatedOptionIdsBySet(
  jobId: string,
  sets: Array<{ id: string; artifact: SelectionConceptSetArtifact }>,
): Promise<Map<string, Record<string, ConceptOptionOutcome>>> {
  const operationIds = sets.flatMap((set) =>
    set.artifact.options.map((option) => operationIdFor(set.id, option.optionId)));
  const evaluated = new Map<string, Record<string, ConceptOptionOutcome>>();
  if (!operationIds.length) return evaluated;
  const proposalRows = await prisma.chatMessage.findMany({
    where: { operationId: { in: operationIds } },
    select: { id: true, operationId: true },
  });
  if (!proposalRows.length) return evaluated;
  const receipts = await prisma.chatMessage.findMany({
    where: { jobId, gateStage: 5, role: 'receipt' },
    select: { patchJson: true },
  });
  const SETTLED: ReadonlySet<string> = new Set(['accepted', 'demoted', 'failed', 'refunded']);
  const outcomeByProposal = new Map<string, ConceptOptionOutcome>();
  for (const row of receipts) {
    const patch = row.patchJson;
    if (!patch || typeof patch !== 'object' || Array.isArray(patch)) continue;
    const { event, sourceMessageId, outcome } = patch as Record<string, unknown>;
    if (typeof sourceMessageId !== 'string') continue;
    if (event === 'seed_submitted') {
      if (!outcomeByProposal.has(sourceMessageId)) outcomeByProposal.set(sourceMessageId, 'pending');
    } else if (event === 'seed_settled') {
      // Settled always overwrites, whatever order the rows arrive in.
      outcomeByProposal.set(
        sourceMessageId,
        typeof outcome === 'string' && SETTLED.has(outcome)
          ? outcome as ConceptOptionOutcome
          : 'failed',
      );
    }
  }
  for (const row of proposalRows) {
    const outcome = outcomeByProposal.get(row.id);
    if (!outcome) continue;
    const [, setId, optionId] = row.operationId!.split(':');
    evaluated.set(setId, { ...(evaluated.get(setId) ?? {}), [optionId]: outcome });
  }
  return evaluated;
}

function patchForOption(
  conceptSetId: string,
  artifact: SelectionConceptSetArtifact,
  optionId: string,
) {
  const option = artifact.options.find((candidate) => candidate.optionId === optionId);
  if (!option) return null;
  return IdeaSynthesisPatchSchema.parse({
    kind: 'idea_synthesis',
    operation: option.operation,
    proposedTitle: option.title,
    proposedBrief: option.brief,
    changeSummary: option.changeSummary,
    rationale: option.rationale,
    parents: option.parentContributions.map((parent) => ({
      ideaId: parent.ideaId,
      ideaRevision: parent.ideaRevision,
      solutionName: parent.solutionName,
      contribution: parent.contribution,
    })),
    evidence: {
      sourceAnchors: option.parentContributions.map((parent) => ({
        ideaId: parent.ideaId,
        ideaRevision: parent.ideaRevision,
        candidateSnapshotSha256: parent.candidateSnapshotSha256,
        ...(parent.pain ? { pain: parent.pain } : {}),
        ...(parent.audience ? { audience: parent.audience } : {}),
      })),
      requiresValidation: [
        ...option.evidenceToRecheck,
        ...option.assumptions.map((assumption) => `New assumption: ${assumption.statement}`),
      ].slice(0, 10),
    },
    newAssumptions: option.assumptions.map((assumption) => assumption.statement),
    evaluation: {
      version: 1,
      conceptSetId,
      optionId: option.optionId,
      inputFingerprint: artifact.inputFingerprint,
      changedAxes: option.changedAxes,
      assumptions: option.assumptions,
      retainedEvidence: option.retainedEvidence,
      evidenceToRecheck: option.evidenceToRecheck,
      disqualifiers: option.disqualifiers,
      suggestedTest: option.suggestedTest,
    },
  });
}

function editable(job: ConceptJob): string | null {
  if (job.status !== JobStatus.AWAITING_SELECTION) return 'Concept options are only available during idea selection';
  if (job.selectionFinalDecision) return 'The final decision is already locked';
  return null;
}

selectionConceptSetsRouter.get(
  '/:jobId/selection-concept-sets',
  requireInternalAuth,
  requireDecisionToolsAccess,
  async (req: AuthenticatedRequest, res: Response) => {
    try {
      const { jobId } = JobParamsSchema.parse(req.params);
      const job = await ownedJob(jobId, req.user!.id);
      if (!job) {
        res.status(404).json({ error: 'Job not found' });
        return;
      }
      const rows = await prisma.selectionConceptSet.findMany({
        where: { jobId, archivedAt: null },
        orderBy: { createdAt: 'desc' },
        take: 10,
        select: { id: true, artifact: true, createdAt: true },
      });
      const parsedRows = rows.flatMap((row) => {
        const parsed = SelectionConceptSetArtifactSchema.safeParse(row.artifact);
        return parsed.success ? [{ row, artifact: parsed.data }] : [];
      });
      const evaluated = await evaluatedOptionIdsBySet(
        jobId,
        parsedRows.map(({ row, artifact }) => ({ id: row.id, artifact })),
      );
      const sets = parsedRows.map(({ row, artifact }) =>
        publicSet(row, parentRevisionStale(job, artifact), evaluated.get(row.id) ?? {}));
      res.setHeader('Cache-Control', 'private, no-store');
      res.json({ sets });
    } catch (error) {
      if (error instanceof z.ZodError) {
        res.status(400).json({ error: 'Invalid concept-set reference' });
        return;
      }
      console.error('Failed to load selection concept sets:', error);
      res.status(500).json({ error: 'Failed to load concept options' });
    }
  },
);

selectionConceptSetsRouter.post(
  '/:jobId/selection-concept-sets',
  requireInternalAuth,
  requireDecisionToolsAccess,
  async (req: AuthenticatedRequest, res: Response) => {
    try {
      const { jobId } = JobParamsSchema.parse(req.params);
      const request = SelectionConceptSetRequestSchema.parse(req.body);
      const job = await ownedJob(jobId, req.user!.id);
      if (!job) {
        res.status(404).json({ error: 'Job not found' });
        return;
      }
      const editError = editable(job);
      if (editError) {
        res.status(409).json({ error: editError });
        return;
      }
      const input = await loadContextInput(job, request);
      if (!input) {
        res.status(409).json({ error: 'A selected parent revision changed; reopen the shortlist' });
        return;
      }
      const prepared = prepareSelectionConceptSetInput(input);
      // LIVE sets only. Reviving a discarded set here made "Discard this set" a no-op:
      // asking for the same directions again handed back the artifact the user had just
      // thrown away, with no way to get different ones. A discard is now final, and the
      // same inputs generate fresh directions.
      const cached = await prisma.selectionConceptSet.findFirst({
        where: { jobId, inputFingerprint: prepared.inputFingerprint, archivedAt: null },
        select: { id: true, artifact: true, createdAt: true },
      });
      if (cached) {
        const cachedArtifact = SelectionConceptSetArtifactSchema.parse(cached.artifact);
        const evaluated = await evaluatedOptionIdsBySet(
          jobId,
          [{ id: cached.id, artifact: cachedArtifact }],
        );
        res.setHeader('Cache-Control', 'private, no-store');
        res.json({ set: publicSet(cached, false, evaluated.get(cached.id) ?? {}), cached: true });
        return;
      }
      // Single-flight. Deliberately AFTER the fingerprint cache read above: a second tab
      // repeating the same request should get the finished set, not a "busy" error. Only
      // a genuinely new generation contends for the lock.
      const lock = await acquireGenerationLock(jobId);
      if (!lock) {
        res.status(409).json({
          error: 'Directions are already being generated for this research. Wait for that run to finish, then try again — if it was the same request, its result will be waiting.',
          code: 'CONCEPT_SET_GENERATION_IN_PROGRESS',
        });
        return;
      }
      try {
        const existingSetCount = await prisma.selectionConceptSet.count({
          where: { jobId, archivedAt: null },
        });
        if (existingSetCount >= MAX_CONCEPT_SETS_PER_JOB) {
          res.status(409).json({ error: 'This job reached its Concept Forge limit. Work with the existing sets, or discard a saved set you no longer need to free room' });
          return;
        }
        if (!CONFIG.openaiApiKey && !CONFIG.openrouterApiKey) {
          res.status(503).json({ error: 'Concept Forge is temporarily unavailable' });
          return;
        }

        let generated;
        try {
          generated = await generateSelectionConceptSet(input);
        } catch (error) {
          if (error instanceof ConceptSetGenerationError) {
            // The tokens were spent even though the guardrails rejected the output.
            await recordForgeCost(jobId, error.costUsd);
            res.status(502).json({ error: GUARDRAIL_MESSAGES[error.code], code: error.code });
            return;
          }
          if (error instanceof ConceptSetTimeoutError) {
            // Same billing rule: the upstream call ran, it just did not finish in time.
            await recordForgeCost(jobId, error.costUsd);
            res.status(504).json({
              error: 'Generating directions took too long and was stopped. Nothing was saved — try again.',
            });
            return;
          }
          throw error;
        }
        const freshJob = await ownedJob(jobId, req.user!.id);
        const freshInput = freshJob && editable(freshJob) === null
          ? await loadContextInput(freshJob, request)
          : null;
        if (
          !freshJob
          || !freshInput
          || prepareSelectionConceptSetInput(freshInput).inputFingerprint !== generated.artifact.inputFingerprint
        ) {
          res.status(409).json({ error: 'The shortlist or its evidence changed while options were being prepared' });
          return;
        }

        let created;
        try {
          created = await prisma.selectionConceptSet.create({
            data: {
              jobId,
              purpose: generated.artifact.purpose,
              inputFingerprint: generated.artifact.inputFingerprint,
              parentRefs: generated.artifact.parents as unknown as Prisma.InputJsonValue,
              artifact: generated.artifact as unknown as Prisma.InputJsonValue,
              model: generated.artifact.model,
              promptId: generated.artifact.promptId,
            },
            select: { id: true, artifact: true, createdAt: true },
          });
        } catch (error) {
          if (error instanceof Prisma.PrismaClientKnownRequestError && error.code === 'P2002') {
            // The partial unique index still raises P2002 when a concurrent request won the
            // race; the winner is by definition the LIVE row for this fingerprint.
            const winner = await prisma.selectionConceptSet.findFirst({
              where: {
                jobId,
                inputFingerprint: generated.artifact.inputFingerprint,
                archivedAt: null,
              },
              select: { id: true, artifact: true, createdAt: true },
            });
            if (winner) {
              await recordForgeCost(jobId, generated.costUsd);
              res.json({ set: publicSet(winner, false), cached: true });
              return;
            }
          }
          throw error;
        }
        await recordForgeCost(jobId, generated.costUsd);
        res.status(201).json({ set: publicSet(created, false), cached: false });
      } finally {
        await lock.release();
      }
    } catch (error) {
      if (error instanceof z.ZodError) {
        res.status(400).json({ error: 'Invalid Concept Forge request', details: error.errors });
        return;
      }
      if (error instanceof Error && error.message in GUARDRAIL_MESSAGES) {
        const code = error.message as ConceptSetGuardrailCode;
        res.status(502).json({ error: GUARDRAIL_MESSAGES[code], code });
        return;
      }
      console.error('Failed to create selection concept set:', error);
      res.status(500).json({ error: 'Failed to create concept options' });
    }
  },
);

const SetParamsSchema = JobParamsSchema.extend({ setId: z.string().uuid() });

selectionConceptSetsRouter.post(
  '/:jobId/selection-concept-sets/:setId/archive',
  requireInternalAuth,
  requireDecisionToolsAccess,
  async (req: AuthenticatedRequest, res: Response) => {
    try {
      const params = SetParamsSchema.parse(req.params);
      const job = await ownedJob(params.jobId, req.user!.id);
      if (!job) {
        res.status(404).json({ error: 'Job not found' });
        return;
      }
      const editError = editable(job);
      if (editError) {
        res.status(409).json({ error: editError });
        return;
      }
      const row = await prisma.selectionConceptSet.findFirst({
        where: { id: params.setId, jobId: params.jobId },
        select: { id: true, archivedAt: true },
      });
      if (!row) {
        res.status(404).json({ error: 'Concept set not found' });
        return;
      }
      // Idempotent: archiving an already-archived set is a no-op success.
      if (!row.archivedAt) {
        await prisma.selectionConceptSet.updateMany({
          where: { id: row.id, archivedAt: null },
          data: { archivedAt: new Date() },
        });
      }
      res.status(204).send();
    } catch (error) {
      if (error instanceof z.ZodError) {
        res.status(400).json({ error: 'Invalid concept-set reference' });
        return;
      }
      console.error('Failed to archive selection concept set:', error);
      res.status(500).json({ error: 'Failed to discard the concept set' });
    }
  },
);

selectionConceptSetsRouter.post(
  '/:jobId/selection-concept-sets/:setId/options/:optionId/proposal',
  requireInternalAuth,
  requireDecisionToolsAccess,
  async (req: AuthenticatedRequest, res: Response) => {
    try {
      const params = OptionParamsSchema.parse(req.params);
      const input = PrepareSelectionConceptOptionSchema.parse(req.body);
      const job = await ownedJob(params.jobId, req.user!.id);
      if (!job) {
        res.status(404).json({ error: 'Job not found' });
        return;
      }
      const editError = editable(job);
      if (editError) {
        res.status(409).json({ error: editError });
        return;
      }
      const row = await prisma.selectionConceptSet.findFirst({
        where: { id: params.setId, jobId: params.jobId, archivedAt: null },
        select: { id: true, artifact: true },
      });
      if (!row) {
        res.status(404).json({ error: 'Concept set not found' });
        return;
      }
      const artifact = SelectionConceptSetArtifactSchema.parse(row.artifact);
      if (artifact.inputFingerprint !== input.expectedInputFingerprint) {
        res.status(409).json({ error: 'The concept options changed; review the current set before evaluating' });
        return;
      }
      const currentInput = await loadContextInput(job, requestFromArtifact(artifact));
      if (
        !currentInput
        || prepareSelectionConceptSetInput(currentInput).inputFingerprint !== artifact.inputFingerprint
      ) {
        res.status(409).json({ error: 'The shortlist or evidence changed after these options were created' });
        return;
      }
      let patch;
      try {
        patch = patchForOption(row.id, artifact, params.optionId);
      } catch (error) {
        if (error instanceof z.ZodError) {
          console.error(`Stored concept set ${row.id} produced an invalid synthesis patch:`, error);
          res.status(500).json({ error: 'Failed to prepare concept option' });
          return;
        }
        throw error;
      }
      if (!patch) {
        res.status(404).json({ error: 'Concept option not found' });
        return;
      }
      const operationId = operationIdFor(row.id, params.optionId);
      const existing = await prisma.chatMessage.findUnique({
        where: { operationId },
        select: { id: true, patchJson: true },
      });
      if (existing) {
        res.json({ sourceMessageId: existing.id, patch: existing.patchJson, cached: true });
        return;
      }
      let message;
      try {
        message = await prisma.chatMessage.create({
          data: {
            jobId: params.jobId,
            gateStage: 5,
            role: 'assistant',
            content: 'Concept Forge prepared this option for your explicit evaluation decision. The source candidates remain unchanged.',
            patchJson: patch as unknown as Prisma.InputJsonValue,
            origin: 'concept_forge',
            operationId,
          },
          select: { id: true, patchJson: true },
        });
      } catch (error) {
        if (error instanceof Prisma.PrismaClientKnownRequestError && error.code === 'P2002') {
          const winner = await prisma.chatMessage.findUnique({
            where: { operationId },
            select: { id: true, patchJson: true },
          });
          if (winner) {
            res.json({ sourceMessageId: winner.id, patch: winner.patchJson, cached: true });
            return;
          }
        }
        throw error;
      }
      res.status(201).json({ sourceMessageId: message.id, patch: message.patchJson, cached: false });
    } catch (error) {
      if (error instanceof z.ZodError) {
        res.status(400).json({ error: 'Invalid concept-option reference' });
        return;
      }
      console.error('Failed to prepare concept option:', error);
      res.status(500).json({ error: 'Failed to prepare concept option' });
    }
  },
);
