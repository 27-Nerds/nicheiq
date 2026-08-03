import { Router, type Response } from 'express';
import {
  DispatchKind,
  DispatchState,
  JobStatus,
  Prisma,
  SelectionExperimentOutcome,
} from '@prisma/client';
import { z } from 'zod';
import { requireInternalAuth, type AuthenticatedRequest } from '../middleware/auth.js';
import { requireDecisionToolsAccess } from '../middleware/featureAccess.js';
import { prisma } from '../services/db.js';
import { generateSelectionIdeaNarrowing } from '../services/selectionIdeaNarrowingService.js';
import { ensureIdeaIdentities, ideaName } from '../utils/ideaIdentity.js';

export const selectionIdeaNarrowingRouter = Router();

const ParamsSchema = z.object({
  jobId: z.string().uuid(),
  experimentId: z.string().uuid(),
});

const experimentInclude = {
  conclusion: true,
  job: {
    select: {
      status: true,
      solutionIdeas: true,
      selectionDecisionProfile: true,
      selectionFinalDecision: { select: { id: true } },
    },
  },
} satisfies Prisma.SelectionExperimentInclude;

type NarrowingExperiment = Prisma.SelectionExperimentGetPayload<{ include: typeof experimentInclude }>;

function operationIdFor(conclusionId: string): string {
  return `narrow:${conclusionId}:v1`;
}

async function findOwnedExperiment(
  jobId: string,
  experimentId: string,
  userId: string,
): Promise<NarrowingExperiment | null> {
  return prisma.selectionExperiment.findFirst({
    where: { id: experimentId, jobId, job: { userId } },
    include: experimentInclude,
  });
}

function eligibleOutcome(
  outcome: SelectionExperimentOutcome,
): outcome is typeof SelectionExperimentOutcome.FAIL | typeof SelectionExperimentOutcome.AMBIGUOUS {
  return outcome === SelectionExperimentOutcome.FAIL
    || outcome === SelectionExperimentOutcome.AMBIGUOUS;
}

