import { JobStatus, Prisma } from '@prisma/client';
import { Router, type Response } from 'express';
import { z } from 'zod';
import { CONFIG } from '../config.js';
import { requireInternalAuth, type AuthenticatedRequest } from '../middleware/auth.js';
import { getPreviewReportForJob } from '../services/assetService.js';
import { prisma } from '../services/db.js';
import {
  generateSelectionConceptSet,
  prepareSelectionConceptSetInput,
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

function publicSet(row: { id: string; artifact: unknown; createdAt: Date }, stale: boolean) {
  return {
    id: row.id,
    artifact: SelectionConceptSetArtifactSchema.parse(row.artifact),
    stale,
    createdAt: row.createdAt,
  };
}

function operationIdFor(setId: string, optionId: string): string {
  return `concept:${setId}:${optionId}`;
}

function patchForOption(artifact: SelectionConceptSetArtifact, optionId: string) {
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
  async (req: AuthenticatedRequest, res: Response) => {
    try {
      const { jobId } = JobParamsSchema.parse(req.params);
      const job = await ownedJob(jobId, req.user!.id);
      if (!job) {
        res.status(404).json({ error: 'Job not found' });
        return;
      }
      const rows = await prisma.selectionConceptSet.findMany({
        where: { jobId },
        orderBy: { createdAt: 'desc' },
        take: 10,
        select: { id: true, artifact: true, createdAt: true },
      });
      const sets = rows.flatMap((row) => {
        const parsed = SelectionConceptSetArtifactSchema.safeParse(row.artifact);
        return parsed.success ? [publicSet(row, parentRevisionStale(job, parsed.data))] : [];
      });
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
      const cached = await prisma.selectionConceptSet.findUnique({
        where: { jobId_inputFingerprint: { jobId, inputFingerprint: prepared.inputFingerprint } },
        select: { id: true, artifact: true, createdAt: true },
      });
      if (cached) {
        res.setHeader('Cache-Control', 'private, no-store');
        res.json({ set: publicSet(cached, false), cached: true });
        return;
      }
      const existingSetCount = await prisma.selectionConceptSet.count({ where: { jobId } });
      if (existingSetCount >= MAX_CONCEPT_SETS_PER_JOB) {
        res.status(409).json({ error: 'This job reached its Concept Forge limit; existing directions cannot be removed or reused to free room, so work with the existing sets' });
        return;
      }
      if (!CONFIG.openaiApiKey && !CONFIG.openrouterApiKey) {
        res.status(503).json({ error: 'Concept Forge is temporarily unavailable' });
        return;
      }

      const generated = await generateSelectionConceptSet(input);
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
          const winner = await prisma.selectionConceptSet.findUnique({
            where: { jobId_inputFingerprint: { jobId, inputFingerprint: generated.artifact.inputFingerprint } },
            select: { id: true, artifact: true, createdAt: true },
          });
          if (winner) {
            if (generated.costUsd > 0) {
              await prisma.job.update({
                where: { id: jobId },
                data: { chatCostUsd: { increment: generated.costUsd } },
              }).catch((updateError) => console.error('Failed to record Concept Forge cost:', updateError));
            }
            res.json({ set: publicSet(winner, false), cached: true });
            return;
          }
        }
        throw error;
      }
      if (generated.costUsd > 0) {
        await prisma.job.update({
          where: { id: jobId },
          data: { chatCostUsd: { increment: generated.costUsd } },
        }).catch((error) => console.error('Failed to record Concept Forge cost:', error));
      }
      res.status(201).json({ set: publicSet(created, false), cached: false });
    } catch (error) {
      if (error instanceof z.ZodError) {
        res.status(400).json({ error: 'Invalid Concept Forge request', details: error.errors });
        return;
      }
      if (error instanceof Error && [
        'INVALID_CONCEPT_SET_OUTPUT',
        'UNSUPPORTED_CONCEPT_SET_CLAIM',
        'CONCEPT_OPTIONS_NOT_DISTINCT',
        'INVALID_CONCEPT_OPTION_LANES',
        'COMBINED_CONCEPT_OPTION_REQUIRED',
        'INVALID_CONCEPT_SOURCE',
        'DUPLICATE_CONCEPT_SOURCE',
        'INVALID_CONCEPT_SOURCE_COUNT',
        'INVALID_CONCEPT_TEST_ASSUMPTION',
      ].includes(error.message)) {
        res.status(502).json({ error: 'Concept Forge returned options that could not be verified' });
        return;
      }
      console.error('Failed to create selection concept set:', error);
      res.status(500).json({ error: 'Failed to create concept options' });
    }
  },
);

selectionConceptSetsRouter.post(
  '/:jobId/selection-concept-sets/:setId/options/:optionId/proposal',
  requireInternalAuth,
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
        where: { id: params.setId, jobId: params.jobId },
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
        patch = patchForOption(artifact, params.optionId);
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
