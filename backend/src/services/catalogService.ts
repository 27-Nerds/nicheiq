import { readFileSync, existsSync } from 'fs';
import { z } from 'zod';
import { prisma } from './db.js';
import { getJobAsset } from './jobService.js';
import { AssetType, Prisma } from '@prisma/client';
import { resolveAssetPath } from '../utils/assetPath.js';
import { getRedis } from './redis.js';
import { extractOrCreateResearchContext, hasMeaningfulResearchContext } from './researchContextService.js';

// ============================================
// Slug helpers
// ============================================

function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 120);
}

// Idea/pain-point slugs: [descriptor]-[niche]-[format], capped at 8 segments,
// with numeric collision suffix. Mirrors what scripts/migrateCatalogSlugs.ts
// uses so backfilled and newly-published content share the same slug shape.
const IDEA_PAIN_SLUG_MAX_SEGMENTS = 8;

function capSlugSegments(slug: string, max: number): string {
  return slug.split('-').filter(Boolean).slice(0, max).join('-');
}

async function nicheSlugForCategory(categoryId: string): Promise<string> {
  const cat = await prisma.catalogCategory.findUnique({
    where: { id: categoryId },
    select: { slug: true, parent: { select: { slug: true } } },
  });
  // Parent slug is the niche for nested categories; otherwise the category's own slug.
  return cat?.parent?.slug ?? cat?.slug ?? 'misc';
}

/**
 * Build a unique slug for a freshly-published CatalogIdea.
 * Pattern: `<descriptor>-<niche>-<format>` (capped at 8 segments).
 */
export async function generateIdeaSlug(
  args: {
    name: string;
    categoryId: string;
    format?: string | null;
  },
  tx?: Prisma.TransactionClient,
): Promise<string> {
  const client = tx ?? prisma;
  const descriptor = slugify(args.name);
  if (!descriptor) throw new Error('Cannot generate idea slug from empty name');
  const niche = await nicheSlugForCategory(args.categoryId);
  const format = (args.format && slugify(args.format)) || 'saas';
  const base = capSlugSegments(`${descriptor}-${niche}-${format}`, IDEA_PAIN_SLUG_MAX_SEGMENTS);

  let candidate = base;
  let i = 2;
  while (await client.catalogIdea.findFirst({ where: { slug: candidate } })) {
    candidate = `${base}-${i}`;
    i++;
    if (i > 200) throw new Error(`Could not generate unique idea slug for base "${base}"`);
  }
  return candidate;
}

/**
 * Build a unique slug for a freshly-published CatalogPainPoint.
 * Pattern: `<descriptor>-<niche>-pain` (capped at 8 segments).
 *
 * Pass `tx` when called inside `prisma.$transaction` so uniqueness is
 * checked against the tx snapshot rather than the global client.
 */
export async function generatePainPointSlug(
  args: {
    title: string;
    categoryId: string;
  },
  tx?: Prisma.TransactionClient,
): Promise<string> {
  const client = tx ?? prisma;
  const descriptor = slugify(args.title);
  if (!descriptor) throw new Error('Cannot generate pain-point slug from empty title');
  const niche = await nicheSlugForCategory(args.categoryId);
  const base = capSlugSegments(`${descriptor}-${niche}-pain`, IDEA_PAIN_SLUG_MAX_SEGMENTS);

  let candidate = base;
  let i = 2;
  while (await client.catalogPainPoint.findFirst({ where: { slug: candidate } })) {
    candidate = `${base}-${i}`;
    i++;
    if (i > 200) throw new Error(`Could not generate unique pain-point slug for base "${base}"`);
  }
  return candidate;
}

/**
 * Generate a slug that's unique scoped to the given parent.
 *
 * Top-level categories (parentId=null) share a global namespace via the
 * partial unique index; child categories share a per-parent namespace via
 * @@unique([parentId, slug]). The slug stays in local form (no parent
 * prefix) so it produces clean nested URLs like /ideas/saas/b2b-tools.
 */
async function generateUniqueSlug(name: string, parentId: string | null = null): Promise<string> {
  const base = slugify(name);
  if (!base) throw new Error('Could not slugify name');

  const existing = await prisma.catalogCategory.findFirst({
    where: { parentId, slug: base },
  });
  if (!existing) return base;

  for (let i = 2; i <= 100; i++) {
    const candidate = `${base}-${i}`;
    const exists = await prisma.catalogCategory.findFirst({
      where: { parentId, slug: candidate },
    });
    if (!exists) return candidate;
  }
  throw new Error('Could not generate unique slug');
}

// ============================================
// Category CRUD
// ============================================

export async function listCategories(activeOnly = false) {
  const where = activeOnly ? { isActive: true, parentId: null } : { parentId: null };
  const childWhere = activeOnly ? { isActive: true } : {};

  const categories = await prisma.catalogCategory.findMany({
    where,
    include: {
      children: {
        where: childWhere,
        orderBy: { sortOrder: 'asc' },
        include: {
          _count: { select: { painPoints: { where: { isActive: true } }, ideas: { where: { isActive: true } } } },
        },
      },
      superGroup: { select: { id: true, name: true, slug: true, sortOrder: true } },
      _count: { select: { painPoints: { where: { isActive: true } }, ideas: { where: { isActive: true } } } },
    },
    orderBy: { sortOrder: 'asc' },
  });

  return categories;
}

export async function createCategory(data: {
  name: string;
  slug?: string;
  description?: string;
  parentId?: string;
  sortOrder?: number;
}) {
  // Two-level max: if parentId set, parent must be top-level
  if (data.parentId) {
    const parent = await prisma.catalogCategory.findUnique({
      where: { id: data.parentId },
    });
    if (!parent) throw new Error('Parent category not found');
    if (parent.parentId) throw new Error('Cannot nest more than two levels');
  }

  let slug: string;
  const parentId = data.parentId ?? null;
  if (data.slug) {
    const existing = await prisma.catalogCategory.findFirst({
      where: { parentId, slug: data.slug },
    });
    if (existing) throw new Error('Slug already exists at this level');
    slug = data.slug;
  } else {
    slug = await generateUniqueSlug(data.name, parentId);
  }

  const created = await prisma.catalogCategory.create({
    data: {
      name: data.name,
      slug,
      description: data.description,
      parentId: data.parentId,
      sortOrder: data.sortOrder ?? 0,
    },
  });

  if (created.parentId) {
    await invalidateCategoryLanding(created.parentId);
  } else {
    await invalidatePublicCategoryTree();
  }

  return created;
}

export async function updateCategory(id: string, data: {
  name?: string;
  slug?: string;
  description?: string | null;
  parentId?: string | null;
  superGroupId?: string | null;
  sortOrder?: number;
  isActive?: boolean;
  seoTitle?: string | null;
  seoDescription?: string | null;
  longDescription?: string | null;
  faqJson?: unknown;
  tags?: string[];
}) {
  // Two-level validation if changing parent
  if (data.parentId !== undefined && data.parentId !== null) {
    const parent = await prisma.catalogCategory.findUnique({ where: { id: data.parentId } });
    if (!parent) throw new Error('Parent category not found');
    if (parent.parentId) throw new Error('Cannot nest more than two levels');
    if (parent.id === id) throw new Error('Cannot set category as its own parent');
  }

  // Check slug uniqueness if changing — slugs are now scoped to parent.
  // Look up the target row to know its parent context (or new parent if changing).
  if (data.slug) {
    const targetParentId =
      data.parentId !== undefined
        ? data.parentId
        : (await prisma.catalogCategory.findUnique({ where: { id }, select: { parentId: true } }))
            ?.parentId ?? null;

    const conflict = await prisma.catalogCategory.findFirst({
      where: { parentId: targetParentId, slug: data.slug, id: { not: id } },
    });
    if (conflict) throw new Error('Slug already exists at this level');
  }

  // Capture the previous URL location so stale Redis entries for renamed/moved
  // categories are removed immediately instead of lingering until TTL expiry.
  const before = await prisma.catalogCategory.findUnique({
    where: { id },
    select: {
      slug: true,
      legacySlug: true,
      parentId: true,
      parent: { select: { slug: true } },
    },
  });

  // Prisma's strict types reject `unknown` for Json columns; cast at the boundary.
  const updated = await prisma.catalogCategory.update({
    where: { id },
    data: data as never,
  });

  const after = await prisma.catalogCategory.findUnique({
    where: { id },
    select: {
      slug: true,
      legacySlug: true,
      parentId: true,
      parent: { select: { slug: true } },
    },
  });

  await invalidateCategoryLandingLocations([before, after]);

  // Invalidate legacy-redirect cache for both the old and new slug + legacySlug
  // forms so the resolver re-queries Postgres on next crawl hit.
  if (before) {
    const keys = new Set<string>();
    if (before.slug) keys.add(before.slug);
    if (before.legacySlug) keys.add(before.legacySlug);
    if (updated.slug) keys.add(updated.slug);
    if (updated.legacySlug) keys.add(updated.legacySlug);
    await invalidateLegacyCategoryRedirect([...keys]);
  }

  return updated;
}

export async function deleteCategory(id: string) {
  // Check for items (including inactive)
  const [ideaCount, painPointCount] = await Promise.all([
    prisma.catalogIdea.count({ where: { categoryId: id } }),
    prisma.catalogPainPoint.count({ where: { categoryId: id } }),
  ]);

  if (ideaCount > 0 || painPointCount > 0) {
    throw new Error(`Category has ${ideaCount} ideas and ${painPointCount} pain points. Reassign or delete them first.`);
  }

  const before = await prisma.catalogCategory.findUnique({
    where: { id },
    select: {
      slug: true,
      parentId: true,
      parent: { select: { slug: true } },
    },
  });

  const deleted = await prisma.catalogCategory.delete({ where: { id } });
  await invalidateCategoryLandingLocations([before]);
  return deleted;
}

// ============================================
// Cache population
// ============================================

// Validation for Json array fields from report
const StringArraySchema = z.array(z.string().max(1000)).max(20);

function safeStringArray(val: unknown): string[] | undefined {
  const result = StringArraySchema.safeParse(val);
  return result.success ? result.data : undefined;
}

function safeFloat(val: unknown): number | null {
  if (val == null) return null;
  const n = Number(val);
  return Number.isFinite(n) ? n : null;
}

function safeString(val: unknown): string | null {
  if (val == null) return null;
  return String(val);
}


export async function populateItemCache(jobId: string) {
  // Get report
  const asset = await getJobAsset(jobId, AssetType.REPORT_JSON);
  if (!asset) return;
  const resolvedPath = resolveAssetPath(asset.filePath);
  if (!existsSync(resolvedPath)) return;

  const report = JSON.parse(readFileSync(resolvedPath, 'utf-8'));

  // Get share to find userId
  const share = await prisma.reportShare.findUnique({ where: { jobId } });
  if (!share) return;

  const niche = report.niche || '';
  const verdict = report.executive_dashboard?.go_no_go_verdict?.verdict || null;
  const generatedAt = report.generated_at ? new Date(report.generated_at) : null;

  const upserts: Promise<unknown>[] = [];

  // Selected solution (index = -1)
  if (report.selected_solution_details) {
    const sol = report.selected_solution_details;
    upserts.push(
      prisma.catalogItemCache.upsert({
        where: { jobId_itemType_itemIndex: { jobId, itemType: 'idea', itemIndex: -1 } },
        create: {
          jobId,
          userId: share.userId,
          niche,
          itemType: 'idea',
          itemIndex: -1,
          itemName: sol.solution_name || report.selected_solution_name || 'Selected Solution',
          itemDescription: sol.description || '',
          itemScores: {
            market_fit: sol.market_fit_score,
            technical_feasibility: sol.technical_feasibility_score,
            novelty: sol.novelty_score,
            solo_dev: sol.solo_dev_feasibility,
          },
          verdict,
          reportGeneratedAt: generatedAt,
        },
        update: {
          itemName: sol.solution_name || report.selected_solution_name || 'Selected Solution',
          itemDescription: sol.description || '',
          itemScores: {
            market_fit: sol.market_fit_score,
            technical_feasibility: sol.technical_feasibility_score,
            novelty: sol.novelty_score,
            solo_dev: sol.solo_dev_feasibility,
          },
          verdict,
          reportGeneratedAt: generatedAt,
        },
      })
    );
  }

  // Alternative solutions (index = 0+)
  if (Array.isArray(report.alternative_solutions)) {
    for (let i = 0; i < report.alternative_solutions.length; i++) {
      const alt = report.alternative_solutions[i];
      upserts.push(
        prisma.catalogItemCache.upsert({
          where: { jobId_itemType_itemIndex: { jobId, itemType: 'idea', itemIndex: i } },
          create: {
            jobId,
            userId: share.userId,
            niche,
            itemType: 'idea',
            itemIndex: i,
            itemName: alt.solution_name || `Alternative ${i + 1}`,
            itemDescription: alt.description || alt.summary || '',
            itemScores: {
              market_fit: alt.market_fit_score,
              technical_feasibility: alt.technical_feasibility_score,
              novelty: alt.novelty_score,
              solo_dev: alt.solo_dev_feasibility,
            },
            verdict,
            reportGeneratedAt: generatedAt,
          },
          update: {
            itemName: alt.solution_name || `Alternative ${i + 1}`,
            itemDescription: alt.description || alt.summary || '',
            itemScores: {
              market_fit: alt.market_fit_score,
              technical_feasibility: alt.technical_feasibility_score,
              novelty: alt.novelty_score,
              solo_dev: alt.solo_dev_feasibility,
            },
            verdict,
            reportGeneratedAt: generatedAt,
          },
        })
      );
    }
  }

  // Pain points (index = 0+)
  if (Array.isArray(report.detailed_pain_points)) {
    for (let i = 0; i < report.detailed_pain_points.length; i++) {
      const pp = report.detailed_pain_points[i];
      upserts.push(
        prisma.catalogItemCache.upsert({
          where: { jobId_itemType_itemIndex: { jobId, itemType: 'painPoint', itemIndex: i } },
          create: {
            jobId,
            userId: share.userId,
            niche,
            itemType: 'painPoint',
            itemIndex: i,
            itemName: pp.title || `Pain Point ${i + 1}`,
            itemDescription: pp.description || '',
            itemScores: {
              severity: pp.severity_score,
              willingness_to_pay: pp.willingness_to_pay,
              mention_count: pp.mention_count,
            },
            verdict: pp.opportunity_level || null,
            reportGeneratedAt: generatedAt,
          },
          update: {
            itemName: pp.title || `Pain Point ${i + 1}`,
            itemDescription: pp.description || '',
            itemScores: {
              severity: pp.severity_score,
              willingness_to_pay: pp.willingness_to_pay,
              mention_count: pp.mention_count,
            },
            verdict: pp.opportunity_level || null,
            reportGeneratedAt: generatedAt,
          },
        })
      );
    }
  }

  await Promise.all(upserts);
}

