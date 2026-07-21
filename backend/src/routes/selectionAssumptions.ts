import { JobStatus, Prisma } from '@prisma/client';
import { Router, type Response } from 'express';
import { z } from 'zod';
import { requireInternalAuth, type AuthenticatedRequest } from '../middleware/auth.js';
import { prisma } from '../services/db.js';
import {
  PRISMA_ASSUMPTION_LENS,
  selectionAssumptionInclude,
  serializeSelectionAssumption,
} from '../services/selectionAssumptionService.js';
import { findOwnedJob } from '../services/selectionOwnedJobService.js';
import {
  SelectionAssumptionCreateSchema,
  SelectionAssumptionPatchSchema,
  type SelectionAssumptionCreate,
} from '../types/selectionAssumption.js';
import { SelectionChallengeArtifactSchema } from '../types/selectionChallenge.js';
import { canonicalJsonSha256 } from '../utils/canonicalFingerprint.js';
import { ensureIdeaIdentities } from '../utils/ideaIdentity.js';

const JobParamsSchema = z.object({ jobId: z.string().uuid() });
const AssumptionParamsSchema = JobParamsSchema.extend({ assumptionId: z.string().uuid() });

export const selectionAssumptionsRouter = Router();

function currentIdeaPairs(jobId: string, solutionIdeas: unknown) {
  return new Set(ensureIdeaIdentities(jobId, solutionIdeas).map(idea =>
    `${String(idea.idea_id)}\0${String(idea.idea_revision)}`
  ));
}

function isCurrentIdea(jobId: string, solutionIdeas: unknown, ideaId: string, ideaRevision: number) {
  return currentIdeaPairs(jobId, solutionIdeas).has(`${ideaId}\0${ideaRevision}`);
}

function statementFingerprint(input: {
  ideaId: string;
  ideaRevision: number;
  lens: string;
  statement: string;
}) {
  return canonicalJsonSha256({
    ideaId: input.ideaId,
    ideaRevision: input.ideaRevision,
    lens: input.lens,
    statement: input.statement.trim().replace(/\s+/g, ' ').toLocaleLowerCase('en-US'),
  });
}

function isExactCreateRetry(
  existing: {
    ideaId: string;
    ideaRevision: number;
    lens: keyof typeof APP_LENS_FOR_RETRY;
    statement: string;
    impactIfFalse: string;
    falsificationQuestion: string;
    impact: string;
    originChallengeId: string | null;
    originQuestionId: string | null;
  },
  input: SelectionAssumptionCreate,
) {
  return existing.ideaId === input.ideaId
    && existing.ideaRevision === input.ideaRevision
    && APP_LENS_FOR_RETRY[existing.lens] === input.lens
    && existing.statement === input.statement
    && existing.impactIfFalse === input.impactIfFalse
    && existing.falsificationQuestion === input.falsificationQuestion
    && existing.impact === input.impact
    && existing.originChallengeId === input.originChallengeId
    && existing.originQuestionId === input.originQuestionId;
}

const APP_LENS_FOR_RETRY = {
  DEMAND: 'demand',
  COMPETITION: 'competition',
  DISTRIBUTION: 'distribution',
  DEPENDENCIES: 'dependencies',
} as const;

selectionAssumptionsRouter.get(
  '/:jobId/selection-assumptions',
  requireInternalAuth,
  async (req: AuthenticatedRequest, res: Response) => {
    try {
      const params = JobParamsSchema.parse(req.params);
      const job = await findOwnedJob(params.jobId, req.user!.id, {
        id: true,
        solutionIdeas: true,
      });
      if (!job) {
        res.status(404).json({ error: 'Job not found' });
        return;
      }

      const assumptions = await prisma.selectionAssumption.findMany({
        where: { jobId: job.id },
        include: selectionAssumptionInclude,
        orderBy: [{ ownerState: 'asc' }, { createdAt: 'asc' }],
      });
      const current = currentIdeaPairs(job.id, job.solutionIdeas);
      res.setHeader('Cache-Control', 'private, no-store');
      res.json({
        assumptions: assumptions.map(assumption => serializeSelectionAssumption(
          assumption,
          !current.has(`${assumption.ideaId}\0${assumption.ideaRevision}`),
        )),
      });
    } catch (error) {
      if (error instanceof z.ZodError) {
        res.status(400).json({ error: 'Invalid job ID format' });
        return;
      }
      console.error('Failed to list selection assumptions:', error);
      res.status(500).json({ error: 'Failed to load assumptions' });
    }
  },
);

