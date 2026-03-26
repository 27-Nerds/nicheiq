import { readFileSync, existsSync } from 'fs';
import { z } from 'zod';
import { prisma } from './db.js';
import { getJobAsset } from './jobService.js';
import { AssetType } from '@prisma/client';
import { resolveAssetPath } from '../utils/assetPath.js';

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

async function generateUniqueSlug(name: string, parentSlug?: string): Promise<string> {
  const base = parentSlug ? `${parentSlug}-${slugify(name)}` : slugify(name);
  const existing = await prisma.catalogCategory.findUnique({ where: { slug: base } });
  if (!existing) return base;
  // Append numeric suffix
  for (let i = 2; i <= 100; i++) {
    const candidate = `${base}-${i}`;
    const exists = await prisma.catalogCategory.findUnique({ where: { slug: candidate } });
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
  if (data.slug) {
    const existing = await prisma.catalogCategory.findUnique({ where: { slug: data.slug } });
    if (existing) throw new Error('Slug already exists');
    slug = data.slug;
  } else {
    let parentSlug: string | undefined;
    if (data.parentId) {
      const parent = await prisma.catalogCategory.findUnique({ where: { id: data.parentId } });
      parentSlug = parent?.slug;
    }
    slug = await generateUniqueSlug(data.name, parentSlug);
  }

  return prisma.catalogCategory.create({
    data: {
      name: data.name,
      slug,
      description: data.description,
      parentId: data.parentId,
      sortOrder: data.sortOrder ?? 0,
    },
  });
}

export async function updateCategory(id: string, data: {
  name?: string;
  slug?: string;
  description?: string | null;
  parentId?: string | null;
  superGroupId?: string | null;
  sortOrder?: number;
  isActive?: boolean;
}) {
  // Two-level validation if changing parent
  if (data.parentId !== undefined && data.parentId !== null) {
    const parent = await prisma.catalogCategory.findUnique({ where: { id: data.parentId } });
    if (!parent) throw new Error('Parent category not found');
    if (parent.parentId) throw new Error('Cannot nest more than two levels');
    if (parent.id === id) throw new Error('Cannot set category as its own parent');
  }

  // Check slug uniqueness if changing
  if (data.slug) {
    const existing = await prisma.catalogCategory.findUnique({ where: { slug: data.slug } });
    if (existing && existing.id !== id) throw new Error('Slug already exists');
  }

  return prisma.catalogCategory.update({
    where: { id },
    data,
  });
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

  return prisma.catalogCategory.delete({ where: { id } });
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
  const verdict = report.executive_dashboard?.go_no_go_verdict?.verdict || null;
  const generatedAt = report.generated_at ? new Date(report.generated_at) : null;

  try {
    const idea = await prisma.$transaction(async (tx) => {
      const created = await tx.catalogIdea.create({
        data: {
          categoryId: params.categoryId,
          sourceJobId: params.sourceJobId,
          sourceNiche: report.niche || '',
          sourceVerdict: verdict,
          sourceGeneratedAt: generatedAt,
          sourceItemIndex: params.itemIndex,
          solutionName,
          description: (solution.description as string) || '',
          valueProposition: (solution.value_proposition as string) ?? null,
          projectType: (solution.project_type as string) ?? null,
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

  try {
    const painPoint = await prisma.$transaction(async (tx) => {
      const created = await tx.catalogPainPoint.create({
        data: {
          categoryId: params.categoryId,
          sourceJobId: params.sourceJobId,
          sourceNiche: report.niche || '',
          sourceGeneratedAt: generatedAt,
          sourceItemIndex: params.itemIndex,
          title: pp.title || `Pain Point ${params.itemIndex + 1}`,
          description: pp.description || '',
          mentionCount: pp.mention_count ?? 0,
          severityScore: pp.severity_score ?? 0,
          willingnessToPayScore: pp.willingness_to_pay ?? 0,
          opportunityLevel: pp.opportunity_level || 'medium',
          representativeQuotes: safeStringArray(pp.representative_quotes) || undefined,
          sourcePlatforms: safeStringArray(pp.source_platforms) || undefined,
          categories: safeStringArray(pp.categories) || undefined,
          affectedSegments: safeStringArray(pp.affected_segments) || undefined,
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
  return prisma.$transaction(async (tx) => {
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
}

export async function updateCatalogPainPoint(id: string, data: {
  categoryId?: string;
  isFeatured?: boolean;
  isActive?: boolean;
}) {
  return prisma.$transaction(async (tx) => {
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
}

// ============================================
// Depublish
// ============================================

export async function depublishIdea(id: string) {
  const idea = await prisma.catalogIdea.findUnique({ where: { id } });
  if (!idea) return null;

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

  return idea;
}

export async function depublishPainPoint(id: string) {
  const pp = await prisma.catalogPainPoint.findUnique({ where: { id } });
  if (!pp) return null;

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

  return pp;
}

// ============================================
// snake_case transform for SolutionPreview compat
// ============================================

function toIdeaPreview(idea: Record<string, any>) {
  return {
    id: idea.id,
    solution_name: idea.solutionName,
    description: idea.description,
    value_proposition: idea.valueProposition,
    project_type: idea.projectType,
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
    source_niche: idea.sourceNiche,
    source_verdict: idea.sourceVerdict,
    is_featured: idea.isFeatured,
    category: idea.category,
    created_at: idea.createdAt,
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
    const category = await prisma.catalogCategory.findUnique({
      where: { slug: params.categorySlug },
      include: { children: { select: { id: true } } },
    });
    if (category) {
      // Include parent and all children
      const categoryIds = [category.id, ...category.children.map(c => c.id)];
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
    const category = await prisma.catalogCategory.findUnique({
      where: { slug: params.categorySlug },
      include: { children: { select: { id: true } } },
    });
    if (category) {
      const categoryIds = [category.id, ...category.children.map(c => c.id)];
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
        solutionName: true,
        description: true,
        marketFitScore: true,
        category: { select: { name: true, slug: true } },
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
        title: true,
        description: true,
        severityScore: true,
        category: { select: { name: true, slug: true } },
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
      isParent: !c.parentId,
      ideaCount: c._count.ideas,
      painPointCount: c._count.painPoints,
      childCount: c._count.children,
    })),
    ideas: ideas.map(i => ({
      id: i.id,
      solution_name: i.solutionName,
      description: i.description,
      market_fit_score: i.marketFitScore,
      category: i.category,
    })),
    painPoints: painPoints.map(pp => ({
      id: pp.id,
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
