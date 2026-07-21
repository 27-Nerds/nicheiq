import crypto from 'crypto';
import {
  ExperimentEvidenceSignal,
  ExperimentMethod,
  Prisma,
  SelectionExperimentEventType,
  SelectionExperimentRunStatus,
  SelectionExperimentStatus,
} from '@prisma/client';
import { Router, type Request, type Response } from 'express';
import rateLimit from 'express-rate-limit';
import { z } from 'zod';
import { CONFIG } from '../config.js';
import { requireInternalAuth, type AuthenticatedRequest } from '../middleware/auth.js';
import { prisma } from '../services/db.js';
import { calculateSelectionExperimentResults } from '../services/selectionExperimentResultService.js';
import {
  SelectionExperimentEventInputSchema,
  SelectionExperimentLaunchSchema,
  type SelectionExperimentLaunch,
} from '../types/selectionExperiment.js';

export const selectionExperimentRunsRouter = Router();
export const publicSelectionExperimentRunsRouter = Router();

const OwnerParamsSchema = z.object({
  jobId: z.string().uuid(),
  experimentId: z.string().uuid(),
});
const PublicParamsSchema = z.object({
  publicToken: z.string().regex(/^[A-Za-z0-9_-]{20,64}$/),
});
const ViewPayloadSchema = z.object({
  runId: z.string().uuid(),
  viewId: z.string().uuid(),
  issuedAt: z.number().int().positive(),
});

const CTA_LABELS: Record<SelectionExperimentLaunch['ctaLabel'], string> = {
  IM_INTERESTED: "I'm interested",
  SHOW_ME_THE_CONCEPT: 'Show me the concept',
  ID_TRY_THIS: "I'd try this",
};
const DISCLOSURE = {
  title: 'This is a concept test',
  body: "This product is not available yet. No account or payment was created. Your click only tells the researcher that this specific promise caught your attention.",
};

const publicEventLimiter = rateLimit({
  windowMs: 60 * 1000,
  max: CONFIG.nodeEnv === 'production' ? 60 : 1_000,
  keyGenerator: (req: Request) => {
    const forwarded = req.headers['x-client-ip'];
    const clientIp = Array.isArray(forwarded) ? forwarded[0] : forwarded || req.ip;
    return `${clientIp}:${req.params.publicToken}`;
  },
  message: { error: 'Too many responses, please slow down' },
  standardHeaders: true,
  legacyHeaders: false,
  validate: { ip: false, keyGeneratorIpFallback: false },
});

function generatePublicToken(): string {
  return crypto.randomBytes(24).toString('base64url');
}

function signViewToken(runId: string): string {
  const payload = Buffer.from(JSON.stringify({
    runId,
    viewId: crypto.randomUUID(),
    issuedAt: Date.now(),
  })).toString('base64url');
  const signature = crypto
    .createHmac('sha256', CONFIG.experimentSigningSecret)
    .update(payload)
    .digest('base64url');
  return `${payload}.${signature}`;
}

function verifyViewToken(token: string, runId: string): { viewId: string } | null {
  const [payload, signature, extra] = token.split('.');
  if (!payload || !signature || extra) return null;

  const expected = crypto
    .createHmac('sha256', CONFIG.experimentSigningSecret)
    .update(payload)
    .digest();
  let provided: Buffer;
  try {
    provided = Buffer.from(signature, 'base64url');
  } catch {
    return null;
  }
  if (provided.length !== expected.length || !crypto.timingSafeEqual(provided, expected)) return null;

  try {
    const parsed = ViewPayloadSchema.parse(JSON.parse(Buffer.from(payload, 'base64url').toString('utf8')));
    const age = Date.now() - parsed.issuedAt;
    if (parsed.runId !== runId || age < -5 * 60_000 || age > 24 * 60 * 60_000) return null;
    return { viewId: parsed.viewId };
  } catch {
    return null;
  }
}

function publicArtifact(input: SelectionExperimentLaunch) {
  return {
    version: 1,
    headline: input.headline,
    promise: input.promise,
    ctaLabel: CTA_LABELS[input.ctaLabel],
    disclosure: DISCLOSURE,
  };
}

function serializeRun(run: {
  id: string;
  publicToken: string;
  status: SelectionExperimentRunStatus;
  artifact: Prisma.JsonValue;
  launchedAt: Date;
  closedAt: Date | null;
}) {
  return {
    id: run.id,
    publicToken: run.publicToken,
    status: run.status,
    artifact: run.artifact,
    launchedAt: run.launchedAt,
    closedAt: run.closedAt,
  };
}

