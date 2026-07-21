import { Router, Response } from 'express';
import { JobStatus, Prisma, SelectionExperimentStatus } from '@prisma/client';
import { z } from 'zod';
import { requireInternalAuth, AuthenticatedRequest } from '../middleware/auth.js';
import { getDiscoveryDataForJob, getPreviewReportForJob } from '../services/assetService.js';
import { prisma } from '../services/db.js';
import { prepareSelectionChallengeInput } from '../services/selectionChallengeService.js';
import {
  materializeSelectionExperimentBrief,
  renderSelectionExperimentBriefMarkdown,
} from '../services/selectionExperimentBriefService.js';
import { ensureIdeaIdentities, ideaName, type IdeaRecord } from '../utils/ideaIdentity.js';
import {
  SelectionExperimentDraftSchema,
  type SelectionExperimentDraft,
} from '../types/selectionExperiment.js';
import { SelectionChallengeArtifactSchema } from '../types/selectionChallenge.js';

const JobParamsSchema = z.object({ jobId: z.string().uuid() });
const ExperimentParamsSchema = JobParamsSchema.extend({ experimentId: z.string().uuid() });
const ExperimentExportParamsSchema = ExperimentParamsSchema.extend({ format: z.enum(['md', 'json']) });
const EDITABLE_JOB_STATUSES = new Set<JobStatus>([JobStatus.AWAITING_SELECTION]);

export const selectionExperimentsRouter = Router();

function ideaSnapshot(idea: IdeaRecord) {
  return {
    idea_id: idea.idea_id,
    idea_revision: idea.idea_revision,
    solution_name: ideaName(idea),
    headline: typeof idea.headline === 'string' ? idea.headline : null,
    source_pain: typeof idea.source_pain === 'string' ? idea.source_pain : null,
    source_segment: typeof idea.source_segment === 'string' ? idea.source_segment : null,
    value_proposition: typeof idea.value_proposition === 'string' ? idea.value_proposition : null,
    critic_concern: typeof idea.critic_concern === 'string' ? idea.critic_concern : null,
  };
}

function draftData(input: SelectionExperimentDraft) {
  return {
    assumptionType: input.assumptionType,
    assumption: input.assumption,
    whyCritical: input.whyCritical,
    currentEvidence: input.currentEvidence,
    method: input.method,
    evidenceSignal: input.evidenceSignal,
    stimulus: input.stimulus,
    audience: input.audience,
    channel: input.channel,
    primaryMetric: input.primaryMetric,
    passThreshold: input.passThreshold,
    failThreshold: input.failThreshold,
    measurementWindow: input.measurementWindow,
    sampleTarget: input.sampleTarget,
    costEstimate: input.costEstimate,
    passAction: input.passAction,
    failAction: input.failAction,
    flatAction: input.flatAction,
    invalidAction: input.invalidAction,
  };
}

async function validLinkedAssumption(
  assumptionId: string,
  jobId: string,
  ideaId: string,
  ideaRevision: number,
) {
  return prisma.selectionAssumption.findFirst({
    where: { id: assumptionId, jobId, ideaId, ideaRevision },
    select: { id: true },
  });
}

selectionExperimentsRouter.get(
  '/:jobId/selection-experiments/:experimentId/export/:format',
  requireInternalAuth,
  async (req: AuthenticatedRequest, res: Response) => {
    try {
      const params = ExperimentExportParamsSchema.parse(req.params);
      const experiment = await prisma.selectionExperiment.findFirst({
        where: { id: params.experimentId, jobId: params.jobId, job: { userId: req.user!.id } },
      });
      if (!experiment) {
        res.status(404).json({ error: 'Experiment not found' });
        return;
      }
      if (experiment.status !== SelectionExperimentStatus.LOCKED || !experiment.lockedAt) {
        res.status(409).json({ error: 'Lock the test brief before exporting it' });
        return;
      }
      const brief = materializeSelectionExperimentBrief(experiment);
      const safeIdeaId = experiment.ideaId.replace(/[^a-zA-Z0-9_-]/g, '-').slice(0, 100) || 'idea';
      res.setHeader('Cache-Control', 'private, no-store');
      res.setHeader(
        'Content-Disposition',
        `attachment; filename="nicheiq-test-brief-${safeIdeaId}.${params.format}"`,
      );
      if (params.format === 'md') {
        res.type('text/markdown').send(renderSelectionExperimentBriefMarkdown(brief));
        return;
      }
      res.type('application/json').send(`${JSON.stringify(brief, null, 2)}\n`);
    } catch (error) {
      if (error instanceof z.ZodError) {
        res.status(400).json({ error: 'Invalid experiment export reference' });
        return;
      }
      console.error('Failed to export selection experiment:', error);
      res.status(500).json({ error: 'Failed to export test brief' });
    }
  },
);

