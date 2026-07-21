import { Router, Request, Response } from 'express';
import rateLimit from 'express-rate-limit';
import { z } from 'zod';
import { JobStatus } from '@prisma/client';
import { CONFIG } from '../config.js';
import { requireInternalAuth, verifyOwnership, AuthenticatedRequest } from '../middleware/auth.js';
import { prisma } from '../services/db.js';
import { getJob } from '../services/jobService.js';

const MAX_DOCUMENT_BYTES = 512 * 1024;
const MAX_TOTAL_POINTS = 50_000;
const EDITABLE_STATUSES = new Set<JobStatus>([
  JobStatus.AWAITING_SELECTION,
  JobStatus.REGENERATING,
]);
const ALLOWED_SECTION_KEYS = new Set([
  'section:overview',
  'section:market-snapshot',
  'research:page',
  'section:pain-points',
  'section:audience',
  'section:community',
  'section:dossier-header',
]);

const JobIdParamSchema = z.object({ jobId: z.string().uuid() });
const ShareTokenParamSchema = z.object({
  shareToken: z.string().regex(/^[A-Za-z0-9_-]{22}$/),
});
const AnnotationQuerySchema = z.object({
  sinceRevision: z.coerce.number().int().nonnegative().optional(),
});

const PointSchema = z.tuple([
  z.number().finite().min(0).max(1),
  z.number().finite().min(0).max(1),
]);
const AnchorPointSchema = z.object({
  key: z.string().min(1).max(320),
  x: z.number().finite().min(0).max(1),
  y: z.number().finite().min(0).max(1),
  width: z.number().finite().positive().max(1_000_000).optional(),
  height: z.number().finite().positive().max(1_000_000).optional(),
}).strict();
const AnchorSchema = z.object({
  key: z.string().min(1).max(320),
  width: z.number().finite().positive().max(1_000_000),
  height: z.number().finite().positive().max(1_000_000),
}).strict();
const StrokeSchema = z.object({
  id: z.string().uuid(),
  surfaceHeight: z.number().finite().positive().max(1_000_000).optional(),
  color: z.string().regex(/^#[0-9a-fA-F]{6}$/),
  width: z.number().finite().min(1).max(24),
  createdAt: z.number().int().nonnegative(),
  points: z.array(PointSchema).min(1).max(2_000),
  anchor: AnchorSchema.optional(),
  anchors: z.array(AnchorPointSchema.nullable()).max(2_000).optional(),
}).strict().superRefine((stroke, ctx) => {
  if (stroke.anchors && stroke.anchors.length !== stroke.points.length) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'Anchor and point counts must match' });
  }
});
const SurfaceSchema = z.object({
  strokes: z.array(StrokeSchema).max(500),
}).strict();

function isAllowedSurfaceKey(key: string): boolean {
  if (ALLOWED_SECTION_KEYS.has(key)) return true;
  return (
    key.startsWith('solution-row:') ||
    key.startsWith('solution-detail:') ||
    key.startsWith('ruled-out-detail:')
  ) && key.length <= 320 && !/[\u0000-\u001f]/.test(key);
}

const AnnotationDocumentSchema = z.object({
  version: z.literal(1),
  surfaces: z.record(z.string(), SurfaceSchema),
}).strict().superRefine((document, ctx) => {
  const entries = Object.entries(document.surfaces);
  if (entries.length > 100) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'Too many annotation surfaces' });
  }

  let totalPoints = 0;
  for (const [key, surface] of entries) {
    if (!isAllowedSurfaceKey(key)) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'Unsupported annotation surface: ' + key });
    }
    for (const stroke of surface.strokes) totalPoints += stroke.points.length;
  }
  if (totalPoints > MAX_TOTAL_POINTS) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'Annotation document has too many points' });
  }
});

const AnnotationBodySchema = z.object({ document: AnnotationDocumentSchema }).strict();
const EMPTY_DOCUMENT = { version: 1 as const, surfaces: {} };

const annotationPollingLimiter = rateLimit({
  windowMs: 60 * 1000,
  max: CONFIG.nodeEnv === 'production' ? 30 : 1000,
  keyGenerator: (req: Request) => String(req.ip) + ':' + String(req.params.shareToken),
  message: { error: 'Too many requests, please slow down' },
  standardHeaders: true,
  legacyHeaders: false,
  validate: { ip: false, keyGeneratorIpFallback: false },
});

