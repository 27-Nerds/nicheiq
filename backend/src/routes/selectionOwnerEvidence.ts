import { createHash } from 'crypto';
import { Router, type Response } from 'express';
import {
  JobStatus,
  Prisma,
  SelectionChallengeLens,
  SelectionOwnerEvidenceKind,
  SelectionOwnerEvidencePosition,
} from '@prisma/client';
import { z } from 'zod';
import { requireInternalAuth, type AuthenticatedRequest } from '../middleware/auth.js';
import { requireDecisionToolsAccess } from '../middleware/featureAccess.js';
import { prisma } from '../services/db.js';
import {
  SelectionOwnerEvidenceInputSchema,
  SelectionOwnerEvidenceRetractionSchema,
  type SelectionOwnerEvidenceInput,
} from '../types/selectionOwnerEvidence.js';
import { ensureIdeaIdentities } from '../utils/ideaIdentity.js';

const JobParamsSchema = z.object({ jobId: z.string().uuid() });
const EvidenceParamsSchema = JobParamsSchema.extend({ evidenceId: z.string().uuid() });
const EDITABLE_JOB_STATUSES = new Set<JobStatus>([JobStatus.AWAITING_SELECTION]);
const MAX_ACTIVE_EVIDENCE_PER_JOB = 200;

const PRISMA_LENS = {
  demand: SelectionChallengeLens.DEMAND,
  competition: SelectionChallengeLens.COMPETITION,
  distribution: SelectionChallengeLens.DISTRIBUTION,
  dependencies: SelectionChallengeLens.DEPENDENCIES,
} as const;

function normalizeUrl(value: string | null): string | null {
  if (!value) return null;
  const url = new URL(value);
  url.hash = '';
  return url.toString();
}

function fingerprint(input: SelectionOwnerEvidenceInput): string {
  return createHash('sha256').update(JSON.stringify({
    ideaId: input.ideaId,
    ideaRevision: input.ideaRevision,
    lens: input.lens,
    kind: input.kind,
    position: input.position,
    title: input.title,
    content: input.content,
    sourceUrl: normalizeUrl(input.sourceUrl),
    observedAt: input.observedAt ? new Date(input.observedAt).toISOString() : null,
  })).digest('hex');
}

function serialize(row: {
  id: string;
  jobId: string;
  ideaId: string;
  ideaRevision: number;
  lens: SelectionChallengeLens;
  kind: SelectionOwnerEvidenceKind;
  position: SelectionOwnerEvidencePosition;
  title: string;
  content: string;
  sourceUrl: string | null;
  observedAt: Date | null;
  createdAt: Date;
  retractedAt: Date | null;
  retractionReason: string | null;
}) {
  return {
    id: row.id,
    jobId: row.jobId,
    ideaId: row.ideaId,
    ideaRevision: row.ideaRevision,
    lens: row.lens.toLowerCase(),
    kind: row.kind,
    position: row.position,
    title: row.title,
    content: row.content,
    sourceUrl: row.sourceUrl,
    observedAt: row.observedAt?.toISOString() ?? null,
    createdAt: row.createdAt.toISOString(),
    retractedAt: row.retractedAt?.toISOString() ?? null,
    retractionReason: row.retractionReason,
  };
}

async function ownedJob(jobId: string, userId: string) {
  return prisma.job.findFirst({
    where: { id: jobId, userId },
    select: {
      id: true,
      status: true,
      solutionIdeas: true,
      selectionFinalDecision: { select: { id: true } },
    },
  });
}

function editable(job: NonNullable<Awaited<ReturnType<typeof ownedJob>>>): boolean {
  return EDITABLE_JOB_STATUSES.has(job.status) && !job.selectionFinalDecision;
}

export const selectionOwnerEvidenceRouter = Router();

selectionOwnerEvidenceRouter.get(
  '/:jobId/selection-evidence',
  requireInternalAuth,
  requireDecisionToolsAccess,
  async (req: AuthenticatedRequest, res: Response) => {
    const params = JobParamsSchema.safeParse(req.params);
    if (!params.success) {
      res.status(400).json({ error: 'Invalid job ID format' });
      return;
    }
    try {
      const job = await ownedJob(params.data.jobId, req.user!.id);
      if (!job) {
        res.status(404).json({ error: 'Job not found' });
        return;
      }
      const evidence = await prisma.selectionOwnerEvidence.findMany({
        where: { jobId: job.id },
        orderBy: { createdAt: 'desc' },
      });
      res.setHeader('Cache-Control', 'private, no-store');
      res.json({ evidence: evidence.map(serialize), editable: editable(job) });
    } catch (error) {
      console.error('Failed to load owner selection evidence:', error);
      res.status(500).json({ error: 'Failed to load selection evidence' });
    }
  },
);

