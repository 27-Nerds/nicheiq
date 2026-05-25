/**
 * Seed the per-sub-niche free preview: pick a RANDOM active idea + pain in each category and
 * flag it `isFreePreview` (the single publicly-visible item when not entitled). This is the
 * stable seed — the gate keys solely on `isFreePreview`, with no score-based fallback.
 *
 * Usage:
 *   cd backend
 *   npx tsx scripts/assignFreePreview.ts              # assign-where-missing (idempotent, sticky)
 *   npx tsx scripts/assignFreePreview.ts --reassign   # force re-randomize EVERY category
 *   npm run assign:free-preview [-- --reassign]
 *
 * Default mode skips categories that already have an ACTIVE flagged item (so re-runs don't
 * reshuffle), but re-seeds any whose previous pick went inactive. `--reassign` re-randomizes all.
 * Each category is updated clear-FIRST-then-set in one transaction to satisfy the partial unique
 * index (one isFreePreview per category). Touched categories get their landing cache invalidated.
 */

import { pathToFileURL } from 'node:url';
import { prisma } from '../src/services/db.js';
import {
  invalidateCategoryLanding,
  invalidateCatalogTotals,
  invalidateTopCatalogPainPoints,
} from '../src/services/catalogService.js';

const REASSIGN = process.argv.includes('--reassign');

/** Pick a random element's id, or null for an empty list. Pure — unit-testable. */
export function pickRandom<T extends { id: string }>(rows: T[]): string | null {
  if (rows.length === 0) return null;
  return rows[Math.floor(Math.random() * rows.length)].id;
}

interface Counts {
  ideasAssigned: number;
  ideasSkipped: number;
  ideasNoItems: number;
  painsAssigned: number;
  painsSkipped: number;
  painsNoItems: number;
}

async function main(): Promise<void> {
  const counts: Counts = {
    ideasAssigned: 0,
    ideasSkipped: 0,
    ideasNoItems: 0,
    painsAssigned: 0,
    painsSkipped: 0,
    painsNoItems: 0,
  };
  const touched = new Set<string>();

  const categories = await prisma.catalogCategory.findMany({
    where: { isActive: true },
    select: { id: true },
  });
  console.log(`[assignFreePreview] ${categories.length} active categories · mode=${REASSIGN ? 'reassign-all' : 'assign-where-missing'}`);

  for (const { id: categoryId } of categories) {
    // ----- Ideas -----
    if (!REASSIGN) {
      const existing = await prisma.catalogIdea.findFirst({
        where: { categoryId, isActive: true, slug: { not: null }, isFreePreview: true },
        select: { id: true },
      });
      if (existing) counts.ideasSkipped++;
      else await assignIdea(categoryId, counts, touched);
    } else {
      await assignIdea(categoryId, counts, touched);
    }

    // ----- Pain points -----
    if (!REASSIGN) {
      const existing = await prisma.catalogPainPoint.findFirst({
        where: { categoryId, isActive: true, slug: { not: null }, isFreePreview: true },
        select: { id: true },
      });
      if (existing) counts.painsSkipped++;
      else await assignPain(categoryId, counts, touched);
    } else {
      await assignPain(categoryId, counts, touched);
    }
  }

  // Reflect the new picks in the public teaser immediately.
  for (const categoryId of touched) {
    await invalidateCategoryLanding(categoryId);
  }
  if (touched.size > 0) {
    await invalidateCatalogTotals();
    await invalidateTopCatalogPainPoints();
  }

  console.log('[assignFreePreview] Done:', counts, `· categories touched: ${touched.size}`);
}

async function assignIdea(categoryId: string, counts: Counts, touched: Set<string>): Promise<void> {
  const candidates = await prisma.catalogIdea.findMany({
    where: { categoryId, isActive: true, slug: { not: null } },
    select: { id: true },
  });
  const chosen = pickRandom(candidates);
  if (!chosen) {
    counts.ideasNoItems++;
    return;
  }
  // Clear FIRST (incl. any inactive flagged row) then set — the partial unique index forbids
  // two flagged rows in a category at any statement boundary.
  await prisma.$transaction([
    prisma.catalogIdea.updateMany({ where: { categoryId, isFreePreview: true }, data: { isFreePreview: false } }),
    prisma.catalogIdea.update({ where: { id: chosen }, data: { isFreePreview: true } }),
  ]);
  counts.ideasAssigned++;
  touched.add(categoryId);
}

async function assignPain(categoryId: string, counts: Counts, touched: Set<string>): Promise<void> {
  const candidates = await prisma.catalogPainPoint.findMany({
    where: { categoryId, isActive: true, slug: { not: null } },
    select: { id: true },
  });
  const chosen = pickRandom(candidates);
  if (!chosen) {
    counts.painsNoItems++;
    return;
  }
  await prisma.$transaction([
    prisma.catalogPainPoint.updateMany({ where: { categoryId, isFreePreview: true }, data: { isFreePreview: false } }),
    prisma.catalogPainPoint.update({ where: { id: chosen }, data: { isFreePreview: true } }),
  ]);
  counts.painsAssigned++;
  touched.add(categoryId);
}

// Only run when invoked directly (so the pure `pickRandom` helper is importable by tests
// without triggering a DB-mutating run).
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main()
    .catch((err) => {
      console.error('[assignFreePreview] Error:', err);
      process.exit(1);
    })
    .finally(() => prisma.$disconnect());
}
