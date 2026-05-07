import { Router, Response } from 'express';
import { z } from 'zod';
import { prisma } from '../services/db.js';
import { requireInternalAuth, AuthenticatedRequest } from '../middleware/auth.js';

export const savesRouter = Router();

// All save endpoints carry per-user data — never CDN-cacheable.
savesRouter.use((_req, res, next) => {
  res.set('Cache-Control', 'private, no-store, no-cache, must-revalidate');
  next();
});

savesRouter.use(requireInternalAuth);

// ============================================
// Schemas
// ============================================

const SaveIdeaBody = z.object({
  ideaId: z.string().uuid(),
  notes: z.string().max(2000).nullish(),
});

const SavePainPointBody = z.object({
  painPointId: z.string().uuid(),
  notes: z.string().max(2000).nullish(),
});

const NotesPatch = z.object({
  notes: z.string().max(2000).nullable(),
});

const ListQuery = z.object({
  cursor: z.string().uuid().optional(),
  limit: z.coerce.number().int().min(1).max(100).default(50),
  hasNotes: z
    .enum(['true', 'false'])
    .optional()
    .transform((v) => (v === undefined ? undefined : v === 'true')),
});

const StatusQuery = z.object({
  ids: z
    .string()
    .min(1)
    .transform((s) => s.split(',').map((id) => id.trim()).filter(Boolean))
    .pipe(z.array(z.string().uuid()).max(50)),
});

// ============================================
// Selects — keep only the fields the saved-page card UI needs.
// Mirrors the IdeaPreview / PainPointPreview projections in
// catalogService.ts so frontend cards render identically.
// ============================================

// `parent` carries the top-level niche when the saved item lives in a
// sub-niche — surfaces "Parent · Leaf" breadcrumbs on the saved page.
const categoryWithParentSelect = {
  id: true,
  name: true,
  slug: true,
  parent: { select: { name: true, slug: true } },
} as const;

const savedIdeaSelect = {
  id: true,
  slug: true,
  solutionName: true,
  headline: true,
  shortDescription: true,
  description: true,
  format: true,
  projectType: true,
  marketFitScore: true,
  technicalFeasibility: true,
  seoScalabilityScore: true,
  sourceVerdict: true,
  sourceNiche: true,
  isFeatured: true,
  category: { select: categoryWithParentSelect },
} as const;

const savedPainPointSelect = {
  id: true,
  slug: true,
  title: true,
  description: true,
  mentionCount: true,
  severityScore: true,
  willingnessToPayScore: true,
  opportunityLevel: true,
  representativeQuotes: true,
  sourcePlatforms: true,
  themeId: true,
  solutionApproach: true,
  isFeatured: true,
  sourceNiche: true,
  category: { select: categoryWithParentSelect },
} as const;

// ============================================
// Ideas
// ============================================

savesRouter.post('/ideas', async (req: AuthenticatedRequest, res: Response) => {
  const parsed = SaveIdeaBody.safeParse(req.body);
  if (!parsed.success) {
    res.status(400).json({ error: 'Invalid body', details: parsed.error.flatten() });
    return;
  }
  const userId = req.user!.id;
  const { ideaId, notes } = parsed.data;

  // Confirm the idea exists before creating an orphan-prone row. The FK would
  // catch this too, but a friendlier 404 is worth the extra query.
  const idea = await prisma.catalogIdea.findUnique({
    where: { id: ideaId },
    select: { id: true },
  });
  if (!idea) {
    res.status(404).json({ error: 'Idea not found' });
    return;
  }

  // Idempotent: same (userId, ideaId) returns the existing row; never 409.
  const saved = await prisma.savedIdea.upsert({
    where: { userId_ideaId: { userId, ideaId } },
    create: { userId, ideaId, notes: notes ?? null },
    update: {}, // intentionally don't overwrite notes on duplicate save click
  });
  res.status(200).json(saved);
});

savesRouter.delete('/ideas/:ideaId', async (req: AuthenticatedRequest, res: Response) => {
  const userId = req.user!.id;
  const { ideaId } = req.params;
  if (!z.string().uuid().safeParse(ideaId).success) {
    res.status(400).json({ error: 'Invalid ideaId' });
    return;
  }
  const result = await prisma.savedIdea.deleteMany({
    where: { userId, ideaId },
  });
  // 204 whether or not the row existed — DELETE is idempotent.
  res.status(204).send();
  void result;
});

savesRouter.patch('/ideas/:ideaId', async (req: AuthenticatedRequest, res: Response) => {
  const userId = req.user!.id;
  const { ideaId } = req.params;
  if (!z.string().uuid().safeParse(ideaId).success) {
    res.status(400).json({ error: 'Invalid ideaId' });
    return;
  }
  const parsed = NotesPatch.safeParse(req.body);
  if (!parsed.success) {
    res.status(400).json({ error: 'Invalid body', details: parsed.error.flatten() });
    return;
  }
  const updated = await prisma.savedIdea.updateMany({
    where: { userId, ideaId },
    data: { notes: parsed.data.notes },
  });
  if (updated.count === 0) {
    res.status(404).json({ error: 'Saved idea not found' });
    return;
  }
  const row = await prisma.savedIdea.findUnique({
    where: { userId_ideaId: { userId, ideaId } },
  });
  res.status(200).json(row);
});

