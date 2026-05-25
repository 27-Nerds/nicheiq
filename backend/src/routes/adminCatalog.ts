import { Router, Response } from 'express';
import { z } from 'zod';
import { CONFIG } from '../config.js';
import { AuthenticatedRequest } from '../middleware/auth.js';
import {
  listCategories,
  createCategory,
  updateCategory,
  deleteCategory,
  listCachedItems,
  listShareOwners,
  ensureCachePopulated,
  publishIdea,
  publishPainPoint,
  updateCatalogIdea,
  updateCatalogPainPoint,
  depublishIdea,
  depublishPainPoint,
  invalidateCategoryLanding,
  resolveFreePreviewIdeaId,
  resolveFreePreviewPainId,
} from '../services/catalogService.js';
import {
  generateForCategory,
  generateForIdea,
  generateForPainPoint,
  FaqGenerationError,
} from '../services/faqGeneratorService.js';
import { categorizeBatch } from '../services/categorizationService.js';
import { enqueueCatalogPainPointsJob, enqueueCatalogIdeasJob } from '../services/queueService.js';
import {
  listCollectionsAdmin,
  getCollectionAdmin,
  createCollection,
  updateCollection,
  deleteCollection,
  addItemToCollection,
  removeItemFromCollection,
  reorderItems,
} from '../services/catalogCollectionService.js';
import { prisma } from '../services/db.js';
import { getRedis } from '../services/redis.js';
import {
  extractOrCreateResearchContext,
  hasMeaningfulResearchContext,
  MEANINGFUL_SELECT,
} from '../services/researchContextService.js';
import { JobStatus } from '@prisma/client';
import {
  FaqEntrySchema,
  FaqArraySchema,
  type FaqJsonMeta,
} from '../types/faq.js';

export const adminCatalogRouter = Router();

const redis = getRedis();

// ============================================
// Zod Schemas
// ============================================

const CreateCategorySchema = z.object({
  name: z.string().min(1).max(100),
  slug: z.string().min(1).max(120).regex(/^[a-z0-9-]+$/).optional(),
  description: z.string().max(500).optional(),
  parentId: z.string().uuid().optional(),
  sortOrder: z.number().int().min(0).max(1000).optional(),
});

// FaqEntrySchema (and the NO_HTML_RE regex) live in `../types/faq.ts` so the
// new /faq/save route and the legacy PATCH /categories/:id below can share
// validation. We import per-entry only here — the legacy PATCH path keeps its
// permissive bounds (0-15, no array-level dup or anchor checks). The new save
// route uses the stricter `FaqArraySchema` from the same module.
const NO_HTML_RE = /<[^>]*>/;

const UpdateCategorySchema = z.object({
  name: z.string().min(1).max(100).optional(),
  slug: z.string().min(1).max(120).regex(/^[a-z0-9-]+$/).optional(),
  description: z.string().max(500).nullable().optional(),
  parentId: z.string().uuid().nullable().optional(),
  superGroupId: z.string().uuid().nullable().optional(),
  sortOrder: z.number().int().min(0).max(1000).optional(),
  isActive: z.boolean().optional(),
  // Phase 2 SEO fields. longDescription rejects HTML to prevent stored XSS on
  // the public landing page; FAQ entries are individually validated above.
  seoTitle: z
    .string()
    .min(10)
    .max(160)
    .refine((s) => !NO_HTML_RE.test(s), { message: 'HTML not allowed' })
    .nullable()
    .optional(),
  seoDescription: z
    .string()
    .min(20)
    .max(320)
    .refine((s) => !NO_HTML_RE.test(s), { message: 'HTML not allowed' })
    .nullable()
    .optional(),
  longDescription: z
    .string()
    .min(50)
    .max(2000)
    .refine((s) => !NO_HTML_RE.test(s), { message: 'HTML not allowed' })
    .nullable()
    .optional(),
  faqJson: z.array(FaqEntrySchema).max(15).nullable().optional(),
  tags: z
    .array(z.string().min(1).max(40).regex(/^[a-zA-Z0-9 +&\-_/]+$/))
    .max(8)
    .optional(),
}).refine(d => Object.keys(d).length > 0, { message: 'At least one field required' });

const PublishIdeaSchema = z.object({
  categoryId: z.string().uuid(),
  sourceJobId: z.string().uuid(),
  itemIndex: z.number().int().min(-1).max(20),
});

const PublishPainPointSchema = z.object({
  categoryId: z.string().uuid(),
  sourceJobId: z.string().uuid(),
  itemIndex: z.number().int().min(0).max(30),
});

const UpdatePublishedItemSchema = z.object({
  categoryId: z.string().uuid().optional(),
  isFeatured: z.boolean().optional(),
  isFreePreview: z.boolean().optional(),
  isActive: z.boolean().optional(),
}).refine(d => Object.keys(d).length > 0, { message: 'At least one field required' });

const CategorizeBatchSchema = z.object({
  itemType: z.enum(['idea', 'painPoint']),
  items: z.array(z.object({
    id: z.string().max(100),
    name: z.string().max(300),
    description: z.string().max(500),
    niche: z.string().max(2000),
  })).min(1).max(200),
});

const ListItemsSchema = z.object({
  type: z.enum(['ideas', 'painPoints']),
  userId: z.string().uuid().optional(),
  isPublished: z.enum(['true', 'false']).optional(),
  page: z.coerce.number().int().min(1).default(1),
  limit: z.coerce.number().int().min(1).max(100).default(20),
});

