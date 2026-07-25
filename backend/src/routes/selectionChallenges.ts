import { Router, Response } from 'express';
import {
  JobStatus,
  Prisma,
  SelectionChallengeLens as PrismaSelectionChallengeLens,
} from '@prisma/client';
import { z } from 'zod';
import { CONFIG } from '../config.js';
import { requireInternalAuth, type AuthenticatedRequest } from '../middleware/auth.js';
import { requireDecisionToolsAccess } from '../middleware/featureAccess.js';
import { getDiscoveryDataForJob, getPreviewReportForJob } from '../services/assetService.js';
import { prisma } from '../services/db.js';
import {
  generateSelectionChallenge,
  prepareSelectionChallengeInput,
} from '../services/selectionChallengeService.js';
import {
  SELECTION_CHALLENGE_LENSES,
  SelectionChallengeArtifactSchema,
  SelectionChallengeRequestSchema,
  type SelectionChallengeLens,
} from '../types/selectionChallenge.js';
import { ensureIdeaIdentities, type IdeaRecord } from '../utils/ideaIdentity.js';

const JobParamsSchema = z.object({ jobId: z.string().uuid() });
const EDITABLE_JOB_STATUSES = new Set<JobStatus>([JobStatus.AWAITING_SELECTION]);

const PRISMA_LENS: Record<SelectionChallengeLens, PrismaSelectionChallengeLens> = {
  demand: PrismaSelectionChallengeLens.DEMAND,
  competition: PrismaSelectionChallengeLens.COMPETITION,
  distribution: PrismaSelectionChallengeLens.DISTRIBUTION,
  dependencies: PrismaSelectionChallengeLens.DEPENDENCIES,
};

const APP_LENS: Record<PrismaSelectionChallengeLens, SelectionChallengeLens> = {
  DEMAND: 'demand',
  COMPETITION: 'competition',
  DISTRIBUTION: 'distribution',
  DEPENDENCIES: 'dependencies',
};

const jobSelect = {
  id: true,
  status: true,
  solutionIdeas: true,
} as const;

function serializeChallenge(row: { id: string; artifact: unknown }) {
  const artifact = SelectionChallengeArtifactSchema.parse(row.artifact);
  return { id: row.id, ...artifact };
}

async function loadPackets(jobId: string) {
  const [previewReport, discoveryData, ownerEvidence, experimentResults] = await Promise.all([
    getPreviewReportForJob(jobId).catch(() => null),
    getDiscoveryDataForJob(jobId).catch(() => null),
    prisma.selectionOwnerEvidence.findMany({
      where: { jobId, retractedAt: null },
      orderBy: { createdAt: 'desc' },
    }),
    prisma.selectionExperiment.findMany({
      where: {
        jobId,
        originChallengeId: { not: null },
        conclusion: { isNot: null },
      },
      select: {
        id: true,
        ideaId: true,
        ideaRevision: true,
        originChallengeId: true,
        originChallenge: {
          select: {
            id: true,
            ideaId: true,
            ideaRevision: true,
            lens: true,
          },
        },
        conclusion: {
          select: {
            id: true,
            createdAt: true,
            snapshot: true,
          },
        },
      },
      orderBy: [{ createdAt: 'desc' }, { id: 'desc' }],
    }),
  ]);
  return { previewReport, discoveryData, ownerEvidence, experimentResults };
}

function currentIdea(pool: IdeaRecord[], ideaId: string, ideaRevision: number): IdeaRecord | null {
  return pool.find(idea => idea.idea_id === ideaId && idea.idea_revision === ideaRevision) ?? null;
}

export const selectionChallengesRouter = Router();

selectionChallengesRouter.get(
  '/:jobId/selection-challenges',
  requireInternalAuth,
  requireDecisionToolsAccess,
  async (req: AuthenticatedRequest, res: Response) => {
    const params = JobParamsSchema.safeParse(req.params);
    if (!params.success) {
      res.status(400).json({ error: 'Invalid job ID format' });
      return;
    }

    try {
      const job = await prisma.job.findFirst({
        where: { id: params.data.jobId, userId: req.user!.id },
        select: jobSelect,
      });
      if (!job) {
        res.status(404).json({ error: 'Job not found' });
        return;
      }

      const pool = ensureIdeaIdentities(job.id, job.solutionIdeas);
      if (pool.length === 0) {
        res.setHeader('Cache-Control', 'private, no-store');
        res.json({ challenges: [], stale: [] });
        return;
      }
      const packets = await loadPackets(job.id);
      const rows = await prisma.selectionChallenge.findMany({
        where: {
          jobId: job.id,
          ideaId: { in: pool.map(idea => String(idea.idea_id)) },
        },
        orderBy: { createdAt: 'desc' },
      });

      const challenges: ReturnType<typeof serializeChallenge>[] = [];
      const stale: Array<{ ideaId: string; ideaRevision: number; lens: SelectionChallengeLens }> = [];
      for (const idea of pool) {
        for (const lens of SELECTION_CHALLENGE_LENSES) {
          const prepared = prepareSelectionChallengeInput({
            lens,
            idea,
            ...packets,
          });
          const candidates = rows.filter(row =>
            row.ideaId === idea.idea_id
            && row.ideaRevision === idea.idea_revision
            && APP_LENS[row.lens] === lens
          );
          const current = candidates.find(row => row.inputFingerprint === prepared.inputFingerprint);
          if (current) {
            const parsed = SelectionChallengeArtifactSchema.safeParse(current.artifact);
            if (parsed.success) challenges.push({ id: current.id, ...parsed.data });
          } else if (candidates.length > 0) {
            stale.push({
              ideaId: String(idea.idea_id),
              ideaRevision: Number(idea.idea_revision),
              lens,
            });
          }
        }
      }

      res.setHeader('Cache-Control', 'private, no-store');
      res.json({ challenges, stale });
    } catch (error) {
      console.error('Failed to load selection challenges:', error);
      res.status(500).json({ error: 'Failed to load evidence stress tests' });
    }
  },
);