selectionOwnerEvidenceRouter.post(
  '/:jobId/selection-evidence',
  requireInternalAuth,
  requireDecisionToolsAccess,
  async (req: AuthenticatedRequest, res: Response) => {
    const params = JobParamsSchema.safeParse(req.params);
    const input = SelectionOwnerEvidenceInputSchema.safeParse(req.body);
    if (!params.success || !input.success) {
      res.status(400).json({
        error: 'Validation error',
        details: params.success ? input.error?.errors : params.error.errors,
      });
      return;
    }
    try {
      const inputFingerprint = fingerprint(input.data);
      const where = {
        jobId: params.data.jobId,
        ideaId: input.data.ideaId,
        ideaRevision: input.data.ideaRevision,
        inputFingerprint,
      };
      const result = await prisma.$transaction(async tx => {
        const job = await tx.job.findFirst({
          where: { id: params.data.jobId, userId: req.user!.id },
          select: {
            id: true,
            status: true,
            solutionIdeas: true,
            selectionFinalDecision: { select: { id: true } },
          },
        });
        if (!job) return { kind: 'not_found' as const };
        if (!editable(job)) return { kind: 'locked' as const };
        const idea = ensureIdeaIdentities(job.id, job.solutionIdeas).find(candidate =>
          candidate.idea_id === input.data.ideaId
          && candidate.idea_revision === input.data.ideaRevision
        );
        if (!idea) return { kind: 'stale' as const };
        const existing = await tx.selectionOwnerEvidence.findFirst({ where });
        if (existing) {
          return existing.retractedAt
            ? { kind: 'retracted' as const }
            : { kind: 'cached' as const, row: existing };
        }
        const activeCount = await tx.selectionOwnerEvidence.count({
          where: { jobId: job.id, retractedAt: null },
        });
        if (activeCount >= MAX_ACTIVE_EVIDENCE_PER_JOB) return { kind: 'full' as const };
        const row = await tx.selectionOwnerEvidence.create({
          data: {
            ...where,
            lens: PRISMA_LENS[input.data.lens],
            kind: input.data.kind,
            position: input.data.position,
            title: input.data.title,
            content: input.data.content,
            sourceUrl: normalizeUrl(input.data.sourceUrl),
            observedAt: input.data.observedAt ? new Date(input.data.observedAt) : null,
            createdByUserId: req.user!.id,
          },
        });
        return { kind: 'created' as const, row };
      }, { isolationLevel: Prisma.TransactionIsolationLevel.Serializable });

      if (result.kind === 'not_found') {
        res.status(404).json({ error: 'Job not found' });
        return;
      }
      if (result.kind === 'locked') {
        res.status(409).json({ error: 'Evidence can only be added during idea selection' });
        return;
      }
      if (result.kind === 'stale') {
        res.status(409).json({ error: 'This idea revision changed; reopen the comparison' });
        return;
      }
      if (result.kind === 'retracted') {
        res.status(409).json({ error: 'This exact evidence was retracted; add a corrected record instead' });
        return;
      }
      if (result.kind === 'full') {
        res.status(409).json({ error: 'This selection already has the maximum number of active evidence records' });
        return;
      }
      res.setHeader('Cache-Control', 'private, no-store');
      res.status(result.kind === 'created' ? 201 : 200).json({
        evidence: serialize(result.row),
        cached: result.kind === 'cached',
      });
    } catch (error) {
      if (error instanceof Prisma.PrismaClientKnownRequestError && error.code === 'P2002') {
        const winner = await prisma.selectionOwnerEvidence.findFirst({
          where: {
            jobId: params.data.jobId,
            ideaId: input.data.ideaId,
            ideaRevision: input.data.ideaRevision,
            inputFingerprint: fingerprint(input.data),
            retractedAt: null,
          },
        });
        if (winner) {
          res.setHeader('Cache-Control', 'private, no-store');
          res.json({ evidence: serialize(winner), cached: true });
          return;
        }
      }
      if (error instanceof Prisma.PrismaClientKnownRequestError && error.code === 'P2034') {
        res.status(409).json({ error: 'The selection changed concurrently; reopen the comparison' });
        return;
      }
      console.error('Failed to add owner selection evidence:', error);
      res.status(500).json({ error: 'Failed to add selection evidence' });
    }
  },
);

selectionOwnerEvidenceRouter.post(
  '/:jobId/selection-evidence/:evidenceId/retract',
  requireInternalAuth,
  requireDecisionToolsAccess,
  async (req: AuthenticatedRequest, res: Response) => {
    const params = EvidenceParamsSchema.safeParse(req.params);
    const input = SelectionOwnerEvidenceRetractionSchema.safeParse(req.body);
    if (!params.success || !input.success) {
      res.status(400).json({
        error: 'Validation error',
        details: params.success ? input.error?.errors : params.error.errors,
      });
      return;
    }
    try {
      const job = await ownedJob(params.data.jobId, req.user!.id);
      if (!job) {
        res.status(404).json({ error: 'Job not found' });
        return;
      }
      if (!editable(job)) {
        res.status(409).json({ error: 'Evidence can only be retracted before the selection decision is locked' });
        return;
      }
      const existing = await prisma.selectionOwnerEvidence.findFirst({
        where: { id: params.data.evidenceId, jobId: job.id },
      });
      if (!existing) {
        res.status(404).json({ error: 'Evidence not found' });
        return;
      }
      if (existing.retractedAt) {
        res.setHeader('Cache-Control', 'private, no-store');
        res.json({ evidence: serialize(existing), cached: true });
        return;
      }
      const retractedAt = new Date();
      const updated = await prisma.selectionOwnerEvidence.updateMany({
        where: { id: existing.id, jobId: job.id, retractedAt: null },
        data: {
          retractedAt,
          retractionReason: input.data.reason,
        },
      });
      if (updated.count === 0) {
        const winner = await prisma.selectionOwnerEvidence.findFirst({
          where: { id: existing.id, jobId: job.id },
        });
        if (!winner) {
          res.status(404).json({ error: 'Evidence not found' });
          return;
        }
        res.setHeader('Cache-Control', 'private, no-store');
        res.json({ evidence: serialize(winner), cached: true });
        return;
      }
      res.setHeader('Cache-Control', 'private, no-store');
      res.json({
        evidence: serialize({
          ...existing,
          retractedAt,
          retractionReason: input.data.reason,
        }),
        cached: false,
      });
    } catch (error) {
      console.error('Failed to retract owner selection evidence:', error);
      res.status(500).json({ error: 'Failed to retract selection evidence' });
    }
  },
);