export const discoveryAnnotationsRouter = Router();

discoveryAnnotationsRouter.get('/:jobId/discovery-annotations', requireInternalAuth, async (req: AuthenticatedRequest, res: Response) => {
  const parsed = JobIdParamSchema.safeParse(req.params);
  if (!parsed.success) {
    res.status(400).json({ error: 'Invalid job ID format' });
    return;
  }

  const job = await getJob(parsed.data.jobId);
  if (!job) {
    res.status(404).json({ error: 'Job not found' });
    return;
  }
  if (!verifyOwnership(req, job.userId)) {
    res.status(403).json({ error: 'Not authorized' });
    return;
  }

  const annotations = await prisma.discoveryAnnotationDocument.findUnique({
    where: { jobId: parsed.data.jobId },
  });
  res.setHeader('Cache-Control', 'private, no-store');
  res.json(annotations
    ? { revision: annotations.revision, document: annotations.document, updatedAt: annotations.updatedAt }
    : { revision: 0, document: EMPTY_DOCUMENT, updatedAt: null });
});

discoveryAnnotationsRouter.put('/:jobId/discovery-annotations', requireInternalAuth, async (req: AuthenticatedRequest, res: Response) => {
  const parsed = JobIdParamSchema.safeParse(req.params);
  if (!parsed.success) {
    res.status(400).json({ error: 'Invalid job ID format' });
    return;
  }

  const job = await getJob(parsed.data.jobId);
  if (!job) {
    res.status(404).json({ error: 'Job not found' });
    return;
  }
  if (!verifyOwnership(req, job.userId)) {
    res.status(403).json({ error: 'Not authorized' });
    return;
  }
  if (!EDITABLE_STATUSES.has(job.status)) {
    res.status(400).json({ error: 'Annotations can only be edited after Discovery completes' });
    return;
  }
  if (Buffer.byteLength(JSON.stringify(req.body), 'utf8') > MAX_DOCUMENT_BYTES) {
    res.status(413).json({ error: 'Annotation document is too large' });
    return;
  }

  const body = AnnotationBodySchema.safeParse(req.body);
  if (!body.success) {
    res.status(400).json({ error: 'Invalid annotation document', details: body.error.flatten() });
    return;
  }

  const annotations = await prisma.discoveryAnnotationDocument.upsert({
    where: { jobId: parsed.data.jobId },
    create: { jobId: parsed.data.jobId, document: body.data.document, revision: 1 },
    update: { document: body.data.document, revision: { increment: 1 } },
  });
  res.setHeader('Cache-Control', 'private, no-store');
  res.json({ revision: annotations.revision, document: annotations.document, updatedAt: annotations.updatedAt });
});

export const publicDiscoveryAnnotationsRouter = Router();

publicDiscoveryAnnotationsRouter.get('/:shareToken/annotations', annotationPollingLimiter, async (req: Request, res: Response) => {
  const params = ShareTokenParamSchema.safeParse(req.params);
  const query = AnnotationQuerySchema.safeParse(req.query);
  if (!params.success || !query.success) {
    res.status(404).json({ error: 'Not found' });
    return;
  }

  const share = await prisma.discoveryShare.findUnique({
    where: { shareToken: params.data.shareToken },
    select: { jobId: true, isActive: true },
  });
  if (!share || !share.isActive) {
    res.status(404).json({ error: 'Not found' });
    return;
  }

  const annotations = await prisma.discoveryAnnotationDocument.findUnique({
    where: { jobId: share.jobId },
  });
  const revision = annotations?.revision ?? 0;

  res.setHeader('X-Robots-Tag', 'noindex, nofollow');
  res.setHeader('Cache-Control', 'private, no-store');
  res.setHeader('Referrer-Policy', 'no-referrer');
  if (query.data.sinceRevision === revision) {
    res.status(204).end();
    return;
  }

  res.json({
    revision,
    document: annotations?.document ?? EMPTY_DOCUMENT,
    updatedAt: annotations?.updatedAt ?? null,
  });
});