// ============================================
// Rate limit helper for categorize (atomic per-item)
// ============================================

const RATE_LIMIT_LUA = `
local current = tonumber(redis.call('GET', KEYS[1]) or '0')
if current + tonumber(ARGV[1]) > tonumber(ARGV[2]) then
  return -1
end
redis.call('INCRBY', KEYS[1], ARGV[1])
redis.call('EXPIRE', KEYS[1], 3600)
return current + tonumber(ARGV[1])
`;

async function checkCategorizeRateLimit(userId: string, itemCount: number): Promise<{ allowed: boolean; retryAfter?: number }> {
  const key = `nicheiq:categorize:items:${userId}:hourly`;
  const limit = CONFIG.categorizeItemRateHourly;

  try {
    const result = await redis.eval(RATE_LIMIT_LUA, 1, key, String(itemCount), String(limit)) as number;
    if (result === -1) {
      const ttl = await redis.ttl(key);
      return { allowed: false, retryAfter: ttl > 0 ? ttl : 3600 };
    }
    return { allowed: true };
  } catch {
    return { allowed: true }; // Fail open
  }
}

// ============================================
// Category routes
// ============================================

adminCatalogRouter.get('/categories', async (_req: AuthenticatedRequest, res: Response) => {
  try {
    const [categories, activeJobs] = await Promise.all([
      listCategories(),
      prisma.job.findMany({
        where: {
          catalogCategoryId: { not: null },
          jobMode: { in: ['catalog_pain_points', 'catalog_ideas'] },
          status: { in: [JobStatus.PENDING, JobStatus.QUEUED, JobStatus.RUNNING] },
        },
        select: { id: true, catalogCategoryId: true, jobMode: true, status: true },
      }),
    ]);

    // Build a lookup: categoryId → active jobs
    const jobsByCategoryId = new Map<string, typeof activeJobs>();
    for (const job of activeJobs) {
      if (!job.catalogCategoryId) continue;
      const existing = jobsByCategoryId.get(job.catalogCategoryId) || [];
      existing.push(job);
      jobsByCategoryId.set(job.catalogCategoryId, existing);
    }

    const relevantCategoryIds = new Set<string>();
    for (const parent of categories as any[]) {
      relevantCategoryIds.add(parent.id);
      for (const child of parent.children || []) {
        relevantCategoryIds.add(child.id);
      }
    }

    // Step 1: resolve which CatalogResearchContext rows are placeholders.
    // Each CRC backs many pain points via shared sourceJobId, so projecting
    // the meaningful-fields JSON once per CRC (rather than once per pain
    // point as the previous version did) is the actual win here.
    const contexts = relevantCategoryIds.size > 0
      ? await prisma.catalogResearchContext.findMany({
        select: { sourceJobId: true, ...MEANINGFUL_SELECT },
      })
      : [];
    const placeholderJobIds = contexts
      .filter((c) => !hasMeaningfulResearchContext(c))
      .map((c) => c.sourceJobId);

    // Step 2: count legacy pain points per category in SQL. No row JSON
    // leaves the database — Postgres returns one integer per category.
    const legacyCounts = placeholderJobIds.length > 0
      ? await prisma.catalogPainPoint.groupBy({
        by: ['categoryId'],
        where: {
          isActive: true,
          categoryId: { in: [...relevantCategoryIds] },
          sourceJobId: { in: placeholderJobIds },
        },
        _count: { _all: true },
      })
      : [];

    const legacyPainPointsByCategoryId = new Map<string, number>(
      legacyCounts.map((c) => [c.categoryId, c._count._all]),
    );

    // Attach activeJobs and legacy pain-point counts to child categories. Parent
    // counts include direct parent-category pain points plus all child counts,
    // because admin publish/change-category flows can assign pain points to either.
    const enriched = categories.map((parent: any) => {
      const children = (parent.children || []).map((child: any) => ({
        ...child,
        activeJobs: jobsByCategoryId.get(child.id) || [],
        legacyPainPoints: legacyPainPointsByCategoryId.get(child.id) || 0,
      }));
      const directLegacyPainPoints = legacyPainPointsByCategoryId.get(parent.id) || 0;
      const childLegacyPainPoints = children.reduce(
        (sum: number, child: any) => sum + (child.legacyPainPoints || 0),
        0,
      );
      return {
        ...parent,
        legacyPainPoints: directLegacyPainPoints + childLegacyPainPoints,
        children,
      };
    });

    res.json({ categories: enriched });
  } catch (error) {
    console.error('Failed to list categories:', error);
    res.status(500).json({ error: 'Failed to list categories' });
  }
});

adminCatalogRouter.post('/categories', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const parsed = CreateCategorySchema.safeParse(req.body);
    if (!parsed.success) {
      res.status(400).json({ error: 'Validation error', details: parsed.error.errors });
      return;
    }
    const category = await createCategory(parsed.data);
    res.status(201).json(category);
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Failed to create category';
    res.status(400).json({ error: message });
  }
});

adminCatalogRouter.patch('/categories/:id', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const parsed = UpdateCategorySchema.safeParse(req.body);
    if (!parsed.success) {
      res.status(400).json({ error: 'Validation error', details: parsed.error.errors });
      return;
    }
    const category = await updateCategory(req.params.id, parsed.data);
    res.json(category);
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Failed to update category';
    res.status(400).json({ error: message });
  }
});

