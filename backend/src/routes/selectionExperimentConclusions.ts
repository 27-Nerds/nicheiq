import {
  JobStatus,
  Prisma,
  SelectionExperimentEvidenceSource,
  SelectionExperimentOutcome,
  SelectionExperimentRunStatus,
  SelectionExperimentStatus,
} from '@prisma/client';
import { Router, type Response } from 'express';
import { z } from 'zod';
import { requireInternalAuth, type AuthenticatedRequest } from '../middleware/auth.js';
import { requireDecisionToolsAccess } from '../middleware/featureAccess.js';
import { canonicalJsonSha256 } from '../utils/canonicalFingerprint.js';
import { prisma } from '../services/db.js';
import { calculateSelectionExperimentResults } from '../services/selectionExperimentResultService.js';
import {
  deriveSelectionAssumptionEvidence,
  selectionAssumptionInclude,
} from '../services/selectionAssumptionService.js';
import {
  SelectionExperimentConclusionInputSchema,
  type SelectionExperimentConclusionInput,
} from '../types/selectionExperiment.js';

const ParamsSchema = z.object({
  jobId: z.string().uuid(),
  experimentId: z.string().uuid(),
});

const experimentInclude = Prisma.validator<Prisma.SelectionExperimentInclude>()({
  job: { select: { status: true } },
  run: true,
  conclusion: true,
  linkedAssumption: { include: selectionAssumptionInclude },
});
type ConclusionExperiment = Prisma.SelectionExperimentGetPayload<{ include: typeof experimentInclude }>;

export const selectionExperimentConclusionsRouter = Router();

export function fingerprintConclusionRequest(input: SelectionExperimentConclusionInput): string {
  return canonicalJsonSha256(input);
}

function nextActionFor(experiment: ConclusionExperiment, outcome: SelectionExperimentOutcome): string {
  switch (outcome) {
    case SelectionExperimentOutcome.PASS: return experiment.passAction;
    case SelectionExperimentOutcome.FAIL: return experiment.failAction;
    case SelectionExperimentOutcome.AMBIGUOUS: return experiment.flatAction;
    case SelectionExperimentOutcome.INVALID: return experiment.invalidAction;
  }
}

function experimentSnapshot(experiment: ConclusionExperiment) {
  return {
    experimentId: experiment.id,
    jobId: experiment.jobId,
    ideaId: experiment.ideaId,
    ideaRevision: experiment.ideaRevision,
    ideaSnapshot: experiment.ideaSnapshot,
    originSnapshot: experiment.originSnapshot,
    assumptionId: experiment.assumptionId,
    assumptionType: experiment.assumptionType,
    evidenceSignal: experiment.evidenceSignal,
    assumption: experiment.assumption,
    whyCritical: experiment.whyCritical,
    currentEvidence: experiment.currentEvidence,
    method: experiment.method,
    stimulus: experiment.stimulus,
    audience: experiment.audience,
    channel: experiment.channel,
    lockedAt: experiment.lockedAt?.toISOString() ?? null,
  };
}

function precommitmentSnapshot(experiment: ConclusionExperiment) {
  return {
    primaryMetric: experiment.primaryMetric,
    passThreshold: experiment.passThreshold,
    failThreshold: experiment.failThreshold,
    measurementWindow: experiment.measurementWindow,
    sampleTarget: experiment.sampleTarget,
    passAction: experiment.passAction,
    failAction: experiment.failAction,
    ambiguousAction: experiment.flatAction,
    invalidAction: experiment.invalidAction,
  };
}

function assumptionTransitionFromSnapshot(snapshot: Prisma.JsonValue) {
  if (!snapshot || typeof snapshot !== 'object' || Array.isArray(snapshot)) return null;
  return 'assumptionTransition' in snapshot ? snapshot.assumptionTransition ?? null : null;
}

async function findOwnedExperiment(jobId: string, experimentId: string, userId: string) {
  return prisma.selectionExperiment.findFirst({
    where: {
      id: experimentId,
      jobId,
      job: { userId },
    },
    include: experimentInclude,
  });
}