selectionAssumptionsRouter.post(
  '/:jobId/selection-assumptions',
  requireInternalAuth,
  async (req: AuthenticatedRequest, res: Response) => {
    try {
      const params = JobParamsSchema.parse(req.params);
      const input = SelectionAssumptionCreateSchema.parse(req.body);
      const job = await findOwnedJob(params.jobId, req.user!.id, {
        id: true,
        status: true,
        solutionIdeas: true,
        selectionFinalDecision: { select: { id: true } },
      });
      if (!job) {
        res.status(404).json({ error: 'Job not found' });
        return;
      }
      if (job.status !== JobStatus.AWAITING_SELECTION) {
        res.status(409).json({ error: 'Assumptions can only be captured during idea selection' });
        return;
      }
      if (job.selectionFinalDecision) {
        res.status(409).json({ error: 'The owner decision is locked; assumptions can no longer change' });
        return;
      }
      if (!isCurrentIdea(job.id, job.solutionIdeas, input.ideaId, input.ideaRevision)) {
        res.status(409).json({ error: 'This idea revision is no longer current' });
        return;
      }

      if (input.originChallengeId && input.originQuestionId) {
        const challenge = await prisma.selectionChallenge.findFirst({
          where: {
            id: input.originChallengeId,
            jobId: job.id,
            ideaId: input.ideaId,
            ideaRevision: input.ideaRevision,
            lens: PRISMA_ASSUMPTION_LENS[input.lens],
          },
          select: { artifact: true },
        });
        const artifact = SelectionChallengeArtifactSchema.safeParse(challenge?.artifact);
        const hasQuestion = artifact.success
          && artifact.data.questions.some(question => question.questionId === input.originQuestionId);
        if (!challenge || !artifact.success || !hasQuestion) {
          res.status(400).json({ error: 'Evidence-check origin does not match this idea revision, lens, and question' });
          return;
        }
      }

      const statementFingerprintValue = statementFingerprint(input);
      const originWhere = input.originChallengeId && input.originQuestionId
        ? {
            jobId: job.id,
            originChallengeId: input.originChallengeId,
            originQuestionId: input.originQuestionId,
          }
        : null;
      const existing = await prisma.selectionAssumption.findFirst({
        where: originWhere ?? {
          jobId: job.id,
          ideaId: input.ideaId,
          ideaRevision: input.ideaRevision,
          lens: PRISMA_ASSUMPTION_LENS[input.lens],
          statementFingerprint: statementFingerprintValue,
        },
        include: selectionAssumptionInclude,
      });
      if (existing) {
        if (!isExactCreateRetry(existing, input)) {
          res.status(409).json({ error: 'This assumption already exists; update it with its current version' });
          return;
        }
        res.json({
          assumption: serializeSelectionAssumption(existing, false),
          cached: true,
        });
        return;
      }

      try {
        const assumption = await prisma.selectionAssumption.create({
          data: {
            jobId: job.id,
            ideaId: input.ideaId,
            ideaRevision: input.ideaRevision,
            lens: PRISMA_ASSUMPTION_LENS[input.lens],
            statement: input.statement,
            impactIfFalse: input.impactIfFalse,
            falsificationQuestion: input.falsificationQuestion,
            impact: input.impact,
            originChallengeId: input.originChallengeId,
            originQuestionId: input.originQuestionId,
            statementFingerprint: statementFingerprintValue,
            createdByUserId: req.user!.id,
          },
          include: selectionAssumptionInclude,
        });
        res.status(201).json({
          assumption: serializeSelectionAssumption(assumption, false),
          cached: false,
        });
      } catch (error) {
        if (error instanceof Prisma.PrismaClientKnownRequestError && error.code === 'P2002') {
          const raced = await prisma.selectionAssumption.findFirst({
            where: originWhere ?? {
              jobId: job.id,
              ideaId: input.ideaId,
              ideaRevision: input.ideaRevision,
              lens: PRISMA_ASSUMPTION_LENS[input.lens],
              statementFingerprint: statementFingerprintValue,
            },
            include: selectionAssumptionInclude,
          });
          if (raced && isExactCreateRetry(raced, input)) {
            res.json({ assumption: serializeSelectionAssumption(raced, false), cached: true });
            return;
          }
          res.status(409).json({ error: 'This assumption already exists; reload before updating it' });
          return;
        }
        throw error;
      }
    } catch (error) {
      if (error instanceof z.ZodError) {
        res.status(400).json({ error: 'Validation error', details: error.errors });
        return;
      }
      console.error('Failed to create selection assumption:', error);
      res.status(500).json({ error: 'Failed to create assumption' });
    }
  },
);