adminCatalogRouter.delete('/categories/:id', async (req: AuthenticatedRequest, res: Response) => {
  try {
    await deleteCategory(req.params.id);
    res.json({ success: true });
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Failed to delete category';
    res.status(400).json({ error: message });
  }
});

// ============================================
// Super-group routes
// ============================================

adminCatalogRouter.get('/super-groups', async (_req: AuthenticatedRequest, res: Response) => {
  try {
    const superGroups = await prisma.catalogSuperGroup.findMany({
      where: { isActive: true },
      orderBy: { sortOrder: 'asc' },
      select: { id: true, name: true, slug: true, sortOrder: true },
    });
    res.json({ superGroups });
  } catch (error) {
    console.error('Failed to list super-groups:', error);
    res.status(500).json({ error: 'Failed to list super-groups' });
  }
});

// ============================================
// Curation source routes
// ============================================

adminCatalogRouter.get('/items', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const parsed = ListItemsSchema.safeParse(req.query);
    if (!parsed.success) {
      res.status(400).json({ error: 'Validation error', details: parsed.error.errors });
      return;
    }
    const { type, userId, isPublished, page, limit } = parsed.data;

    // Lazy populate cache for any active shares missing cache entries
    await ensureCachePopulated();

    const result = await listCachedItems({
      type,
      userId,
      isPublished: isPublished === 'true' ? true : isPublished === 'false' ? false : undefined,
      page,
      limit,
    });
    res.json(result);
  } catch (error) {
    console.error('Failed to list cached items:', error);
    res.status(500).json({ error: 'Failed to list items' });
  }
});

adminCatalogRouter.get('/share-owners', async (_req: AuthenticatedRequest, res: Response) => {
  try {
    const owners = await listShareOwners();
    res.json({ owners });
  } catch (error) {
    console.error('Failed to list share owners:', error);
    res.status(500).json({ error: 'Failed to list share owners' });
  }
});

// ============================================
// LLM categorization
// ============================================

adminCatalogRouter.post('/categorize', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const parsed = CategorizeBatchSchema.safeParse(req.body);
    if (!parsed.success) {
      res.status(400).json({ error: 'Validation error', details: parsed.error.errors });
      return;
    }

    // Rate limit (atomic per-item)
    const rateResult = await checkCategorizeRateLimit(req.user!.id, parsed.data.items.length);
    if (!rateResult.allowed) {
      res.status(429).json({ error: 'Rate limit exceeded', retryAfter: rateResult.retryAfter });
      return;
    }

    const result = await categorizeBatch(parsed.data.items, parsed.data.itemType);
    res.json(result);
  } catch (error) {
    console.error('Categorization failed:', error);
    res.status(500).json({ error: 'Categorization failed' });
  }
});

// ============================================
// Publishing routes
// ============================================

adminCatalogRouter.post('/ideas', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const parsed = PublishIdeaSchema.safeParse(req.body);
    if (!parsed.success) {
      res.status(400).json({ error: 'Validation error', details: parsed.error.errors });
      return;
    }
    const idea = await publishIdea({
      ...parsed.data,
      publishedById: req.user!.id,
    });
    res.status(201).json(idea);
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Failed to publish idea';
    const status = message.includes('already been published') ? 409 : 400;
    res.status(status).json({ error: message });
  }
});

adminCatalogRouter.patch('/ideas/:id', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const parsed = UpdatePublishedItemSchema.safeParse(req.body);
    if (!parsed.success) {
      res.status(400).json({ error: 'Validation error', details: parsed.error.errors });
      return;
    }
    const idea = await updateCatalogIdea(req.params.id, parsed.data);
    res.json(idea);
  } catch (error) {
    console.error('Failed to update idea:', error);
    res.status(400).json({ error: 'Failed to update idea' });
  }
});

adminCatalogRouter.delete('/ideas/:id', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const result = await depublishIdea(req.params.id);
    if (!result) {
      res.status(404).json({ error: 'Published idea not found' });
      return;
    }
    console.log(`[AUDIT] Admin ${req.user!.id} depublished idea ${req.params.id} (${result.solutionName})`);
    res.json({ success: true });
  } catch (error) {
    console.error('Failed to depublish idea:', error);
    res.status(500).json({ error: 'Failed to depublish idea' });
  }
});

adminCatalogRouter.post('/pain-points', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const parsed = PublishPainPointSchema.safeParse(req.body);
    if (!parsed.success) {
      res.status(400).json({ error: 'Validation error', details: parsed.error.errors });
      return;
    }
    const pp = await publishPainPoint({
      ...parsed.data,
      publishedById: req.user!.id,
    });
    res.status(201).json(pp);
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Failed to publish pain point';
    const status = message.includes('already been published') ? 409 : 400;
    res.status(status).json({ error: message });
  }
});

adminCatalogRouter.patch('/pain-points/:id', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const parsed = UpdatePublishedItemSchema.safeParse(req.body);
    if (!parsed.success) {
      res.status(400).json({ error: 'Validation error', details: parsed.error.errors });
      return;
    }
    const pp = await updateCatalogPainPoint(req.params.id, parsed.data);
    res.json(pp);
  } catch (error) {
    console.error('Failed to update pain point:', error);
    res.status(400).json({ error: 'Failed to update pain point' });
  }
});