export async function removeItemCache(jobId: string) {
  await prisma.catalogItemCache.deleteMany({ where: { jobId } });
}

// ============================================
// Lazy cache population for existing shares
// ============================================

export async function ensureCachePopulated() {
  // Find active ReportShares that have no CatalogItemCache entries
  const activeShares = await prisma.reportShare.findMany({
    where: { isActive: true },
    select: { jobId: true },
  });

  if (activeShares.length === 0) return;

  const jobIds = activeShares.map(s => s.jobId);

  // Find which jobIds already have cache entries
  const cached = await prisma.catalogItemCache.findMany({
    where: { jobId: { in: jobIds } },
    select: { jobId: true },
    distinct: ['jobId'],
  });
  const cachedJobIds = new Set(cached.map(c => c.jobId));

  // Populate cache for shares that are missing
  const missing = jobIds.filter(id => !cachedJobIds.has(id));
  for (const jobId of missing) {
    try {
      await populateItemCache(jobId);
    } catch (err) {
      console.error(`Failed to lazily populate cache for job ${jobId}:`, err);
    }
  }
}

// ============================================
// Admin curation source (from cache)
// ============================================

export async function listCachedItems(params: {
  type: 'ideas' | 'painPoints';
  userId?: string;
  isPublished?: boolean;
  page: number;
  limit: number;
}) {
  const itemType = params.type === 'ideas' ? 'idea' : 'painPoint';
  const where: Record<string, unknown> = { itemType };
  if (params.userId) where.userId = params.userId;
  if (params.isPublished !== undefined) where.isPublished = params.isPublished;

  const [items, total] = await Promise.all([
    prisma.catalogItemCache.findMany({
      where,
      orderBy: { createdAt: 'desc' },
      skip: (params.page - 1) * params.limit,
      take: params.limit,
    }),
    prisma.catalogItemCache.count({ where }),
  ]);

  // Enrich published items with their published record IDs (batch lookup)
  const publishedItems = items.filter(i => i.isPublished);
  let publishedRecordMap = new Map<string, string>();

  if (publishedItems.length > 0) {
    const jobIds = [...new Set(publishedItems.map(i => i.jobId))];

    if (itemType === 'idea') {
      const records = await prisma.catalogIdea.findMany({
        where: { sourceJobId: { in: jobIds }, isActive: true },
        select: { id: true, sourceJobId: true, sourceItemIndex: true },
      });
      for (const r of records) {
        publishedRecordMap.set(`${r.sourceJobId}:${r.sourceItemIndex}`, r.id);
      }
    } else {
      const records = await prisma.catalogPainPoint.findMany({
        where: { sourceJobId: { in: jobIds }, isActive: true },
        select: { id: true, sourceJobId: true, sourceItemIndex: true },
      });
      for (const r of records) {
        publishedRecordMap.set(`${r.sourceJobId}:${r.sourceItemIndex}`, r.id);
      }
    }
  }

  // Enrich items with the original user query (Job.niche) for display
  const allJobIds = [...new Set(items.map(i => i.jobId))];
  const jobs = allJobIds.length > 0
    ? await prisma.job.findMany({
        where: { id: { in: allJobIds } },
        select: { id: true, niche: true },
      })
    : [];
  const jobNicheMap = new Map(jobs.map(j => [j.id, j.niche]));

  const enrichedItems = items.map(item => ({
    ...item,
    nicheQuery: jobNicheMap.get(item.jobId) ?? null,
    publishedRecordId: item.isPublished
      ? publishedRecordMap.get(`${item.jobId}:${item.itemIndex}`) ?? null
      : null,
  }));

  return {
    items: enrichedItems,
    total,
    page: params.page,
    totalPages: Math.ceil(total / params.limit),
  };
}

export async function listShareOwners() {
  const owners = await prisma.catalogItemCache.findMany({
    select: { userId: true },
    distinct: ['userId'],
  });

  // Fetch minimal user info
  const userIds = owners.map(o => o.userId);
  const users = await prisma.user.findMany({
    where: { id: { in: userIds } },
    select: { id: true, name: true },
  });

  return users;
}

// ============================================
// Publishing
// ============================================

export async function publishIdea(params: {
  categoryId: string;
  sourceJobId: string;
  itemIndex: number;
  publishedById: string;
}) {
  // Read report
  const asset = await getJobAsset(params.sourceJobId, AssetType.REPORT_JSON);
  if (!asset) throw new Error('Report not found');
  const resolvedPath = resolveAssetPath(asset.filePath);
  if (!existsSync(resolvedPath)) throw new Error('Report file not found');

  const report = JSON.parse(readFileSync(resolvedPath, 'utf-8'));

  // Extract solution based on index
  let solution: Record<string, unknown>;
  if (params.itemIndex === -1) {
    // Selected solution
    if (!report.selected_solution_details) throw new Error('Selected solution not found in report');
    solution = report.selected_solution_details;
    // Use selected_solution_name as fallback name
    if (!solution.solution_name) solution.solution_name = report.selected_solution_name;
  } else {
    // Alternative solution
    if (!Array.isArray(report.alternative_solutions) || params.itemIndex >= report.alternative_solutions.length) {
      throw new Error(`Alternative solution at index ${params.itemIndex} not found in report`);
    }
    solution = report.alternative_solutions[params.itemIndex];
  }

  const solutionName = (solution.solution_name as string) || 'Unknown Solution';
  const projectType = (solution.project_type as string) ?? null;
  const verdict = report.executive_dashboard?.go_no_go_verdict?.verdict || null;
  const generatedAt = report.generated_at ? new Date(report.generated_at) : null;

  // Generate the public slug + format outside the transaction (the slug
  // uniqueness check needs to read committed data).
  const slug = await generateIdeaSlug({
    name: solutionName,
    categoryId: params.categoryId,
    format: projectType,
  });
  const format = projectType ? slugify(projectType) || 'saas' : 'saas';

  // Phase 5: ensure CatalogResearchContext row exists BEFORE the idea insert
  // so the FK target is in place. Idempotent — first publish for a sourceJobId
  // does the projection work, subsequent publishes short-circuit.
  await extractOrCreateResearchContext(params.sourceJobId);

  try {
    const idea = await prisma.$transaction(async (tx) => {
      const created = await tx.catalogIdea.create({
        data: {
          categoryId: params.categoryId,
          slug,
          format,
          sourceJobId: params.sourceJobId,
          sourceNiche: report.niche || '',
          sourceVerdict: verdict,
          sourceGeneratedAt: generatedAt,
          sourceItemIndex: params.itemIndex,
          solutionName,
          headline: (solution.headline as string) ?? null,
          shortDescription: (solution.short_description as string) ?? null,
          description: (solution.description as string) || '',
          valueProposition: (solution.value_proposition as string) ?? null,
          projectType,
          coreFeatures: safeStringArray(solution.core_features) || undefined,
          targetPersonas: safeStringArray(solution.target_personas) || undefined,
          technicalApproach: (solution.technical_approach as string) ?? null,
          differentiationFactors: safeStringArray(solution.differentiation_factors) || undefined,
          pricingStrategy: (solution.pricing_strategy as string) ?? null,
          estimatedDevTime: (solution.estimated_development_time as string) ?? null,
          marketFitScore: safeFloat(solution.market_fit_score),
          technicalFeasibility: safeFloat(solution.technical_feasibility_score),
          seoScalabilityScore: safeFloat(solution.seo_scalability_score_refined) ?? safeFloat(solution.seo_scalability_score),
          noveltyScore: safeFloat(solution.novelty_score),
          soloDevFeasibility: safeFloat(solution.solo_dev_feasibility),
          estimatedCacOrganic: safeString(solution.estimated_cac_organic_refined) ?? safeString(solution.estimated_cac_organic),
          estimatedIndexablePages: safeFloat(solution.estimated_indexable_pages) != null ? Math.round(safeFloat(solution.estimated_indexable_pages)!) : null,
          programmaticSeoOpp: safeString(solution.programmatic_seo_opportunity_refined) ?? safeString(solution.programmatic_seo_opportunity),
          // Phase 13 of detail-page IA rework: surface idea-specific BaseSolutionIdea
          // fields on /idea/[slug]. AlternativeSolution Pydantic model lacks all of
          // these except estimated_cac_paid, so alternative rows land with null/[].
          whyItWorks: safeString(solution.why_it_works),
          conventionalApproach: safeString(solution.conventional_approach),
          innovationAngle: safeString(solution.innovation_angle),
          estimatedCacPaid: safeString(solution.estimated_cac_paid),
          organicDiscoveryQueries: safeStringArray(solution.organic_discovery_queries) ?? [],
          // Phase 1 of detail-page IA rework: denormalize the selected solution's
          // pain_points_addressed list onto each idea row so /pain-point/[slug]
          // can do a fast `addressedPainTitles: { has: title }` lookup.
          // Alternative-solution rows (itemIndex >= 0): the Pydantic
          // AlternativeSolution model has no pain_points_addressed field
          // (research_state.py:241-283), so safeStringArray returns undefined
          // → falls through to []. Phase 8 of the plan extends the model.
          addressedPainTitles: safeStringArray(solution.pain_points_addressed) ?? [],
          publishedById: params.publishedById,
        },
      });

      // Mark cache entry as published (atomic with create)
      await tx.catalogItemCache.updateMany({
        where: {
          jobId: params.sourceJobId,
          itemType: 'idea',
          itemIndex: params.itemIndex,
        },
        data: { isPublished: true, categoryId: params.categoryId },
      });

      return created;
    });

    await invalidateCategoryLanding(params.categoryId);
    return idea;
  } catch (error: unknown) {
    if (error && typeof error === 'object' && 'code' in error && (error as { code: string }).code === 'P2002') {
      throw new Error('This solution has already been published from this report');
    }
    throw error;
  }
}

