import { Router, Response } from 'express';
import { z } from 'zod';
import { Redis } from 'ioredis';
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
} from '../services/catalogService.js';
import { categorizeBatch } from '../services/categorizationService.js';
import { enqueueCatalogPainPointsJob, enqueueCatalogIdeasJob } from '../services/queueService.js';
import { prisma } from '../services/db.js';
import { JobStatus } from '@prisma/client';

export const adminCatalogRouter = Router();

// Redis for rate limiting
const redis = new Redis(CONFIG.redisUrl, {
  retryStrategy: (times: number) => Math.min(times * 100, 3000),
  maxRetriesPerRequest: 3,
});

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

const UpdateCategorySchema = z.object({
  name: z.string().min(1).max(100).optional(),
  slug: z.string().min(1).max(120).regex(/^[a-z0-9-]+$/).optional(),
  description: z.string().max(500).nullable().optional(),
  parentId: z.string().uuid().nullable().optional(),
  superGroupId: z.string().uuid().nullable().optional(),
  sortOrder: z.number().int().min(0).max(1000).optional(),
  isActive: z.boolean().optional(),
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

    // Attach activeJobs to child categories
    const enriched = categories.map((parent: any) => ({
      ...parent,
      children: (parent.children || []).map((child: any) => ({
        ...child,
        activeJobs: jobsByCategoryId.get(child.id) || [],
      })),
    }));

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

    await enqueueCatalogIdeasJob(job.id, categoryId, painPointData, niche, category.parent?.name || '');

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
    const painPoints = await prisma.catalogPainPoint.findMany({
      where: { categoryId: req.params.id, isActive: true },
      orderBy: { severityScore: 'desc' },
    });
    res.json({ painPoints });
  } catch (error) {
    console.error('Failed to list pain points:', error);
    res.status(500).json({ error: 'Failed to list pain points' });
  }
});