adminCatalogRouter.delete('/pain-points/:id', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const result = await depublishPainPoint(req.params.id);
    if (!result) {
      res.status(404).json({ error: 'Published pain point not found' });
      return;
    }
    console.log(`[AUDIT] Admin ${req.user!.id} depublished pain point ${req.params.id} (${result.title})`);
    res.json({ success: true });
  } catch (error) {
    console.error('Failed to depublish pain point:', error);
    res.status(500).json({ error: 'Failed to depublish pain point' });
  }
});

// ============================================
// Catalog Content Generation
// ============================================

const GenerateIdeasBodySchema = z.object({
  painPointIds: z.array(z.string().uuid()).min(1).max(30),
});

/**
 * POST /categories/:id/generate-pain-points
 * Triggers pain point generation for a category via the Python pipeline.
 */
adminCatalogRouter.post('/categories/:id/generate-pain-points', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const categoryId = req.params.id;

    // Fetch category (with parent for context)
    const category = await prisma.catalogCategory.findUnique({
      where: { id: categoryId },
      include: { parent: { select: { name: true } } },
    });

    if (!category) {
      res.status(404).json({ error: 'Category not found' });
      return;
    }

    const categoryDesc = category.description || category.name;

    // Fast-path duplicate check
    const existingJob = await prisma.job.findFirst({
      where: {
        catalogCategoryId: categoryId,
        jobMode: 'catalog_pain_points',
        status: { in: [JobStatus.QUEUED, JobStatus.PENDING, JobStatus.RUNNING] },
      },
      select: { id: true },
    });
    if (existingJob) {
      res.status(409).json({
        error: 'A pain point generation job is already active for this category',
        jobId: existingJob.id,
      });
      return;
    }

    // Create a Job record to track this generation task
    let job;
    try {
      job = await prisma.job.create({
        data: {
          userId: req.user!.id,
          niche: categoryDesc,
          status: JobStatus.QUEUED,
          jobMode: 'catalog_pain_points',
          catalogCategoryId: categoryId,
          selectedSolutions: [],
        },
      });
    } catch (e: any) {
      if (e.code === 'P2002') {
        const existing = await prisma.job.findFirst({
          where: {
            catalogCategoryId: categoryId,
            jobMode: 'catalog_pain_points',
            status: { in: [JobStatus.QUEUED, JobStatus.PENDING, JobStatus.RUNNING] },
          },
          select: { id: true },
        });
        res.status(409).json({
          error: 'A pain point generation job is already active for this category',
          jobId: existing?.id,
        });
        return;
      }
      throw e;
    }

    // Enqueue the task
    await enqueueCatalogPainPointsJob(job.id, categoryId, category.name, categoryDesc, category.parent?.name || '');

    res.json({ jobId: job.id });
  } catch (error) {
    console.error('Failed to trigger pain point generation:', error);
    res.status(500).json({ error: 'Failed to trigger generation' });
  }
});

/**
 * POST /categories/:id/generate-ideas
 * Triggers idea generation from selected pain points for a category.
 */
