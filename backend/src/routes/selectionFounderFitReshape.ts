import {
  DispatchKind,
  DispatchState,
  JobStatus,
  Prisma,
} from '@prisma/client';
import { Router, type Response } from 'express';
import { z } from 'zod';
import { CONFIG } from '../config.js';
import { requireInternalAuth, type AuthenticatedRequest } from '../middleware/auth.js';
import { requireDecisionToolsAccess } from '../middleware/featureAccess.js';
import { prisma } from '../services/db.js';
import { parseCurrentFounderFitArtifact } from '../services/founderFitService.js';
import { generateSelectionFounderFitReshape } from '../services/selectionFounderFitReshapeService.js';
import {
  findOwnedSelectionWorkspaceJob as findOwnedJob,
  type SelectionWorkspaceJob as ReshapeJob,
} from '../services/selectionOwnedJobService.js';
import { ensureIdeaIdentities, ideaName } from '../utils/ideaIdentity.js';

export const selectionFounderFitReshapeRouter = Router();

const ParamsSchema = z.object({
  jobId: z.string().uuid(),
  ideaId: z.string().trim().min(1).max(128),
  ideaRevision: z.coerce.number().int().positive(),
});

import { createHash } from 'node:crypto';

function operationIdFor(inputFingerprint: string, ideaId: string, ideaRevision: number): string {
  const raw = `founder-fit-reshape:${inputFingerprint}:${ideaId}:${ideaRevision}`;
  if (raw.length <= 64) return raw;
  return `ffr:${createHash('sha256').update(raw).digest('hex').slice(0, 60)}`;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

async function settlementFor(jobId: string, sourceMessageId: string) {
  const [dispatch, receipts] = await Promise.all([
    prisma.jobDispatch.findFirst({
      where: { jobId, kind: DispatchKind.SEED_IDEA, sourceMessageId },
      orderBy: { createdAt: 'desc' },
      select: { state: true },
    }),
    prisma.chatMessage.findMany({
      where: { jobId, gateStage: 5, role: 'receipt' },
      orderBy: { createdAt: 'desc' },
      take: 100,
      select: { patchJson: true },
    }),
  ]);
  for (const receipt of receipts) {
    const envelope = asRecord(receipt.patchJson);
    if (envelope?.kind !== 'ledger_event' || envelope.sourceMessageId !== sourceMessageId) continue;
    const outcome = typeof envelope.outcome === 'string' ? envelope.outcome : null;
    if (outcome && ['accepted', 'demoted', 'failed', 'refunded'].includes(outcome)) {
      return { state: outcome, idea: asRecord(envelope.idea) };
    }
  }
  if (!dispatch) return { state: 'ready', idea: null };
  if (dispatch.state === DispatchState.FAILED) return { state: 'failed', idea: null };
  return { state: 'pending', idea: null };
}

async function responseFor(jobId: string, operationId: string) {
  const proposalMessage = await prisma.chatMessage.findUnique({
    where: { operationId },
    select: { id: true, content: true, patchJson: true, createdAt: true },
  });
  if (!proposalMessage || !asRecord(proposalMessage.patchJson)) return null;
  return {
    proposalMessage,
    settlement: await settlementFor(jobId, proposalMessage.id),
  };
}

function reshapeContext(job: ReshapeJob, ideaId: string, ideaRevision: number) {
  if (job.status !== JobStatus.AWAITING_SELECTION) {
    return { error: 'Ideas can only be reshaped during idea selection' } as const;
  }
  if (job.selectionFinalDecision) {
    return { error: 'The final decision is already locked; create a new research run to reshape this idea' } as const;
  }
  const pool = ensureIdeaIdentities(job.id, job.solutionIdeas);
  const artifact = parseCurrentFounderFitArtifact(
    job.selectionFounderFit,
    job.selectionDecisionProfile,
    pool,
  );
  if (!artifact) return { error: 'Run founder fit again for the current profile and idea revisions' } as const;
  const parent = pool.find((idea) =>
    idea.idea_id === ideaId && idea.idea_revision === ideaRevision
  );
  const result = artifact.results.find((candidate) =>
    candidate.ideaId === ideaId && candidate.ideaRevision === ideaRevision
  );
  if (!parent || !ideaName(parent)) {
    return { error: 'The exact parent idea revision is no longer in this selection pool' } as const;
  }
  if (!result || result.verdict !== 'needs_reshape') {
    return { error: 'Only a current “Reshape first” founder-fit result can produce this variant' } as const;
  }
  const conflicts = result.dimensions.filter((dimension) => dimension.status === 'conflict');
  if (conflicts.some((dimension) => dimension.dimension === 'hard_constraints')) {
    return { error: 'A literal hard-constraint conflict cannot be softened into a reshape proposal' } as const;
  }
  if (!conflicts.length) {
    return { error: 'This founder-fit result has no explicit conflict to reshape' } as const;
  }
  return { artifact, parent, result } as const;
}

selectionFounderFitReshapeRouter.get(
  '/:jobId/founder-fit/:ideaId/:ideaRevision/reshape-proposal',
  requireInternalAuth,
  requireDecisionToolsAccess,
  async (req: AuthenticatedRequest, res: Response) => {
    try {
      const params = ParamsSchema.parse(req.params);
      const job = await findOwnedJob(params.jobId, req.user!.id);
      if (!job) {
        res.status(404).json({ error: 'Job not found' });
        return;
      }
      const context = reshapeContext(job, params.ideaId, params.ideaRevision);
      if ('error' in context) {
        res.status(409).json({ error: context.error });
        return;
      }
      const existing = await responseFor(
        job.id,
        operationIdFor(context.artifact.inputFingerprint, params.ideaId, params.ideaRevision),
      );
      res.json(existing ?? { proposalMessage: null, settlement: null });
    } catch (error) {
      if (error instanceof z.ZodError) {
        res.status(400).json({ error: 'Invalid founder-fit reshape reference' });
        return;
      }
      console.error('Failed to load founder-fit reshape proposal:', error);
      res.status(500).json({ error: 'Failed to load founder-fit reshape proposal' });
    }
  },
);

selectionFounderFitReshapeRouter.post(
  '/:jobId/founder-fit/:ideaId/:ideaRevision/reshape-proposal',
  requireInternalAuth,
  requireDecisionToolsAccess,
  async (req: AuthenticatedRequest, res: Response) => {
    try {
      const params = ParamsSchema.parse(req.params);
      const job = await findOwnedJob(params.jobId, req.user!.id);
      if (!job) {
        res.status(404).json({ error: 'Job not found' });
        return;
      }
      const context = reshapeContext(job, params.ideaId, params.ideaRevision);
      if ('error' in context) {
        res.status(409).json({ error: context.error });
        return;
      }
      const operationId = operationIdFor(
        context.artifact.inputFingerprint,
        params.ideaId,
        params.ideaRevision,
      );
      const existing = await responseFor(job.id, operationId);
      if (existing) {
        res.json({ ...existing, cached: true });
        return;
      }
      if (!CONFIG.openaiApiKey) {
        res.status(503).json({ error: 'Founder-fit reshape agent unavailable' });
        return;
      }

      const generated = await generateSelectionFounderFitReshape({
        artifact: context.artifact,
        parent: {
          ideaId: params.ideaId,
          ideaRevision: params.ideaRevision,
          solutionName: ideaName(context.parent)!,
          snapshot: context.parent,
        },
      });

      const fresh = await findOwnedJob(params.jobId, req.user!.id);
      const freshContext = fresh
        ? reshapeContext(fresh, params.ideaId, params.ideaRevision)
        : { error: 'Job not found' } as const;
      if (
        !fresh
        || 'error' in freshContext
        || freshContext.artifact.inputFingerprint !== context.artifact.inputFingerprint
      ) {
        res.status(409).json({ error: 'The profile, fit analysis, or idea changed while the variant was being prepared' });
        return;
      }

      let proposalMessage;
      try {
        proposalMessage = await prisma.chatMessage.create({
          data: {
            jobId: job.id,
            gateStage: 5,
            role: 'assistant',
            content: generated.content,
            patchJson: generated.patch as unknown as Prisma.InputJsonValue,
            costUsd: generated.costUsd || null,
            model: generated.model,
            origin: 'founder_fit_reshape',
            operationId,
            inputTokens: generated.usage.inputTokens,
            outputTokens: generated.usage.outputTokens,
            cacheWriteTokens: generated.usage.cacheWriteTokens,
            cacheReadTokens: generated.usage.cacheReadTokens,
          },
          select: { id: true, content: true, patchJson: true, createdAt: true },
        });
      } catch (error) {
        if (error instanceof Prisma.PrismaClientKnownRequestError && error.code === 'P2002') {
          const winner = await responseFor(job.id, operationId);
          if (winner) {
            res.json({ ...winner, cached: true });
            return;
          }
        }
        throw error;
      }
      if (generated.costUsd > 0) {
        await prisma.job.update({
          where: { id: job.id },
          data: { chatCostUsd: { increment: generated.costUsd } },
        }).catch((error) => console.error('Failed to record founder-fit reshape cost:', error));
      }
      res.status(201).json({
        proposalMessage,
        settlement: { state: 'ready', idea: null },
        cached: false,
      });
    } catch (error) {
      if (error instanceof z.ZodError) {
        res.status(502).json({ error: 'The founder-fit reshape agent returned an invalid proposal' });
        return;
      }
      if (error instanceof Error && [
        'INVALID_FOUNDER_FIT_RESHAPE_OUTPUT',
        'UNSUPPORTED_FOUNDER_FIT_RESHAPE_CLAIM',
      ].includes(error.message)) {
        res.status(502).json({ error: 'The founder-fit reshape agent returned an unsupported proposal' });
        return;
      }
      console.error('Failed to generate founder-fit reshape proposal:', error);
      res.status(502).json({ error: 'Failed to generate founder-fit reshape proposal' });
    }
  },
);
