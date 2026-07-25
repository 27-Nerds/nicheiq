import { Prisma, type SelectionDecisionHandoff } from '@prisma/client';
import { Router, type Response } from 'express';
import { z } from 'zod';
import { requireInternalAuth, type AuthenticatedRequest } from '../middleware/auth.js';
import { requireDecisionToolsAccess } from '../middleware/featureAccess.js';
import { prisma } from '../services/db.js';
import {
  artifactAsPrismaJson,
  materializeDecisionHandoff,
  renderDecisionHandoffMarkdown,
  serializeDecisionHandoffJson,
  type SelectionDecisionHandoffArtifact,
} from '../services/selectionDecisionHandoffService.js';

const ParamsSchema = z.object({ jobId: z.string().uuid() });
const ExportParamsSchema = ParamsSchema.extend({ format: z.enum(['md', 'json']) });
const MaterializeSchema = z.object({ finalDecisionId: z.string().uuid() }).strict();

export const selectionDecisionHandoffsRouter = Router();

async function loadOwnedDecision(jobId: string, userId: string) {
  return prisma.job.findFirst({
    where: { id: jobId, userId },
    select: {
      id: true,
      selectionFinalDecision: {
        include: { decisionHandoff: true },
      },
    },
  });
}

function publicHandoff(handoff: SelectionDecisionHandoff) {
  return {
    id: handoff.id,
    finalDecisionId: handoff.finalDecisionId,
    action: handoff.action,
    ideaId: handoff.ideaId,
    ideaRevision: handoff.ideaRevision,
    inputFingerprint: handoff.inputFingerprint,
    artifact: handoff.artifact,
    createdAt: handoff.createdAt,
  };
}

function knownError(error: unknown): { status: number; message: string } | null {
  if (!(error instanceof Error)) return null;
  const messages: Record<string, string> = {
    HANDOFF_TARGET_MISMATCH: 'The final decision target does not match its frozen idea snapshot',
    HANDOFF_NULL_TARGET_REQUIRED: 'Park and stop decisions cannot carry an implementation target',
    HANDOFF_TEST_BRIEF_REQUIRED: 'Test first requires the locked test brief frozen with the owner decision',
    HANDOFF_TEST_BRIEF_MISMATCH: 'The selected test brief does not match the frozen decision target',
    HANDOFF_NULL_TEST_BRIEF_REQUIRED: 'Only a Test first decision can carry a locked test brief',
    HANDOFF_PRE_MORTEM_REQUIRED: 'Proceed and Test first require the pre-mortem frozen with the owner decision',
    HANDOFF_PRE_MORTEM_MISMATCH: 'The pre-mortem does not match the frozen decision target',
    HANDOFF_NULL_PRE_MORTEM_REQUIRED: 'Park and Stop decisions cannot carry a pre-mortem',
  };
  return messages[error.message] ? { status: 409, message: messages[error.message] } : null;
}

selectionDecisionHandoffsRouter.get(
  '/:jobId/decision-handoff/export/:format',
  requireInternalAuth,
  requireDecisionToolsAccess,
  async (req: AuthenticatedRequest, res: Response) => {
    try {
      const { jobId, format } = ExportParamsSchema.parse(req.params);
      const job = await loadOwnedDecision(jobId, req.user!.id);
      if (!job) {
        res.status(404).json({ error: 'Job not found' });
        return;
      }
      const handoff = job.selectionFinalDecision?.decisionHandoff;
      if (!handoff) {
        res.status(404).json({ error: 'Decision handoff not found' });
        return;
      }
      const artifact = handoff.artifact as unknown as SelectionDecisionHandoffArtifact;
      const filename = `nicheiq-decision-${jobId.slice(0, 8)}.${format}`;
      res.setHeader('Cache-Control', 'private, no-store');
      res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
      if (format === 'md') {
        res.type('text/markdown').send(
          renderDecisionHandoffMarkdown(artifact, handoff.inputFingerprint),
        );
        return;
      }
      res.type('application/json').send(
        serializeDecisionHandoffJson(artifact, handoff.inputFingerprint),
      );
    } catch (error) {
      if (error instanceof z.ZodError) {
        res.status(400).json({ error: 'Invalid handoff export reference' });
        return;
      }
      console.error('Failed to export selection decision handoff:', error);
      res.status(500).json({ error: 'Failed to export decision handoff' });
    }
  },
);