adminCatalogRouter.post('/categories/:id/generate-ideas', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const categoryId = req.params.id;

    const parsed = GenerateIdeasBodySchema.safeParse(req.body);
    if (!parsed.success) {
      res.status(400).json({ error: 'Validation error', details: parsed.error.errors });
      return;
    }

    // Fetch selected pain points (validate they belong to this category)
    const painPoints = await prisma.catalogPainPoint.findMany({
      where: {
        id: { in: parsed.data.painPointIds },
        categoryId,
        isActive: true,
      },
    });

    if (painPoints.length === 0) {
      res.status(400).json({ error: 'No valid pain points found for this category' });
      return;
    }

    // Fetch category for niche description
    const category = await prisma.catalogCategory.findUnique({
      where: { id: categoryId },
      include: { parent: { select: { name: true } } },
    });

    if (!category) {
      res.status(404).json({ error: 'Category not found' });
      return;
    }

    const niche = category.description || category.name;

    // Fast-path duplicate check
    const existingJob = await prisma.job.findFirst({
      where: {
        catalogCategoryId: categoryId,
        jobMode: 'catalog_ideas',
        status: { in: [JobStatus.QUEUED, JobStatus.PENDING, JobStatus.RUNNING] },
      },
      select: { id: true },
    });
    if (existingJob) {
      res.status(409).json({
        error: 'An idea generation job is already active for this category',
        jobId: existingJob.id,
      });
      return;
    }

    // Phase 5.4 — pick the parent sourceJobId so generated ideas FK into the
    // most-recent pain-points-job's CatalogResearchContext. Group selected
    // pain points by sourceJobId, take the max effective timestamp per group
    // (sourceGeneratedAt ?? updatedAt ?? createdAt — sourceGeneratedAt drives
    // lineage, updatedAt catches merge-bumped rows, createdAt is the fallback
    // for legacy rows). Pick the group with the latest timestamp.
    const groups = new Map<string, number>();
    for (const pp of painPoints) {
      if (!pp.sourceJobId) continue;
      const ts = (pp.sourceGeneratedAt ?? pp.updatedAt ?? pp.createdAt).getTime();
      const existing = groups.get(pp.sourceJobId);
      if (existing == null || ts > existing) {
        groups.set(pp.sourceJobId, ts);
      }
    }
    if (groups.size === 0) {
      res.status(400).json({ error: 'Selected pain points have no valid sourceJobId' });
      return;
    }
    const parentSourceJobId = [...groups.entries()].sort((a, b) => b[1] - a[1])[0][0];
    if (groups.size > 1) {
      console.warn(
        `[adminCatalog] generate-ideas: pain points span ${groups.size} sourceJobIds; using latest=${parentSourceJobId}`,
      );
    }

    // Meaningfulness gate. Runs BEFORE job.create so a legacy parent context
    // never leaves an orphan QUEUED job that blocks future retries via the
    // duplicate-active-job guard above. `forceRefreshPlaceholders: true`
    // matches the symmetric worker callback at workers.ts:1075 — gives a
    // race-safe second extraction attempt for rows whose report asset only
    // just landed on disk.
    const parentContext = await extractOrCreateResearchContext(parentSourceJobId, {
      forceRefreshPlaceholders: true,
      sourceKind: 'catalog',
    });
    if (!hasMeaningfulResearchContext(parentContext)) {
      res.status(409).json({
        error:
          'Selected pain points come from a legacy research run with no renderable data. Re-run pain-point research for this category to refresh before generating ideas.',
        action: 'rerun-pain-points',
        categoryId,
      });
      return;
    }

    // Create a Job record
    let job;
    try {
      job = await prisma.job.create({
        data: {
          userId: req.user!.id,
          niche,
          status: JobStatus.QUEUED,
          jobMode: 'catalog_ideas',
          catalogCategoryId: categoryId,
          selectedSolutions: [],
        },
      });
    } catch (e: any) {
      if (e.code === 'P2002') {
        const existing = await prisma.job.findFirst({
          where: {
            catalogCategoryId: categoryId,
            jobMode: 'catalog_ideas',
            status: { in: [JobStatus.QUEUED, JobStatus.PENDING, JobStatus.RUNNING] },
          },
          select: { id: true },
        });
        res.status(409).json({
          error: 'An idea generation job is already active for this category',
          jobId: existing?.id,
        });
        return;
      }
      throw e;
    }

    // Serialize pain point data for the worker (all fields needed to reconstruct PainPoint objects)
    const painPointData = painPoints.map(pp => ({
      title: pp.title,
      description: pp.description,
      mentionCount: pp.mentionCount,
      severityScore: pp.severityScore,
      willingnessToPayScore: pp.willingnessToPayScore,
      opportunityLevel: pp.opportunityLevel,
      representativeQuotes: pp.representativeQuotes,
      sourcePlatforms: pp.sourcePlatforms,
      categories: pp.categories,
      affectedSegments: pp.affectedSegments,
    }));

    // Query existing ideas for this category to avoid regenerating duplicates
    const existingIdeas = await prisma.catalogIdea.findMany({
      where: { categoryId },
      select: { solutionName: true, description: true },
    });
    const existingIdeasMapped = existingIdeas.map(i => ({
      name: i.solutionName,
      description: i.description || '',
    }));

    await enqueueCatalogIdeasJob(
      job.id,
      categoryId,
      painPointData,
      niche,
      category.parent?.name || '',
      existingIdeasMapped,
      parentSourceJobId,
      parentContext.contentCategorization ?? undefined,
    );

    res.json({ jobId: job.id });
  } catch (error) {
    console.error('Failed to trigger idea generation:', error);
    res.status(500).json({ error: 'Failed to trigger generation' });
  }
});

/**
 * GET /categories/:id/pain-points
 * List pain points for a category (used by the idea generation modal).
 */
// ============================================
// Reddit Thread Cache (Admin)
// ============================================

const ListRedditThreadsSchema = z.object({
  subreddit: z.string().max(50).optional(),
  search: z.string().max(200).optional(),
  page: z.coerce.number().int().min(1).default(1),
  limit: z.coerce.number().int().min(1).max(100).default(20),
  sort: z.enum(['score', 'fetchedAt', 'redditCreatedAt', 'numComments']).default('fetchedAt'),
  sortDir: z.enum(['asc', 'desc']).default('desc'),
});

adminCatalogRouter.get('/reddit-threads', async (_req: AuthenticatedRequest, res: Response) => {
  try {
    const parsed = ListRedditThreadsSchema.safeParse(_req.query);
    if (!parsed.success) {
      res.status(400).json({ error: 'Validation error', details: parsed.error.errors });
      return;
    }

    const { subreddit, search, page, limit, sort, sortDir } = parsed.data;

    const where: any = {};
    if (subreddit) {
      where.subreddit = subreddit;
    }
    if (search) {
      where.title = { contains: search, mode: 'insensitive' };
    }

    const [threads, total] = await Promise.all([
      prisma.redditThread.findMany({
        where,
        orderBy: { [sort]: sortDir },
        skip: (page - 1) * limit,
        take: limit,
        select: {
          id: true,
          postId: true,
          url: true,
          title: true,
          selftext: true,
          author: true,
          subreddit: true,
          score: true,
          numComments: true,
          redditCreatedAt: true,
          fetchedAt: true,
        },
      }),
      prisma.redditThread.count({ where }),
    ]);

    res.json({
      threads,
      total,
      page,
      totalPages: Math.ceil(total / limit),
    });
  } catch (error) {
    console.error('Failed to list reddit threads:', error);
    res.status(500).json({ error: 'Failed to list reddit threads' });
  }
});