export async function publishPainPoint(params: {
  categoryId: string;
  sourceJobId: string;
  itemIndex: number;
  publishedById: string;
}) {
  const asset = await getJobAsset(params.sourceJobId, AssetType.REPORT_JSON);
  if (!asset) throw new Error('Report not found');
  const resolvedPath = resolveAssetPath(asset.filePath);
  if (!existsSync(resolvedPath)) throw new Error('Report file not found');

  const report = JSON.parse(readFileSync(resolvedPath, 'utf-8'));

  if (!Array.isArray(report.detailed_pain_points) || params.itemIndex >= report.detailed_pain_points.length) {
    throw new Error(`Pain point at index ${params.itemIndex} not found in report`);
  }

  const pp = report.detailed_pain_points[params.itemIndex];
  const generatedAt = report.generated_at ? new Date(report.generated_at) : null;
  const ppTitle = pp.title || `Pain Point ${params.itemIndex + 1}`;
  const ppSlug = await generatePainPointSlug({
    title: ppTitle,
    categoryId: params.categoryId,
  });

  // Phase 5: ensure CatalogResearchContext row exists BEFORE the pain-point
  // insert so the FK target is in place. Idempotent.
  await extractOrCreateResearchContext(params.sourceJobId);

  try {
    const painPoint = await prisma.$transaction(async (tx) => {
      const created = await tx.catalogPainPoint.create({
        data: {
          categoryId: params.categoryId,
          slug: ppSlug,
          sourceJobId: params.sourceJobId,
          sourceNiche: report.niche || '',
          sourceGeneratedAt: generatedAt,
          sourceItemIndex: params.itemIndex,
          title: ppTitle,
          description: pp.description || '',
          mentionCount: pp.mention_count ?? 0,
          severityScore: pp.severity_score ?? 0,
          willingnessToPayScore: pp.willingness_to_pay ?? 0,
          opportunityLevel: pp.opportunity_level || 'medium',
          representativeQuotes: safeStringArray(pp.representative_quotes) || undefined,
          sourcePlatforms: safeStringArray(pp.source_platforms) || undefined,
          categories: safeStringArray(pp.categories) || undefined,
          affectedSegments: safeStringArray(pp.affected_segments) || undefined,
          themeId: typeof pp.parent_theme_id === 'string' && pp.parent_theme_id ? pp.parent_theme_id : null,
          solutionApproach: pp.solution_approach ?? null,
          publishedById: params.publishedById,
        },
      });

      // Mark cache entry as published (atomic with create)
      await tx.catalogItemCache.updateMany({
        where: {
          jobId: params.sourceJobId,
          itemType: 'painPoint',
          itemIndex: params.itemIndex,
        },
        data: { isPublished: true, categoryId: params.categoryId },
      });

      return created;
    });

    await invalidateCategoryLanding(params.categoryId);
    return painPoint;
  } catch (error: unknown) {
    if (error && typeof error === 'object' && 'code' in error && (error as { code: string }).code === 'P2002') {
      throw new Error('This pain point has already been published from this report');
    }
    throw error;
  }
}

export async function updateCatalogIdea(id: string, data: {
  categoryId?: string;
  isFeatured?: boolean;
  isActive?: boolean;
}) {
  // Capture original categoryId so we can invalidate both old and new on category change.
  const before = await prisma.catalogIdea.findUnique({
    where: { id },
    select: { categoryId: true },
  });

  const result = await prisma.$transaction(async (tx) => {
    const idea = await tx.catalogIdea.update({
      where: { id },
      data,
    });

    // Sync cache when isActive or categoryId changes
    const cacheUpdate: Record<string, unknown> = {};
    if (data.isActive !== undefined) cacheUpdate.isPublished = data.isActive;
    if (data.categoryId !== undefined) cacheUpdate.categoryId = data.categoryId;

    if (Object.keys(cacheUpdate).length > 0) {
      await tx.catalogItemCache.updateMany({
        where: {
          jobId: idea.sourceJobId,
          itemType: 'idea',
          itemIndex: idea.sourceItemIndex,
        },
        data: cacheUpdate,
      });
    }

    return idea;
  });

  // Invalidate landing for current category and original (if moved).
  await invalidateCategoryLanding(result.categoryId);
  if (before && before.categoryId !== result.categoryId) {
    await invalidateCategoryLanding(before.categoryId);
  }

  return result;
}

export async function updateCatalogPainPoint(id: string, data: {
  categoryId?: string;
  isFeatured?: boolean;
  isActive?: boolean;
}) {
  const before = await prisma.catalogPainPoint.findUnique({
    where: { id },
    select: { categoryId: true },
  });

  const result = await prisma.$transaction(async (tx) => {
    const pp = await tx.catalogPainPoint.update({
      where: { id },
      data,
    });

    const cacheUpdate: Record<string, unknown> = {};
    if (data.isActive !== undefined) cacheUpdate.isPublished = data.isActive;
    if (data.categoryId !== undefined) cacheUpdate.categoryId = data.categoryId;

    if (Object.keys(cacheUpdate).length > 0) {
      await tx.catalogItemCache.updateMany({
        where: {
          jobId: pp.sourceJobId,
          itemType: 'painPoint',
          itemIndex: pp.sourceItemIndex,
        },
        data: cacheUpdate,
      });
    }

    return pp;
  });

  await invalidateCategoryLanding(result.categoryId);
  if (before && before.categoryId !== result.categoryId) {
    await invalidateCategoryLanding(before.categoryId);
  }

  return result;
}

// ============================================
// Depublish
// ============================================

export async function depublishIdea(id: string) {
  const idea = await prisma.catalogIdea.findUnique({ where: { id } });
  if (!idea) return null;

  const categoryIdToInvalidate = idea.categoryId;

  await prisma.$transaction(async (tx) => {
    await tx.catalogIdea.update({ where: { id }, data: { isActive: false } });

    const result = await tx.catalogItemCache.updateMany({
      where: {
        jobId: idea.sourceJobId,
        itemType: 'idea',
        itemIndex: idea.sourceItemIndex,
      },
      data: { isPublished: false, categoryId: null },
    });

    if (result.count === 0) {
      // Generated item with no cache entry — create one so it appears in Curate tab
      await tx.catalogItemCache.upsert({
        where: {
          jobId_itemType_itemIndex: {
            jobId: idea.sourceJobId,
            itemType: 'idea',
            itemIndex: idea.sourceItemIndex,
          },
        },
        update: { isPublished: false, categoryId: null },
        create: {
          jobId: idea.sourceJobId,
          userId: idea.publishedById,
          niche: idea.sourceNiche,
          itemType: 'idea',
          itemIndex: idea.sourceItemIndex,
          itemName: idea.solutionName,
          itemDescription: idea.description,
          itemScores: {
            marketFitScore: idea.marketFitScore,
            noveltyScore: idea.noveltyScore,
            technicalFeasibility: idea.technicalFeasibility,
          },
          verdict: idea.sourceVerdict,
          isPublished: false,
          categoryId: null,
          reportGeneratedAt: idea.sourceGeneratedAt,
        },
      });
    }
  });

  await invalidateCategoryLanding(categoryIdToInvalidate);
  return idea;
}

export async function depublishPainPoint(id: string) {
  const pp = await prisma.catalogPainPoint.findUnique({ where: { id } });
  if (!pp) return null;

  const categoryIdToInvalidate = pp.categoryId;

  await prisma.$transaction(async (tx) => {
    await tx.catalogPainPoint.update({ where: { id }, data: { isActive: false } });

    const result = await tx.catalogItemCache.updateMany({
      where: {
        jobId: pp.sourceJobId,
        itemType: 'painPoint',
        itemIndex: pp.sourceItemIndex,
      },
      data: { isPublished: false, categoryId: null },
    });

    if (result.count === 0) {
      // Generated item with no cache entry — create one so it appears in Curate tab
      await tx.catalogItemCache.upsert({
        where: {
          jobId_itemType_itemIndex: {
            jobId: pp.sourceJobId,
            itemType: 'painPoint',
            itemIndex: pp.sourceItemIndex,
          },
        },
        update: { isPublished: false, categoryId: null },
        create: {
          jobId: pp.sourceJobId,
          userId: pp.publishedById,
          niche: pp.sourceNiche,
          itemType: 'painPoint',
          itemIndex: pp.sourceItemIndex,
          itemName: pp.title,
          itemDescription: pp.description,
          itemScores: {
            severityScore: pp.severityScore,
            willingnessToPayScore: pp.willingnessToPayScore,
          },
          verdict: null,
          isPublished: false,
          categoryId: null,
          reportGeneratedAt: pp.sourceGeneratedAt,
        },
      });
    }
  });

  await invalidateCategoryLanding(categoryIdToInvalidate);
  return pp;
}

// ============================================
// snake_case transform for SolutionPreview compat
// ============================================

// Phase 15.13 — explicit return type so `BackendIdeaPreview` (alias below)
// stays in sync with the snake_case shape consumed by the frontend.
type BackendIdeaPreview = ReturnType<typeof toIdeaPreview>;

// Phase 15.13 — pain-point landing-payload shape. Mirrors what
// `topPainPointsRaw.map(({ sourceJobId, publishedById, ...rest }) => rest)`
// emits below; declared explicitly so dropping a field anywhere in the chain
// is caught at the type level.
interface BackendPainPointPreview {
  id: string;
  slug: string | null;
  title: string;
  description: string;
  mentionCount: number;
  severityScore: number;
  willingnessToPayScore: number;
  opportunityLevel: string;
  // Prisma serializes JSON columns as `JsonValue`. Frontend coerces to the
  // strict shapes (string[] | null) at parse time.
  representativeQuotes: unknown;
  sourcePlatforms: unknown;
  categories: unknown;
  affectedSegments: unknown;
  themeId: string | null;
  solutionApproach: string | null;
  isFeatured: boolean;
  isActive: boolean;
  sourceNiche: string;
  sourceItemIndex: number;
  sourceGeneratedAt: Date | null;
  createdAt: Date;
  updatedAt: Date;
  category: { id: string; name: string; slug: string };
}

function toIdeaPreview(idea: Record<string, any>) {
  return {
    id: idea.id,
    slug: idea.slug,
    solution_name: idea.solutionName,
    headline: idea.headline ?? null,
    short_description: idea.shortDescription ?? null,
    description: idea.description,
    value_proposition: idea.valueProposition,
    project_type: idea.projectType,
    format: idea.format,
    core_features: idea.coreFeatures,
    target_personas: idea.targetPersonas,
    differentiation_factors: idea.differentiationFactors,
    pricing_strategy: idea.pricingStrategy,
    estimated_development_time: idea.estimatedDevTime,
    market_fit_score: idea.marketFitScore,
    technical_feasibility_score: idea.technicalFeasibility,
    seo_scalability_score: idea.seoScalabilityScore,
    novelty_score: idea.noveltyScore,
    solo_dev_feasibility: idea.soloDevFeasibility,
    estimated_cac_organic: idea.estimatedCacOrganic,
    programmatic_seo_opportunity: idea.programmaticSeoOpp,
    // Catalog-specific fields
    technical_approach: idea.technicalApproach,
    estimated_indexable_pages: idea.estimatedIndexablePages,
    // Phase 13 — idea-specific BaseSolutionIdea fields. Empty array → null
    // so frontend can use truthy-check `{#if idea.organic_discovery_queries}`
    // to hide the section without a length check.
    why_it_works: idea.whyItWorks ?? null,
    conventional_approach: idea.conventionalApproach ?? null,
    innovation_angle: idea.innovationAngle ?? null,
    estimated_cac_paid: idea.estimatedCacPaid ?? null,
    organic_discovery_queries: Array.isArray(idea.organicDiscoveryQueries) && idea.organicDiscoveryQueries.length > 0
      ? idea.organicDiscoveryQueries
      : null,
    source_niche: idea.sourceNiche,
    source_verdict: idea.sourceVerdict,
    is_featured: idea.isFeatured,
    category: idea.category,
    created_at: idea.createdAt,
    updated_at: idea.updatedAt,
  };
}

// ============================================
// User-facing queries
// ============================================

// Sort mappings (prevent orderBy injection)
const ideaSortMap: Record<string, Record<string, string>> = {
  newest: { createdAt: 'desc' },
  highest_market_fit: { marketFitScore: 'desc' },
  highest_novelty: { noveltyScore: 'desc' },
};

const painPointSortMap: Record<string, Record<string, string>> = {
  newest: { createdAt: 'desc' },
  highest_severity: { severityScore: 'desc' },
  highest_wtp: { willingnessToPayScore: 'desc' },
  most_mentions: { mentionCount: 'desc' },
};

export async function listPublishedIdeas(params: {
  categorySlug?: string;
  page: number;
  limit: number;
  sortBy: string;
}) {
  const where: Record<string, unknown> = { isActive: true };

  if (params.categorySlug) {
    // Slug lookups must tolerate both the new local form (post-Phase-2.5) and
    // the legacy globally-unique form (preserved in `legacySlug`) so existing
    // /api/catalog/ideas?category=saas-b2b-tools links continue to work.
    const category = await prisma.catalogCategory.findFirst({
      where: {
        OR: [{ slug: params.categorySlug }, { legacySlug: params.categorySlug }],
      },
      include: { children: { select: { id: true } } },
    });
    if (category) {
      const categoryIds = [category.id, ...category.children.map((c) => c.id)];
      where.categoryId = { in: categoryIds };
    }
  }

  const orderBy = ideaSortMap[params.sortBy] || ideaSortMap.newest;

  const [items, total] = await Promise.all([
    prisma.catalogIdea.findMany({
      where,
      include: { category: { select: { id: true, name: true, slug: true } } },
      orderBy,
      skip: (params.page - 1) * params.limit,
      take: params.limit,
    }),
    prisma.catalogIdea.count({ where }),
  ]);

  // Strip sensitive fields and transform to snake_case
  const sanitized = items.map(({ sourceJobId: _s, publishedById: _p, ...rest }) => toIdeaPreview(rest));

  return {
    items: sanitized,
    total,
    page: params.page,
    totalPages: Math.ceil(total / params.limit),
  };
}