selectionExperimentRunsRouter.post(
  '/:jobId/selection-experiments/:experimentId/run',
  requireInternalAuth,
  async (req: AuthenticatedRequest, res: Response) => {
    try {
      const params = OwnerParamsSchema.parse(req.params);
      const input = SelectionExperimentLaunchSchema.parse(req.body);
      const experiment = await prisma.selectionExperiment.findFirst({
        where: {
          id: params.experimentId,
          jobId: params.jobId,
          job: { userId: req.user!.id },
        },
        include: { run: true, conclusion: true },
      });

      if (!experiment) {
        res.status(404).json({ error: 'Experiment not found' });
        return;
      }
      if (experiment.conclusion) {
        res.status(409).json({ error: 'A concluded experiment cannot publish a new run' });
        return;
      }
      if (experiment.run) {
        if (experiment.run.status === SelectionExperimentRunStatus.CLOSED) {
          res.status(409).json({ error: 'A closed run cannot be relaunched; create a new experiment brief' });
          return;
        }
        res.json({ run: serializeRun(experiment.run) });
        return;
      }
      if (
        experiment.status !== SelectionExperimentStatus.LOCKED ||
        experiment.method !== ExperimentMethod.CTA_SMOKE_TEST ||
        experiment.evidenceSignal !== ExperimentEvidenceSignal.CTA_INTEREST
      ) {
        res.status(409).json({
          error: 'Hosted tests require a locked CTA smoke-test brief measuring CTA interest',
        });
        return;
      }

      try {
        const run = await prisma.selectionExperimentRun.create({
          data: {
            experimentId: experiment.id,
            publicToken: generatePublicToken(),
            artifact: publicArtifact(input),
          },
        });
        res.status(201).json({ run: serializeRun(run) });
      } catch (error) {
        if (error instanceof Prisma.PrismaClientKnownRequestError && error.code === 'P2002') {
          const run = await prisma.selectionExperimentRun.findUnique({ where: { experimentId: experiment.id } });
          if (run?.status === SelectionExperimentRunStatus.ACTIVE) {
            res.json({ run: serializeRun(run) });
            return;
          }
        }
        throw error;
      }
    } catch (error) {
      if (error instanceof z.ZodError) {
        res.status(400).json({ error: 'Validation error', details: error.errors });
        return;
      }
      console.error('Failed to launch selection experiment:', error);
      res.status(500).json({ error: 'Failed to publish test' });
    }
  },
);

selectionExperimentRunsRouter.post(
  '/:jobId/selection-experiments/:experimentId/run/close',
  requireInternalAuth,
  async (req: AuthenticatedRequest, res: Response) => {
    try {
      const params = OwnerParamsSchema.parse(req.params);
      const experiment = await prisma.selectionExperiment.findFirst({
        where: {
          id: params.experimentId,
          jobId: params.jobId,
          job: { userId: req.user!.id },
        },
        include: { run: true },
      });
      if (!experiment?.run) {
        res.status(404).json({ error: 'Experiment run not found' });
        return;
      }
      if (experiment.run.status === SelectionExperimentRunStatus.CLOSED) {
        res.json({ run: serializeRun(experiment.run) });
        return;
      }

      const closedAt = new Date();
      const changed = await prisma.selectionExperimentRun.updateMany({
        where: { id: experiment.run.id, status: SelectionExperimentRunStatus.ACTIVE },
        data: { status: SelectionExperimentRunStatus.CLOSED, closedAt },
      });
      if (changed.count !== 1) {
        const run = await prisma.selectionExperimentRun.findUnique({ where: { id: experiment.run.id } });
        if (run) {
          res.json({ run: serializeRun(run) });
          return;
        }
        res.status(404).json({ error: 'Experiment run not found' });
        return;
      }
      const run = await prisma.selectionExperimentRun.findUniqueOrThrow({ where: { id: experiment.run.id } });
      res.json({ run: serializeRun(run) });
    } catch (error) {
      if (error instanceof z.ZodError) {
        res.status(400).json({ error: 'Invalid experiment reference' });
        return;
      }
      console.error('Failed to close selection experiment:', error);
      res.status(500).json({ error: 'Failed to close test' });
    }
  },
);

