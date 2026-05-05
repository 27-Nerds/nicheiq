/**
 * Phase 1 of detail-page IA rework — backfill `CatalogIdea.addressedPainTitles`
 * for historical rows.
 *
 * Critical correctness rule: many CatalogIdea rows can share one
 * CatalogResearchContext (one selected idea + N alternatives + M
 * worker-generated all FK to the same context via sourceJobId). The shared
 * context stores ONE `selectedSolution` blob with `pain_points_addressed`.
 * Naively copying that into every row would write the SELECTED solution's
 * pain titles onto alternatives and worker-generated ideas — wrong.
 *
 * Classification:
 *   - selectedPopulated: row is the per-job selected idea
 *       (sourceItemIndex === -1 AND solutionName matches
 *        researchContext.selectedSolutionName, case-insensitive trim)
 *       → copy from researchContext.selectedSolution.pain_points_addressed
 *   - alternativeCleared: row is a publishIdea-published alternative
 *       (sourceItemIndex >= 0, publishedById !== 'system')
 *       → set [] (alternatives have no pain mapping in their Pydantic model;
 *         Phase 8 of the plan extends the model — this script can be re-run
 *         after that to also populate from researchContext.alternativeSolutions)
 *   - workerCleared: row is a worker-generated catalog idea
 *       (publishedById === 'system' per workers.ts:1459)
 *       → set [] (the original pain_points_addressed payload was lost on
 *         insert; rely on the new write-path B for future runs)
 *   - skipped: row is something else (legacy / unclassifiable) → set [] + log
 *
 * Usage:
 *   cd backend
 *   DRY_RUN=1 npx tsx scripts/backfillAddressedPains.ts   # log only
 *   npx tsx scripts/backfillAddressedPains.ts             # apply
 *
 * Idempotent — safe to re-run.
 */

import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

const DRY_RUN = process.env.DRY_RUN === '1';

interface ClassificationCounts {
  selectedPopulated: number;
  alternativeCleared: number;
  workerCleared: number;
  skipped: number;
}

function extractPainTitles(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((s): s is string => typeof s === 'string' && s.trim() !== '');
}

async function main() {
  const counts: ClassificationCounts = {
    selectedPopulated: 0,
    alternativeCleared: 0,
    workerCleared: 0,
    skipped: 0,
  };

  // researchContext is a Prisma RELATION on CatalogIdea (FK), NOT a JSON column.
  // Must use `include` to fetch it. Also pull alternativeSolutions so we can
  // read pain_points_addressed for alternative rows once Phase 8 has been
  // applied to fresh reports.
  const ideas = await prisma.catalogIdea.findMany({
    where: { isActive: true },
    include: {
      researchContext: {
        select: {
          selectedSolution: true,
          selectedSolutionName: true,
          alternativeSolutions: true,
        },
      },
    },
  });

  console.log(`[backfillAddressedPains] Loaded ${ideas.length} active ideas. DRY_RUN=${DRY_RUN}`);

  for (const idea of ideas) {
    const ctx = idea.researchContext;
    let titles: string[] = [];

    // Phase 13 — also populate idea-specific BaseSolutionIdea fields. Only the
    // selected-solution branch can recover these (alternatives + worker rows
    // don't have the source payload preserved in researchContext).
    let phase13Fields: {
      whyItWorks: string | null;
      conventionalApproach: string | null;
      innovationAngle: string | null;
      estimatedCacPaid: string | null;
      organicDiscoveryQueries: string[];
    } = {
      whyItWorks: null,
      conventionalApproach: null,
      innovationAngle: null,
      estimatedCacPaid: null,
      organicDiscoveryQueries: [],
    };

    const isSelected =
      idea.sourceItemIndex === -1 &&
      typeof ctx?.selectedSolutionName === 'string' &&
      idea.solutionName.trim().toLowerCase() === ctx.selectedSolutionName.trim().toLowerCase();

    if (isSelected) {
      const sel = ctx.selectedSolution as Record<string, unknown> | null | undefined;
      titles = extractPainTitles(sel?.pain_points_addressed);
      phase13Fields = {
        whyItWorks: typeof sel?.why_it_works === 'string' ? sel.why_it_works : null,
        conventionalApproach: typeof sel?.conventional_approach === 'string' ? sel.conventional_approach : null,
        innovationAngle: typeof sel?.innovation_angle === 'string' ? sel.innovation_angle : null,
        estimatedCacPaid: typeof sel?.estimated_cac_paid === 'string' ? sel.estimated_cac_paid : null,
        organicDiscoveryQueries: Array.isArray(sel?.organic_discovery_queries)
          ? (sel.organic_discovery_queries as unknown[]).filter((s): s is string => typeof s === 'string')
          : [],
      };
      counts.selectedPopulated++;
    } else if (idea.publishedById === 'system') {
      counts.workerCleared++;
    } else if (idea.sourceItemIndex >= 0) {
      // Phase 8 — opportunistically read pain_points_addressed from the matching
      // alternativeSolutions[itemIndex] entry. Reports projected before the
      // Phase 8 model change won't have this field → falls through to [].
      const alts = ctx?.alternativeSolutions;
      if (Array.isArray(alts) && alts[idea.sourceItemIndex] && typeof alts[idea.sourceItemIndex] === 'object') {
        const alt = alts[idea.sourceItemIndex] as Record<string, unknown>;
        titles = extractPainTitles(alt.pain_points_addressed);
        // Phase 13 — alternatives may also carry estimated_cac_paid (the only
        // overlap field on the AlternativeSolution Pydantic model). Other
        // fields stay null per documented v1 limitation.
        if (typeof alt.estimated_cac_paid === 'string') {
          phase13Fields.estimatedCacPaid = alt.estimated_cac_paid;
        }
      }
      counts.alternativeCleared++;
    } else {
      counts.skipped++;
      console.warn(
        `[backfillAddressedPains] Unclassified row id=${idea.id} solutionName="${idea.solutionName}" sourceItemIndex=${idea.sourceItemIndex} publishedById=${idea.publishedById}`,
      );
    }

    if (!DRY_RUN) {
      await prisma.catalogIdea.update({
        where: { id: idea.id },
        data: { addressedPainTitles: titles, ...phase13Fields },
      });
    }
  }

  console.log('[backfillAddressedPains] Classification counts:', counts);
  console.log(
    `[backfillAddressedPains] ${DRY_RUN ? 'DRY-RUN — no writes' : 'Updates applied'}.`,
  );
}

main()
  .catch((err) => {
    console.error('[backfillAddressedPains] Error:', err);
    process.exit(1);
  })
  .finally(() => prisma.$disconnect());