export async function listPublishedPainPoints(params: {
  categorySlug?: string;
  page: number;
  limit: number;
  sortBy: string;
}) {
  const where: Record<string, unknown> = { isActive: true };

  if (params.categorySlug) {
    const category = await prisma.catalogCategory.findFirst({
      where: {
        OR: [{ slug: params.categorySlug }, { legacySlug: params.categorySlug }],
      },
      include: { children: { select: { id: true } } },
    });
    if (category) {
      const categoryIds = [category.id, ...category.children.map((c) => c.id)];
      where.categoryId = { in: categoryIds };
    }
  }

  const orderBy = painPointSortMap[params.sortBy] || painPointSortMap.newest;

  const [items, total] = await Promise.all([
    prisma.catalogPainPoint.findMany({
      where,
      include: { category: { select: { id: true, name: true, slug: true } } },
      orderBy,
      skip: (params.page - 1) * params.limit,
      take: params.limit,
    }),
    prisma.catalogPainPoint.count({ where }),
  ]);

  const sanitized = items.map(({ sourceJobId: _s, publishedById: _p, ...rest }) => rest);

  return {
    items: sanitized,
    total,
    page: params.page,
    totalPages: Math.ceil(total / params.limit),
  };
}

export async function getPublishedIdea(id: string) {
  const idea = await prisma.catalogIdea.findFirst({
    where: { id, isActive: true },
    include: { category: { select: { id: true, name: true, slug: true } } },
  });
  if (!idea) return null;
  const { sourceJobId: _s, publishedById: _p, ...rest } = idea;
  return toIdeaPreview(rest);
}

export async function getPublishedPainPoint(id: string) {
  const pp = await prisma.catalogPainPoint.findFirst({
    where: { id, isActive: true },
    include: { category: { select: { id: true, name: true, slug: true } } },
  });
  if (!pp) return null;
  const { sourceJobId: _s, publishedById: _p, ...rest } = pp;
  return rest;
}

export async function getCatalogStats() {
  const [ideas, painPoints, categories] = await Promise.all([
    prisma.catalogIdea.count({ where: { isActive: true } }),
    prisma.catalogPainPoint.count({ where: { isActive: true } }),
    prisma.catalogCategory.count({ where: { isActive: true } }),
  ]);

  return { ideas, painPoints, categories };
}

// ============================================
// Federated search
// ============================================

export async function searchCatalog(query: string, limit = 5) {
  const [categories, ideas, painPoints] = await Promise.all([
    prisma.catalogCategory.findMany({
      where: {
        isActive: true,
        name: { contains: query, mode: 'insensitive' },
      },
      select: {
        id: true,
        name: true,
        slug: true,
        parentId: true,
        // Parent slug needed by frontend to build nested URLs (/ideas/{parent}/{child})
        parent: { select: { slug: true } },
        _count: { select: { ideas: { where: { isActive: true } }, painPoints: { where: { isActive: true } }, children: true } },
      },
      take: limit,
      orderBy: { name: 'asc' },
    }),
    prisma.catalogIdea.findMany({
      where: {
        isActive: true,
        solutionName: { contains: query, mode: 'insensitive' },
      },
      select: {
        id: true,
        slug: true,
        solutionName: true,
        description: true,
        marketFitScore: true,
        category: { select: { name: true, slug: true, parent: { select: { slug: true } } } },
      },
      take: limit,
      orderBy: { createdAt: 'desc' },
    }),
    prisma.catalogPainPoint.findMany({
      where: {
        isActive: true,
        title: { contains: query, mode: 'insensitive' },
      },
      select: {
        id: true,
        slug: true,
        title: true,
        description: true,
        severityScore: true,
        category: { select: { name: true, slug: true, parent: { select: { slug: true } } } },
      },
      take: limit,
      orderBy: { createdAt: 'desc' },
    }),
  ]);

  return {
    categories: categories.map(c => ({
      id: c.id,
      name: c.name,
      slug: c.slug,
      parentSlug: c.parent?.slug ?? null,
      isParent: !c.parentId,
      ideaCount: c._count.ideas,
      painPointCount: c._count.painPoints,
      childCount: c._count.children,
    })),
    ideas: ideas.map(i => ({
      id: i.id,
      slug: i.slug,
      solution_name: i.solutionName,
      description: i.description,
      market_fit_score: i.marketFitScore,
      category: i.category,
    })),
    painPoints: painPoints.map(pp => ({
      id: pp.id,
      slug: pp.slug,
      title: pp.title,
      description: pp.description,
      severity_score: pp.severityScore,
      category: pp.category,
    })),
  };
}

// ============================================
// Discover — random pain points for /new page
// ============================================

interface DiscoverPainPoint {
  id: string;
  title: string;
  description: string;
  severityScore: number | null;
  mentionCount: number | null;
}

export async function getDiscoverPainPoints(count: number = 4): Promise<DiscoverPainPoint[]> {
  return prisma.$queryRaw<DiscoverPainPoint[]>`
    SELECT id, title, description, "severityScore", "mentionCount"
    FROM "CatalogPainPoint"
    WHERE "isActive" = true
    ORDER BY RANDOM()
    LIMIT ${count}
  `;
}

// ============================================
// Landing-page payload, slug-based detail lookups, sitemap entries
// (Phase 2 — public catalog SEO restructure)
// ============================================

// v2 — Phase 5.5 enrichment adds nicheContext/qualitySignals/categorizationSummary/
// painAnalysisSummary/topPainCategories + audienceSignals + extended Theme shape.
// Stale v1 entries age out via TTL (~5 min); no manual flush needed.
const LANDING_CACHE_PREFIX = 'catalog:landing:v2';
const LANDING_CACHE_TTL_BASE = 600; // seconds; ±10% jitter applied per write
const TREE_CACHE_KEY = 'catalog:tree:v1';
const TREE_CACHE_TTL = 300;

function landingCacheKey(parentSlug: string, childSlug?: string | null): string {
  return childSlug
    ? `${LANDING_CACHE_PREFIX}:${parentSlug}:${childSlug}`
    : `${LANDING_CACHE_PREFIX}:${parentSlug}`;
}

function jitteredTtl(): number {
  const jitter = Math.floor(LANDING_CACHE_TTL_BASE * 0.1);
  return LANDING_CACHE_TTL_BASE + Math.floor(Math.random() * (2 * jitter + 1)) - jitter;
}

interface CategoryLandingLocation {
  slug: string;
  parentId: string | null;
  parent: { slug: string } | null;
}

function landingKeysForLocation(location: CategoryLandingLocation | null | undefined): string[] {
  if (!location) return [];
  if (location.parentId && location.parent) {
    return [
      landingCacheKey(location.parent.slug, location.slug),
      landingCacheKey(location.parent.slug),
    ];
  }
  return [landingCacheKey(location.slug)];
}

async function invalidateCategoryLandingLocations(
  locations: Array<CategoryLandingLocation | null | undefined>,
): Promise<void> {
  try {
    const keys = new Set<string>([TREE_CACHE_KEY]);
    for (const location of locations) {
      for (const key of landingKeysForLocation(location)) {
        keys.add(key);
      }
    }
    await getRedis().del(...keys);
  } catch (err) {
    console.error('Failed to invalidate landing cache:', err);
  }
}

/**
 * Invalidate the landing-page cache for a category. Always invalidates the
 * category itself; if the category is a child, also invalidates its parent
 * (since the parent landing aggregates ideas/pain-points from all its children).
 */
export async function invalidateCategoryLanding(categoryId: string): Promise<void> {
  try {
    const cat = await prisma.catalogCategory.findUnique({
      where: { id: categoryId },
      select: { slug: true, parentId: true, parent: { select: { slug: true } } },
    });
    if (!cat) return;

    await invalidateCategoryLandingLocations([cat]);
  } catch (err) {
    console.error('Failed to invalidate landing cache:', err);
  }
}

// ============================================
// Phase 5.4 — Catalog rebuild summary types
// ============================================
//
// These flattened summaries live on top-level landing/detail payloads so the
// public catalog UI doesn't have to unwrap researchContext JSON columns.
// All shapes use camelCase to match landing-payload convention. Fields are
// always nullable — the frontend's degradation contract requires `{#if}`
// guards everywhere.

interface CatalogThemeSummary {
  title: string;
  // Stable slug (auto-generated from title via Pydantic ThemeCategory model_validator).
  // Used by the catalog UI to group pain points (whose parent_theme_id matches this id)
  // under their source theme. Null on legacy rows ingested before the field existed.
  id: string | null;
  severity: number | null;       // 0-100 (NOT scaled by frontend)
  mentionCount: number | null;
  sources: string[];             // deprecated alias of primaryUserSegments — see Risks in plan
  // Phase 5.5 — extended ThemeCard render fields.
  description: string | null;    // from theme.definition
  frequency: string | null;      // 'High' | 'Medium' | 'Low' (verbatim from crew)
  primaryUserSegments: string[]; // same source as `sources` for now
}

interface CatalogAudienceSegmentSummary {
  name: string;
  sizeLabel: string | null;
  bullets: string[];
  // Phase 5.5 — surfaced for AudienceSegmentCard's `.seg-meta` footer.
  expertiseLevel: string | null;     // 'Beginner' | 'Intermediate' | 'Advanced'
  budgetSensitivity: string | null;  // 'High' | 'Medium' | 'Low'
}

// Phase 5.5 — flattened blobs for the catalog landing payload.
interface CatalogNicheContextSummary {
  description: string | null;
  industryBoundaries: string | null;  // STRING — not a list (Pydantic NicheContext.industry_boundaries: str)
  marketSegments: string[] | null;
}

interface CatalogAudienceSignalsSummary {
  vocabulary: string[];                // common_vocabulary
  frustrations: string[];              // frustrations_with_existing
  currentTools: string[];              // tools_currently_used
  communityHubs: string[];
  recommendedChannels: string[];
  messagingFrameworks: string[];
  contentPreferences: string | null;   // STRING — not list
  earlyAdopterTactics: string | null;  // Optional[str]
}

interface CatalogQualitySignalsSummary {
  contentTier: string | null;          // EXCELLENT | GOOD | MINIMAL | INSUFFICIENT
  painPointTier: string | null;        // GOLD | SILVER | BRONZE | INSUFFICIENT
  confidenceScore: number | null;      // 0-1
  overallDataQuality: string | null;   // HIGH | MEDIUM | LOW (FinalReport-only; null on preview rows)
  engagementMetrics: { totalEngagement: number; avgEngagementPerSource: number } | null;
}

interface CatalogCompetitorSummary {
  name: string;
  url: string | null;
  competitorType: string | null;   // DIRECT | PARTIAL | INDIRECT (verbatim)
  description: string;
  keyFeatures: string[];
  pricingModel: string | null;
  strengths: string[];
  weaknesses: string[];
  position: 'leader' | 'challenger' | 'niche' | null;  // new in Phase 5.4
}

interface CatalogKeywordClusterSummary {
  name: string;
  primaryKeyword: string | null;
  totalSearchVolume: number;
  contentRecommendation: string | null;
  estimatedTrafficPotential: string | null;
  priority: number | null;
  // Per-keyword volume/difficulty enrichment deferred — supporting_keywords
  // are strings until pipeline ships per-keyword metrics. Each becomes
  // `{ term, volume: 0, difficulty: 'medium' }` placeholder in v1.
  keywords: Array<{
    term: string;
    volume: number;
    difficulty: 'easy' | 'medium' | 'hard';
  }>;
}

interface CatalogSubredditSource {
  name: string;
  postCount: number;
}

// Phase 2 of detail-page IA rework — cross-link return shapes for the
// `getPainPointBySlug` and `getIdeaBySlug` extensions.
interface SiblingPainSummary {
  slug: string;             // Backend filters slug: { not: null }, so non-null here.
  title: string;
  description: string;      // CatalogPainPoint.description is @db.Text NOT NULL.
  severityScore: number;
  mentionCount: number;
  opportunityLevel: string | null;
}

type AddressedPainLookup = Record<
  string,
  { slug: string; severityScore: number; mentionCount: number }
>;

// Phase 14 of detail-page IA rework — source-grounded evidence shapes.
interface QuoteSource {
  quote: string;
  postId: string;
  subreddit: string;
  score: number;
}

interface CatalogTopRedditThread {
  postId: string;
  title: string;
  subreddit: string;
  score: number;
  numComments: number;
  url: string;
  keyInsight: string;
}

