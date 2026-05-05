/**
 * Phase 11 of detail-page IA rework — backfill `CatalogPainPoint.themeId` for
 * legacy rows ingested before the column was projected.
 *
 * Strategy: each pain row's parent CatalogResearchContext has a
 * `detailedPainPoints` JSON array (projected by researchContextService.ts:495
 * from report.detailed_pain_points). Each entry carries a `title` and a
 * `parent_theme_id` (Pydantic PainPoint.parent_theme_id). For each row with
 * `themeId IS NULL`, find the matching entry by title and copy its
 * `parent_theme_id` to the column.
 *
 * Title resilience: tries exact match first; falls back to a normalized
 * comparison (case-insensitive, punctuation-stripped) so worker-side merges
 * that mutate stored titles slightly don't break the join.
 *
 * Usage:
 *   cd backend
 *   DRY_RUN=1 npx tsx scripts/backfillPainPointThemeIds.ts   # log only
 *   npx tsx scripts/backfillPainPointThemeIds.ts             # apply
 *
 * Idempotent — safe to re-run. Reports {matched, unmatched, alreadySet, skipped}.
 */

import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();
const DRY_RUN = process.env.DRY_RUN === '1';

interface Counts {
  matched: number;          // null → set to a theme_id
  unmatched: number;        // no detailedPainPoints entry matches the title
  alreadySet: number;       // themeId was already set (skipped)
  skipped: number;          // no researchContext, no detailedPainPoints, etc.
}

/** Normalize a title for fuzzy match. Lowercase + strip punctuation/whitespace. */
function normalizeTitle(s: string): string {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, '');
}

interface PainPointEntry {
  title?: unknown;
  parent_theme_id?: unknown;
  parentThemeId?: unknown;  // tolerate either snake_case or camelCase projection
}

function findThemeIdForTitle(
  detailedPainPoints: unknown,
  targetTitle: string,
): string | null {
  if (!Array.isArray(detailedPainPoints)) return null;
  const target = targetTitle.trim();
  const targetNorm = normalizeTitle(target);

  // Exact match first.
  for (const entry of detailedPainPoints as PainPointEntry[]) {
    if (!entry || typeof entry !== 'object') continue;
    const t = entry.title;
    if (typeof t !== 'string') continue;
    if (t.trim() === target) {
      const id = entry.parent_theme_id ?? entry.parentThemeId;
      return typeof id === 'string' && id.trim() !== '' ? id : null;
    }
  }
  // Normalized fallback.
  for (const entry of detailedPainPoints as PainPointEntry[]) {
    if (!entry || typeof entry !== 'object') continue;
    const t = entry.title;
    if (typeof t !== 'string') continue;
    if (normalizeTitle(t) === targetNorm) {
      const id = entry.parent_theme_id ?? entry.parentThemeId;
      return typeof id === 'string' && id.trim() !== '' ? id : null;
    }
  }
  return null;
}

async function main() {
  const counts: Counts = { matched: 0, unmatched: 0, alreadySet: 0, skipped: 0 };

  const rows = await prisma.catalogPainPoint.findMany({
    where: { isActive: true },
    include: {
      researchContext: { select: { detailedPainPoints: true } },
    },
  });

  console.log(`[backfillPainPointThemeIds] Loaded ${rows.length} active pain points. DRY_RUN=${DRY_RUN}`);

  const unmatchedSamples: Array<{ id: string; title: string }> = [];

  for (const pp of rows) {
    if (typeof pp.themeId === 'string' && pp.themeId.trim() !== '') {
      counts.alreadySet++;
      continue;
    }
    const ctx = pp.researchContext;
    if (!ctx?.detailedPainPoints) {
      counts.skipped++;
      continue;
    }

    const themeId = findThemeIdForTitle(ctx.detailedPainPoints, pp.title);
    if (themeId) {
      counts.matched++;
      if (!DRY_RUN) {
        await prisma.catalogPainPoint.update({
          where: { id: pp.id },
          data: { themeId },
        });
      }
    } else {
      counts.unmatched++;
      if (unmatchedSamples.length < 10) {
        unmatchedSamples.push({ id: pp.id, title: pp.title });
      }
    }
  }

  console.log('[backfillPainPointThemeIds] Counts:', counts);
  if (unmatchedSamples.length > 0) {
    console.log('[backfillPainPointThemeIds] First unmatched samples:');
    for (const s of unmatchedSamples) {
      console.log(`  - id=${s.id}: "${s.title}"`);
    }
  }
  console.log(
    `[backfillPainPointThemeIds] ${DRY_RUN ? 'DRY-RUN — no writes' : 'Updates applied'}.`,
  );
}

main()
  .catch((err) => {
    console.error('[backfillPainPointThemeIds] Error:', err);
    process.exit(1);
  })
  .finally(() => prisma.$disconnect());