function currentParent(experiment: NarrowingExperiment) {
  return ensureIdeaIdentities(experiment.jobId, experiment.job.solutionIdeas).find((idea) =>
    idea.idea_id === experiment.ideaId && idea.idea_revision === experiment.ideaRevision
  );
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
    if (outcome && ['accepted', 'demoted', 'failed', 'refunded', 'cancelled'].includes(outcome)) {
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

function eligibilityError(experiment: NarrowingExperiment): string | null {
  if (!experiment.conclusion) return 'Record the experiment conclusion before narrowing this idea';
  if (!eligibleOutcome(experiment.conclusion.outcome)) {
    return 'Only a failed or ambiguous conclusion can produce a narrowed variant';
  }
  if (experiment.job.status !== JobStatus.AWAITING_SELECTION) {
    return 'Ideas can only be reshaped during idea selection';
  }
  if (experiment.job.selectionFinalDecision) {
    return 'The final decision is already locked; create a new research run to reshape this idea';
  }
  if (!currentParent(experiment)) {
    return 'The exact parent idea revision is no longer in this selection pool';
  }
  if (!ideaName(currentParent(experiment)!)) {
    return 'The parent idea is missing a usable name';
  }
  return null;
}

selectionIdeaNarrowingRouter.get(
  '/:jobId/selection-experiments/:experimentId/narrowing-proposal',
  requireInternalAuth,
  requireDecisionToolsAccess,
  async (req: AuthenticatedRequest, res: Response) => {
    try {
      const params = ParamsSchema.parse(req.params);
      const experiment = await findOwnedExperiment(params.jobId, params.experimentId, req.user!.id);
      if (!experiment) {
        res.status(404).json({ error: 'Experiment not found' });
        return;
      }
      if (!experiment.conclusion) {
        res.json({ proposalMessage: null, settlement: null });
        return;
      }
      const existing = await responseFor(params.jobId, operationIdFor(experiment.conclusion.id));
      res.json(existing ?? { proposalMessage: null, settlement: null });
    } catch (error) {
      if (error instanceof z.ZodError) {
        res.status(400).json({ error: 'Invalid experiment reference' });
        return;
      }
      console.error('Failed to load narrowing proposal:', error);
      res.status(500).json({ error: 'Failed to load narrowing proposal' });
    }
  },
);

selectionIdeaNarrowingRouter.post(
  '/:jobId/selection-experiments/:experimentId/narrowing-proposal',
  requireInternalAuth,
  requireDecisionToolsAccess,
  async (req: AuthenticatedRequest, res: Response) => {
    try {
      const params = ParamsSchema.parse(req.params);
      const experiment = await findOwnedExperiment(params.jobId, params.experimentId, req.user!.id);
      if (!experiment) {
        res.status(404).json({ error: 'Experiment not found' });
        return;
      }
      const eligibility = eligibilityError(experiment);
      if (eligibility) {
        res.status(409).json({ error: eligibility });
        return;
      }
      const conclusion = experiment.conclusion!;
      const operationId = operationIdFor(conclusion.id);
      const existing = await responseFor(params.jobId, operationId);
      if (existing) {
        res.json({ ...existing, cached: true });
        return;
      }
      const parent = currentParent(experiment)!;
      const parentName = ideaName(parent)!;
      const generated = await generateSelectionIdeaNarrowing({
        jobId: experiment.jobId,
        experimentId: experiment.id,
        conclusionId: conclusion.id,
        outcome: conclusion.outcome as 'FAIL' | 'AMBIGUOUS',
        evidenceSource: conclusion.evidenceSource,
        parent: {
          ideaId: experiment.ideaId,
          ideaRevision: experiment.ideaRevision,
          solutionName: parentName,
          snapshot: parent,
        },
        conclusionSnapshot: conclusion.snapshot,
        decisionProfile: experiment.job.selectionDecisionProfile,
      });

      const fresh = await findOwnedExperiment(params.jobId, params.experimentId, req.user!.id);
      if (
        !fresh
        || fresh.conclusion?.id !== conclusion.id
        || eligibilityError(fresh)
      ) {
        res.status(409).json({ error: 'The idea or conclusion changed while the variant was being prepared' });
        return;
      }

      let proposalMessage;
      try {
        proposalMessage = await prisma.chatMessage.create({
          data: {
            jobId: experiment.jobId,
            gateStage: 5,
            role: 'assistant',
            content: generated.content,
            patchJson: generated.patch as unknown as Prisma.InputJsonValue,
            costUsd: generated.costUsd || null,
            model: generated.model,
            origin: 'experiment_narrowing',
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
          const winner = await responseFor(params.jobId, operationId);
          if (winner) {
            res.json({ ...winner, cached: true });
            return;
          }
        }
        throw error;
      }
      if (generated.costUsd > 0) {
        await prisma.job.update({
          where: { id: experiment.jobId },
          data: { chatCostUsd: { increment: generated.costUsd } },
        }).catch((error) => console.error('Failed to record narrowing-agent cost:', error));
      }
      res.status(201).json({
        proposalMessage,
        settlement: { state: 'ready', idea: null },
        cached: false,
      });
    } catch (error) {
      if (error instanceof z.ZodError) {
        res.status(502).json({ error: 'The narrowing agent returned an invalid proposal' });
        return;
      }
      if (
        error instanceof Error
        && ['INVALID_NARROWING_OUTPUT', 'UNSUPPORTED_NARROWING_CLAIM'].includes(error.message)
      ) {
        res.status(502).json({ error: 'The narrowing agent returned an unsupported proposal' });
        return;
      }
      if (error instanceof Error && error.message === 'STALE_CONCLUSION_SNAPSHOT') {
        res.status(409).json({ error: 'The stored conclusion no longer matches this idea revision' });
        return;
      }
      if (error instanceof Error && error.message === 'AI_PROVIDER_UNAVAILABLE') {
        res.status(503).json({ error: 'Narrowing agent unavailable' });
        return;
      }
      console.error('Failed to generate narrowing proposal:', error);
      res.status(502).json({ error: 'Failed to generate narrowed variant' });
    }
  },
);