interface CategoryLandingPayload {
  category: {
    id: string;
    name: string;
    slug: string;
    description: string | null;
    seoTitle: string | null;
    seoDescription: string | null;
    longDescription: string | null;
    faqJson: unknown;
    tags: string[];
    isActive: boolean;
    createdAt: string;
    updatedAt: string;
  };
  parent: { id: string; name: string; slug: string } | null;
  superGroup: { id: string; name: string; slug: string } | null;
  children: Array<{
    id: string;
    name: string;
    slug: string;
    description: string | null;
    ideaCount: number;
    painPointCount: number;
  }>;
  siblings: Array<{ id: string; name: string; slug: string }>;
  // Phase 15.13 — strict types replace `Record<string, unknown>`. `toIdeaPreview`'s
  // return shape becomes the contract for `topIdeas`; the pain-point map below
  // produces a similarly explicit shape (Prisma row minus internal-only fields).
  topIdeas: BackendIdeaPreview[];
  topPainPoints: BackendPainPointPreview[];
  totalIdeas: number;
  totalPainPoints: number;
  sources: string[];
  // Phase 5.4 — flattened summaries for the new public catalog UI. All sourced
  // from the most-recent research context for the category subtree (same row
  // that backs `researchContext` below). Every field nullable — the frontend
  // hides sections when null.
  themes: CatalogThemeSummary[] | null;
  audienceSegments: CatalogAudienceSegmentSummary[] | null;
  competitors: CatalogCompetitorSummary[] | null;
  keywordClusters: CatalogKeywordClusterSummary[] | null;
  subredditSources: CatalogSubredditSource[] | null;
  // Two-track sources metric per scope rule (NOT a single mixed total).
  contentItemsMined: number;       // posts/threads analyzed (sum)
  sourceCommunities: number;       // distinct platform communities (count)
  // Always null until pipeline produces per-category growth data. Reserved.
  growthPercent: number | null;
  // Phase 5.5 — catalog page enrichment.
  nicheContext: CatalogNicheContextSummary | null;
  audienceSignals: CatalogAudienceSignalsSummary | null;
  qualitySignals: CatalogQualitySignalsSummary | null;
  categorizationSummary: string | null;
  painAnalysisSummary: string | null;
  topPainCategories: string[] | null;
  // Phase 14 — niche-wide top reddit threads (uncapped on niche page).
  topRedditThreads: CatalogTopRedditThread[] | null;
  // Phase 15.5 — count of GO-verdict ideas across the category subtree.
  verdictGoCount: number;
  // Phase 5: research context from the most-recent published item's source job.
  // Null when the category has zero published items, or when the item's
  // sourceJobId still maps to a placeholder context row (report.json missing).
  // Frontend renders this as "Analysis from latest research in this niche."
  researchContext: Record<string, unknown> | null;
}

// ============================================
// Phase 5.4 — flatten / extract helpers
// ============================================

/** Difficulty 0-100 (raw DataForSEO scale) → 3-bucket label for the catalog UI. */
function bucketKeywordDifficulty(score: number | null | undefined): 'easy' | 'medium' | 'hard' {
  if (score == null || !Number.isFinite(score)) return 'medium';
  if (score <= 33) return 'easy';
  if (score <= 66) return 'medium';
  return 'hard';
}

/** Pull theme severity summary from researchContext.themeSeverityScores (Phase 5.4 column). */
function flattenThemes(ctx: { themeSeverityScores?: unknown } | null): CatalogThemeSummary[] | null {
  if (!ctx?.themeSeverityScores || !Array.isArray(ctx.themeSeverityScores)) return null;
  const out: CatalogThemeSummary[] = [];
  for (const t of ctx.themeSeverityScores as Array<Record<string, unknown>>) {
    if (!t || typeof t !== 'object') continue;
    const title = typeof t.title === 'string' ? t.title : null;
    if (!title) continue;
    const segments = Array.isArray(t.primary_user_segments)
      ? (t.primary_user_segments as unknown[]).filter((s): s is string => typeof s === 'string')
      : Array.isArray(t.sources)
        ? (t.sources as unknown[]).filter((s): s is string => typeof s === 'string')
        : [];
    out.push({
      title,
      id: typeof t.theme_id === 'string' && t.theme_id ? t.theme_id : null,
      severity: typeof t.severity === 'number' ? t.severity : null,
      mentionCount: typeof t.mention_count === 'number' ? t.mention_count : null,
      sources: segments,
      description: typeof t.description === 'string' ? t.description : null,
      frequency: typeof t.frequency === 'string' ? t.frequency : null,
      primaryUserSegments: segments,
    });
  }
  return out.length > 0 ? out : null;
}

/** Pull audience segment summary from researchContext.audienceMapping. */
function flattenAudienceSegments(
  ctx: { audienceMapping?: unknown } | null,
): CatalogAudienceSegmentSummary[] | null {
  if (!ctx?.audienceMapping || typeof ctx.audienceMapping !== 'object') return null;
  const segments = (ctx.audienceMapping as Record<string, unknown>).audience_segments;
  if (!Array.isArray(segments) || segments.length === 0) return null;
  const out: CatalogAudienceSegmentSummary[] = [];
  for (const s of segments as Array<Record<string, unknown>>) {
    if (!s || typeof s !== 'object') continue;
    const name = typeof s.segment_name === 'string' ? s.segment_name : null;
    if (!name) continue;
    // Mirror the Pydantic AudienceSegment shape (research_state.py:986).
    // pain_point_alignment is the most actionable; fall back to motivation_drivers.
    const bullets: string[] = [];
    for (const key of ['pain_point_alignment', 'motivation_drivers', 'discovery_channels']) {
      const arr = (s as Record<string, unknown>)[key];
      if (Array.isArray(arr)) {
        for (const item of arr) {
          if (typeof item === 'string' && bullets.length < 3) bullets.push(item);
        }
      }
      if (bullets.length >= 3) break;
    }
    const sizeLabel =
      typeof s.size_estimate === 'string'
        ? s.size_estimate
        : typeof s.size_label === 'string'
          ? s.size_label
          : null;
    const expertiseLevel = typeof s.expertise_level === 'string' ? s.expertise_level : null;
    const budgetSensitivity = typeof s.budget_sensitivity === 'string' ? s.budget_sensitivity : null;
    out.push({ name, sizeLabel, bullets, expertiseLevel, budgetSensitivity });
  }
  return out.length > 0 ? out : null;
}

/** Pull competitor summaries from researchContext.competitorProfiles. */
function flattenCompetitors(
  ctx: { competitorProfiles?: unknown } | null,
): CatalogCompetitorSummary[] | null {
  if (!ctx?.competitorProfiles || !Array.isArray(ctx.competitorProfiles)) return null;
  const out: CatalogCompetitorSummary[] = [];
  for (const c of ctx.competitorProfiles as Array<Record<string, unknown>>) {
    if (!c || typeof c !== 'object') continue;
    const name = typeof c.name === 'string' ? c.name : null;
    if (!name) continue;
    // Normalize position to one of leader/challenger/niche; null if unrecognized.
    let position: 'leader' | 'challenger' | 'niche' | null = null;
    if (typeof c.position === 'string') {
      const p = c.position.trim().toLowerCase();
      if (p === 'leader' || p === 'challenger' || p === 'niche') position = p;
    }
    out.push({
      name,
      url: typeof c.url === 'string' ? c.url : null,
      competitorType: typeof c.competitor_type === 'string' ? c.competitor_type : null,
      description: typeof c.description === 'string' ? c.description : '',
      keyFeatures: Array.isArray(c.key_features)
        ? (c.key_features as unknown[]).filter((f): f is string => typeof f === 'string')
        : [],
      pricingModel: typeof c.pricing_model === 'string' ? c.pricing_model : null,
      strengths: Array.isArray(c.strengths)
        ? (c.strengths as unknown[]).filter((f): f is string => typeof f === 'string')
        : [],
      weaknesses: Array.isArray(c.weaknesses)
        ? (c.weaknesses as unknown[]).filter((f): f is string => typeof f === 'string')
        : [],
      position,
    });
  }
  return out.length > 0 ? out : null;
}

/** Pull keyword clusters from researchContext.keywordClusters (Phase 5.4 column). */
function flattenKeywordClusters(
  ctx: { keywordClusters?: unknown } | null,
): CatalogKeywordClusterSummary[] | null {
  if (!ctx?.keywordClusters || !Array.isArray(ctx.keywordClusters)) return null;
  const out: CatalogKeywordClusterSummary[] = [];
  for (const c of ctx.keywordClusters as Array<Record<string, unknown>>) {
    if (!c || typeof c !== 'object') continue;
    const name = typeof c.cluster_name === 'string' ? c.cluster_name : null;
    if (!name) continue;
    const supporting = Array.isArray(c.supporting_keywords)
      ? (c.supporting_keywords as unknown[]).filter((k): k is string => typeof k === 'string')
      : [];
    out.push({
      name,
      primaryKeyword: typeof c.primary_keyword === 'string' ? c.primary_keyword : null,
      totalSearchVolume: typeof c.total_monthly_volume === 'number' ? c.total_monthly_volume : 0,
      contentRecommendation: typeof c.content_recommendation === 'string' ? c.content_recommendation : null,
      estimatedTrafficPotential:
        typeof c.estimated_traffic_potential === 'string' ? c.estimated_traffic_potential : null,
      priority: typeof c.priority === 'number' ? c.priority : null,
      // Per-keyword volume/difficulty placeholders — pipeline doesn't yet
      // populate per-keyword metrics on TopicCluster. Reserved for future.
      keywords: supporting.map((term) => ({
        term,
        volume: 0,
        difficulty: bucketKeywordDifficulty(null),
      })),
    });
  }
  return out.length > 0 ? out : null;
}

/** Pull per-subreddit source counts from researchContext.topSubreddits. */
function flattenSubredditSources(
  ctx: { topSubreddits?: unknown } | null,
): CatalogSubredditSource[] | null {
  if (!ctx?.topSubreddits || !Array.isArray(ctx.topSubreddits)) return null;
  const out: CatalogSubredditSource[] = [];
  for (const s of ctx.topSubreddits as Array<Record<string, unknown>>) {
    if (!s || typeof s !== 'object') continue;
    const name = typeof s.name === 'string' ? s.name : null;
    if (!name) continue;
    const postCount = typeof s.post_count === 'number' ? s.post_count : 0;
    out.push({ name, postCount });
  }
  return out.length > 0 ? out : null;
}

/**
 * Two-track sources metric. `contentItemsMined` is total posts/threads
 * analyzed; `sourceCommunities` is the count of distinct platform communities.
 * Per scope rule, these are NOT summed into one number.
 */
function deriveSourcesMetric(ctx: {
  redditPostsAnalyzed?: number | null;
  twitterThreadsAnalyzed?: number | null;
  genericPostsAnalyzed?: number | null;
  topSubreddits?: unknown;
} | null): { contentItemsMined: number; sourceCommunities: number } {
  if (!ctx) return { contentItemsMined: 0, sourceCommunities: 0 };
  const reddit = ctx.redditPostsAnalyzed ?? 0;
  const twitter = ctx.twitterThreadsAnalyzed ?? 0;
  const generic = ctx.genericPostsAnalyzed ?? 0;
  const subreddits = Array.isArray(ctx.topSubreddits) ? ctx.topSubreddits.length : 0;
  return {
    contentItemsMined: reddit + twitter + generic,
    sourceCommunities: subreddits,
  };
}

// ============================================
// Phase 5.5 — niche / audience-signals / quality flatten helpers
// ============================================

/** Pull niche-context blob from researchContext.nicheContext column. */
function flattenNicheContext(
  ctx: { nicheContext?: unknown } | null,
): CatalogNicheContextSummary | null {
  if (!ctx?.nicheContext || typeof ctx.nicheContext !== 'object') return null;
  const c = ctx.nicheContext as Record<string, unknown>;
  const description = typeof c.description === 'string' ? c.description : null;
  const industryBoundaries = typeof c.industryBoundaries === 'string' ? c.industryBoundaries : null;
  const marketSegments = Array.isArray(c.marketSegments)
    ? (c.marketSegments as unknown[]).filter((s): s is string => typeof s === 'string')
    : null;
  if (!description && !industryBoundaries && !marketSegments) return null;
  return { description, industryBoundaries, marketSegments };
}

/**
 * Pull rich audience-signal sub-fields from the EXISTING `audienceMapping`
 * column (no new projection needed — these 8 fields are already inside the
 * full AudienceMappingResult.model_dump() blob, 11/11 in real preview reports).
 *
 * Pydantic types per research_state.py:1042-1057:
 *   - common_vocabulary, frustrations_with_existing, tools_currently_used,
 *     community_hubs, recommended_channels, messaging_frameworks: list[str] (required)
 *   - content_preferences: str (required)
 *   - early_adopter_tactics: Optional[str]
 */
