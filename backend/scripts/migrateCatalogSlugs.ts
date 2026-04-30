/**
 * Phase 2.5 — Slug migration script.
 *
 * Run AFTER applying migration `20260427100000_add_catalog_slug_columns_seo_fields_and_indexes`
 * and BEFORE applying any follow-up migration that enforces NOT NULL on slug
 * columns.
 *
 * Idempotent — safe to re-run after partial failure. Logs progress and
 * reports counts at the end.
 *
 * Usage:
 *   cd backend
 *   npx tsx scripts/migrateCatalogSlugs.ts
 *
 * What it does:
 * 1. CatalogCategory: ensures legacySlug is populated (already done by the
 *    migration SQL but defensive). For child categories, regenerates `slug`
 *    to local form (slugify(name) instead of legacy parent-prefixed form),
 *    with collision suffix scoped to parent.
 * 2. CatalogIdea: generates a public slug `[descriptor]-[niche]-[format]`
 *    capped at 8 segments, with numeric suffix on collision.
 * 3. CatalogPainPoint: same pattern, derived from title.
 *
 * Defaults `format` to 'saas' for any idea that doesn't yet carry a value.
 */

import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

const MAX_SLUG_SEGMENTS = 8;
const SLUG_MAX_LEN = 160;

function slugify(text: string): string {
  return text
    .toLowerCase()
    .normalize('NFKD')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, SLUG_MAX_LEN);
}

function capSegments(slug: string, max: number): string {
  const segments = slug.split('-').filter(Boolean);
  return segments.slice(0, max).join('-');
}

async function uniqueIdeaSlug(base: string): Promise<string> {
  let candidate = base;
  let i = 2;
  // The slug is unique across CatalogIdea; we use findFirst because slug is
  // nullable and we want to skip NULL collisions.
  while (await prisma.catalogIdea.findFirst({ where: { slug: candidate } })) {
    candidate = `${base}-${i}`;
    i++;
    if (i > 200) throw new Error(`Could not generate unique idea slug for base "${base}"`);
  }
  return candidate;
}

async function uniquePainPointSlug(base: string): Promise<string> {
  let candidate = base;
  let i = 2;
  while (await prisma.catalogPainPoint.findFirst({ where: { slug: candidate } })) {
    candidate = `${base}-${i}`;
    i++;
    if (i > 200) throw new Error(`Could not generate unique pain-point slug for base "${base}"`);
  }
  return candidate;
}

async function uniqueCategorySlugUnderParent(
  base: string,
  parentId: string | null,
  excludeId: string,
): Promise<string> {
  let candidate = base;
  let i = 2;
  while (
    await prisma.catalogCategory.findFirst({
      where: {
        parentId,
        slug: candidate,
        id: { not: excludeId },
      },
    })
  ) {
    candidate = `${base}-${i}`;
    i++;
    if (i > 200) throw new Error(`Could not generate unique category slug for base "${base}"`);
  }
  return candidate;
}

async function migrateCategories(): Promise<{ updated: number; skipped: number }> {
  // Only child categories may have legacy parent-prefixed slugs (`saas-b2b-tools`).
  // Top-level categories keep their existing slug.
  const children = await prisma.catalogCategory.findMany({
    where: { parentId: { not: null } },
    select: { id: true, name: true, slug: true, legacySlug: true, parentId: true },
  });

  let updated = 0;
  let skipped = 0;

  for (const child of children) {
    const desiredBase = slugify(child.name);
    if (!desiredBase) {
      console.warn(`[skip] category ${child.id} (${child.name}) — could not slugify name`);
      skipped++;
      continue;
    }

    // If the current slug is already the local form (no parent prefix), nothing to do.
    if (child.slug === desiredBase) {
      skipped++;
      continue;
    }

    const newSlug = await uniqueCategorySlugUnderParent(desiredBase, child.parentId, child.id);

    await prisma.catalogCategory.update({
      where: { id: child.id },
      data: {
        slug: newSlug,
        // Preserve the legacy slug for redirect lookups; only set if not already populated.
        legacySlug: child.legacySlug ?? child.slug,
      },
    });
    updated++;
  }

  return { updated, skipped };
}

