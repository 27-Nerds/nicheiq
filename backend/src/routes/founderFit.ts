import { Router, Response } from 'express';
import { JobStatus, Prisma } from '@prisma/client';
import { z } from 'zod';
import { CONFIG } from '../config.js';
import { requireInternalAuth, type AuthenticatedRequest } from '../middleware/auth.js';
import { requireDecisionToolsAccess } from '../middleware/featureAccess.js';
import { prisma } from '../services/db.js';
import { hasApiKeyForModel } from '../services/openai.js';
import {
  FounderFitGenerationError,
  founderFitFingerprint,
  founderFitIdeaSnapshot,
  generateFounderFitArtifact,
  parseCurrentFounderFitArtifact,
  type FounderFitFailureCause,
} from '../services/founderFitService.js';
import { FounderFitRequestSchema } from '../types/founderFit.js';
import { SelectionDecisionProfileSchema } from '../types/job.js';
import { ensureIdeaIdentities } from '../utils/ideaIdentity.js';

const JobParamsSchema = z.object({ jobId: z.string().uuid() });
const EDITABLE_JOB_STATUSES = new Set<JobStatus>([JobStatus.AWAITING_SELECTION]);

const FOUNDER_FIT_FAILURES: Record<FounderFitFailureCause, { code: string; error: string }> = {
  timeout: {
    code: 'FOUNDER_FIT_TIMEOUT',
    error: 'Founder-fit analysis timed out; no selection data was changed',
  },
  upstream: {
    code: 'FOUNDER_FIT_UPSTREAM',
    error: 'Founder-fit analysis is temporarily unavailable; no selection data was changed',
  },
  no_content: {
    code: 'FOUNDER_FIT_NO_CONTENT',
    error: 'Founder-fit analysis returned no usable result; no selection data was changed',
  },
  bad_json: {
    code: 'FOUNDER_FIT_BAD_JSON',
    error: 'Founder-fit analysis returned an invalid result; no selection data was changed',
  },
  schema_mismatch: {
    code: 'FOUNDER_FIT_SCHEMA_MISMATCH',
    error: 'Founder-fit analysis returned an incomplete result; no selection data was changed',
  },
  coverage_mismatch: {
    code: 'FOUNDER_FIT_COVERAGE_MISMATCH',
    error: 'Founder-fit analysis did not cover every selected idea; no selection data was changed',
  },
};

export const founderFitRouter = Router();

const jobSelect = {
  id: true,
  status: true,
  solutionIdeas: true,
  selectionDecisionProfile: true,
  selectionFounderFit: true,
  updatedAt: true,
} as const;

founderFitRouter.get('/:jobId/founder-fit', requireInternalAuth, requireDecisionToolsAccess, async (req: AuthenticatedRequest, res: Response) => {
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

    const ideas = ensureIdeaIdentities(job.id, job.solutionIdeas);
    const analysis = parseCurrentFounderFitArtifact(
      job.selectionFounderFit,
      job.selectionDecisionProfile,
      ideas,
    );
    res.setHeader('Cache-Control', 'private, no-store');
    res.json({ analysis, stale: Boolean(job.selectionFounderFit) && !analysis });
  } catch (error) {
    console.error('Failed to load founder-fit analysis:', error);
    res.status(500).json({ error: 'Failed to load founder-fit analysis' });
  }
});

founderFitRouter.post('/:jobId/founder-fit', requireInternalAuth, requireDecisionToolsAccess, async (req: AuthenticatedRequest, res: Response) => {
  const params = JobParamsSchema.safeParse(req.params);
  const input = FounderFitRequestSchema.safeParse(req.body);
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
      res.status(409).json({ error: 'Founder fit can only be analyzed during idea selection' });
      return;
    }

    const profile = SelectionDecisionProfileSchema.safeParse(job.selectionDecisionProfile);
    if (!profile.success) {
      res.status(409).json({ error: 'Save your decision context before analyzing founder fit' });
      return;
    }

    const pool = ensureIdeaIdentities(job.id, job.solutionIdeas);
    const ideas = input.data.ideas.flatMap((reference) => {
      const idea = pool.find(candidate =>
        candidate.idea_id === reference.ideaId && candidate.idea_revision === reference.ideaRevision
      );
      return idea ? [idea] : [];
    });
    if (ideas.length !== input.data.ideas.length) {
      res.status(409).json({ error: 'One or more idea revisions changed; reopen the comparison' });
      return;
    }

    const snapshots = ideas.map(founderFitIdeaSnapshot);
    const fingerprint = founderFitFingerprint(profile.data, snapshots);
    const current = parseCurrentFounderFitArtifact(
      job.selectionFounderFit,
      profile.data,
      pool,
    );
    if (current?.inputFingerprint === fingerprint) {
      res.setHeader('Cache-Control', 'private, no-store');
      res.json({ analysis: current, cached: true });
      return;
    }
    if (!hasApiKeyForModel(CONFIG.founderFitModel)) {
      res.status(503).json({ error: 'Founder-fit analysis is temporarily unavailable' });
      return;
    }

    const analysis = await generateFounderFitArtifact(profile.data, ideas);
    const result = await prisma.job.updateMany({
      where: {
        id: job.id,
        userId: req.user!.id,
        status: job.status,
        updatedAt: job.updatedAt,
      },
      data: { selectionFounderFit: analysis as unknown as Prisma.InputJsonValue },
    });
    if (result.count !== 1) {
      res.status(409).json({ error: 'The selection changed while founder fit was being analyzed' });
      return;
    }

    res.setHeader('Cache-Control', 'private, no-store');
    res.status(201).json({ analysis, cached: false });
  } catch (error) {
    console.error('Failed to analyze founder fit:', error);
    if (error instanceof FounderFitGenerationError) {
      const failure = FOUNDER_FIT_FAILURES[error.failureCause];
      res.status(error.failureCause === 'timeout' ? 504 : 502).json(failure);
      return;
    }
    res.status(502).json({ error: 'Founder-fit analysis failed; no selection data was changed' });
  }
});