function flattenAudienceSignals(
  ctx: { audienceMapping?: unknown } | null,
): CatalogAudienceSignalsSummary | null {
  if (!ctx?.audienceMapping || typeof ctx.audienceMapping !== 'object') return null;
  const am = ctx.audienceMapping as Record<string, unknown>;
  const stringList = (key: string): string[] =>
    Array.isArray(am[key])
      ? (am[key] as unknown[]).filter((s): s is string => typeof s === 'string')
      : [];
  const stringOrNull = (key: string): string | null =>
    typeof am[key] === 'string' ? (am[key] as string) : null;

  const out: CatalogAudienceSignalsSummary = {
    vocabulary: stringList('common_vocabulary'),
    frustrations: stringList('frustrations_with_existing'),
    currentTools: stringList('tools_currently_used'),
    communityHubs: stringList('community_hubs'),
    recommendedChannels: stringList('recommended_channels'),
    messagingFrameworks: stringList('messaging_frameworks'),
    contentPreferences: stringOrNull('content_preferences'),
    earlyAdopterTactics: stringOrNull('early_adopter_tactics'),
  };
  // Return null when every field is empty (legacy rows without audienceMapping).
  const hasAny =
    out.vocabulary.length > 0 ||
    out.frustrations.length > 0 ||
    out.currentTools.length > 0 ||
    out.communityHubs.length > 0 ||
    out.recommendedChannels.length > 0 ||
    out.messagingFrameworks.length > 0 ||
    !!out.contentPreferences ||
    !!out.earlyAdopterTactics;
  return hasAny ? out : null;
}

/**
 * Pull quality signals from the projected `qualitySignals` column. Shape was
 * built by extractQualitySignals in researchContextService.
 */
function flattenQualitySignals(
  ctx: { qualitySignals?: unknown } | null,
): CatalogQualitySignalsSummary | null {
  if (!ctx?.qualitySignals || typeof ctx.qualitySignals !== 'object') return null;
  const q = ctx.qualitySignals as Record<string, unknown>;
  const contentTier = typeof q.contentTier === 'string' ? q.contentTier : null;
  const painPointTier = typeof q.painPointTier === 'string' ? q.painPointTier : null;
  const confidenceScore = typeof q.confidenceScore === 'number' ? q.confidenceScore : null;
  const overallDataQuality = typeof q.overallDataQuality === 'string' ? q.overallDataQuality : null;
  let engagementMetrics: { totalEngagement: number; avgEngagementPerSource: number } | null = null;
  if (q.engagementMetrics && typeof q.engagementMetrics === 'object') {
    const em = q.engagementMetrics as Record<string, unknown>;
    const total = typeof em.totalEngagement === 'number' ? em.totalEngagement : null;
    const avg = typeof em.avgEngagementPerSource === 'number' ? em.avgEngagementPerSource : null;
    if (total != null) engagementMetrics = { totalEngagement: total, avgEngagementPerSource: avg ?? 0 };
  }
  if (!contentTier && !painPointTier && confidenceScore == null && !overallDataQuality && !engagementMetrics) {
    return null;
  }
  return { contentTier, painPointTier, confidenceScore, overallDataQuality, engagementMetrics };
}

const TOP_PREVIEW_LIMIT = 6;

async function buildCategoryLandingPayload(
  categoryId: string,
): Promise<CategoryLandingPayload | null> {
  const category = await prisma.catalogCategory.findUnique({
    where: { id: categoryId },
    include: {
      parent: { select: { id: true, name: true, slug: true, parentId: true } },
      superGroup: { select: { id: true, name: true, slug: true } },
      children: {
        where: { isActive: true },
        orderBy: { sortOrder: 'asc' },
        select: {
          id: true,
          name: true,
          slug: true,
          description: true,
          _count: {
            select: {
              ideas: { where: { isActive: true } },
              painPoints: { where: { isActive: true } },
            },
          },
        },
      },
    },
  });

  if (!category) return null;

  const childIds = category.children.map((c) => c.id);
  const aggregateIds = [category.id, ...childIds];

  const [topIdeasRaw, topPainPointsRaw, totalIdeas, totalPainPoints, verdictGoCount, siblingsRaw] = await Promise.all([
    prisma.catalogIdea.findMany({
      where: { isActive: true, slug: { not: null }, categoryId: { in: aggregateIds } },
      include: { category: { select: { id: true, name: true, slug: true } } },
      orderBy: [{ marketFitScore: 'desc' }, { createdAt: 'desc' }],
      take: TOP_PREVIEW_LIMIT,
    }),
    prisma.catalogPainPoint.findMany({
      where: { isActive: true, slug: { not: null }, categoryId: { in: aggregateIds } },
      include: { category: { select: { id: true, name: true, slug: true } } },
      orderBy: [{ severityScore: 'desc' }, { createdAt: 'desc' }],
      take: TOP_PREVIEW_LIMIT,
    }),
    prisma.catalogIdea.count({ where: { isActive: true, categoryId: { in: aggregateIds } } }),
    prisma.catalogPainPoint.count({ where: { isActive: true, categoryId: { in: aggregateIds } } }),
    // Phase 15.5 — backend-aggregate count of GO-verdict ideas, not just visible
    // top set. Frontend hides the tile when 0; non-zero render is truthful.
    prisma.catalogIdea.count({
      where: { isActive: true, categoryId: { in: aggregateIds }, sourceVerdict: 'GO' },
    }),
    category.parentId
      ? prisma.catalogCategory.findMany({
          where: {
            isActive: true,
            parentId: category.parentId,
            id: { not: category.id },
          },
          select: { id: true, name: true, slug: true },
          orderBy: { sortOrder: 'asc' },
          take: 12,
        })
      : Promise.resolve([]),
  ]);

  const topIdeas = topIdeasRaw.map(({ sourceJobId: _s, publishedById: _p, ...rest }) => toIdeaPreview(rest));
  const topPainPoints = topPainPointsRaw.map(({ sourceJobId: _s, publishedById: _p, ...rest }) => rest);

  // Phase 5: Attach the most-recent published item's research context so the
  // category landing renders the same Audience/Market/Trend sections as
  // detail pages, framed as "Analysis from latest research in this niche."
  const recentItem = await findMostRecentItemSourceJobId(aggregateIds);
  const researchContext = recentItem
    ? await prisma.catalogResearchContext.findUnique({ where: { sourceJobId: recentItem } })
    : null;
  // Phase 5.4: render only when there's meaningful (non-timestamp-only)
  // projected data. Materializer always writes timestamps so we can't gate
  // on tier or single-field presence alone.
  const researchContextOrNull =
    researchContext && hasMeaningfulResearchContext(researchContext)
      ? (researchContext as unknown as Record<string, unknown>)
      : null;

  // Phase 5.4 — derive flattened summaries from the same researchContext that
  // backs the heavy researchContext field below. The researchContextOrNull
  // gate above means: when there's no meaningful context, all summary fields
  // are null. This keeps the contract simple — components do `{#if themes}`
  // and never need to inspect researchContext directly.
  const ctxForSummaries = researchContextOrNull ? (researchContext ?? null) : null;
  const themes = flattenThemes(ctxForSummaries);
  const audienceSegments = flattenAudienceSegments(ctxForSummaries);
  const competitors = flattenCompetitors(ctxForSummaries);
  const keywordClusters = flattenKeywordClusters(ctxForSummaries);
  const subredditSources = flattenSubredditSources(ctxForSummaries);
  const { contentItemsMined, sourceCommunities } = deriveSourcesMetric(ctxForSummaries);
  // Phase 5.5 — niche / audience-signals / quality / pain-analysis prose.
  const nicheContext = flattenNicheContext(ctxForSummaries);
  const audienceSignals = flattenAudienceSignals(ctxForSummaries);
  const qualitySignals = flattenQualitySignals(ctxForSummaries);
  const categorizationSummary = ctxForSummaries?.categorizationSummary ?? null;
  const painAnalysisSummary = ctxForSummaries?.painAnalysisSummary ?? null;
  const topPainCategories = Array.isArray(ctxForSummaries?.topPainCategories)
    ? (ctxForSummaries?.topPainCategories as unknown[]).filter((s): s is string => typeof s === 'string')
    : null;
  // Phase 14 — niche-wide top reddit threads. Niche page renders all 5
  // (uncapped). Pain page caps at 3 separately in getPainPointBySlug.
  const topRedditThreads = flattenTopRedditThreads(ctxForSummaries);

  return {
    category: {
      id: category.id,
      name: category.name,
      slug: category.slug,
      description: category.description,
      seoTitle: category.seoTitle,
      seoDescription: category.seoDescription,
      longDescription: category.longDescription,
      faqJson: category.faqJson,
      tags: category.tags ?? [],
      isActive: category.isActive,
      createdAt: category.createdAt.toISOString(),
      updatedAt: category.updatedAt.toISOString(),
    },
    parent: category.parent
      ? { id: category.parent.id, name: category.parent.name, slug: category.parent.slug }
      : null,
    superGroup: category.superGroup,
    children: category.children.map((c) => ({
      id: c.id,
      name: c.name,
      slug: c.slug,
      description: c.description,
      ideaCount: c._count.ideas,
      painPointCount: c._count.painPoints,
    })),
    siblings: siblingsRaw,
    topIdeas,
    topPainPoints,
    totalIdeas,
    totalPainPoints,
    // v1: hardcode the source platforms NicheIQ currently ingests from. Kept
    // for back-compat with existing landing-payload consumers — new UI uses
    // contentItemsMined + sourceCommunities below.
    sources: ['Reddit', 'Hacker News'],
    // Phase 15.5 — backend-aggregate count (whole category subtree).
    verdictGoCount,
    // Phase 5.4 — flattened summaries.
    themes,
    audienceSegments,
    competitors,
    keywordClusters,
    subredditSources,
    contentItemsMined,
    sourceCommunities,
    growthPercent: null,  // Reserved — pipeline doesn't compute per-category growth yet.
    // Phase 5.5 — catalog page enrichment.
    nicheContext,
    audienceSignals,
    qualitySignals,
    categorizationSummary,
    painAnalysisSummary,
    topPainCategories,
    // Phase 14 — top reddit threads (uncapped on niche page).
    topRedditThreads,
    researchContext: researchContextOrNull,
  };
}

/**
 * Phase 5 helper: returns the sourceJobId of the most-recently-published
 * active CatalogIdea or CatalogPainPoint inside the given category subtree
 * (categoryId or any of its child categoryIds), or null if there are no
 * active items.
 *
 * Pragmatic over precise — top-level categories aggregate "the most recent
 * research in this niche" rather than blending analysis from every job. The
 * frontend frames it as such ("Analysis from latest research in this niche").
 */
async function findMostRecentItemSourceJobId(
  categoryIds: string[],
): Promise<string | null> {
  if (categoryIds.length === 0) return null;

  // Raw SQL because Prisma's orderBy can't COALESCE. Lineage timestamp is
  // sourceGeneratedAt (set by worker), with updatedAt + createdAt fallbacks
  // for legacy rows. Postgres preserves camelCase column names when quoted.
  const rows = await prisma.$queryRaw<{ source_job_id: string }[]>`
    SELECT source_job_id
    FROM (
      SELECT
        "sourceJobId" AS source_job_id,
        COALESCE("sourceGeneratedAt", "updatedAt", "createdAt") AS effective_ts
      FROM "CatalogIdea"
      WHERE "isActive" = true AND "categoryId" IN (${Prisma.join(categoryIds)})
      UNION ALL
      SELECT
        "sourceJobId" AS source_job_id,
        COALESCE("sourceGeneratedAt", "updatedAt", "createdAt") AS effective_ts
      FROM "CatalogPainPoint"
      WHERE "isActive" = true AND "categoryId" IN (${Prisma.join(categoryIds)})
    ) AS combined
    ORDER BY effective_ts DESC
    LIMIT 1
  `;

  return rows[0]?.source_job_id ?? null;
}

/**
 * Resolve a public landing-page payload by URL slug tuple.
 *
 * - parentSlug only → top-level category (parentId IS NULL).
 * - parentSlug + childSlug → nested category with that (parent, child) tuple.
 *
 * Returns `null` for unknown slug, `{ inactive: true }` for an inactive category
 * (caller should respond 410 Gone).
 */