selectionExperimentsRouter.get('/:jobId/selection-experiments', requireInternalAuth, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const params = JobParamsSchema.parse(req.params);
    const job = await prisma.job.findFirst({
      where: { id: params.jobId, userId: req.user!.id },
      select: { id: true },
    });
    if (!job) {
      res.status(404).json({ error: 'Job not found' });
      return;
    }

    const experiments = await prisma.selectionExperiment.findMany({
      where: { jobId: job.id },
      include: { run: true, conclusion: true },
      orderBy: { createdAt: 'desc' },
    });
    res.setHeader('Cache-Control', 'private, no-store');
    res.json({ experiments });
  } catch (error) {
    if (error instanceof z.ZodError) {
      res.status(400).json({ error: 'Invalid job ID format' });
      return;
    }
    console.error('Failed to list selection experiments:', error);
    res.status(500).json({ error: 'Failed to load experiments' });
  }
});

selectionExperimentsRouter.post('/:jobId/selection-experiments', requireInternalAuth, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const params = JobParamsSchema.parse(req.params);
    const input = SelectionExperimentDraftSchema.parse(req.body);
    if (Boolean(input.originChallengeId) !== Boolean(input.originQuestionId)) {
      res.status(400).json({ error: 'Challenge and question provenance must be provided together' });
      return;
    }
    const job = await prisma.job.findFirst({
      where: { id: params.jobId, userId: req.user!.id },
      select: { id: true, status: true, solutionIdeas: true },
    });
    if (!job) {
      res.status(404).json({ error: 'Job not found' });
      return;
    }
    if (!EDITABLE_JOB_STATUSES.has(job.status)) {
      res.status(409).json({ error: 'Experiments can only be drafted during idea selection' });
      return;
    }

    const ideas = ensureIdeaIdentities(job.id, job.solutionIdeas);
    const idea = ideas.find(candidate =>
      candidate.idea_id === input.ideaId && candidate.idea_revision === input.ideaRevision
    );
    if (!idea) {
      res.status(400).json({ error: 'Idea revision not found in this selection pool' });
      return;
    }
    if (
      input.assumptionId
      && !await validLinkedAssumption(input.assumptionId, job.id, input.ideaId, input.ideaRevision)
    ) {
      res.status(400).json({ error: 'Linked assumption does not match this job and exact idea revision' });
      return;
    }

    let originData: {
      originChallengeId?: string;
      originQuestionId?: string;
      originSnapshot?: Prisma.InputJsonValue;
    } = {};
    if (input.originChallengeId && input.originQuestionId) {
      const challenge = await prisma.selectionChallenge.findFirst({
        where: {
          id: input.originChallengeId,
          jobId: job.id,
          ideaId: input.ideaId,
          ideaRevision: input.ideaRevision,
        },
        select: { artifact: true },
      });
      const artifact = SelectionChallengeArtifactSchema.safeParse(challenge?.artifact);
      const question = artifact.success
        ? artifact.data.questions.find(candidate => candidate.questionId === input.originQuestionId)
        : null;
      if (!challenge || !artifact.success || !question) {
        res.status(400).json({ error: 'Evidence-check origin does not match this idea revision and question' });
        return;
      }
      const [previewReport, discoveryData, ownerEvidence] = await Promise.all([
        getPreviewReportForJob(job.id).catch(() => null),
        getDiscoveryDataForJob(job.id).catch(() => null),
        prisma.selectionOwnerEvidence.findMany({
          where: { jobId: job.id, retractedAt: null },
          orderBy: { createdAt: 'desc' },
        }),
      ]);
      const currentInput = prepareSelectionChallengeInput({
        lens: artifact.data.lens,
        idea,
        previewReport,
        discoveryData,
        ownerEvidence,
      });
      if (currentInput.inputFingerprint !== artifact.data.inputFingerprint) {
        res.status(409).json({ error: 'This evidence check is stale; recheck the gap before drafting a test' });
        return;
      }
      const evidenceKeys = [...new Set([
        ...question.skeptic.evidenceKeys,
        ...question.auditor.evidenceKeys,
      ])];
      const citedSources = artifact.data.evidenceSnapshot.filter(source => evidenceKeys.includes(source.key));
      originData = {
        originChallengeId: input.originChallengeId,
        originQuestionId: input.originQuestionId,
        originSnapshot: {
          version: 1,
          kind: 'SELECTION_CHALLENGE_QUESTION',
          challengeId: input.originChallengeId,
          challengeInputFingerprint: artifact.data.inputFingerprint,
          questionId: question.questionId,
          lens: artifact.data.lens,
          consensus: question.consensus,
          evidenceKeys,
          skeptic: question.skeptic,
          auditor: question.auditor,
          citedSources,
        },
      };
    }

    const experiment = await prisma.selectionExperiment.create({
      data: {
        jobId: job.id,
        ideaId: input.ideaId,
        ideaRevision: input.ideaRevision,
        ideaSnapshot: ideaSnapshot(idea),
        assumptionId: input.assumptionId ?? null,
        ...originData,
        ...draftData(input),
      },
    });
    res.status(201).json({ experiment });
  } catch (error) {
    if (error instanceof z.ZodError) {
      res.status(400).json({ error: 'Validation error', details: error.errors });
      return;
    }
    console.error('Failed to create selection experiment:', error);
    res.status(500).json({ error: 'Failed to create experiment' });
  }
});