adminCatalogRouter.get('/reddit-threads/stats', async (_req: AuthenticatedRequest, res: Response) => {
  try {
    const [totalThreads, commentStats, subredditStats, fetchDates] = await Promise.all([
      prisma.redditThread.count(),
      prisma.redditThread.aggregate({
        _sum: { numComments: true },
      }),
      prisma.redditThread.groupBy({
        by: ['subreddit'],
        _count: { subreddit: true },
        orderBy: { _count: { subreddit: 'desc' } },
      }),
      prisma.redditThread.aggregate({
        _max: { fetchedAt: true },
        _min: { fetchedAt: true },
      }),
    ]);

    res.json({
      totalThreads,
      totalComments: commentStats._sum.numComments || 0,
      uniqueSubreddits: subredditStats.length,
      bySubreddit: subredditStats.map((s: { subreddit: string; _count: { subreddit: number } }) => ({ name: s.subreddit, count: s._count.subreddit })),
      latestFetch: fetchDates._max.fetchedAt,
      oldestFetch: fetchDates._min.fetchedAt,
    });
  } catch (error) {
    console.error('Failed to get reddit thread stats:', error);
    res.status(500).json({ error: 'Failed to get stats' });
  }
});

adminCatalogRouter.delete('/reddit-threads/cleanup', async (_req: AuthenticatedRequest, res: Response) => {
  try {
    const cutoff = new Date(Date.now() - 60 * 24 * 60 * 60 * 1000); // 60 days
    const result = await prisma.redditThread.deleteMany({
      where: { fetchedAt: { lt: cutoff } },
    });
    res.json({ deletedCount: result.count });
  } catch (error) {
    console.error('Failed to cleanup reddit threads:', error);
    res.status(500).json({ error: 'Failed to cleanup' });
  }
});

// ============================================
// Category pain points
// ============================================

adminCatalogRouter.get('/categories/:id/pain-points', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const rows = await prisma.catalogPainPoint.findMany({
      where: { categoryId: req.params.id, isActive: true },
      orderBy: { severityScore: 'desc' },
      include: { researchContext: { select: MEANINGFUL_SELECT } },
    });
    const painPoints = rows.map(({ researchContext, ...pp }) => ({
      ...pp,
      isLegacy: !hasMeaningfulResearchContext(researchContext),
    }));
    // The free-preview pain for this category (null when none is flagged — fully gated).
    const effectiveFreePreviewPainPointId = await resolveFreePreviewPainId(req.params.id);
    res.json({ painPoints, effectiveFreePreviewPainPointId });
  } catch (error) {
    console.error('Failed to list pain points:', error);
    res.status(500).json({ error: 'Failed to list pain points' });
  }
});

adminCatalogRouter.get('/categories/:id/ideas', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const ideas = await prisma.catalogIdea.findMany({
      where: { categoryId: req.params.id, isActive: true },
      orderBy: { createdAt: 'desc' },
    });
    const effectiveFreePreviewIdeaId = await resolveFreePreviewIdeaId(req.params.id);
    res.json({ ideas, effectiveFreePreviewIdeaId });
  } catch (error) {
    console.error('Failed to list ideas:', error);
    res.status(500).json({ error: 'Failed to list ideas' });
  }
});

// ============================================
// Phase 5.4 — Featured Collections admin CRUD
// ============================================

const SlugRegex = /^[a-z0-9-]+$/;
const CollectionCreateSchema = z.object({
  slug: z.string().min(1).max(120).regex(SlugRegex),
  name: z.string().min(1).max(120),
  description: z.string().max(2000).nullable().optional(),
  tagline: z.string().max(160).nullable().optional(),
  colorAccent: z.string().max(20).nullable().optional(),
  sortOrder: z.number().int().min(0).optional(),
  isActive: z.boolean().optional(),
});
const CollectionUpdateSchema = CollectionCreateSchema.partial();
const ItemAddSchema = z
  .object({
    ideaId: z.string().uuid().nullable().optional(),
    painPointId: z.string().uuid().nullable().optional(),
    position: z.number().int().min(0).optional(),
  })
  .refine(
    (a) => Boolean(a.ideaId) !== Boolean(a.painPointId),
    'Exactly one of ideaId or painPointId must be provided',
  );
const ReorderSchema = z.object({
  orderedIds: z.array(z.string().uuid()).min(1),
});

adminCatalogRouter.get('/collections', async (_req, res: Response) => {
  try {
    const collections = await listCollectionsAdmin();
    res.json({ collections });
  } catch (err) {
    console.error('Failed to list collections:', err);
    res.status(500).json({ error: 'Failed to list collections' });
  }
});

adminCatalogRouter.get('/collections/:id', async (req, res: Response) => {
  try {
    const collection = await getCollectionAdmin(req.params.id);
    if (!collection) {
      res.status(404).json({ error: 'Collection not found' });
      return;
    }
    res.json({ collection });
  } catch (err) {
    console.error('Failed to fetch collection:', err);
    res.status(500).json({ error: 'Failed to fetch collection' });
  }
});

adminCatalogRouter.post('/collections', async (req, res: Response) => {
  try {
    const parse = CollectionCreateSchema.safeParse(req.body);
    if (!parse.success) {
      res.status(400).json({ error: 'Validation error', details: parse.error.flatten() });
      return;
    }
    const created = await createCollection(parse.data);
    res.status(201).json({ collection: created });
  } catch (err) {
    console.error('Failed to create collection:', err);
    res.status(500).json({ error: 'Failed to create collection' });
  }
});

adminCatalogRouter.patch('/collections/:id', async (req, res: Response) => {
  try {
    const parse = CollectionUpdateSchema.safeParse(req.body);
    if (!parse.success) {
      res.status(400).json({ error: 'Validation error', details: parse.error.flatten() });
      return;
    }
    const updated = await updateCollection(req.params.id, parse.data);
    res.json({ collection: updated });
  } catch (err) {
    console.error('Failed to update collection:', err);
    res.status(500).json({ error: 'Failed to update collection' });
  }
});