selectionChallengesRouter.post(
  '/:jobId/selection-challenges',
  requireInternalAuth,
  requireDecisionToolsAccess,
  async (req: AuthenticatedRequest, res: Response) => {
    const params = JobParamsSchema.safeParse(req.params);
    const input = SelectionChallengeRequestSchema.safeParse(req.body);
    if (!params.success || !input.success) {
      res.status(400).json({
        error: 'Validation error',
        details: params.success ? input.error?.errors : params.error.errors,
      });
      return;
    }

    try {
      const job = await prisma.job.findFirst({
        where: { id: params.data.jobId, userId: req.user!.id },
        select: jobSelect,
      });
      if (!job) {
        res.status(404).json({ error: 'Job not found' });
        return;
      }
      if (!EDITABLE_JOB_STATUSES.has(job.status)) {
        res.status(409).json({ error: 'Evidence can only be stress-tested during idea selection' });
        return;
      }

      const pool = ensureIdeaIdentities(job.id, job.solutionIdeas);
      const idea = currentIdea(pool, input.data.ideaId, input.data.ideaRevision);
      if (!idea) {
        res.status(409).json({ error: 'This idea revision changed; reopen the comparison' });
        return;
      }
      const packets = await loadPackets(job.id);
      const prepared = prepareSelectionChallengeInput({
        lens: input.data.lens,
        idea,
        ...packets,
      });
      const where = {
        jobId: job.id,
        ideaId: input.data.ideaId,
        ideaRevision: input.data.ideaRevision,
        lens: PRISMA_LENS[input.data.lens],
        inputFingerprint: prepared.inputFingerprint,
      };
      const cached = await prisma.selectionChallenge.findFirst({ where });
      if (cached) {
        res.setHeader('Cache-Control', 'private, no-store');
        res.json({ challenge: serializeChallenge(cached), cached: true });
        return;
      }
      if (
        prepared.evidenceSnapshot.length > 0
        && !CONFIG.openaiApiKey
        && !CONFIG.openrouterApiKey
      ) {
        res.status(503).json({ error: 'Evidence stress tests are temporarily unavailable' });
        return;
      }

      const artifact = await generateSelectionChallenge({
        lens: input.data.lens,
        idea,
        ...packets,
      });

      const currentJob = await prisma.job.findFirst({
        where: { id: job.id, userId: req.user!.id },
        select: jobSelect,
      });
      if (!currentJob || currentJob.status !== JobStatus.AWAITING_SELECTION) {
        res.status(409).json({ error: 'The selection changed while evidence was being checked' });
        return;
      }
      const latestIdea = currentIdea(
        ensureIdeaIdentities(currentJob.id, currentJob.solutionIdeas),
        input.data.ideaId,
        input.data.ideaRevision,
      );
      if (!latestIdea) {
        res.status(409).json({ error: 'The idea changed while evidence was being checked' });
        return;
      }
      const latestPackets = await loadPackets(job.id);
      const latestPrepared = prepareSelectionChallengeInput({
        lens: input.data.lens,
        idea: latestIdea,
        ...latestPackets,
      });
      if (latestPrepared.inputFingerprint !== artifact.inputFingerprint) {
        res.status(409).json({ error: 'The research evidence changed while it was being checked' });
        return;
      }

      try {
        const created = await prisma.selectionChallenge.create({
          data: {
            ...where,
            ideaSnapshot: artifact.ideaSnapshot as Prisma.InputJsonValue,
            evidenceSnapshot: artifact.evidenceSnapshot as unknown as Prisma.InputJsonValue,
            artifact: artifact as unknown as Prisma.InputJsonValue,
            skepticModel: artifact.skepticModel,
            auditorModel: artifact.auditorModel,
            promptVersion: artifact.promptVersion,
          },
        });
        res.setHeader('Cache-Control', 'private, no-store');
        res.status(201).json({ challenge: serializeChallenge(created), cached: false });
      } catch (error) {
        if (error instanceof Prisma.PrismaClientKnownRequestError && error.code === 'P2002') {
          const winner = await prisma.selectionChallenge.findFirst({ where });
          if (winner) {
            res.setHeader('Cache-Control', 'private, no-store');
            res.json({ challenge: serializeChallenge(winner), cached: true });
            return;
          }
        }
        throw error;
      }
    } catch (error) {
      console.error('Failed to stress-test selection evidence:', error);
      res.status(502).json({ error: 'Evidence stress test failed; no selection data was changed' });
    }
  },
);