selectionExperimentRunsRouter.get(
  '/:jobId/selection-experiments/:experimentId/results',
  requireInternalAuth,
  async (req: AuthenticatedRequest, res: Response) => {
    try {
      const params = OwnerParamsSchema.parse(req.params);
      const experiment = await prisma.selectionExperiment.findFirst({
        where: {
          id: params.experimentId,
          jobId: params.jobId,
          job: { userId: req.user!.id },
        },
        select: {
          sampleTarget: true,
          run: true,
        },
      });
      if (!experiment?.run) {
        res.status(404).json({ error: 'Experiment run not found' });
        return;
      }

      const results = await calculateSelectionExperimentResults(prisma, {
        runId: experiment.run.id,
        runStatus: experiment.run.status,
        sampleTarget: experiment.sampleTarget,
        observedThrough: experiment.run.closedAt ?? undefined,
      });

      res.setHeader('Cache-Control', 'private, no-store');
      res.json({
        results: {
          runStatus: results.runStatus,
          exposures: results.exposures,
          ctaClicks: results.ctaClicks,
          disclosures: results.disclosures,
          ctaRate: results.ctaRate,
          sampleTarget: results.sampleTarget,
          sampleProgress: results.sampleProgress,
          firstEventAt: results.firstEventAt,
          lastEventAt: results.lastEventAt,
          dataQualityWarning: results.dataQualityWarning,
        },
      });
    } catch (error) {
      if (error instanceof z.ZodError) {
        res.status(400).json({ error: 'Invalid experiment reference' });
        return;
      }
      console.error('Failed to load selection experiment results:', error);
      res.status(500).json({ error: 'Failed to load test results' });
    }
  },
);

publicSelectionExperimentRunsRouter.get(
  '/:publicToken',
  async (req: Request, res: Response) => {
    try {
      const params = PublicParamsSchema.parse(req.params);
      const run = await prisma.selectionExperimentRun.findFirst({
        where: {
          publicToken: params.publicToken,
          status: SelectionExperimentRunStatus.ACTIVE,
        },
        select: { id: true, artifact: true },
      });
      if (!run) {
        res.status(404).json({ error: 'Not found' });
        return;
      }

      res.setHeader('Cache-Control', 'private, no-store');
      res.setHeader('Referrer-Policy', 'no-referrer');
      res.setHeader('X-Robots-Tag', 'noindex, nofollow');
      res.json({
        test: {
          artifact: run.artifact,
          viewToken: signViewToken(run.id),
        },
      });
    } catch (error) {
      if (error instanceof z.ZodError) {
        res.status(404).json({ error: 'Not found' });
        return;
      }
      console.error('Failed to load public experiment:', error);
      res.status(500).json({ error: 'Failed to load concept test' });
    }
  },
);

publicSelectionExperimentRunsRouter.post(
  '/:publicToken/events',
  publicEventLimiter,
  async (req: Request, res: Response) => {
    try {
      const params = PublicParamsSchema.parse(req.params);
      const input = SelectionExperimentEventInputSchema.parse(req.body);
      const run = await prisma.selectionExperimentRun.findFirst({
        where: {
          publicToken: params.publicToken,
          status: SelectionExperimentRunStatus.ACTIVE,
        },
        select: { id: true },
      });
      if (!run) {
        res.status(404).json({ error: 'Not found' });
        return;
      }

      const view = verifyViewToken(input.viewToken, run.id);
      if (!view) {
        res.status(400).json({ error: 'Invalid view token' });
        return;
      }
      const occurredAt = new Date(input.occurredAt);
      const age = Date.now() - occurredAt.getTime();
      if (age < -5 * 60_000 || age > 24 * 60 * 60_000) {
        res.status(400).json({ error: 'Event timestamp is outside the accepted window' });
        return;
      }

      if (
        input.type === SelectionExperimentEventType.CTA_CLICKED ||
        input.type === SelectionExperimentEventType.FAKE_DOOR_DISCLOSED
      ) {
        const prerequisite = input.type === SelectionExperimentEventType.CTA_CLICKED
          ? SelectionExperimentEventType.STIMULUS_EXPOSED
          : SelectionExperimentEventType.CTA_CLICKED;
        const prior = await prisma.selectionExperimentEvent.findFirst({
          where: { runId: run.id, viewId: view.viewId, type: prerequisite },
          select: { id: true },
        });
        if (!prior) {
          res.status(409).json({ error: 'Event sequence is incomplete' });
          return;
        }
      }

      try {
        await prisma.selectionExperimentEvent.create({
          data: {
            runId: run.id,
            eventId: input.eventId,
            viewId: view.viewId,
            type: input.type,
            occurredAt,
          },
        });
      } catch (error) {
        if (!(error instanceof Prisma.PrismaClientKnownRequestError && error.code === 'P2002')) {
          throw error;
        }
      }
      res.status(202).json({ accepted: true });
    } catch (error) {
      if (error instanceof z.ZodError) {
        res.status(400).json({ error: 'Invalid event', details: error.errors });
        return;
      }
      console.error('Failed to record public experiment event:', error);
      res.status(500).json({ error: 'Failed to record response' });
    }
  },
);