adminCatalogRouter.delete('/collections/:id', async (req, res: Response) => {
  try {
    await deleteCollection(req.params.id);
    res.status(204).end();
  } catch (err) {
    console.error('Failed to delete collection:', err);
    res.status(500).json({ error: 'Failed to delete collection' });
  }
});

adminCatalogRouter.post('/collections/:id/items', async (req, res: Response) => {
  try {
    const parse = ItemAddSchema.safeParse(req.body);
    if (!parse.success) {
      res.status(400).json({ error: 'Validation error', details: parse.error.flatten() });
      return;
    }
    const created = await addItemToCollection({
      collectionId: req.params.id,
      ideaId: parse.data.ideaId ?? null,
      painPointId: parse.data.painPointId ?? null,
      position: parse.data.position,
    });
    res.status(201).json({ item: created });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Failed to add item';
    console.error('Failed to add collection item:', err);
    res.status(400).json({ error: message });
  }
});

adminCatalogRouter.delete('/collections/:id/items/:itemId', async (req, res: Response) => {
  try {
    await removeItemFromCollection(req.params.itemId);
    res.status(204).end();
  } catch (err) {
    console.error('Failed to remove collection item:', err);
    res.status(500).json({ error: 'Failed to remove item' });
  }
});

adminCatalogRouter.post('/collections/:id/reorder', async (req, res: Response) => {
  try {
    const parse = ReorderSchema.safeParse(req.body);
    if (!parse.success) {
      res.status(400).json({ error: 'Validation error', details: parse.error.flatten() });
      return;
    }
    await reorderItems(req.params.id, parse.data.orderedIds);
    res.status(204).end();
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Failed to reorder';
    console.error('Failed to reorder collection:', err);
    res.status(400).json({ error: message });
  }
});

// ============================================
// FAQ generation + save (admin-triggered LLM Q&A)
// See plans/pure-giggling-beacon.md Phase B for the full design.
// ============================================

const FaqEntityTypeSchema = z.enum(['category', 'idea', 'pain-point']);

const FaqGenerateBodySchema = z.object({
  entityType: FaqEntityTypeSchema,
  entityId: z.string().uuid(),
});

const FaqSaveBodySchema = z.object({
  entityType: FaqEntityTypeSchema,
  entityId: z.string().uuid(),
  // Validated again per-entity-type below with FaqArraySchema(anchorTerms);
  // here we just check the per-entry shape and array bounds.
  faqs: z.array(FaqEntrySchema).min(2).max(10),
  source: z.enum(['generated', 'manual']),
  model: z.string().optional(),
  generatedAt: z.string().datetime().optional(),
  tokensUsed: z.number().int().nonnegative().optional(),
});

// Per-admin per-hour rate limits — one Redis key per (action, user). Limits
// configured via FAQ_GENERATE_RATE_HOURLY / FAQ_SAVE_RATE_HOURLY env vars.
async function checkFaqRateLimit(
  action: 'generate' | 'save',
  userId: string,
): Promise<{ allowed: boolean; retryAfter?: number }> {
  const key = `nicheiq:faq:${action}:${userId}:hourly`;
  const limit =
    action === 'generate' ? CONFIG.faqGenerateRateHourly : CONFIG.faqSaveRateHourly;
  try {
    const result = (await redis.eval(RATE_LIMIT_LUA, 1, key, '1', String(limit))) as number;
    if (result === -1) {
      const ttl = await redis.ttl(key);
      return { allowed: false, retryAfter: ttl > 0 ? ttl : 3600 };
    }
    return { allowed: true };
  } catch {
    return { allowed: true }; // fail open — same posture as categorize limiter
  }
}

// ----- GET /ideas/:id (shaped DTO for FAQ mini-editor) -----
adminCatalogRouter.get('/ideas/:id', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const idea = await prisma.catalogIdea.findUnique({
      where: { id: req.params.id },
      select: {
        id: true,
        slug: true,
        solutionName: true,
        headline: true,
        faqJson: true,
        faqJsonMeta: true,
        updatedAt: true,
        category: {
          select: {
            id: true,
            name: true,
            parent: { select: { name: true } },
          },
        },
      },
    });
    if (!idea) {
      res.status(404).json({ error: 'Idea not found' });
      return;
    }
    res.json(idea);
  } catch (err) {
    console.error('Failed to fetch idea:', err);
    res.status(500).json({ error: 'Failed to fetch idea' });
  }
});

// ----- GET /pain-points/:id (shaped DTO for FAQ mini-editor) -----
adminCatalogRouter.get('/pain-points/:id', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const painPoint = await prisma.catalogPainPoint.findUnique({
      where: { id: req.params.id },
      select: {
        id: true,
        slug: true,
        title: true,
        faqJson: true,
        faqJsonMeta: true,
        updatedAt: true,
        category: {
          select: {
            id: true,
            name: true,
            parent: { select: { name: true } },
          },
        },
      },
    });
    if (!painPoint) {
      res.status(404).json({ error: 'Pain point not found' });
      return;
    }
    res.json(painPoint);
  } catch (err) {
    console.error('Failed to fetch pain point:', err);
    res.status(500).json({ error: 'Failed to fetch pain point' });
  }
});