export async function getCategoryLanding(args: {
  parentSlug: string;
  childSlug?: string | null;
}): Promise<CategoryLandingPayload | { inactive: true } | null> {
  const cacheKey = landingCacheKey(args.parentSlug, args.childSlug);
  const redis = getRedis();

  try {
    const cached = await redis.get(cacheKey);
    if (cached) {
      return JSON.parse(cached) as CategoryLandingPayload;
    }
  } catch (err) {
    console.error('Landing cache read failed:', err);
  }

  let category: { id: string; isActive: boolean } | null;
  if (args.childSlug) {
    const parent = await prisma.catalogCategory.findFirst({
      where: { parentId: null, slug: args.parentSlug },
      select: { id: true },
    });
    if (!parent) return null;
    category = await prisma.catalogCategory.findFirst({
      where: { parentId: parent.id, slug: args.childSlug },
      select: { id: true, isActive: true },
    });
  } else {
    category = await prisma.catalogCategory.findFirst({
      where: { parentId: null, slug: args.parentSlug },
      select: { id: true, isActive: true },
    });
  }

  if (!category) return null;
  if (!category.isActive) return { inactive: true };

  const payload = await buildCategoryLandingPayload(category.id);
  if (!payload) return null;

  try {
    await redis.setex(cacheKey, jitteredTtl(), JSON.stringify(payload));
  } catch (err) {
    console.error('Landing cache write failed:', err);
  }

  return payload;
}

// ============================================
// Phase 2 — Detail-page cross-link helpers
// ============================================

/**
 * Find pain points sharing the same parent theme as the current pain.
 * Returns [] when themeId is null (legacy rows) — section hides gracefully.
 */
async function getSiblingPainPoints(
  themeId: string | null,
  excludeId: string,
  categoryId: string,
  limit = 5,
): Promise<SiblingPainSummary[]> {
  if (!themeId) return [];
  const rows = await prisma.catalogPainPoint.findMany({
    where: {
      themeId,
      id: { not: excludeId },
      categoryId,
      isActive: true,
      slug: { not: null },           // schema:626 — slug is String?
    },
    orderBy: [{ severityScore: 'desc' }, { mentionCount: 'desc' }],
    take: limit,
    select: {
      slug: true,
      title: true,
      description: true,
      severityScore: true,
      mentionCount: true,
      opportunityLevel: true,
    },
  });
  // After the slug-not-null filter, slug is still typed as `string | null` by
  // Prisma. Coerce post-filter — guarantee non-null contract for SiblingPainSummary.
  return rows
    .filter((r): r is typeof r & { slug: string } => r.slug !== null)
    .map((r) => ({
      slug: r.slug,
      title: r.title,
      description: r.description,
      severityScore: r.severityScore,
      mentionCount: r.mentionCount,
      opportunityLevel: r.opportunityLevel,
    }));
}

/**
 * Find catalog ideas whose addressedPainTitles array contains the given pain
 * title. Scoped to a single sub-niche (categoryId) to prevent cross-niche bleed.
 */
async function getIdeasAddressingPain(
  painTitle: string,
  categoryId: string,
  excludeIds: string[] = [],
  limit = 5,
) {
  const rows = await prisma.catalogIdea.findMany({
    where: {
      isActive: true,
      categoryId,
      id: { notIn: excludeIds },
      slug: { not: null },           // schema:555 — slug is String?
      addressedPainTitles: { has: painTitle },  // GIN-indexed array contains
    },
    orderBy: [{ isFeatured: 'desc' }, { marketFitScore: 'desc' }],
    take: limit,
    include: {
      category: {
        select: {
          id: true,
          name: true,
          slug: true,
          parent: { select: { name: true, slug: true } },
        },
      },
    },
  });
  return rows
    .filter((r): r is typeof r & { slug: string } => r.slug !== null)
    .map((r) => toIdeaPreview(r));
  // Note: `addressedPainTitles` is intentionally NOT included in the
  // toIdeaPreview() whitelist (line ~997) — sibling/related idea cards don't
  // display it. Silent drop is correct.
}

/**
 * Find other catalog ideas in the same sub-niche.
 */
async function getSiblingIdeas(
  categoryId: string,
  excludeId: string,
  limit = 5,
) {
  const rows = await prisma.catalogIdea.findMany({
    where: {
      categoryId,
      id: { not: excludeId },
      isActive: true,
      slug: { not: null },           // schema:555
    },
    orderBy: [{ isFeatured: 'desc' }, { marketFitScore: 'desc' }],
    take: limit,
    include: {
      category: {
        select: {
          id: true,
          name: true,
          slug: true,
          parent: { select: { name: true, slug: true } },
        },
      },
    },
  });
  return rows
    .filter((r): r is typeof r & { slug: string } => r.slug !== null)
    .map((r) => toIdeaPreview(r));
}

/**
 * Resolve a list of pain titles into their canonical CatalogPainPoint slugs +
 * severity/mention metadata. Used by the idea page to upgrade
 * `r.detailedPainPoints` entries into linked cards.
 *
 * v1 uses exact-title match scoped to the same categoryId. If logs show
 * frequent unresolved titles, lift `normalizeTitle` from workers.ts and apply
 * normalize-fallback (see plan Phase 2 risk note).
 */
async function resolvePainPointSlugs(
  painTitles: string[],
  categoryId: string,
): Promise<AddressedPainLookup> {
  if (!Array.isArray(painTitles) || painTitles.length === 0) return {};
  const rows = await prisma.catalogPainPoint.findMany({
    where: {
      title: { in: painTitles },
      categoryId,
      isActive: true,
      slug: { not: null },
    },
    select: { title: true, slug: true, severityScore: true, mentionCount: true },
  });
  const out: AddressedPainLookup = {};
  for (const r of rows) {
    if (r.slug == null) continue;
    // Pick the FIRST match per title — collision is rare (same title within
    // one categoryId). Log a guardrail when it happens so we can investigate.
    if (out[r.title]) {
      console.warn(
        `[resolvePainPointSlugs] Title collision in categoryId=${categoryId}: "${r.title}" — picking first match`,
      );
      continue;
    }
    out[r.title] = {
      slug: r.slug,
      severityScore: r.severityScore,
      mentionCount: r.mentionCount,
    };
  }
  return out;
}

// =============================================================================
// Phase 14 — source-grounded evidence + comparative ranking helpers.
// =============================================================================

/**
 * Compute a pain point's rank within its sub-niche by severity. Returns
 * { rank: 1..N, total: N }, or null when the pain doesn't appear in the
 * category's active set (defensive — shouldn't happen).
 */
async function getPainPointRank(
  painId: string,
  categoryId: string,
): Promise<{ rank: number; total: number } | null> {
  const all = await prisma.catalogPainPoint.findMany({
    where: { categoryId, isActive: true },
    select: { id: true, severityScore: true, mentionCount: true },
    orderBy: [{ severityScore: 'desc' }, { mentionCount: 'desc' }],
  });
  if (all.length === 0) return null;
  const idx = all.findIndex((p) => p.id === painId);
  if (idx === -1) return null;
  return { rank: idx + 1, total: all.length };
}

/**
 * Resolve the per-quote source-attribution for a given pain by matching its
 * title against entries in researchContext.painPointQuoteSources.
 *
 * v1 uses exact match first, then a normalized fallback (lowercase + strip
 * non-alphanumeric) to survive worker-merge title drift (same Phase 11 risk).
 * Returns sources sorted by score desc — highest-upvote quotes first.
 */
function resolveQuoteSourcesForPain(
  painPointQuoteSources: unknown,
  painTitle: string,
): QuoteSource[] | null {
  if (!painPointQuoteSources || typeof painPointQuoteSources !== 'object') return null;
  const sources = painPointQuoteSources as Record<string, unknown>;
  const normalize = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, '');
  const target = painTitle.trim();
  const targetNorm = normalize(target);

  // Exact match first.
  for (const entry of Object.values(sources)) {
    if (!entry || typeof entry !== 'object') continue;
    const e = entry as Record<string, unknown>;
    if (typeof e.pain_point_title !== 'string') continue;
    if (e.pain_point_title.trim() === target) {
      return mapToQuoteSources(e.quotes_with_sources);
    }
  }
  // Normalized fallback.
  for (const entry of Object.values(sources)) {
    if (!entry || typeof entry !== 'object') continue;
    const e = entry as Record<string, unknown>;
    if (typeof e.pain_point_title !== 'string') continue;
    if (normalize(e.pain_point_title) === targetNorm) {
      return mapToQuoteSources(e.quotes_with_sources);
    }
  }
  return null;
}

function mapToQuoteSources(raw: unknown): QuoteSource[] | null {
  if (!Array.isArray(raw)) return null;
  const out: QuoteSource[] = [];
  for (const r of raw) {
    if (!r || typeof r !== 'object') continue;
    const o = r as Record<string, unknown>;
    if (typeof o.quote !== 'string' || typeof o.post_id !== 'string' || typeof o.subreddit !== 'string') continue;
    out.push({
      quote: o.quote,
      postId: o.post_id,
      subreddit: o.subreddit,
      score: typeof o.score === 'number' ? o.score : Number(o.score) || 0,
    });
  }
  out.sort((a, b) => b.score - a.score);
  return out.length > 0 ? out : null;
}

/**
 * Flatten researchContext.topRedditThreads (snake_case from projection) into
 * camelCase shapes expected by the public API. Returns null when missing/empty.
 */
function flattenTopRedditThreads(
  ctx: { topRedditThreads?: unknown } | null,
): CatalogTopRedditThread[] | null {
  if (!ctx?.topRedditThreads || !Array.isArray(ctx.topRedditThreads)) return null;
  const out: CatalogTopRedditThread[] = [];
  for (const t of ctx.topRedditThreads) {
    if (!t || typeof t !== 'object') continue;
    const o = t as Record<string, unknown>;
    if (typeof o.post_id !== 'string' || typeof o.title !== 'string' || typeof o.url !== 'string') continue;
    out.push({
      postId: o.post_id,
      title: o.title,
      subreddit: typeof o.subreddit === 'string' ? o.subreddit : '',
      score: typeof o.score === 'number' ? o.score : Number(o.score) || 0,
      numComments: typeof o.num_comments === 'number' ? o.num_comments : Number(o.num_comments) || 0,
      url: o.url,
      keyInsight: typeof o.key_insight === 'string' ? o.key_insight : '',
    });
  }
  return out.length > 0 ? out : null;
}

export async function getIdeaBySlug(slug: string) {
  const idea = await prisma.catalogIdea.findFirst({
    where: { slug, isActive: true },
    include: {
      category: {
        select: {
          id: true,
          name: true,
          slug: true,
          parent: { select: { name: true, slug: true } },
        },
      },
      researchContext: true,
    },
  });
  if (!idea) return null;
  const { sourceJobId: _s, publishedById: _p, researchContext, ...rest } = idea;
  const preview = toIdeaPreview(rest);
  // Phase 5.4 — surface flattened summaries alongside the full researchContext.
  // Detail pages get BOTH (the heavy nested object AND the flat summaries) so
  // components can read either depending on what they need.
  const ctx = researchContext;

  // Phase 2 of detail-page IA rework — cross-link joins.
  // Run in parallel with a single Promise.all to keep request latency flat.
  const [siblingIdeas, addressedPains] = await Promise.all([
    getSiblingIdeas(idea.categoryId, idea.id),
    resolvePainPointSlugs(idea.addressedPainTitles, idea.categoryId),
  ]);

  return {
    ...preview,
    researchContext,
    themes: flattenThemes(ctx),
    audienceSegments: flattenAudienceSegments(ctx),
    competitors: flattenCompetitors(ctx),
    keywordClusters: flattenKeywordClusters(ctx),
    subredditSources: flattenSubredditSources(ctx),
    ...deriveSourcesMetric(ctx),
    // Phase 5.5 — catalog page enrichment.
    nicheContext: flattenNicheContext(ctx),
    audienceSignals: flattenAudienceSignals(ctx),
    qualitySignals: flattenQualitySignals(ctx),
    categorizationSummary: ctx?.categorizationSummary ?? null,
    painAnalysisSummary: ctx?.painAnalysisSummary ?? null,
    topPainCategories: Array.isArray(ctx?.topPainCategories)
      ? (ctx?.topPainCategories as unknown[]).filter((s): s is string => typeof s === 'string')
      : null,
    // Phase 2 — detail-page IA cross-links.
    siblingIdeas,
    addressedPains,
  };
}