savesRouter.get('/ideas', async (req: AuthenticatedRequest, res: Response) => {
  const parsed = ListQuery.safeParse(req.query);
  if (!parsed.success) {
    res.status(400).json({ error: 'Invalid query', details: parsed.error.flatten() });
    return;
  }
  const userId = req.user!.id;
  const { cursor, limit, hasNotes } = parsed.data;

  const where: Record<string, unknown> = { userId };
  if (hasNotes === true) where.notes = { not: null };
  if (hasNotes === false) where.notes = null;

  const rows = await prisma.savedIdea.findMany({
    where,
    orderBy: { createdAt: 'desc' },
    take: limit + 1,
    ...(cursor ? { cursor: { id: cursor }, skip: 1 } : {}),
    include: { idea: { select: savedIdeaSelect } },
  });

  const hasMore = rows.length > limit;
  const items = hasMore ? rows.slice(0, limit) : rows;
  res.status(200).json({
    items,
    nextCursor: hasMore ? items[items.length - 1].id : null,
  });
});

savesRouter.get('/ideas/status', async (req: AuthenticatedRequest, res: Response) => {
  const parsed = StatusQuery.safeParse(req.query);
  if (!parsed.success) {
    res.status(400).json({ error: 'Invalid query', details: parsed.error.flatten() });
    return;
  }
  const userId = req.user!.id;
  const ids = parsed.data.ids;
  const rows = await prisma.savedIdea.findMany({
    where: { userId, ideaId: { in: ids } },
    select: { ideaId: true },
  });
  const status: Record<string, boolean> = {};
  for (const id of ids) status[id] = false;
  for (const r of rows) status[r.ideaId] = true;
  res.status(200).json(status);
});

// ============================================
// Pain points
// ============================================

savesRouter.post('/pain-points', async (req: AuthenticatedRequest, res: Response) => {
  const parsed = SavePainPointBody.safeParse(req.body);
  if (!parsed.success) {
    res.status(400).json({ error: 'Invalid body', details: parsed.error.flatten() });
    return;
  }
  const userId = req.user!.id;
  const { painPointId, notes } = parsed.data;

  const exists = await prisma.catalogPainPoint.findUnique({
    where: { id: painPointId },
    select: { id: true },
  });
  if (!exists) {
    res.status(404).json({ error: 'Pain point not found' });
    return;
  }

  const saved = await prisma.savedPainPoint.upsert({
    where: { userId_painPointId: { userId, painPointId } },
    create: { userId, painPointId, notes: notes ?? null },
    update: {},
  });
  res.status(200).json(saved);
});

savesRouter.delete('/pain-points/:painPointId', async (req: AuthenticatedRequest, res: Response) => {
  const userId = req.user!.id;
  const { painPointId } = req.params;
  if (!z.string().uuid().safeParse(painPointId).success) {
    res.status(400).json({ error: 'Invalid painPointId' });
    return;
  }
  await prisma.savedPainPoint.deleteMany({ where: { userId, painPointId } });
  res.status(204).send();
});

savesRouter.patch('/pain-points/:painPointId', async (req: AuthenticatedRequest, res: Response) => {
  const userId = req.user!.id;
  const { painPointId } = req.params;
  if (!z.string().uuid().safeParse(painPointId).success) {
    res.status(400).json({ error: 'Invalid painPointId' });
    return;
  }
  const parsed = NotesPatch.safeParse(req.body);
  if (!parsed.success) {
    res.status(400).json({ error: 'Invalid body', details: parsed.error.flatten() });
    return;
  }
  const updated = await prisma.savedPainPoint.updateMany({
    where: { userId, painPointId },
    data: { notes: parsed.data.notes },
  });
  if (updated.count === 0) {
    res.status(404).json({ error: 'Saved pain point not found' });
    return;
  }
  const row = await prisma.savedPainPoint.findUnique({
    where: { userId_painPointId: { userId, painPointId } },
  });
  res.status(200).json(row);
});

savesRouter.get('/pain-points', async (req: AuthenticatedRequest, res: Response) => {
  const parsed = ListQuery.safeParse(req.query);
  if (!parsed.success) {
    res.status(400).json({ error: 'Invalid query', details: parsed.error.flatten() });
    return;
  }
  const userId = req.user!.id;
  const { cursor, limit, hasNotes } = parsed.data;

  const where: Record<string, unknown> = { userId };
  if (hasNotes === true) where.notes = { not: null };
  if (hasNotes === false) where.notes = null;

  const rows = await prisma.savedPainPoint.findMany({
    where,
    orderBy: { createdAt: 'desc' },
    take: limit + 1,
    ...(cursor ? { cursor: { id: cursor }, skip: 1 } : {}),
    include: { painPoint: { select: savedPainPointSelect } },
  });

  const hasMore = rows.length > limit;
  const items = hasMore ? rows.slice(0, limit) : rows;
  res.status(200).json({
    items,
    nextCursor: hasMore ? items[items.length - 1].id : null,
  });
});

savesRouter.get('/pain-points/status', async (req: AuthenticatedRequest, res: Response) => {
  const parsed = StatusQuery.safeParse(req.query);
  if (!parsed.success) {
    res.status(400).json({ error: 'Invalid query', details: parsed.error.flatten() });
    return;
  }
  const userId = req.user!.id;
  const ids = parsed.data.ids;
  const rows = await prisma.savedPainPoint.findMany({
    where: { userId, painPointId: { in: ids } },
    select: { painPointId: true },
  });
  const status: Record<string, boolean> = {};
  for (const id of ids) status[id] = false;
  for (const r of rows) status[r.painPointId] = true;
  res.status(200).json(status);
});

// ============================================
// Counts — used by the (app) layout to badge the user-menu "Saved" row.
// ============================================

savesRouter.get('/counts', async (req: AuthenticatedRequest, res: Response) => {
  const userId = req.user!.id;
  const [ideas, painPoints] = await Promise.all([
    prisma.savedIdea.count({ where: { userId } }),
    prisma.savedPainPoint.count({ where: { userId } }),
  ]);
  res.status(200).json({ ideas, painPoints });
});