async function migrateIdeas(): Promise<{ updated: number; skipped: number }> {
  const ideas = await prisma.catalogIdea.findMany({
    where: { slug: null },
    select: {
      id: true,
      solutionName: true,
      format: true,
      categoryId: true,
      category: { select: { slug: true, parent: { select: { slug: true } } } },
    },
  });

  let updated = 0;
  let skipped = 0;

  for (const idea of ideas) {
    const descriptorRaw = slugify(idea.solutionName);
    if (!descriptorRaw) {
      console.warn(`[skip] idea ${idea.id} (${idea.solutionName}) — could not slugify name`);
      skipped++;
      continue;
    }

    const nicheSlug = idea.category.parent?.slug ?? idea.category.slug;
    const formatSlug = (idea.format && slugify(idea.format)) || 'saas';

    // Build descriptor-niche-format, then cap to 8 segments.
    const composed = `${descriptorRaw}-${nicheSlug}-${formatSlug}`;
    const base = capSegments(composed, MAX_SLUG_SEGMENTS);
    const slug = await uniqueIdeaSlug(base);

    await prisma.catalogIdea.update({
      where: { id: idea.id },
      data: { slug, format: idea.format ?? 'saas' },
    });
    updated++;
  }

  return { updated, skipped };
}

async function migratePainPoints(): Promise<{ updated: number; skipped: number }> {
  const pps = await prisma.catalogPainPoint.findMany({
    where: { slug: null },
    select: {
      id: true,
      title: true,
      categoryId: true,
      category: { select: { slug: true, parent: { select: { slug: true } } } },
    },
  });

  let updated = 0;
  let skipped = 0;

  for (const pp of pps) {
    const descriptorRaw = slugify(pp.title);
    if (!descriptorRaw) {
      console.warn(`[skip] pain-point ${pp.id} (${pp.title}) — could not slugify title`);
      skipped++;
      continue;
    }

    const nicheSlug = pp.category.parent?.slug ?? pp.category.slug;
    const composed = `${descriptorRaw}-${nicheSlug}-pain`;
    const base = capSegments(composed, MAX_SLUG_SEGMENTS);
    const slug = await uniquePainPointSlug(base);

    await prisma.catalogPainPoint.update({
      where: { id: pp.id },
      data: { slug },
    });
    updated++;
  }

  return { updated, skipped };
}

async function main() {
  console.log('=== Phase 2.5 — Catalog slug migration ===\n');

  console.log('1) CatalogCategory: regenerating child slugs to local form…');
  const cats = await migrateCategories();
  console.log(`   updated=${cats.updated}  skipped=${cats.skipped}\n`);

  console.log('2) CatalogIdea: generating descriptor-niche-format slugs…');
  const ideas = await migrateIdeas();
  console.log(`   updated=${ideas.updated}  skipped=${ideas.skipped}\n`);

  console.log('3) CatalogPainPoint: generating descriptor-niche-pain slugs…');
  const pps = await migratePainPoints();
  console.log(`   updated=${pps.updated}  skipped=${pps.skipped}\n`);

  // Sanity check: how many rows still lack a slug?
  const [ideaNullCount, ppNullCount] = await Promise.all([
    prisma.catalogIdea.count({ where: { slug: null } }),
    prisma.catalogPainPoint.count({ where: { slug: null } }),
  ]);

  console.log('=== Verification ===');
  console.log(`   CatalogIdea NULL slug count:      ${ideaNullCount}`);
  console.log(`   CatalogPainPoint NULL slug count: ${ppNullCount}`);

  if (ideaNullCount === 0 && ppNullCount === 0) {
    console.log('\n[OK] Backfill complete. Safe to apply the follow-up migration that enforces NOT NULL.');
  } else {
    console.log('\n[WARN] Some rows still lack slugs. Investigate before enforcing NOT NULL.');
  }
}

main()
  .catch((err) => {
    console.error('Migration failed:', err);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