selectionAssumptionsRouter.patch(
  '/:jobId/selection-assumptions/:assumptionId',
  requireInternalAuth,
  async (req: AuthenticatedRequest, res: Response) => {
    try {
      const params = AssumptionParamsSchema.parse(req.params);
      const input = SelectionAssumptionPatchSchema.parse(req.body);
      const job = await findOwnedJob(params.jobId, req.user!.id, {
        id: true,
        status: true,
        solutionIdeas: true,
        selectionFinalDecision: { select: { id: true } },
      });
      if (!job) {
        res.status(404).json({ error: 'Job not found' });
        return;
      }
      const existing = await prisma.selectionAssumption.findFirst({
        where: {
          id: params.assumptionId,
          jobId: job.id,
          createdByUserId: req.user!.id,
        },
        select: { id: true, ideaId: true, ideaRevision: true, lens: true },
      });
      if (!existing) {
        res.status(404).json({ error: 'Assumption not found' });
        return;
      }
      if (
        existing.ideaId !== input.ideaId
        || existing.ideaRevision !== input.ideaRevision
        || !isCurrentIdea(job.id, job.solutionIdeas, input.ideaId, input.ideaRevision)
      ) {
        res.status(409).json({ error: 'This assumption targets a stale idea revision' });
        return;
      }
      if (job.status !== JobStatus.AWAITING_SELECTION) {
        res.status(409).json({ error: 'Assumptions can only be updated during idea selection' });
        return;
      }
      if (job.selectionFinalDecision) {
        res.status(409).json({ error: 'The owner decision is locked; assumptions can no longer change' });
        return;
      }

      const { expectedVersion, ideaId: _ideaId, ideaRevision: _ideaRevision, ...patch } = input;
      let result: { count: number };
      try {
        result = await prisma.selectionAssumption.updateMany({
          where: {
            id: existing.id,
            jobId: job.id,
            ideaId: input.ideaId,
            ideaRevision: input.ideaRevision,
            version: expectedVersion,
          },
          data: {
            ...patch,
            ...(patch.statement ? {
              statementFingerprint: statementFingerprint({
                ideaId: input.ideaId,
                ideaRevision: input.ideaRevision,
                lens: APP_LENS_FOR_RETRY[existing.lens],
                statement: patch.statement,
              }),
            } : {}),
            version: { increment: 1 },
          },
        });
      } catch (error) {
        if (error instanceof Prisma.PrismaClientKnownRequestError && error.code === 'P2002') {
          res.status(409).json({ error: 'An assumption with this statement already exists for this idea and lens' });
          return;
        }
        throw error;
      }
      if (result.count !== 1) {
        res.status(409).json({ error: 'Assumption changed; reload it before saving again' });
        return;
      }
      const assumption = await prisma.selectionAssumption.findUniqueOrThrow({
        where: { id: existing.id },
        include: selectionAssumptionInclude,
      });
      res.json({ assumption: serializeSelectionAssumption(assumption, false) });
    } catch (error) {
      if (error instanceof z.ZodError) {
        res.status(400).json({ error: 'Validation error', details: error.errors });
        return;
      }
      console.error('Failed to update selection assumption:', error);
      res.status(500).json({ error: 'Failed to update assumption' });
    }
  },
);
