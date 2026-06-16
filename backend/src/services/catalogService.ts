import { readFileSync, existsSync } from 'fs';
import { z } from 'zod';
import { prisma } from './db.js';
import { getJobAsset } from './jobService.js';
import { AssetType, Prisma } from '@prisma/client';
import { resolveAssetPath } from '../utils/assetPath.js';
import { getRedis } from './redis.js';
import { extractOrCreateResearchContext, hasMeaningfulResearchContext } from './researchContextService.js';
import { canonicalizeAddressedTitles } from './titleMatching.js';

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

  // When the manual editor changes faqJson, record provenance so the admin
  // editor's "Last generated by …" / "Manually edited …" chip stays accurate
  // regardless of which save path was used. The new /faq/save route writes
  // faqJsonMeta directly with source: 'generated'; this branch covers the
  // existing PATCH /categories/:id path that this service backs.
  const dataWithMeta: Record<string, unknown> = { ...data };
  if (data.faqJson !== undefined) {
    dataWithMeta.faqJsonMeta = {
      source: 'manual',
      updatedAt: new Date().toISOString(),
    };
  }

  // Prisma's strict types reject `unknown` for Json columns; cast at the boundary.
  const updated = await prisma.catalogCategory.update({
    where: { id },
    data: dataWithMeta as never,
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
            obviousness: sol.obviousness_score,
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
            obviousness: sol.obviousness_score,
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
              obviousness: alt.obviousness_score,
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
              obviousness: alt.obviousness_score,
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

  // Validate + canonicalize addressed pain titles against the same job's pain
  // list. Drops titles with no plausible canonical counterpart; logs
  // corrections for audit. Same fuzzy threshold (0.7 bigram) used by the pain-
  // points dedup in workers.ts.
  const llmAddressedTitles = safeStringArray(solution.pain_points_addressed) ?? [];
  const reportPains = Array.isArray(report.detailed_pain_points)
    ? (report.detailed_pain_points as Array<{ title?: unknown }>)
    : [];
  const canon = canonicalizeAddressedTitles(llmAddressedTitles, reportPains);
  if (canon.dropped.length > 0 || canon.corrected.length > 0) {
    console.warn('[publishIdea] addressedPainTitles canonicalization', {
      jobId: params.sourceJobId,
      ideaSlug: slug,
      dropped: canon.dropped,
      corrected: canon.corrected,
    });
  }

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
          obviousnessScore: safeFloat(solution.obviousness_score),
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
          // Now validated + canonicalized against report.detailed_pain_points
          // before persist; see canonicalizeAddressedTitles call above.
          // Alternative-solution rows (itemIndex >= 0): the Pydantic
          // AlternativeSolution model has no pain_points_addressed field
          // (research_state.py:241-283), so the input is empty → canonical is [].
          addressedPainTitles: canon.canonical,
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
    await invalidateCatalogTotals();
  await invalidateTopCatalogPainPoints();
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
    await invalidateCatalogTotals();
  await invalidateTopCatalogPainPoints();
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
  isFreePreview?: boolean;
  isActive?: boolean;
}) {
  // Capture original categoryId so we can invalidate both old and new on category change.
  const before = await prisma.catalogIdea.findUnique({
    where: { id },
    select: { categoryId: true },
  });

  const result = await prisma.$transaction(async (tx) => {
    // Single-free-preview invariant: DEMOTE FIRST, then set. The partial unique index
    // (one isFreePreview per category) is non-deferrable, so we must clear any existing
    // free preview in the FINAL category before the update flips this row on.
    if (data.isFreePreview === true) {
      const finalCategoryId = data.categoryId ?? before?.categoryId;
      if (finalCategoryId) {
        await tx.catalogIdea.updateMany({
          where: { categoryId: finalCategoryId, id: { not: id }, isFreePreview: true },
          data: { isFreePreview: false },
        });
      }
    }

    const idea = await tx.catalogIdea.update({
      where: { id },
      data,
    });

    // Single-featured invariant: if this row is now featured, demote any OTHER
    // featured idea in its (possibly new) category. Keying off the final state
    // (idea.isFeatured) rather than data.isFeatured also covers moving an already
    // featured item into a category that already has one. (isFeatured has no unique
    // index, so set-then-demote is fine here.)
    if (idea.isFeatured) {
      await tx.catalogIdea.updateMany({
        where: { categoryId: idea.categoryId, id: { not: idea.id }, isFeatured: true },
        data: { isFeatured: false },
      });
    }

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
  await invalidateCatalogTotals();
  await invalidateTopCatalogPainPoints();

  return result;
}

export async function updateCatalogPainPoint(id: string, data: {
  categoryId?: string;
  isFeatured?: boolean;
  isFreePreview?: boolean;
  isActive?: boolean;
}) {
  const before = await prisma.catalogPainPoint.findUnique({
    where: { id },
    select: { categoryId: true },
  });

  const result = await prisma.$transaction(async (tx) => {
    // Single-free-preview invariant — demote FIRST (partial unique index; see updateCatalogIdea).
    if (data.isFreePreview === true) {
      const finalCategoryId = data.categoryId ?? before?.categoryId;
      if (finalCategoryId) {
        await tx.catalogPainPoint.updateMany({
          where: { categoryId: finalCategoryId, id: { not: id }, isFreePreview: true },
          data: { isFreePreview: false },
        });
      }
    }

    const pp = await tx.catalogPainPoint.update({
      where: { id },
      data,
    });

    // Single-featured invariant (see updateCatalogIdea) — demote other featured
    // pains in the final category when this one becomes featured.
    if (pp.isFeatured) {
      await tx.catalogPainPoint.updateMany({
        where: { categoryId: pp.categoryId, id: { not: pp.id }, isFeatured: true },
        data: { isFeatured: false },
      });
    }

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
  await invalidateCatalogTotals();
  await invalidateTopCatalogPainPoints();

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
            obviousnessScore: idea.obviousnessScore,
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
  await invalidateCatalogTotals();
  await invalidateTopCatalogPainPoints();
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
  await invalidateCatalogTotals();
  await invalidateTopCatalogPainPoints();
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
  category: {
    id: string;
    name: string;
    slug: string;
    parent: { slug: string; name: string } | null;
  };
  // FAQ projection — same shape as idea preview, flowed through `...rest`
  // spread in getCategoryLanding/getPainPointBySlug. Drives both visible
  // <CategoryFAQ> and FAQPage JSON-LD on the public detail page.
  faqJson: unknown;
  faqJsonMeta: unknown;
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
    obviousness_score: idea.obviousnessScore ?? null,
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
    // FAQ projection — used both for visible <CategoryFAQ> rendering and
    // FAQPage JSON-LD on the public detail page (gated on faqJson.length >= 2).
    faqJson: idea.faqJson ?? null,
    faqJsonMeta: idea.faqJsonMeta ?? null,
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

// v7 — adds `lockedPainCount` (server-authoritative) and includes
// `category.parent: { slug, name }` on idea/pain previews. Bumped so the
// deploy starts cold and every cached payload thereafter carries the new
// fields; old v6 keys age out via TTL (entitled responses bypass this cache
// entirely, so only public payloads are at risk of staleness).
// v6 — added `latestModifiedAt` to the payload (max of category + active
// children + active ideas + active pain-points in the subtree). Powers the
// SEO `dateModified` / `lastReviewed` on CollectionPage.
const LANDING_CACHE_PREFIX = 'catalog:landing:v7';
// Matches the edge `Cache-Control: s-maxage=900` on the landing routes — so
// Redis and the CDN expire in the same window. Freshness on writes is
// preserved by invalidation hooks; this just trims redundant backend roundtrips.
const LANDING_CACHE_TTL_BASE = 900; // seconds; ±10% jitter applied per write
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
  // Phase 17 — only set on parent payloads when themes are aggregated across
  // multiple child sub-niches' research. Sub-niche payloads leave this null
  // (sub-niche owns its themes; no attribution needed).
  sourceSubNiche?: { slug: string; name: string; parentSlug: string } | null;
}

interface CatalogAudienceSourceSubNiche {
  slug: string;
  name: string;
  parentSlug: string;
}

interface CatalogAudienceSegmentSummary {
  name: string;
  sizeLabel: string | null;
  bullets: string[];
  // Phase 5.5 — surfaced for AudienceSegmentCard's `.seg-meta` footer.
  expertiseLevel: string | null;     // 'Beginner' | 'Intermediate' | 'Advanced'
  budgetSensitivity: string | null;  // 'High' | 'Medium' | 'Low'
  // Phase 17 — parent payloads can aggregate audience segments across child
  // sub-niches. In that case each segment carries its own source link data.
  // Sub-niche payloads and direct category-owned fallback rows omit it.
  sourceSubNiche?: CatalogAudienceSourceSubNiche | null;
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
  // Server-authoritative paywall count for pain points (see commentary at
  // computation site in `buildCategoryLandingPayload`). Always present so the
  // frontend loader can read it directly without re-deriving from arithmetic
  // — which would be wrong on entitled+parent paths where the top-12 cap
  // silently hides rows that are NOT paywalled.
  lockedPainCount: number;
  sources: string[];
  // Phase 5.4 — flattened summaries for the new public catalog UI. Most are
  // sourced from the most-recent research context that backs `researchContext`.
  // Phase 17 exception: parent-page `audienceSegments` can aggregate rows from
  // multiple child sub-niches, each tagged with `sourceSubNiche`. Every field
  // nullable — the frontend hides sections when null.
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
  // Phase 16 — provenance for the themes flatten. When non-null, themes were
  // drawn from this sub-niche's research; the parent route renders an attribution
  // link to it. Audience uses per-segment sourceSubNiche in Phase 17 when
  // aggregated across sub-niches. Null when no research exists or when the
  // recent item belongs directly to the parent category.
  researchSourceSubNiche: { slug: string; name: string } | null;
  // Phase 6 — most-recent content/metadata timestamp across the whole subtree
  // (category row + active children + active ideas + active pain-points).
  // Surfaced for the SEO CollectionPage `dateModified` / `lastReviewed` fields.
  // ISO 8601 string; frontend converts to date-only at render.
  latestModifiedAt: string;
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

interface AudienceAggregationChild {
  id: string;
  slug: string;
  name: string;
}

async function aggregateParentAudienceSegments(args: {
  parentSlug: string;
  children: AudienceAggregationChild[];
}): Promise<CatalogAudienceSegmentSummary[] | null> {
  if (args.children.length === 0) return null;

  const recentSources = await findMostRecentItemSourcePerCategory(
    args.children.map((child) => child.id),
  );
  if (recentSources.length === 0) return null;

  const sourceByCategoryId = new Map(
    recentSources.map((source) => [source.categoryId, source]),
  );
  const contexts = await prisma.catalogResearchContext.findMany({
    where: {
      sourceJobId: { in: [...new Set(recentSources.map((source) => source.sourceJobId))] },
    },
  });
  const contextBySourceJobId = new Map(contexts.map((ctx) => [ctx.sourceJobId, ctx]));

  const out: CatalogAudienceSegmentSummary[] = [];
  for (const child of args.children) {
    const source = sourceByCategoryId.get(child.id);
    if (!source) continue;
    const ctx = contextBySourceJobId.get(source.sourceJobId);
    if (!ctx || !hasMeaningfulResearchContext(ctx)) continue;

    const segments = flattenAudienceSegments(ctx);
    if (!segments) continue;

    for (const segment of segments.slice(0, 2)) {
      out.push({
        ...segment,
        sourceSubNiche: {
          slug: child.slug,
          name: child.name,
          parentSlug: args.parentSlug,
        },
      });
      if (out.length >= TOP_PREVIEW_LIMIT) return out;
    }
  }

  return out.length > 0 ? out : null;
}

const THEMES_PREVIEW_LIMIT = 5;

interface ThemeAggregationChild {
  id: string;
  slug: string;
  name: string;
}

/**
 * Phase 17 — themes aggregation across child sub-niches.
 *
 * Mirrors `aggregateParentAudienceSegments` but with stricter activation +
 * dedup rules tailored to themes:
 *
 *   - Activation: require >=2 child sub-niches that produce non-empty
 *     `flattenThemes` results. Counting `hasMeaningfulResearchContext`
 *     alone is too broad (audience-only contexts wouldn't supply themes
 *     and could fool frontend's multi-source check).
 *   - Per-sub-niche cap: top 2 by `mentionCount` desc.
 *   - Filter id-less legacy themes BEFORE the cap (legacy aside owns them).
 *   - Dedup by `theme.id` (auto-derived from title) to avoid duplicate DOM
 *     IDs / Svelte keys when two sub-niches surface the same theme topic.
 *     Keep the highest-mention occurrence; attribution rides with it.
 *   - Sort the deduped pool by `mentionCount` desc, with stable
 *     children-order tiebreaker (children come pre-sorted by sortOrder).
 *   - Total cap: THEMES_PREVIEW_LIMIT.
 *
 * Returns null when activation fails — caller falls back to the existing
 * single-context `flattenThemes(ctxForSummaries)` path.
 */
async function aggregateParentThemes(args: {
  parentSlug: string;
  children: ThemeAggregationChild[];
}): Promise<CatalogThemeSummary[] | null> {
  if (args.children.length === 0) return null;

  const recentSources = await findMostRecentItemSourcePerCategory(
    args.children.map((child) => child.id),
  );
  if (recentSources.length === 0) return null;

  const sourceByCategoryId = new Map(
    recentSources.map((source) => [source.categoryId, source]),
  );
  const contexts = await prisma.catalogResearchContext.findMany({
    where: {
      sourceJobId: { in: [...new Set(recentSources.map((s) => s.sourceJobId))] },
    },
  });
  const contextBySourceJobId = new Map(contexts.map((ctx) => [ctx.sourceJobId, ctx]));

  // Collect candidates with attribution + a stable child-order index for
  // deterministic tiebreaking on equal mention counts.
  type Candidate = CatalogThemeSummary & {
    sourceSubNiche: { slug: string; name: string; parentSlug: string };
    _childOrder: number;
  };
  const candidates: Candidate[] = [];
  const contributingChildIds = new Set<string>();

  for (let i = 0; i < args.children.length; i++) {
    const child = args.children[i]!;
    const source = sourceByCategoryId.get(child.id);
    if (!source) continue;
    const ctx = contextBySourceJobId.get(source.sourceJobId);
    if (!ctx || !hasMeaningfulResearchContext(ctx)) continue;

    const themes = flattenThemes(ctx);
    if (!themes || themes.length === 0) continue;

    // Filter id-less legacy themes — they go to the .empty-themes aside,
    // not the lead/roll table. Excluding them before the cap also
    // guarantees post-dedup id uniqueness.
    const idBearing = themes.filter((t): t is CatalogThemeSummary & { id: string } => !!t.id);
    if (idBearing.length === 0) continue;

    contributingChildIds.add(child.id);

    // Per-sub-niche cap: top 2 by mention count.
    const ranked = [...idBearing].sort(
      (a, b) => (b.mentionCount ?? 0) - (a.mentionCount ?? 0),
    );
    for (const theme of ranked.slice(0, 2)) {
      candidates.push({
        ...theme,
        sourceSubNiche: {
          slug: child.slug,
          name: child.name,
          parentSlug: args.parentSlug,
        },
        _childOrder: i,
      });
    }
  }

  // Activation: only run aggregation when >=2 sub-niches actually contribute
  // themes. With 0-1 contributors, the caller falls back to the single-
  // context flatten — this keeps section-level vs per-row attribution
  // mutually exclusive on the frontend.
  if (contributingChildIds.size < 2) return null;

  // Dedup by theme.id — keep the highest-mention occurrence. Two sub-niches
  // surfacing the same theme title would otherwise produce duplicate DOM
  // anchors and Svelte keys (theme_id is auto-derived from the title).
  const dedupedById = new Map<string, Candidate>();
  for (const c of candidates) {
    if (!c.id) continue; // unreachable post-filter, but TS-narrows here
    const existing = dedupedById.get(c.id);
    if (!existing || (c.mentionCount ?? 0) > (existing.mentionCount ?? 0)) {
      dedupedById.set(c.id, c);
    }
  }

  // Sort by mention count desc; tiebreaker = child sortOrder (encoded as
  // _childOrder during collection). Stable + deterministic.
  const sorted = [...dedupedById.values()].sort((a, b) => {
    const diff = (b.mentionCount ?? 0) - (a.mentionCount ?? 0);
    if (diff !== 0) return diff;
    return a._childOrder - b._childOrder;
  });

  // Strip the helper field; cap at the preview limit.
  const out: CatalogThemeSummary[] = sorted.slice(0, THEMES_PREVIEW_LIMIT).map((c) => {
    const { _childOrder: _drop, ...rest } = c;
    return rest;
  });

  return out.length > 0 ? out : null;
}

/**
 * Pure reducer for parent-page source counts. Takes a list of distinct
 * research contexts (de-duped by sourceJobId upstream) and returns the
 * aggregated metric pair.
 *
 *   - contentItemsMined = Σ (reddit + twitter + generic) across contexts.
 *   - sourceCommunities = size of the UNION of distinct subreddit `name`
 *     values across all contexts' `topSubreddits` arrays. Same name
 *     validation as `flattenSubredditSources` — required string, non-empty
 *     after trim. This is intentionally distinct from the leaf-page count
 *     (`topSubreddits.length`): on parents, two children's `topSubreddits`
 *     can overlap and summing lengths would double-count the same community.
 *
 * Exported for unit testing — keeps the SQL-fetching wrapper thin.
 */
export function reduceParentSourceMetric(
  contexts: Array<{
    redditPostsAnalyzed: number | null;
    twitterThreadsAnalyzed: number | null;
    genericPostsAnalyzed: number | null;
    topSubreddits: unknown;
  }>,
): { contentItemsMined: number; sourceCommunities: number } {
  let contentItemsMined = 0;
  const subredditNames = new Set<string>();
  for (const ctx of contexts) {
    contentItemsMined +=
      (ctx.redditPostsAnalyzed ?? 0) +
      (ctx.twitterThreadsAnalyzed ?? 0) +
      (ctx.genericPostsAnalyzed ?? 0);
    if (Array.isArray(ctx.topSubreddits)) {
      for (const raw of ctx.topSubreddits as unknown[]) {
        if (!raw || typeof raw !== 'object') continue;
        const name = (raw as Record<string, unknown>).name;
        if (typeof name !== 'string') continue;
        const trimmed = name.trim();
        if (!trimmed) continue;
        subredditNames.add(trimmed);
      }
    }
  }
  return { contentItemsMined, sourceCommunities: subredditNames.size };
}

/**
 * Parent-page sources aggregator. Scope = parent + children (passed in via
 * `categoryIds`, typically `[category.id, ...childIds]`). Returns null when
 * no distinct research context contributes anything — caller falls back to
 * the single-context `deriveSourcesMetric(ctxForSummaries)` path.
 *
 * Bypasses `hasMeaningfulResearchContext` on purpose. The gate exists for
 * prose-grade content (audience / themes); raw source counts and subreddit
 * lists are useful regardless of prose quality.
 */
async function aggregateParentSourcesMetric(args: {
  categoryIds: string[];
}): Promise<{ contentItemsMined: number; sourceCommunities: number } | null> {
  if (args.categoryIds.length === 0) return null;

  const recentSources = await findMostRecentItemSourcePerCategory(args.categoryIds);
  if (recentSources.length === 0) return null;

  // Dedup so a job published into multiple categories is counted once.
  const distinctJobIds = [...new Set(recentSources.map((s) => s.sourceJobId))];
  const contexts = await prisma.catalogResearchContext.findMany({
    where: { sourceJobId: { in: distinctJobIds } },
    select: {
      redditPostsAnalyzed: true,
      twitterThreadsAnalyzed: true,
      genericPostsAnalyzed: true,
      topSubreddits: true,
    },
  });
  if (contexts.length === 0) return null;

  const aggregated = reduceParentSourceMetric(contexts);
  if (aggregated.contentItemsMined === 0 && aggregated.sourceCommunities === 0) {
    return null;
  }
  return aggregated;
}

async function buildCategoryLandingPayload(
  categoryId: string,
  opts: { entitled?: boolean } = {},
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
          // Internal use only — feeds `latestModifiedAt` aggregation below.
          // NOT surfaced on `children[]` in the public payload (kept lean).
          updatedAt: true,
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

  // Entitled users (ADMIN / fullCatalogAccess / active subscription) see the FULL list;
  // everyone else sees the featured-only teaser (one idea + one pain per category).
  // `parent` is included so frontend `categoryPath({ slug, parentSlug })` can build
  // nested URLs (/ideas/<parent>/<child>) for sub-niche links on parent landings.
  const ideaInclude = {
    category: {
      select: {
        id: true,
        name: true,
        slug: true,
        parent: { select: { slug: true, name: true } },
      },
    },
  } as const;
  // Top-level parent landings (parentId === null AND has children) cap the
  // aggregated pain list to 12. Aligns with the existing `isParentAggregationCandidate`
  // gate further down; defensive against future nesting.
  const isParentPage = category.parentId === null && category.children.length > 0;
  const ideaFetch = opts.entitled
    ? prisma.catalogIdea.findMany({
        where: { categoryId: { in: aggregateIds }, isActive: true, slug: { not: null } },
        orderBy: FEATURED_IDEA_ORDER,
        include: ideaInclude,
      })
    : Promise.all(aggregateIds.map((id) => freePreviewIdeaForCategory(id)));
  // Parent-aggregated cap path ranks by severity (NOT featured-first). Featured-
  // first is the right policy for the non-entitled featured-only-mode (one per
  // category); for an entitled top-N parent view, users expect "most severe in
  // the subtree" so low-severity featured rows shouldn't crowd out higher-
  // severity non-featured ones. See `paginatedPainFetchPolicyForLanding`.
  const painFetch = opts.entitled
    ? prisma.catalogPainPoint.findMany({
        where: { categoryId: { in: aggregateIds }, isActive: true, slug: { not: null } },
        include: ideaInclude,
        ...paginatedPainFetchPolicyForLanding({ isParentPage }),
      })
    : Promise.all(aggregateIds.map((id) => freePreviewPainForCategory(id)));

  const [
    topIdeasRaw,
    topPainPointsRaw,
    totalIdeas,
    totalPainPoints,
    verdictGoCount,
    siblingsRaw,
    ideaMaxAgg,
    painMaxAgg,
  ] = await Promise.all([
    // Featured-only visible set (non-entitled): exactly one idea (and one pain) per
    // category in the subtree. Entitled callers get the full slugged set instead.
    // Non-featured items NEVER enter the public (non-entitled) payload.
    ideaFetch,
    painFetch,
    // Slug-predicate parity with the visible-set fetches above — without `slug:
    // { not: null }`, the total counts overcount by the number of un-slugged
    // (orphan / pre-publish) rows, which the visible fetch already filters out.
    // Locked-count arithmetic on the frontend (and `lockedPainCount` below)
    // depends on these counts matching the visible set.
    prisma.catalogIdea.count({
      where: { isActive: true, categoryId: { in: aggregateIds }, slug: { not: null } },
    }),
    prisma.catalogPainPoint.count({
      where: { isActive: true, categoryId: { in: aggregateIds }, slug: { not: null } },
    }),
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
    // Feeds `latestModifiedAt`. `category.updatedAt` only changes on metadata
    // edits, so content freshness requires aggregating idea + pain-point
    // timestamps across the whole subtree. Both columns are indexed (severity/
    // mention orders use them too); the aggregate is cheap.
    prisma.catalogIdea.aggregate({
      _max: { updatedAt: true },
      where: { isActive: true, categoryId: { in: aggregateIds } },
    }),
    prisma.catalogPainPoint.aggregate({
      _max: { updatedAt: true },
      where: { isActive: true, categoryId: { in: aggregateIds } },
    }),
  ]);

  // Most-recent timestamp across category metadata + sub-category metadata +
  // active ideas + active pain-points. Persisted on the payload so the SEO
  // CollectionPage gets an honest `dateModified` even when no category row
  // has been touched but content has been added/refreshed beneath it.
  const latestModifiedMs = Math.max(
    category.updatedAt.getTime(),
    ...category.children.map((c) => c.updatedAt.getTime()),
    ideaMaxAgg._max.updatedAt?.getTime() ?? 0,
    painMaxAgg._max.updatedAt?.getTime() ?? 0,
  );
  const latestModifiedAt = new Date(latestModifiedMs).toISOString();

  const topIdeas = topIdeasRaw
    .filter((r): r is NonNullable<typeof r> => r !== null)
    .map(({ sourceJobId: _s, publishedById: _p, ...rest }) => toIdeaPreview(rest));
  const topPainPoints = topPainPointsRaw
    .filter((r): r is NonNullable<typeof r> => r !== null)
    .map(({ sourceJobId: _s, publishedById: _p, ...rest }) => rest);

  // Server-authoritative paywall count for pain points. Entitled users see 0
  // even when the parent cap silently hides rows (those un-shown rows live on
  // sub-niche pages, not behind a paywall). Non-entitled users keep the
  // featured-only-deficit semantic. `lockedIdeaCount` stays frontend-derived
  // — ideas don't have a parent cap so the existing arithmetic is correct
  // (revisit if ideas ever get capped on parent pages).
  const lockedPainCount = computeLockedPainCount({
    entitled: !!opts.entitled,
    totalPainPoints,
    visiblePainPoints: topPainPoints.length,
  });

  // Phase 5: Attach the most-recent published item's research context so the
  // category landing renders the same Audience/Market/Trend sections as
  // detail pages, framed as "Analysis from latest research in this niche."
  const recentItem = await findMostRecentItemSource(aggregateIds);
  const researchContext = recentItem
    ? await prisma.catalogResearchContext.findUnique({ where: { sourceJobId: recentItem.sourceJobId } })
    : null;
  // Phase 16 — provenance attribution. Themes/audience are flattened from the
  // single research context resolved above; on parent pages this can mislead
  // (sub-niche prose labeled at category level). Expose the source sub-niche
  // so the frontend can render an "↗ FROM <sub-niche> RESEARCH" attribution
  // line under those sections. Null when:
  //   - no recent item exists (no themes/audience anyway), or
  //   - the recent item belongs directly to the parent category (no sub-niche
  //     to attribute to — frontend hides the attribution line).
  let researchSourceSubNiche: { slug: string; name: string } | null = null;
  if (recentItem && recentItem.categoryId !== category.id) {
    const sourceCategory = await prisma.catalogCategory.findUnique({
      where: { id: recentItem.categoryId },
      select: { slug: true, name: true },
    });
    if (sourceCategory) {
      researchSourceSubNiche = { slug: sourceCategory.slug, name: sourceCategory.name };
    }
  }
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
  // Parent-path aggregation gate (Wave 2 audience + Wave 3 themes). Only runs
  // for top-level categories with at least one child. Each aggregation falls
  // back to the single-context flatten when its activation rule isn't met.
  const isParentAggregationCandidate =
    category.parentId === null && category.children.length > 0;
  const parentAudienceSegments = isParentAggregationCandidate
    ? await aggregateParentAudienceSegments({
        parentSlug: category.slug,
        children: category.children,
      })
    : null;
  const audienceSegments = parentAudienceSegments ?? flattenAudienceSegments(ctxForSummaries);
  const parentThemes = isParentAggregationCandidate
    ? await aggregateParentThemes({
        parentSlug: category.slug,
        children: category.children,
      })
    : null;
  const themes = parentThemes ?? flattenThemes(ctxForSummaries);
  const competitors = flattenCompetitors(ctxForSummaries);
  const keywordClusters = flattenKeywordClusters(ctxForSummaries);
  const subredditSources = flattenSubredditSources(ctxForSummaries);
  // Parent pages: aggregate source counts across the whole subtree (parent +
  // children) so a single stale "most recent" item doesn't zero out a parent
  // whose siblings have data. Leaf and non-parent pages keep the single-
  // context path. See `aggregateParentSourcesMetric` for semantics, including
  // the intentional distinct-name semantic for `sourceCommunities`.
  const parentSources = isParentAggregationCandidate
    ? await aggregateParentSourcesMetric({ categoryIds: aggregateIds })
    : null;
  const { contentItemsMined, sourceCommunities } =
    parentSources ?? deriveSourcesMetric(ctxForSummaries);
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
    // Most-recent content/metadata timestamp in the whole subtree. SEO
    // CollectionPage threads this to `dateModified` / `lastReviewed` via the
    // frontend helper; values are ISO and converted to date-only at render.
    latestModifiedAt,
    siblings: siblingsRaw,
    topIdeas,
    topPainPoints,
    totalIdeas,
    totalPainPoints,
    lockedPainCount,
    // v1: hardcode the source platforms NicheIQ currently ingests from. Kept
    // for back-compat with existing landing-payload consumers — new UI uses
    // contentItemsMined + sourceCommunities below.
    sources: ['Reddit', 'Hacker News'],
    // Phase 15.5 — backend-aggregate count (whole category subtree).
    verdictGoCount,
    // Phase 5.4 — flattened summaries.
    themes,
    // Phase 17 — parent audience may be aggregated across child sub-niches,
    // with per-segment sourceSubNiche. Themes remain single-source via
    // researchSourceSubNiche.
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
    // Phase 16 — sub-niche provenance for themes on parent pages.
    researchSourceSubNiche,
  };
}

/**
 * Phase 5 helper: returns the sourceJobId AND the categoryId of the most-
 * recently-published active CatalogIdea or CatalogPainPoint inside the given
 * category subtree (categoryId or any of its child categoryIds), or null if
 * there are no active items.
 *
 * The categoryId enables provenance attribution on parent-niche pages — the
 * landing payload exposes which sub-niche's research backed the themes /
 * audience flattens (NOT the topPainPoints, which are aggregated separately
 * across the whole subtree).
 *
 * Pragmatic over precise — top-level categories aggregate "the most recent
 * research in this niche" rather than blending analysis from every job. The
 * frontend frames it as such ("From <sub-niche> research").
 */
async function findMostRecentItemSource(
  categoryIds: string[],
): Promise<{ sourceJobId: string; categoryId: string } | null> {
  if (categoryIds.length === 0) return null;

  // Raw SQL because Prisma's orderBy can't COALESCE. Lineage timestamp is
  // sourceGeneratedAt (set by worker), with updatedAt + createdAt fallbacks
  // for legacy rows. Postgres preserves camelCase column names when quoted.
  const rows = await prisma.$queryRaw<{ source_job_id: string; category_id: string }[]>`
    SELECT source_job_id, category_id
    FROM (
      SELECT
        "sourceJobId" AS source_job_id,
        "categoryId" AS category_id,
        COALESCE("sourceGeneratedAt", "updatedAt", "createdAt") AS effective_ts
      FROM "CatalogIdea"
      WHERE "isActive" = true AND "categoryId" IN (${Prisma.join(categoryIds)})
      UNION ALL
      SELECT
        "sourceJobId" AS source_job_id,
        "categoryId" AS category_id,
        COALESCE("sourceGeneratedAt", "updatedAt", "createdAt") AS effective_ts
      FROM "CatalogPainPoint"
      WHERE "isActive" = true AND "categoryId" IN (${Prisma.join(categoryIds)})
    ) AS combined
    ORDER BY effective_ts DESC
    LIMIT 1
  `;

  const row = rows[0];
  if (!row) return null;
  return { sourceJobId: row.source_job_id, categoryId: row.category_id };
}

async function findMostRecentItemSourcePerCategory(
  categoryIds: string[],
): Promise<Array<{ sourceJobId: string; categoryId: string }>> {
  if (categoryIds.length === 0) return [];

  const rows = await prisma.$queryRaw<{ source_job_id: string; category_id: string }[]>`
    SELECT DISTINCT ON (category_id) source_job_id, category_id
    FROM (
      SELECT
        "sourceJobId" AS source_job_id,
        "categoryId" AS category_id,
        COALESCE("sourceGeneratedAt", "updatedAt", "createdAt") AS effective_ts
      FROM "CatalogIdea"
      WHERE "isActive" = true AND "categoryId" IN (${Prisma.join(categoryIds)})
      UNION ALL
      SELECT
        "sourceJobId" AS source_job_id,
        "categoryId" AS category_id,
        COALESCE("sourceGeneratedAt", "updatedAt", "createdAt") AS effective_ts
      FROM "CatalogPainPoint"
      WHERE "isActive" = true AND "categoryId" IN (${Prisma.join(categoryIds)})
    ) AS combined
    ORDER BY category_id, effective_ts DESC
  `;

  return rows.map((row) => ({ sourceJobId: row.source_job_id, categoryId: row.category_id }));
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
  entitled?: boolean;
}): Promise<CategoryLandingPayload | { inactive: true } | null> {
  const cacheKey = landingCacheKey(args.parentSlug, args.childSlug);
  const redis = getRedis();

  // Entitled responses carry the FULL list (per-user), so they must NOT read from
  // or write to the shared public (featured-only) cache.
  if (!args.entitled) {
    try {
      const cached = await redis.get(cacheKey);
      if (cached) {
        return JSON.parse(cached) as CategoryLandingPayload;
      }
    } catch (err) {
      console.error('Landing cache read failed:', err);
    }
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

  const payload = await buildCategoryLandingPayload(category.id, { entitled: args.entitled });
  if (!payload) return null;

  if (!args.entitled) {
    try {
      await redis.setex(cacheKey, jitteredTtl(), JSON.stringify(payload));
    } catch (err) {
      console.error('Landing cache write failed:', err);
    }
  }

  return payload;
}

// ============================================
// Featured-item resolution (the one free idea + pain per category)
// ============================================

// Display ordering for the ENTITLED full list (floats featured items + top scores first).
// NOT the free-preview gate — that keys solely on `isFreePreview` (see resolvers below).
// `nulls: 'last'` keeps null-score ideas from sorting ahead of scored ones.
const FEATURED_IDEA_ORDER: Prisma.CatalogIdeaOrderByWithRelationInput[] = [
  { isFeatured: 'desc' },
  { marketFitScore: { sort: 'desc', nulls: 'last' } },
  { createdAt: 'desc' },
  { id: 'asc' },
];
const FEATURED_PAIN_ORDER: Prisma.CatalogPainPointOrderByWithRelationInput[] = [
  { isFeatured: 'desc' },
  { severityScore: 'desc' }, // severityScore is non-null in the schema
  { createdAt: 'desc' },
  { id: 'asc' },
];

// Parent-aggregated landing pages (top-level category with children) cap the
// entitled pain list at PARENT_PAIN_CAP and rank by severity directly — see
// the comment on the `orderBy` in `painFetch` for why featured-first is wrong
// here.
const PARENT_PAIN_CAP = 12;
const PARENT_PAIN_ORDER: Prisma.CatalogPainPointOrderByWithRelationInput[] = [
  { severityScore: 'desc' },
  { mentionCount: 'desc' },
  { createdAt: 'desc' },
  { id: 'asc' },
];

/** Pure policy helper — given whether the landing is a parent-aggregation
 *  page, return the prisma orderBy + optional take to use for the entitled
 *  pain fetch. Extracted for unit testing (the call site spreads this
 *  directly into the prisma query). */
export function paginatedPainFetchPolicyForLanding(opts: {
  isParentPage: boolean;
}): {
  orderBy: Prisma.CatalogPainPointOrderByWithRelationInput[];
  take?: number;
} {
  return opts.isParentPage
    ? { orderBy: PARENT_PAIN_ORDER, take: PARENT_PAIN_CAP }
    : { orderBy: FEATURED_PAIN_ORDER };
}

/** Pure helper for `lockedPainCount`. Entitled users always see 0 (their
 *  un-shown rows live on sub-niche pages, not behind a paywall). Non-entitled
 *  users see the deficit between the true total and what was sent. */
export function computeLockedPainCount(opts: {
  entitled: boolean;
  totalPainPoints: number;
  visiblePainPoints: number;
}): number {
  return opts.entitled
    ? 0
    : Math.max(0, opts.totalPainPoints - opts.visiblePainPoints);
}

// The free-preview gate keys ONLY on `isFreePreview` — no score-based fallback. A sub-niche
// with nothing flagged has NO free item (fully gated) until the seed script or an admin pins one.
// At most one flagged row per category (partial unique index + demote-first-then-set in the
// upsert); the `id` order is just a determinism guard against transient duplicates.

/** Id of the free-preview idea for a category, or null when none is flagged. */
export async function resolveFreePreviewIdeaId(categoryId: string): Promise<string | null> {
  const r = await prisma.catalogIdea.findFirst({
    where: { categoryId, isActive: true, slug: { not: null }, isFreePreview: true },
    orderBy: { id: 'asc' },
    select: { id: true },
  });
  return r?.id ?? null;
}

/** Id of the free-preview pain point for a category, or null when none is flagged. */
export async function resolveFreePreviewPainId(categoryId: string): Promise<string | null> {
  const r = await prisma.catalogPainPoint.findFirst({
    where: { categoryId, isActive: true, slug: { not: null }, isFreePreview: true },
    orderBy: { id: 'asc' },
    select: { id: true },
  });
  return r?.id ?? null;
}

/** Full free-preview idea row for the landing payload (null when none is flagged).
 *  `category.parent` is included so the frontend can build nested category
 *  URLs (`/ideas/<parent>/<child>`) for sub-niche links without an extra round-trip. */
async function freePreviewIdeaForCategory(categoryId: string) {
  return prisma.catalogIdea.findFirst({
    where: { categoryId, isActive: true, slug: { not: null }, isFreePreview: true },
    orderBy: { id: 'asc' },
    include: {
      category: {
        select: {
          id: true,
          name: true,
          slug: true,
          parent: { select: { slug: true, name: true } },
        },
      },
    },
  });
}

/** Full free-preview pain row for the landing payload (null when none is flagged).
 *  See `freePreviewIdeaForCategory` for the rationale on including `category.parent`. */
async function freePreviewPainForCategory(categoryId: string) {
  return prisma.catalogPainPoint.findFirst({
    where: { categoryId, isActive: true, slug: { not: null }, isFreePreview: true },
    orderBy: { id: 'asc' },
    include: {
      category: {
        select: {
          id: true,
          name: true,
          slug: true,
          parent: { select: { slug: true, name: true } },
        },
      },
    },
  });
}

/**
 * Whether a user may view the full catalog — i.e. non-featured ideas/pain points and
 * their detail pages. Authoritative DB lookup (header-independent) of: `role === 'ADMIN'`,
 * the manual `fullCatalogAccess` grant, OR an active subscription. The subscription check
 * FAILS CLOSED on a null period (if we couldn't read the Stripe item period we don't grant
 * forever). Fresh read so grants/revocations take effect immediately.
 */
export async function isEntitledUser(userId: string | undefined): Promise<boolean> {
  if (!userId) return false;
  const u = await prisma.user.findUnique({
    where: { id: userId },
    select: {
      role: true,
      fullCatalogAccess: true,
      subscription: { select: { status: true, currentPeriodEnd: true } },
    },
  });
  if (!u) return false;
  if (u.role === 'ADMIN' || u.fullCatalogAccess === true) return true;
  const sub = u.subscription;
  if (!sub) return false;
  const activeStatus = sub.status === 'ACTIVE' || sub.status === 'TRIALING';
  return activeStatus && sub.currentPeriodEnd != null && sub.currentPeriodEnd.getTime() > Date.now();
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
    orderBy: [{ isFeatured: 'desc' }, { severityScore: 'desc' }, { mentionCount: 'desc' }],
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

/**
 * Detail payload for a single idea. `entitled` (ADMIN or fullCatalogAccess) sees
 * the full cross-link lists; a non-entitled user can only reach the ONE featured
 * idea per sub-niche — for any other slug we return `{ locked: true }` (route → 403),
 * and on the featured page we hide non-featured cross-links (siblings → none;
 * addressed pains → only the featured pain) and report locked counts for the
 * "Subscribe to unlock N more" teasers. The locked items never reach the client.
 */
export async function getIdeaBySlug(slug: string, opts: { entitled?: boolean } = {}) {
  const entitled = opts.entitled ?? false;
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

  const featuredIdeaId = await resolveFreePreviewIdeaId(idea.categoryId);
  if (!entitled && idea.id !== featuredIdeaId) {
    return { locked: true as const };
  }

  const { sourceJobId: _s, publishedById: _p, researchContext, ...rest } = idea;
  const preview = toIdeaPreview(rest);
  // Phase 5.4 — surface flattened summaries alongside the full researchContext.
  const ctx = researchContext;

  // Cross-link sections. Entitled users get full lists; non-entitled users (on
  // the one featured page they can reach) get featured-tier cross-links + counts.
  let siblingIdeas: Awaited<ReturnType<typeof getSiblingIdeas>> = [];
  let addressedPains: AddressedPainLookup = {};
  let addressedPainTitles: string[] = [];
  let siblingIdeasLockedCount = 0;
  let addressedLockedCount = 0;

  if (entitled) {
    const [si, ap] = await Promise.all([
      getSiblingIdeas(idea.categoryId, idea.id),
      resolvePainPointSlugs(idea.addressedPainTitles, idea.categoryId),
    ]);
    siblingIdeas = si;
    addressedPains = ap;
    addressedPainTitles = idea.addressedPainTitles ?? [];
  } else {
    // No other ideas surfaced — they're gated. Report how many for the CTA.
    siblingIdeasLockedCount = await prisma.catalogIdea.count({
      where: { categoryId: idea.categoryId, isActive: true, slug: { not: null }, id: { not: idea.id } },
    });
    // Keep only the featured pain among the pains this idea addresses (if any).
    // MUST filter addressedPainTitles too — the frontend renders its pain table
    // from that array, so leaving non-featured titles would leak them as text.
    const allAddressed = await resolvePainPointSlugs(idea.addressedPainTitles ?? [], idea.categoryId);
    const featuredPain = await freePreviewPainForCategory(idea.categoryId);
    const featuredTitle = featuredPain?.title ?? null;
    if (featuredTitle && allAddressed[featuredTitle]) {
      addressedPains = { [featuredTitle]: allAddressed[featuredTitle] };
      addressedPainTitles = [featuredTitle];
    }
    addressedLockedCount = Math.max(0, Object.keys(allAddressed).length - addressedPainTitles.length);
  }

  return {
    ...preview,
    // Engagement: distinct users who have run deep research on this idea.
    researchCount: idea.researchCount ?? 0,
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
    // Phase 2 — detail-page IA cross-links (gated above for non-entitled).
    siblingIdeas,
    addressedPains,
    addressedPainTitles,
    siblingIdeasLockedCount,
    addressedLockedCount,
  };
}

/**
 * Detail payload for a single pain point. Mirrors `getIdeaBySlug`'s gating: a
 * non-entitled user reaches only the ONE featured pain per sub-niche (else
 * `{ locked: true }` → 403). On the featured page, related ideas are limited to the
 * featured idea (if it addresses this pain) and sibling pains are hidden, with
 * locked counts for the teasers.
 */
export async function getPainPointBySlug(slug: string, opts: { entitled?: boolean } = {}) {
  const entitled = opts.entitled ?? false;
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

  const featuredPainId = await resolveFreePreviewPainId(pp.categoryId);
  if (!entitled && pp.id !== featuredPainId) {
    return { locked: true as const };
  }

  const { sourceJobId: _s, publishedById: _p, researchContext, ...rest } = pp;
  // Phase 5.4 — same flattened summaries as the idea detail endpoint.
  const ctx = researchContext;

  let siblingPains: Awaited<ReturnType<typeof getSiblingPainPoints>> = [];
  let relatedIdeas: Awaited<ReturnType<typeof getIdeasAddressingPain>> = [];
  let siblingPainsLockedCount = 0;
  let relatedIdeasLockedCount = 0;

  // rankInfo is this pain's OWN comparative rank (not a list of other items) —
  // always computed regardless of entitlement.
  const rankInfo = await getPainPointRank(pp.id, pp.categoryId);

  if (entitled) {
    const [sp, ri] = await Promise.all([
      getSiblingPainPoints(pp.themeId, pp.id, pp.categoryId),
      getIdeasAddressingPain(pp.title, pp.categoryId),
    ]);
    siblingPains = sp;
    relatedIdeas = ri;
  } else {
    // Sibling pains in this theme are gated — count for the CTA.
    siblingPainsLockedCount = pp.themeId
      ? await prisma.catalogPainPoint.count({
          where: {
            themeId: pp.themeId,
            categoryId: pp.categoryId,
            isActive: true,
            slug: { not: null },
            id: { not: pp.id },
          },
        })
      : 0;
    // Related ideas: surface ONLY the featured idea, and only if it addresses
    // this pain; everything else is gated. Count the rest for the CTA.
    const totalRelated = await prisma.catalogIdea.count({
      where: {
        isActive: true,
        categoryId: pp.categoryId,
        slug: { not: null },
        addressedPainTitles: { has: pp.title },
      },
    });
    const featuredIdeaRow = await freePreviewIdeaForCategory(pp.categoryId);
    const featuredAddresses = (featuredIdeaRow?.addressedPainTitles ?? []).includes(pp.title);
    if (featuredIdeaRow && featuredAddresses) {
      const { sourceJobId: _fs, publishedById: _fp, ...frest } = featuredIdeaRow;
      relatedIdeas = [toIdeaPreview(frest)];
      relatedIdeasLockedCount = Math.max(0, totalRelated - 1);
    } else {
      relatedIdeasLockedCount = totalRelated;
    }
  }

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
    // Phase 2 — detail-page IA cross-links (gated above for non-entitled).
    siblingPains,
    relatedIdeas,
    siblingPainsLockedCount,
    relatedIdeasLockedCount,
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

const TOTALS_CACHE_KEY = 'catalog:totals:v3';
const TOTALS_CACHE_TTL = 300;  // 5 min — same cadence as tree cache

interface CatalogTotals {
  totalIdeas: number;
  totalCategories: number;     // top-level (parentId IS NULL) — for the "Categories" tile
  totalSubcategories: number;  // child categories — for the "Sub-niches" tile
  // Per scope rule, this is content items (posts/threads) NOT communities.
  // Communities are per-niche on landing payloads, not aggregable globally.
  contentItemsMined: number;
  // Sum of redditCommentsAnalyzed across all contexts ("Comments analyzed" tile).
  commentsAnalyzed: number;
  // ISO timestamp of the most recent active idea or pain-point update — drives
  // the hero kicker dateline on /ideas. null when the catalog is empty.
  lastUpdated: string | null;
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

  const [
    totalIdeas,
    totalCategories,
    totalSubcategories,
    sumAgg,
    ideaMaxAgg,
    painPointMaxAgg,
  ] = await Promise.all([
    prisma.catalogIdea.count({ where: { isActive: true } }),
    prisma.catalogCategory.count({ where: { isActive: true, parentId: null } }),
    prisma.catalogCategory.count({ where: { isActive: true, parentId: { not: null } } }),
    prisma.catalogResearchContext.aggregate({
      _sum: {
        redditPostsAnalyzed: true,
        redditCommentsAnalyzed: true,
        twitterThreadsAnalyzed: true,
        genericPostsAnalyzed: true,
      },
    }),
    prisma.catalogIdea.aggregate({
      _max: { updatedAt: true },
      where: { isActive: true },
    }),
    prisma.catalogPainPoint.aggregate({
      _max: { updatedAt: true },
      where: { isActive: true },
    }),
  ]);

  const contentItemsMined =
    (sumAgg._sum.redditPostsAnalyzed ?? 0) +
    (sumAgg._sum.twitterThreadsAnalyzed ?? 0) +
    (sumAgg._sum.genericPostsAnalyzed ?? 0);

  const commentsAnalyzed = sumAgg._sum.redditCommentsAnalyzed ?? 0;

  // Take the larger of the two timestamps so the hero dateline reflects
  // *any* catalog content update, not just idea updates.
  const ideaTs = ideaMaxAgg._max.updatedAt;
  const painTs = painPointMaxAgg._max.updatedAt;
  const lastUpdatedDate =
    ideaTs && painTs ? (ideaTs > painTs ? ideaTs : painTs) : (ideaTs ?? painTs ?? null);

  const totals: CatalogTotals = {
    totalIdeas,
    totalCategories,
    totalSubcategories,
    contentItemsMined,
    commentsAnalyzed,
    lastUpdated: lastUpdatedDate ? lastUpdatedDate.toISOString() : null,
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
// Phase 6 — Cross-catalog top pain points (SEO landing surface on /ideas)
// =====================================================================
//
// Returns the N highest-severity active pain points across the entire
// catalog (any niche), with the source category + parent for linking back
// to /ideas/[parentSlug]/[childSlug]. Powers the "Most In-Demand SaaS
// Niches — {month}" table on the public /ideas index. Schema is already
// indexed for severityScore DESC; mention count breaks ties.

export interface CatalogTopPainPoint {
  id: string;
  slug: string;
  title: string;
  mentionCount: number;
  severityScore: number;
  opportunityLevel: string; // 'high' | 'medium' | 'low' in current data
  category: {
    id: string;
    name: string;
    slug: string;
    parent: { name: string; slug: string } | null;
  };
}

// Cache the top 25 pain points (the upper bound of the limit param) under a
// single key and slice on read. Limit is bounded 1–25, so worst-case storage
// is small and a single key trivializes invalidation. Mirrors the totals/
// landing/tree Redis pattern: defensive try/catch around read+write, fall
// through to DB on Redis errors.
const TOPPAIN_CACHE_KEY = 'catalog:top-pain-points:v1';
// Free-preview variant (only `isFreePreview` pains) — used by the landing "Sample Reports"
// marquee so the showcased cards are the items a non-subscriber can actually open.
const FREEPAIN_CACHE_KEY = 'catalog:free-pain-points:v1';
const TOPPAIN_CACHE_TTL = 300; // 5 min, matches /top-pain-points Cache-Control header
const TOPPAIN_CACHE_FETCH_SIZE = 25;

export async function getTopCatalogPainPoints(
  limit = 10,
  opts: { freeOnly?: boolean } = {},
): Promise<CatalogTopPainPoint[]> {
  const safeLimit = Math.min(Math.max(1, Math.floor(limit)), 25);
  const redis = getRedis();
  const cacheKey = opts.freeOnly ? FREEPAIN_CACHE_KEY : TOPPAIN_CACHE_KEY;

  try {
    const cached = await redis.get(cacheKey);
    if (cached) {
      const all = JSON.parse(cached) as CatalogTopPainPoint[];
      return all.slice(0, safeLimit);
    }
  } catch (err) {
    console.error('top-pain cache read failed:', err);
  }

  const rows = await prisma.catalogPainPoint.findMany({
    where: { isActive: true, slug: { not: null }, ...(opts.freeOnly ? { isFreePreview: true } : {}) },
    select: {
      id: true,
      slug: true,
      title: true,
      mentionCount: true,
      severityScore: true,
      opportunityLevel: true,
      category: {
        select: {
          id: true,
          name: true,
          slug: true,
          parent: { select: { name: true, slug: true } },
        },
      },
    },
    orderBy: [{ severityScore: 'desc' }, { mentionCount: 'desc' }],
    take: TOPPAIN_CACHE_FETCH_SIZE,
  });
  // `slug` is nullable in the schema but filtered above; assert it for the
  // return type so consumers don't have to null-check.
  const all: CatalogTopPainPoint[] = rows.map((r) => ({
    id: r.id,
    slug: r.slug as string,
    title: r.title,
    mentionCount: r.mentionCount,
    severityScore: r.severityScore,
    opportunityLevel: r.opportunityLevel,
    category: r.category,
  }));

  try {
    await redis.setex(cacheKey, TOPPAIN_CACHE_TTL, JSON.stringify(all));
  } catch (err) {
    console.error('top-pain cache write failed:', err);
  }

  return all.slice(0, safeLimit);
}

export async function invalidateTopCatalogPainPoints(): Promise<void> {
  try {
    // Clear both the top (severity-ranked) and free-preview variants so a re-seed or an
    // admin free-preview change refreshes the landing marquee immediately.
    await getRedis().del(TOPPAIN_CACHE_KEY, FREEPAIN_CACHE_KEY);
  } catch (err) {
    console.error('top-pain cache invalidate failed:', err);
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