selectionExperimentConclusionsRouter.get(
  '/:jobId/selection-experiments/:experimentId/conclusion',
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
      res.setHeader('Cache-Control', 'private, no-store');
      res.json({
        conclusion: experiment.conclusion,
        assumptionTransition: experiment.conclusion
          ? assumptionTransitionFromSnapshot(experiment.conclusion.snapshot)
          : null,
      });
    } catch (error) {
      if (error instanceof z.ZodError) {
        res.status(400).json({ error: 'Invalid experiment reference' });
        return;
      }
      console.error('Failed to load selection experiment conclusion:', error);
      res.status(500).json({ error: 'Failed to load test conclusion' });
    }
  },
);

selectionExperimentConclusionsRouter.post(
  '/:jobId/selection-experiments/:experimentId/conclusion',
  requireInternalAuth,
  requireDecisionToolsAccess,
  async (req: AuthenticatedRequest, res: Response) => {
    try {
      const params = ParamsSchema.parse(req.params);
      const input = SelectionExperimentConclusionInputSchema.parse(req.body);
      const requestFingerprint = fingerprintConclusionRequest(input);
      const experiment = await findOwnedExperiment(params.jobId, params.experimentId, req.user!.id);

      if (!experiment) {
        res.status(404).json({ error: 'Experiment not found' });
        return;
      }
      if (experiment.conclusion) {
        if (experiment.conclusion.requestFingerprint === requestFingerprint) {
          res.json({
            conclusion: experiment.conclusion,
            assumptionTransition: assumptionTransitionFromSnapshot(experiment.conclusion.snapshot),
          });
          return;
        }
        res.status(409).json({ error: 'This test already has an immutable conclusion' });
        return;
      }
      if (experiment.status !== SelectionExperimentStatus.LOCKED) {
        res.status(409).json({ error: 'Lock the experiment brief before recording a conclusion' });
        return;
      }
      if (experiment.job.status !== JobStatus.AWAITING_SELECTION) {
        res.status(409).json({ error: 'Conclusions can only be recorded during idea selection' });
        return;
      }

      const nextAction = nextActionFor(experiment, input.outcome);
      let evidence: Record<string, unknown>;

      if (input.evidenceSource === SelectionExperimentEvidenceSource.HOSTED_RUN) {
        if (!experiment.run) {
          res.status(409).json({ error: 'This experiment has no hosted run to conclude' });
          return;
        }
        if (
          experiment.run.status !== SelectionExperimentRunStatus.CLOSED
          || !experiment.run.closedAt
        ) {
          res.status(409).json({ error: 'Close the hosted run before recording its conclusion' });
          return;
        }
        const results = await calculateSelectionExperimentResults(prisma, {
          runId: experiment.run.id,
          runStatus: experiment.run.status,
          sampleTarget: experiment.sampleTarget,
          observedThrough: experiment.run.closedAt,
        });
        if (
          results.quality.status !== 'SUFFICIENT'
          && (input.outcome === SelectionExperimentOutcome.PASS || input.outcome === SelectionExperimentOutcome.FAIL)
        ) {
          res.status(409).json({
            error: results.quality.status === 'INVALID'
              ? 'This hosted evidence is unusable; record INVALID and follow the repair action'
              : 'The planned sample is incomplete; record AMBIGUOUS or INVALID instead of pass or fail',
          });
          return;
        }
        evidence = {
          source: {
            sourceType: 'FIRST_PARTY',
            adapterKey: 'nicheiq-hosted',
            runId: experiment.run.id,
          },
          window: {
            startedAt: experiment.run.launchedAt.toISOString(),
            stoppedAt: experiment.run.closedAt.toISOString(),
            observedThrough: experiment.run.closedAt.toISOString(),
          },
          artifact: experiment.run.artifact,
          sample: {
            observed: results.exposures,
            target: results.sampleTarget,
            unit: 'qualified exposures',
          },
          metrics: [
            { key: 'exposures', label: 'Exposures', valueType: 'COUNT', value: results.exposures, isPrimary: false },
            { key: 'cta_actions', label: 'CTA actions', valueType: 'COUNT', value: results.ctaClicks, isPrimary: false },
            {
              key: 'cta_rate',
              label: experiment.primaryMetric,
              valueType: 'RATE',
              value: results.ctaRate,
              numerator: results.ctaClicks,
              denominator: results.exposures,
              isPrimary: true,
            },
            { key: 'disclosures', label: 'Fake-door disclosures', valueType: 'COUNT', value: results.disclosures, isPrimary: false },
          ],
          quality: results.quality,
          firstEventAt: results.firstEventAt?.toISOString() ?? null,
          lastEventAt: results.lastEventAt?.toISOString() ?? null,
          limitations: input.limitations,
        };
      } else {
        if (experiment.run) {
          res.status(409).json({ error: 'Use the hosted run evidence for this experiment' });
          return;
        }
        evidence = {
          source: {
            sourceType: 'MANUAL',
            adapterKey: 'manual',
            references: input.sourceReferences,
          },
          window: {
            observedThrough: input.observedAt,
          },
          observationSummary: input.observationSummary,
          sample: {
            observed: input.sampleSize,
            target: experiment.sampleTarget,
            unit: null,
          },
          observedMetric: input.observedMetric || null,
          quality: { status: 'UNKNOWN', warnings: [] },
          limitations: input.limitations,
        };
      }

      let assumptionTransition: {
        assumptionId: string;
        before: Record<string, unknown>;
        after: Record<string, unknown>;
      } | null = null;
      if (experiment.linkedAssumption) {
        const before = deriveSelectionAssumptionEvidence(experiment.linkedAssumption);
        const after = deriveSelectionAssumptionEvidence(experiment.linkedAssumption, {
          outcome: input.outcome,
          evidenceSource: input.evidenceSource,
          snapshot: { evidence } as Prisma.JsonObject,
        });
        assumptionTransition = {
          assumptionId: experiment.linkedAssumption.id,
          before: {
            ...before,
            ownerState: experiment.linkedAssumption.ownerState,
            version: experiment.linkedAssumption.version,
          },
          after: {
            ...after,
            ownerState: experiment.linkedAssumption.ownerState,
            version: experiment.linkedAssumption.version,
          },
        };
      }

      const snapshot = {
        schemaVersion: 1,
        experiment: experimentSnapshot(experiment),
        precommitment: precommitmentSnapshot(experiment),
        evidence,
        adjudication: {
          outcome: input.outcome,
          basis: 'OWNER_RECORDED',
          rationale: input.ownerRationale,
          nextAction,
          precommittedActionUsed: true,
        },
        assumptionTransition,
      };

      try {
        const conclusion = await prisma.$transaction(async tx => {
          const currentExperiment = await tx.selectionExperiment.findUnique({
            where: { id: experiment.id },
            select: { assumptionId: true },
          });
          if (currentExperiment?.assumptionId !== experiment.assumptionId) {
            throw new Error('ASSUMPTION_LINK_CHANGED');
          }
          return tx.selectionExperimentConclusion.create({
            data: {
              experimentId: experiment.id,
              ideaId: experiment.ideaId,
              ideaRevision: experiment.ideaRevision,
              outcome: input.outcome,
              evidenceSource: input.evidenceSource,
              requestFingerprint,
              ownerRationale: input.ownerRationale,
              nextActionSnapshot: nextAction,
              snapshot: snapshot as Prisma.InputJsonObject,
              concludedByUserId: req.user!.id,
            },
          });
        });
        res.status(201).json({ conclusion, assumptionTransition });
      } catch (error) {
        if (error instanceof Error && error.message === 'ASSUMPTION_LINK_CHANGED') {
          res.status(409).json({ error: 'The linked assumption changed; reload the experiment before concluding it' });
          return;
        }
        if (error instanceof Prisma.PrismaClientKnownRequestError && error.code === 'P2002') {
          const conclusion = await prisma.selectionExperimentConclusion.findUnique({
            where: { experimentId: experiment.id },
          });
          if (conclusion?.requestFingerprint === requestFingerprint) {
            res.json({
              conclusion,
              assumptionTransition: assumptionTransitionFromSnapshot(conclusion.snapshot),
            });
            return;
          }
          res.status(409).json({ error: 'This test already has an immutable conclusion' });
          return;
        }
        throw error;
      }
    } catch (error) {
      if (error instanceof z.ZodError) {
        res.status(400).json({ error: 'Validation error', details: error.errors });
        return;
      }
      console.error('Failed to record selection experiment conclusion:', error);
      res.status(500).json({ error: 'Failed to record test conclusion' });
    }
  },
);