// ----- POST /faq/generate (LLM call, no DB write) -----
adminCatalogRouter.post('/faq/generate', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const parsed = FaqGenerateBodySchema.safeParse(req.body);
    if (!parsed.success) {
      res.status(400).json({ error: 'Validation error', details: parsed.error.errors });
      return;
    }

    const userId = req.user?.id;
    if (!userId) {
      res.status(401).json({ error: 'Authenticated user required' });
      return;
    }

    const limit = await checkFaqRateLimit('generate', userId);
    if (!limit.allowed) {
      res.set('Retry-After', String(limit.retryAfter ?? 3600));
      res.status(429).json({
        error: `Rate limit reached. Try again in ${Math.ceil((limit.retryAfter ?? 3600) / 60)} minutes.`,
      });
      return;
    }

    const { entityType, entityId } = parsed.data;
    const result =
      entityType === 'category'
        ? await generateForCategory(entityId)
        : entityType === 'idea'
          ? await generateForIdea(entityId)
          : await generateForPainPoint(entityId);

    res.json(result);
  } catch (err) {
    if (err instanceof FaqGenerationError) {
      res.status(422).json({
        error: err.message,
        rawOutput: err.rawOutput,
      });
      return;
    }
    console.error('FAQ generate failed:', err);
    const message = err instanceof Error ? err.message : 'FAQ generation failed';
    res.status(500).json({ error: message });
  }
});

// ----- POST /faq/save (persist + bust cache) -----
adminCatalogRouter.post('/faq/save', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const parsed = FaqSaveBodySchema.safeParse(req.body);
    if (!parsed.success) {
      res.status(400).json({ error: 'Validation error', details: parsed.error.errors });
      return;
    }

    const userId = req.user?.id;
    if (!userId) {
      res.status(401).json({ error: 'Authenticated user required' });
      return;
    }

    const limit = await checkFaqRateLimit('save', userId);
    if (!limit.allowed) {
      res.set('Retry-After', String(limit.retryAfter ?? 3600));
      res.status(429).json({
        error: `Rate limit reached. Try again in ${Math.ceil((limit.retryAfter ?? 3600) / 60)} minutes.`,
      });
      return;
    }

    const { entityType, entityId, faqs, source, model, generatedAt, tokensUsed } = parsed.data;

    // Resolve the anchor term (entity name) for FaqArraySchema validation.
    // For idea pages, anchor on category.name (NOT solution_name codename).
    let anchorTerm: string;
    let parentCategoryIdForCacheBust: string;

    if (entityType === 'category') {
      const cat = await prisma.catalogCategory.findUnique({
        where: { id: entityId },
        select: { id: true, name: true },
      });
      if (!cat) {
        res.status(404).json({ error: 'Category not found' });
        return;
      }
      anchorTerm = cat.name;
      parentCategoryIdForCacheBust = cat.id;
    } else if (entityType === 'idea') {
      const idea = await prisma.catalogIdea.findUnique({
        where: { id: entityId },
        select: { categoryId: true, category: { select: { name: true } } },
      });
      if (!idea) {
        res.status(404).json({ error: 'Idea not found' });
        return;
      }
      anchorTerm = idea.category.name; // niche, NOT solution_name
      parentCategoryIdForCacheBust = idea.categoryId;
    } else {
      const pp = await prisma.catalogPainPoint.findUnique({
        where: { id: entityId },
        select: { title: true, categoryId: true },
      });
      if (!pp) {
        res.status(404).json({ error: 'Pain point not found' });
        return;
      }
      anchorTerm = pp.title;
      parentCategoryIdForCacheBust = pp.categoryId;
    }

    const arrayValidation = FaqArraySchema([anchorTerm]).safeParse(faqs);
    if (!arrayValidation.success) {
      res.status(422).json({
        error: 'FAQ validation failed',
        details: arrayValidation.error.errors,
      });
      return;
    }

    const updatedAt = new Date().toISOString();
    const meta: FaqJsonMeta = {
      source,
      ...(model ? { model } : {}),
      ...(generatedAt ? { generatedAt } : {}),
      ...(tokensUsed !== undefined ? { tokensUsed } : {}),
      updatedAt,
    };

    if (entityType === 'category') {
      await prisma.catalogCategory.update({
        where: { id: entityId },
        data: { faqJson: arrayValidation.data, faqJsonMeta: meta },
      });
    } else if (entityType === 'idea') {
      await prisma.catalogIdea.update({
        where: { id: entityId },
        data: { faqJson: arrayValidation.data, faqJsonMeta: meta },
      });
    } else {
      await prisma.catalogPainPoint.update({
        where: { id: entityId },
        data: { faqJson: arrayValidation.data, faqJsonMeta: meta },
      });
    }

    // Cache invalidation: bust the parent category's landing cache. For
    // category entities the entityId IS the categoryId. For idea/pain-point,
    // the parent category landing aggregates these into top-N lists.
    // No backend Redis cache exists for getIdeaBySlug/getPainPointBySlug —
    // the SvelteKit s-maxage on those public routes is the only intermediate
    // cache, surfaced to admins as a latency caveat in the editor UI.
    await invalidateCategoryLanding(parentCategoryIdForCacheBust);

    res.json({ ok: true, updatedAt });
  } catch (err) {
    console.error('FAQ save failed:', err);
    const message = err instanceof Error ? err.message : 'FAQ save failed';
    res.status(500).json({ error: message });
  }
});
