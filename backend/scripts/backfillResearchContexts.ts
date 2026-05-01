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
 *   npx tsx scripts/backfillResearchContexts.ts                     # default: upgrade placeholders only
 *   npx tsx scripts/backfillResearchContexts.ts --force-refresh     # re-project ALL rows
 *   npx tsx scripts/backfillResearchContexts.ts --from-checkpoints  # Phase 5.5: synthesize
 *                                                                     missing fields from
 *                                                                     output/checkpoints stage files
 *   npx tsx scripts/backfillResearchContexts.ts --from-checkpoints --dry-run  # log only
 *
 * The `--force-refresh` mode is the canonical way to backfill new projected
 * fields after a schema migration. Phase 5.4 (catalog rebuild) added
 * `keywordClusters` and `themeSeverityScores` columns — run with
 * `--force-refresh` once after deploy to populate them on existing rows.
 *
 * The `--from-checkpoints` mode (Phase 5.5) handles rows whose preview_report
 * was materialized BEFORE the materializer was extended to carry pain analysis
 * prose / quality signals. It locates the matching checkpoint directory via
 * job_id substring match (`checkpoint_<niche>_<jobId>_<timestamp>/`), reads
 * stage_3_pain_points.json + stage_4_audience_mapping.json + stage_1_niche_context.json
 * + metadata.json, synthesizes a preview-shaped report, and re-projects.
 * Idempotent. Logs `no checkpoint found` for unmatchable rows.
 *
 * Reports counts: `inserted=N upgraded=M placeholders=K skipped=S` where
 *   inserted   — fresh real rows created from a parseable report.json
 *   upgraded   — existing placeholders flipped to real rows on this run
 *   placeholders — placeholder rows still missing report.json after this run
 *   skipped    — real rows that already existed (returned unchanged)
 */

import { PrismaClient } from '@prisma/client';
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import {
  extractOrCreateResearchContext,
  projectFromBlob,
} from '../src/services/researchContextService.js';

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

// Phase 5.5 — checkpoint discovery + synthesis.
//
// The pipeline writes per-stage state into output/checkpoints/checkpoint_<niche>_<jobId>_<timestamp>/.
// We locate the dir via job_id substring match in the directory name. Multiple
// matches (rare — re-runs of the same job) → pick newest by mtime.
const CHECKPOINTS_DIR = join(process.cwd(), '..', 'output', 'checkpoints');

function findCheckpointDir(jobId: string): string | null {
  if (!existsSync(CHECKPOINTS_DIR)) return null;
  const entries = readdirSync(CHECKPOINTS_DIR, { withFileTypes: true });
  const matching: { path: string; mtime: number }[] = [];
  for (const e of entries) {
    if (!e.isDirectory()) continue;
    if (!e.name.includes(jobId)) continue;
    const path = join(CHECKPOINTS_DIR, e.name);
    try {
      matching.push({ path, mtime: statSync(path).mtimeMs });
    } catch {
      /* skip unreadable */
    }
  }
  if (matching.length === 0) return null;
  matching.sort((a, b) => b.mtime - a.mtime);
  return matching[0].path;
}

function tryReadJson(path: string): Record<string, unknown> | null {
  if (!existsSync(path)) return null;
  try {
    const parsed = JSON.parse(readFileSync(path, 'utf-8'));
    return parsed && typeof parsed === 'object' ? (parsed as Record<string, unknown>) : null;
  } catch (err) {
    console.warn(`[backfillResearchContexts] Failed to read ${path}:`, err);
    return null;
  }
}

/**
 * Synthesize a preview-shaped report blob from checkpoint stage files.
 * Mirrors what _materialize_preview_report would have produced if it had run
 * with the Phase 5.5 carry-set (pain_analysis_summary / top_pain_categories /
 * pain_total_mentions + full data_quality_summary).
 */
