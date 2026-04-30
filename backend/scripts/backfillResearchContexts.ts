/**
 * Phase 5 — Backfill CatalogResearchContext rows for every existing catalog item.
 *
 * Run AFTER applying Migration A (`20260428100000_add_catalog_research_context_table`)
 * and BEFORE applying Migration B that adds the required FK relations on
 * CatalogIdea / CatalogPainPoint. Migration B will fail unless every distinct
 * sourceJobId across both tables has a backing context row.
 *
 * Idempotent — safe to re-run. Real (non-placeholder) rows are returned
 * unchanged; placeholder rows are re-attempted (with `forceRefreshPlaceholders`)
 * so a re-run upgrades placeholders to real rows when the underlying
 * `report.json` becomes available between runs.
 *
 * Usage:
 *   cd backend
 *   npx tsx scripts/backfillResearchContexts.ts
 *
 * Reports counts: `inserted=N upgraded=M placeholders=K skipped=S` where
 *   inserted   — fresh real rows created from a parseable report.json
 *   upgraded   — existing placeholders flipped to real rows on this run
 *   placeholders — placeholder rows still missing report.json after this run
 *   skipped    — real rows that already existed (returned unchanged)
 */

import { PrismaClient } from '@prisma/client';
import { extractOrCreateResearchContext } from '../src/services/researchContextService.js';

const prisma = new PrismaClient();

interface RunCounts {
  inserted: number;
  upgraded: number;
  placeholders: number;
  skipped: number;
}

async function getDistinctSourceJobIds(): Promise<string[]> {
  // Active AND inactive items both need backing rows — Migration B will add a
  // required FK that applies to every row regardless of isActive.
  const ideaJobs = await prisma.catalogIdea.findMany({
    select: { sourceJobId: true },
    distinct: ['sourceJobId'],
  });
  const painPointJobs = await prisma.catalogPainPoint.findMany({
    select: { sourceJobId: true },
    distinct: ['sourceJobId'],
  });
  const set = new Set<string>();
  for (const row of ideaJobs) set.add(row.sourceJobId);
  for (const row of painPointJobs) set.add(row.sourceJobId);
  return [...set];
}

async function main(): Promise<void> {
  console.log('[backfillResearchContexts] Starting…');
  const sourceJobIds = await getDistinctSourceJobIds();
  console.log(`[backfillResearchContexts] Found ${sourceJobIds.length} distinct sourceJobIds`);

  const counts: RunCounts = { inserted: 0, upgraded: 0, placeholders: 0, skipped: 0 };

  // CLI flag --force-refresh re-projects ALL rows (including real rows) —
  // use after a schema migration that adds new projected fields.
  const forceRefreshAll = process.argv.includes('--force-refresh');
  if (forceRefreshAll) {
    console.log(
      '[backfillResearchContexts] --force-refresh active: ALL rows will be re-projected from report.json',
    );
  }

  for (const sourceJobId of sourceJobIds) {
    // Snapshot the row state before extraction so we can classify the outcome.
    const before = await prisma.catalogResearchContext.findUnique({
      where: { sourceJobId },
      select: { dataQualityTier: true, audienceMapping: true },
    });

    let after;
    try {
      after = await extractOrCreateResearchContext(sourceJobId, {
        forceRefreshPlaceholders: true,
        forceRefreshAll,
      });
    } catch (err) {
      console.error(`[backfillResearchContexts] FAILED for ${sourceJobId}:`, err);
      continue;
    }

    const wasPlaceholder =
      before != null &&
      before.dataQualityTier === 'INSUFFICIENT' &&
      before.audienceMapping == null;
    const isPlaceholder =
      after.dataQualityTier === 'INSUFFICIENT' && after.audienceMapping == null;

    if (before == null) {
      if (isPlaceholder) {
        counts.placeholders++;
        console.warn(
          `[backfillResearchContexts] sourceJobId=${sourceJobId} → PLACEHOLDER (report.json missing)`,
        );
      } else {
        counts.inserted++;
      }
    } else if (wasPlaceholder && !isPlaceholder) {
      counts.upgraded++;
    } else if (wasPlaceholder && isPlaceholder) {
      counts.placeholders++;
    } else {
      counts.skipped++;
    }
  }

  console.log(
    `[backfillResearchContexts] Done. inserted=${counts.inserted} upgraded=${counts.upgraded} placeholders=${counts.placeholders} skipped=${counts.skipped}`,
  );

  // Final verification: zero distinct sourceJobIds should now be missing a row.
  const orphans = await prisma.$queryRaw<{ count: bigint }[]>`
    SELECT count(*) as count FROM (
      SELECT DISTINCT "sourceJobId" FROM "CatalogIdea"
      UNION
      SELECT DISTINCT "sourceJobId" FROM "CatalogPainPoint"
    ) s
    WHERE NOT EXISTS (
      SELECT 1 FROM "CatalogResearchContext" c WHERE c."sourceJobId" = s."sourceJobId"
    )
  `;
  const missing = Number(orphans[0]?.count ?? 0);
  if (missing > 0) {
    console.error(
      `[backfillResearchContexts] FAIL: ${missing} sourceJobIds still missing context rows. Migration B will fail. Investigate before proceeding.`,
    );
    process.exit(1);
  }
  console.log('[backfillResearchContexts] OK: every distinct sourceJobId has a context row.');
}

main()
  .catch((err) => {
    console.error('[backfillResearchContexts] FATAL:', err);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