selectionDecisionHandoffsRouter.get(
  '/:jobId/decision-handoff',
  requireInternalAuth,
  requireDecisionToolsAccess,
  async (req: AuthenticatedRequest, res: Response) => {
    try {
      const { jobId } = ParamsSchema.parse(req.params);
      const job = await loadOwnedDecision(jobId, req.user!.id);
      if (!job) {
        res.status(404).json({ error: 'Job not found' });
        return;
      }
      res.setHeader('Cache-Control', 'private, no-store');
      res.json({
        handoff: job.selectionFinalDecision?.decisionHandoff
          ? publicHandoff(job.selectionFinalDecision.decisionHandoff)
          : null,
      });
    } catch (error) {
      if (error instanceof z.ZodError) {
        res.status(400).json({ error: 'Invalid job reference' });
        return;
      }
      console.error('Failed to load selection decision handoff:', error);
      res.status(500).json({ error: 'Failed to load decision handoff' });
    }
  },
);

selectionDecisionHandoffsRouter.post(
  '/:jobId/decision-handoff',
  requireInternalAuth,
  requireDecisionToolsAccess,
  async (req: AuthenticatedRequest, res: Response) => {
    try {
      const { jobId } = ParamsSchema.parse(req.params);
      const { finalDecisionId } = MaterializeSchema.parse(req.body);
      const job = await loadOwnedDecision(jobId, req.user!.id);
      if (!job) {
        res.status(404).json({ error: 'Job not found' });
        return;
      }
      const decision = job.selectionFinalDecision;
      if (!decision) {
        res.status(409).json({ error: 'Record the final owner decision before creating a handoff' });
        return;
      }
      if (decision.id !== finalDecisionId) {
        res.status(409).json({ error: 'The requested final decision is not current for this job' });
        return;
      }

      const materialized = materializeDecisionHandoff(decision);
      if (decision.decisionHandoff) {
        if (decision.decisionHandoff.inputFingerprint === materialized.inputFingerprint) {
          res.json({ handoff: publicHandoff(decision.decisionHandoff) });
          return;
        }
        res.status(409).json({ error: 'The stored handoff does not match the immutable owner decision' });
        return;
      }

      try {
        const handoff = await prisma.selectionDecisionHandoff.create({
          data: {
            finalDecisionId: decision.id,
            action: materialized.action,
            ideaId: materialized.ideaId,
            ideaRevision: materialized.ideaRevision,
            inputFingerprint: materialized.inputFingerprint,
            artifact: artifactAsPrismaJson(materialized.artifact),
          },
        });
        res.status(201).json({ handoff: publicHandoff(handoff) });
      } catch (error) {
        if (error instanceof Prisma.PrismaClientKnownRequestError && error.code === 'P2002') {
          const existing = await prisma.selectionDecisionHandoff.findUnique({
            where: { finalDecisionId: decision.id },
          });
          if (existing?.inputFingerprint === materialized.inputFingerprint) {
            res.json({ handoff: publicHandoff(existing) });
            return;
          }
          res.status(409).json({ error: 'Another decision handoff was created first' });
          return;
        }
        throw error;
      }
    } catch (error) {
      if (error instanceof z.ZodError) {
        res.status(400).json({ error: 'Validation error', details: error.errors });
        return;
      }
      const known = knownError(error);
      if (known) {
        res.status(known.status).json({ error: known.message });
        return;
      }
      console.error('Failed to create selection decision handoff:', error);
      res.status(500).json({ error: 'Failed to create decision handoff' });
    }
  },
);