selectionExperimentsRouter.put('/:jobId/selection-experiments/:experimentId', requireInternalAuth, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const params = ExperimentParamsSchema.parse(req.params);
    const input = SelectionExperimentDraftSchema.parse(req.body);
    if (Boolean(input.originChallengeId) !== Boolean(input.originQuestionId)) {
      res.status(400).json({ error: 'Challenge and question provenance must be provided together' });
      return;
    }
    const existing = await prisma.selectionExperiment.findFirst({
      where: { id: params.experimentId, jobId: params.jobId, job: { userId: req.user!.id } },
      include: { job: { select: { status: true } } },
    });
    if (!existing) {
      res.status(404).json({ error: 'Experiment not found' });
      return;
    }
    if (existing.status !== SelectionExperimentStatus.DRAFT) {
      res.status(409).json({ error: 'Locked experiments are immutable' });
      return;
    }
    if (!EDITABLE_JOB_STATUSES.has(existing.job.status)) {
      res.status(409).json({ error: 'Experiments can only be edited during idea selection' });
      return;
    }
    if (existing.ideaId !== input.ideaId || existing.ideaRevision !== input.ideaRevision) {
      res.status(400).json({ error: 'An experiment cannot be retargeted to another idea revision' });
      return;
    }
    if (
      (existing.originChallengeId ?? null) !== input.originChallengeId
      || (existing.originQuestionId ?? null) !== input.originQuestionId
    ) {
      res.status(400).json({ error: 'Evidence-check provenance cannot be changed' });
      return;
    }
    if (
      input.assumptionId
      && !await validLinkedAssumption(input.assumptionId, existing.jobId, input.ideaId, input.ideaRevision)
    ) {
      res.status(400).json({ error: 'Linked assumption does not match this job and exact idea revision' });
      return;
    }

    const experiment = await prisma.selectionExperiment.update({
      where: { id: existing.id },
      data: {
        ...draftData(input),
        ...(input.assumptionId !== undefined ? { assumptionId: input.assumptionId } : {}),
      },
    });
    res.json({ experiment });
  } catch (error) {
    if (error instanceof z.ZodError) {
      res.status(400).json({ error: 'Validation error', details: error.errors });
      return;
    }
    console.error('Failed to update selection experiment:', error);
    res.status(500).json({ error: 'Failed to update experiment' });
  }
});

selectionExperimentsRouter.post('/:jobId/selection-experiments/:experimentId/lock', requireInternalAuth, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const params = ExperimentParamsSchema.parse(req.params);
    const existing = await prisma.selectionExperiment.findFirst({
      where: { id: params.experimentId, jobId: params.jobId, job: { userId: req.user!.id } },
      include: { job: { select: { status: true } } },
    });
    if (!existing) {
      res.status(404).json({ error: 'Experiment not found' });
      return;
    }
    if (!EDITABLE_JOB_STATUSES.has(existing.job.status)) {
      res.status(409).json({ error: 'Experiments can only be locked during idea selection' });
      return;
    }
    if (existing.status !== SelectionExperimentStatus.DRAFT) {
      res.status(409).json({ error: 'Experiment is already locked' });
      return;
    }

    const lockedAt = new Date();
    const result = await prisma.selectionExperiment.updateMany({
      where: { id: existing.id, status: SelectionExperimentStatus.DRAFT },
      data: { status: SelectionExperimentStatus.LOCKED, lockedAt },
    });
    if (result.count !== 1) {
      res.status(409).json({ error: 'Experiment changed while it was being locked' });
      return;
    }
    const experiment = await prisma.selectionExperiment.findUnique({ where: { id: existing.id } });
    res.json({ experiment });
  } catch (error) {
    if (error instanceof z.ZodError) {
      res.status(400).json({ error: 'Invalid experiment reference' });
      return;
    }
    console.error('Failed to lock selection experiment:', error);
    res.status(500).json({ error: 'Failed to lock experiment' });
  }
});