export async function getPainPointBySlug(slug: string) {
  const pp = await prisma.catalogPainPoint.findFirst({
    where: { slug, isActive: true },
    include: {
      category: {
        select: {
          id: true,
          name: true,
          slug: true,
          parent: { select: { name: true, slug: true } },
        },
      },
      researchContext: true,
    },
  });
  if (!pp) return null;
  const { sourceJobId: _s, publishedById: _p, researchContext, ...rest } = pp;
  // Phase 5.4 — same flattened summaries as the idea detail endpoint. Pain-point
  // preview shape is camelCase already (legacy convention) so summaries fit
  // alongside without case mixing.
  const ctx = researchContext;

  // Phase 2 of detail-page IA rework — cross-link joins.
  // Phase 14 adds rankInfo, source-grounded quote attribution, and top
  // Reddit threads. All run in parallel so request latency stays flat.
  const [siblingPains, relatedIdeas, rankInfo] = await Promise.all([
    getSiblingPainPoints(pp.themeId, pp.id, pp.categoryId),
    getIdeasAddressingPain(pp.title, pp.categoryId),
    getPainPointRank(pp.id, pp.categoryId),
  ]);

  const quoteSources = resolveQuoteSourcesForPain(ctx?.painPointQuoteSources, pp.title);
  const topRedditThreadsAll = flattenTopRedditThreads(ctx);
  // Pain page caps the niche-wide threads to top 3 — niche page renders all 5.
  const topRedditThreads = topRedditThreadsAll?.slice(0, 3) ?? null;

  return {
    ...rest,
    researchContext,
    themes: flattenThemes(ctx),
    audienceSegments: flattenAudienceSegments(ctx),
    competitors: flattenCompetitors(ctx),
    keywordClusters: flattenKeywordClusters(ctx),
    subredditSources: flattenSubredditSources(ctx),
    ...deriveSourcesMetric(ctx),
    // Phase 5.5 — catalog page enrichment.
    nicheContext: flattenNicheContext(ctx),
    audienceSignals: flattenAudienceSignals(ctx),
    qualitySignals: flattenQualitySignals(ctx),
    categorizationSummary: ctx?.categorizationSummary ?? null,
    painAnalysisSummary: ctx?.painAnalysisSummary ?? null,
    topPainCategories: Array.isArray(ctx?.topPainCategories)
      ? (ctx?.topPainCategories as unknown[]).filter((s): s is string => typeof s === 'string')
      : null,
    // Phase 2 — detail-page IA cross-links.
    siblingPains,
    relatedIdeas,
    // Phase 14 — source-grounded evidence + comparative ranking.
    quoteSources,
    rankInfo,
    topRedditThreads,
  };
}

interface SitemapEntry {
  slug: string;
  parentSlug: string | null;
  updatedAt: string;
  ideaCount: number;
  painPointCount: number;
}

/**
 * Sitemap data for active categories. Frontend `sitemap.xml/+server.ts` consumes
 * this to emit `/ideas/{niche}` and `/ideas/{niche}/{sub}` URLs.
 */
export async function getCategorySitemapEntries(): Promise<SitemapEntry[]> {
  const categories = await prisma.catalogCategory.findMany({
    where: { isActive: true },
    select: {
      slug: true,
      updatedAt: true,
      parent: { select: { slug: true } },
      _count: {
        select: {
          ideas: { where: { isActive: true } },
          painPoints: { where: { isActive: true } },
        },
      },
    },
    orderBy: [{ parentId: 'asc' }, { sortOrder: 'asc' }],
  });

  return categories.map((c) => ({
    slug: c.slug,
    parentSlug: c.parent?.slug ?? null,
    updatedAt: c.updatedAt.toISOString(),
    ideaCount: c._count.ideas,
    painPointCount: c._count.painPoints,
  }));
}

interface IdeaSitemapEntry {
  slug: string;
  updatedAt: string;
}

export async function getIdeaSitemapEntries(): Promise<IdeaSitemapEntry[]> {
  const ideas = await prisma.catalogIdea.findMany({
    where: { isActive: true, slug: { not: null } },
    select: { slug: true, updatedAt: true },
    orderBy: { updatedAt: 'desc' },
  });
  return ideas
    .filter((i): i is { slug: string; updatedAt: Date } => typeof i.slug === 'string')
    .map((i) => ({ slug: i.slug, updatedAt: i.updatedAt.toISOString() }));
}

export async function getPainPointSitemapEntries(): Promise<IdeaSitemapEntry[]> {
  const pps = await prisma.catalogPainPoint.findMany({
    where: { isActive: true, slug: { not: null } },
    select: { slug: true, updatedAt: true },
    orderBy: { updatedAt: 'desc' },
  });
  return pps
    .filter((p): p is { slug: string; updatedAt: Date } => typeof p.slug === 'string')
    .map((p) => ({ slug: p.slug, updatedAt: p.updatedAt.toISOString() }));
}

/**
 * Public categories tree (top-level + children with active counts) for the
 * `(public)/ideas/+layout.server.ts` loader. Wraps `listCategories(true)` with
 * a 5-minute Redis cache (`catalog:tree:v1`) so concurrent crawler hits don't
 * stampede Postgres.
 */
export async function getPublicCategoryTree() {
  const redis = getRedis();
  try {
    const cached = await redis.get(TREE_CACHE_KEY);
    if (cached) return JSON.parse(cached);
  } catch (err) {
    console.error('Tree cache read failed:', err);
  }

  const tree = await listCategories(true);

  try {
    await redis.setex(TREE_CACHE_KEY, TREE_CACHE_TTL, JSON.stringify(tree));
  } catch (err) {
    console.error('Tree cache write failed:', err);
  }
  return tree;
}

export async function invalidatePublicCategoryTree(): Promise<void> {
  try {
    await getRedis().del(TREE_CACHE_KEY);
  } catch (err) {
    console.error('Tree cache invalidate failed:', err);
  }
}

// =====================================================================
// Phase 5.4 — Catalog totals (index-page hero stat strip)
// =====================================================================

const TOTALS_CACHE_KEY = 'catalog:totals:v1';
const TOTALS_CACHE_TTL = 300;  // 5 min — same cadence as tree cache

interface CatalogTotals {
  totalIdeas: number;
  totalCategories: number;     // top-level (parentId IS NULL) — for the "Categories" tile
  totalSubcategories: number;  // child categories — for the "Sub-niches" tile
  // Per scope rule, this is content items (posts/threads) NOT communities.
  // Communities are per-niche on landing payloads, not aggregable globally.
  contentItemsMined: number;
}

/**
 * Aggregate counts shown on the public catalog index page hero stat strip.
 *
 * - `totalIdeas`         = active CatalogIdea rows
 * - `totalCategories`    = active top-level CatalogCategory rows (parentId IS NULL)
 * - `totalSubcategories` = active child CatalogCategory rows (parentId set)
 * - `contentItemsMined`  = sum of redditPostsAnalyzed + twitterThreadsAnalyzed
 *                          + genericPostsAnalyzed across all CatalogResearchContext rows
 *
 * Cached in Redis 5 min. Cache key invalidates on the same triggers as the
 * tree cache (category create/update/delete) — see invalidatePublicCategoryTree
 * callers.
 */
export async function getCatalogTotals(): Promise<CatalogTotals> {
  const redis = getRedis();
  try {
    const cached = await redis.get(TOTALS_CACHE_KEY);
    if (cached) return JSON.parse(cached) as CatalogTotals;
  } catch (err) {
    console.error('Totals cache read failed:', err);
  }

  const [totalIdeas, totalCategories, totalSubcategories, sumAgg] = await Promise.all([
    prisma.catalogIdea.count({ where: { isActive: true } }),
    prisma.catalogCategory.count({ where: { isActive: true, parentId: null } }),
    prisma.catalogCategory.count({ where: { isActive: true, parentId: { not: null } } }),
    prisma.catalogResearchContext.aggregate({
      _sum: {
        redditPostsAnalyzed: true,
        twitterThreadsAnalyzed: true,
        genericPostsAnalyzed: true,
      },
    }),
  ]);

  const contentItemsMined =
    (sumAgg._sum.redditPostsAnalyzed ?? 0) +
    (sumAgg._sum.twitterThreadsAnalyzed ?? 0) +
    (sumAgg._sum.genericPostsAnalyzed ?? 0);

  const totals: CatalogTotals = {
    totalIdeas,
    totalCategories,
    totalSubcategories,
    contentItemsMined,
  };

  try {
    await redis.setex(TOTALS_CACHE_KEY, TOTALS_CACHE_TTL, JSON.stringify(totals));
  } catch (err) {
    console.error('Totals cache write failed:', err);
  }
  return totals;
}

export async function invalidateCatalogTotals(): Promise<void> {
  try {
    await getRedis().del(TOTALS_CACHE_KEY);
  } catch (err) {
    console.error('Totals cache invalidate failed:', err);
  }
}

// =====================================================================
// Legacy URL → new URL redirect resolvers (Phase 3.4)
//
// Used by the SvelteKit `hooks.server.ts` 301-redirect layer to map every
// legacy `/catalog/*` URL to its new `/ideas/*` (or `/idea/*`,
// `/pain-point/*`) equivalent. Cached in Redis (24h positive / 1h negative)
// because crawler traffic is read-mostly. Cache invalidation lives inside
// `invalidateCategoryLanding` for category renames.
// =====================================================================

const LEGACY_REDIRECT_PREFIX = 'redirect:legacy:v1';
const LEGACY_TTL_HIT = 24 * 60 * 60; // 24 hours
const LEGACY_TTL_MISS = 60 * 60; // 1 hour (negative cache)

type LegacyKind = 'category' | 'idea' | 'pain-point';

function legacyKey(kind: LegacyKind, key: string): string {
  return `${LEGACY_REDIRECT_PREFIX}:${kind}:${key}`;
}

async function readLegacyCache(kind: LegacyKind, key: string): Promise<string | null | undefined> {
  try {
    const raw = await getRedis().get(legacyKey(kind, key));
    if (raw === null) return undefined; // cache miss (not yet looked up)
    if (raw === '') return null; // negative cache hit (looked up, no result)
    return raw;
  } catch (err) {
    console.error('legacy redirect cache read failed:', err);
    return undefined;
  }
}

async function writeLegacyCache(
  kind: LegacyKind,
  key: string,
  target: string | null,
): Promise<void> {
  try {
    const ttl = target ? LEGACY_TTL_HIT : LEGACY_TTL_MISS;
    await getRedis().setex(legacyKey(kind, key), ttl, target ?? '');
  } catch (err) {
    console.error('legacy redirect cache write failed:', err);
  }
}

/**
 * Resolve a legacy category slug to a new path.
 *
 * Order matters because the slug column is now parent-scoped (post-Phase-2.5):
 *  1. Prefer `legacySlug` — these were globally unique by construction, so
 *     a hit unambiguously identifies one category.
 *  2. Fall back to `slug` for top-level (`parentId IS NULL`) only — top-level
 *     slugs share a global namespace via the partial unique index. Bare
 *     child slug lookup is deliberately not attempted (would be ambiguous).
 *
 * Returns `null` for unknown / inactive categories.
 */
export async function resolveLegacyCategory(legacyKey: string): Promise<string | null> {
  const cached = await readLegacyCache('category', legacyKey);
  if (cached !== undefined) return cached;

  let cat = await prisma.catalogCategory.findFirst({
    where: { legacySlug: legacyKey, isActive: true },
    include: { parent: { select: { slug: true } } },
  });
  if (!cat) {
    cat = await prisma.catalogCategory.findFirst({
      where: { slug: legacyKey, parentId: null, isActive: true },
      include: { parent: { select: { slug: true } } },
    });
  }

  const target = cat
    ? cat.parent
      ? `/ideas/${cat.parent.slug}/${cat.slug}`
      : `/ideas/${cat.slug}`
    : null;

  await writeLegacyCache('category', legacyKey, target);
  return target;
}

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function resolveLegacyIdea(idOrSlug: string): Promise<string | null> {
  const cached = await readLegacyCache('idea', idOrSlug);
  if (cached !== undefined) return cached;

  const isUuid = UUID_RE.test(idOrSlug);
  const idea = await prisma.catalogIdea.findFirst({
    where: { ...(isUuid ? { id: idOrSlug } : { slug: idOrSlug }), isActive: true },
    select: { slug: true },
  });
  const target = idea?.slug ? `/idea/${idea.slug}` : null;
  await writeLegacyCache('idea', idOrSlug, target);
  return target;
}

export async function resolveLegacyPainPoint(idOrSlug: string): Promise<string | null> {
  const cached = await readLegacyCache('pain-point', idOrSlug);
  if (cached !== undefined) return cached;

  const isUuid = UUID_RE.test(idOrSlug);
  const pp = await prisma.catalogPainPoint.findFirst({
    where: { ...(isUuid ? { id: idOrSlug } : { slug: idOrSlug }), isActive: true },
    select: { slug: true },
  });
  const target = pp?.slug ? `/pain-point/${pp.slug}` : null;
  await writeLegacyCache('pain-point', idOrSlug, target);
  return target;
}

/**
 * Invalidate legacy-redirect cache entries for a category. Called when an
 * admin renames a category — both the old and new lookup keys must be evicted
 * so the redirect resolver re-queries the DB.
 */
export async function invalidateLegacyCategoryRedirect(keys: string[]): Promise<void> {
  if (keys.length === 0) return;
  try {
    await getRedis().del(...keys.map((k) => legacyKey('category', k)));
  } catch (err) {
    console.error('legacy redirect cache invalidate failed:', err);
  }
}