function synthesizeFromCheckpoints(checkpointDir: string): Record<string, unknown> | null {
  const stage1 = tryReadJson(join(checkpointDir, 'stage_1_niche_context.json'));
  const stage3 = tryReadJson(join(checkpointDir, 'stage_3_pain_points.json'));
  const stage4 = tryReadJson(join(checkpointDir, 'stage_4_audience_mapping.json'));
  const metadata = tryReadJson(join(checkpointDir, 'metadata.json'));

  // Stage 3 is load-bearing — it carries content_categorization + pain_analysis fields.
  // Without it, the synthesis offers nothing the existing preview lacked.
  if (!stage3) return null;

  const synthesized: Record<string, unknown> = {};
  if (stage1) synthesized.niche_context = stage1;
  if (stage4) synthesized.audience_mapping = stage4;
  if (stage3.content_categorization) synthesized.content_categorization = stage3.content_categorization;
  if (stage3.pain_points) synthesized.detailed_pain_points = stage3.pain_points;
  if (typeof stage3.analysis_summary === 'string') synthesized.pain_analysis_summary = stage3.analysis_summary;
  if (Array.isArray(stage3.top_categories)) synthesized.top_pain_categories = stage3.top_categories;
  if (typeof stage3.total_mentions === 'number') synthesized.pain_total_mentions = stage3.total_mentions;
  if (metadata) {
    synthesized.data_quality_summary = {
      pain_point_quality_tier: metadata.pain_point_quality_tier ?? null,
      social_content_quality_tier: metadata.social_content_quality_tier ?? null,
      pain_point_confidence_score: metadata.pain_point_confidence_score ?? null,
      social_content_metrics: metadata.social_content_metrics ?? null,
    };
  }
  return synthesized;
}

interface CheckpointBackfillCounts {
  enriched: number;       // rows updated with newly-synthesized data
  noCheckpoint: number;   // job_id had no matching checkpoint dir
  noStage3: number;       // checkpoint dir found but no stage_3 file
  alreadyHas: number;     // row already has all the Phase 5.5 fields populated
}

async function runFromCheckpoints(dryRun: boolean): Promise<void> {
  console.log(
    `[backfillResearchContexts] --from-checkpoints active${dryRun ? ' (DRY RUN)' : ''}.`,
  );
  // Target rows: any context lacking categorizationSummary OR painAnalysisSummary
  // (the two scalar fields that prove Phase 5.5 ran). Filter Prisma-side to
  // avoid loading every row.
  const candidates = await prisma.catalogResearchContext.findMany({
    where: {
      OR: [
        { categorizationSummary: null },
        { painAnalysisSummary: null },
        { nicheContext: { equals: null } },
      ],
    },
    select: { sourceJobId: true, categorizationSummary: true, painAnalysisSummary: true },
  });
  console.log(`[backfillResearchContexts] ${candidates.length} candidate rows missing Phase 5.5 fields.`);

  const counts: CheckpointBackfillCounts = {
    enriched: 0,
    noCheckpoint: 0,
    noStage3: 0,
    alreadyHas: 0,
  };

  for (const row of candidates) {
    const checkpointDir = findCheckpointDir(row.sourceJobId);
    if (!checkpointDir) {
      counts.noCheckpoint++;
      console.warn(`[backfillResearchContexts] no checkpoint sourceJobId=${row.sourceJobId}`);
      continue;
    }
    const synthesized = synthesizeFromCheckpoints(checkpointDir);
    if (!synthesized) {
      counts.noStage3++;
      console.warn(
        `[backfillResearchContexts] no stage_3 in ${checkpointDir} sourceJobId=${row.sourceJobId}`,
      );
      continue;
    }
    if (dryRun) {
      counts.enriched++;
      const keys = Object.keys(synthesized).join(', ');
      console.log(
        `[backfillResearchContexts] DRY RUN sourceJobId=${row.sourceJobId} would project: ${keys}`,
      );
      continue;
    }
    try {
      await projectFromBlob(row.sourceJobId, synthesized, { sourceKind: 'catalog' });
      counts.enriched++;
    } catch (err) {
      console.error(`[backfillResearchContexts] FAILED sourceJobId=${row.sourceJobId}:`, err);
    }
  }

  console.log(
    `[backfillResearchContexts] --from-checkpoints done. enriched=${counts.enriched} noCheckpoint=${counts.noCheckpoint} noStage3=${counts.noStage3}`,
  );
}

async function main(): Promise<void> {
  const fromCheckpoints = process.argv.includes('--from-checkpoints');
  const dryRun = process.argv.includes('--dry-run');

  if (fromCheckpoints) {
    await runFromCheckpoints(dryRun);
    return;
  }

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
