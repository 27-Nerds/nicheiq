import { Router, Response } from 'express';
import { z } from 'zod';
import { prisma } from '../services/db.js';
import {
  getIdeaBySlug,
  getPainPointBySlug,
  isEntitledUser,
} from '../services/catalogService.js';
import {
  createJobAndChargeDiscoveryInTx,
  chargeForStageInTx,
  InsufficientCreditsError,
} from '../services/creditService.js';
import { deliverDispatchWork } from '../services/queueService.js';
import { requireInternalAuth, type AuthenticatedRequest } from '../middleware/auth.js';
import { jobCreationLimiter } from '../middleware/rateLimit.js';
import { JobStatus, StageStatus, Prisma, DispatchKind } from '@prisma/client';
import { openDispatch } from '../services/dispatchService.js';
import { PIPELINE_STAGES } from '../types/job.js';
import { CONFIG } from '../config.js';

/**
 * User-initiated research seeded from catalog items.
 *
 * Mounted at `/api/catalog` under `requireInternalAuth` (X-User-ID required) —
 * called only by the SvelteKit proxies. Distinct from `/api/public/catalog`
 * (SSR rendering) and `/api/admin/catalog` (admin catalog generation).
 *
 * - POST /pain-research          — seed 1 (single CTA) or 2-5 (remix) pains,
 *   run discovery stage 5 only, land awaiting-selection (charge `discovery`).
 * - POST /ideas/:slug/deep-research — seed one solution from a catalog idea,
 *   run Phase 2 (5.5 -> 14) in one shot (charge `deep_research`), + interest counter.
 */
export const catalogResearchRouter = Router();

const SlugParam = z.string().min(1).max(160).regex(/^[a-z0-9-]+$/);

const PainResearchSchema = z.object({
  painSlugs: z.array(SlugParam).min(1).max(5),
});

// Defensive bounds on seeded, LLM-bound content so a crafted catalog row can't
// drive a disproportionately large prompt.
const MAX_DESCRIPTION_CHARS = 4000;
const MAX_QUOTES_TOTAL_CHARS = 6000;

function respondCreditsOrError(res: Response, error: unknown, context: string): void {
  if (error instanceof InsufficientCreditsError) {
    res.status(402).json({
      error: 'Insufficient research credits',
      code: 'INSUFFICIENT_CREDITS',
      balance: error.currentBalance,
      required: error.required,
    });
    return;
  }
  if (error instanceof z.ZodError) {
    res.status(400).json({ error: 'Validation error', details: error.errors });
    return;
  }
  console.error(`${context}:`, error);
  res.status(500).json({ error: context });
}

/** Reject if any seeded pain carries oversized text. */
function painSeedTooLarge(pain: { description?: string | null; representative_quotes?: string[] | null }): boolean {
  if ((pain.description?.length ?? 0) > MAX_DESCRIPTION_CHARS) return true;
  const quotesTotal = (pain.representative_quotes ?? []).reduce((sum, q) => sum + (q?.length ?? 0), 0);
  return quotesTotal > MAX_QUOTES_TOTAL_CHARS;
}

/**
 * POST /api/catalog/pain-research
 * Body: { painSlugs: string[] }  (1 = single CTA, 2-5 = remix)
 */
catalogResearchRouter.post(
  '/pain-research',
  requireInternalAuth,
  jobCreationLimiter,
  async (req: AuthenticatedRequest, res: Response) => {
    try {
      const { painSlugs } = PainResearchSchema.parse(req.body);
      const userId = req.user!.id;
      const entitled = await isEntitledUser(userId);

      // Resolve every slug to its authoritative record, enforcing the same
      // entitlement gate the detail pages use. Reject the whole batch if any is
      // locked (matters for remix: a saved pain may no longer be accessible).
      const painSeeds: Record<string, unknown>[] = [];
      for (const slug of painSlugs) {
        const pp = await getPainPointBySlug(slug, { entitled });
        if (!pp) {
          res.status(404).json({ error: 'Pain point not found', slug });
          return;
        }
        if ('locked' in pp) {
          res.status(403).json({ error: 'One or more pain points are not available', slug });
          return;
        }
        const seed = {
          id: pp.id,
          slug: pp.slug,
          title: pp.title,
          description: pp.description,
          mention_count: pp.mentionCount,
          severity_score: pp.severityScore,
          commercial_intent: pp.commercialIntentScore,
          opportunity_level: pp.opportunityLevel,
          representative_quotes: pp.representativeQuotes,
          source_platforms: pp.sourcePlatforms,
          categories: pp.categories,
          affected_segments: pp.affectedSegments,
          solution_approach: pp.solutionApproach,
          parent_theme_id: pp.themeId,
          source_niche: pp.sourceNiche,
        };
        if (painSeedTooLarge(seed as { description?: string; representative_quotes?: string[] })) {
          res.status(400).json({ error: 'Pain point content exceeds size limit', slug });
          return;
        }
        painSeeds.push(seed);
      }

      // Job label (shown on the dashboard) = the chosen pain(s), not the catalog
      // category. Single → the pain title; remix → "Remix: A + B (+N more)".
      // (The pipeline still gets the real source niche via each pain seed's
      // source_niche, so research context is unaffected.)
      const painTitles = painSeeds.map((p) => String(p.title));
      const niche =
        painTitles.length === 1
          ? painTitles[0]
          : `Remix: ${painTitles.slice(0, 2).join(' + ')}${painTitles.length > 2 ? ` +${painTitles.length - 2} more` : ''}`;

      // Create, charge, and authorize the exact paid attempt in one transaction.
      // 'pain_remix' vs 'pain_research' drives the provenance badge's singular/plural.
      const { job, dispatchId } = await prisma.$transaction(async (tx) => {
        const created = await createJobAndChargeDiscoveryInTx(
          tx,
          userId,
          niche,
          undefined,
          'interactive',
          painTitles.length > 1 ? 'pain_remix' : 'pain_research',
        );
        const dispatchId = await openDispatch(tx, {
          jobId: created.job.id,
          kind: DispatchKind.CONTINUE,
          segment: created.transaction?.stage ?? null,
          chargeId: created.transaction?.id ?? null,
          workPayload: {
            job_id: created.job.id,
            pain_seeds: painSeeds,
            niche,
            user_id: userId,
            allowed_project_types: null,
            task_type: 'catalog_pain_research',
            created_at: new Date().toISOString(),
          } as unknown as Prisma.InputJsonValue,
        });
        await tx.job.update({
          where: { id: created.job.id },
          data: { status: JobStatus.QUEUED, queuedAt: new Date() },
        });
        return { job: created.job, dispatchId };
      });

      let deliveryPending = false;
      try {
        await deliverDispatchWork(dispatchId);
      } catch (deliveryError) {
        deliveryPending = true;
        console.error(`[CatalogResearch] pain-research dispatch ${dispatchId} delivery pending:`, deliveryError);
      }

      // Telemetry (reuse existing signals — Job.entryMode is also queryable).
      console.log(JSON.stringify({
        event: painSeeds.length > 1 ? 'remix_research' : 'pain_research',
        userId, jobId: job.id, painCount: painSeeds.length,
      }));

      res.status(201).json({
        id: job.id,
        status: 'queued',
        statusUrl: `${CONFIG.baseUrl}/jobs/${job.id}`,
        operationId: dispatchId,
        deliveryPending,
      });
    } catch (error) {
      respondCreditsOrError(res, error, 'Failed to start pain-point research');
    }
  },
);

/**
 * POST /api/catalog/ideas/:slug/deep-research
 * Seed one solution from a catalog idea; run Phase 2 in one shot.
 */
catalogResearchRouter.post(
  '/ideas/:slug/deep-research',
  requireInternalAuth,
  jobCreationLimiter,
  async (req: AuthenticatedRequest, res: Response) => {
    try {
      const slugParse = SlugParam.safeParse(req.params.slug);
      if (!slugParse.success) {
        res.status(400).json({ error: 'Invalid slug' });
        return;
      }
      const userId = req.user!.id;
      const entitled = await isEntitledUser(userId);

      const idea = await getIdeaBySlug(slugParse.data, { entitled });
      if (!idea) {
        res.status(404).json({ error: 'Idea not found' });
        return;
      }
      if ('locked' in idea) {
        res.status(403).json({ error: 'This idea is not available' });
        return;
      }

      const solutionName = (idea.solution_name ?? '').trim();
      // min 3 chars: SolutionSelection.selected_solution_name enforces min_length=3,
      // so a shorter name would charge the user and then crash the worker.
      if (solutionName.length < 3) {
        res.status(422).json({ error: 'Idea is missing a valid solution name' });
        return;
      }
      if ((idea.description?.length ?? 0) > MAX_DESCRIPTION_CHARS) {
        res.status(400).json({ error: 'Idea content exceeds size limit' });
        return;
      }
      // Job label (shown on the dashboard) = the chosen idea, not its catalog
      // category. Prefer the human headline, fall back to the solution name.
      // (The pipeline still gets the real source niche via the idea seed.)
      const niche = String(idea.headline || solutionName).trim();

      // Seed for the worker (snake_case, as the Python pipeline expects).
      const ideaSeed = {
        id: idea.id,
        slug: idea.slug,
        solution_name: solutionName,
        headline: idea.headline,
        description: idea.description,
        value_proposition: idea.value_proposition,
        project_type: idea.project_type,
        core_features: idea.core_features,
        target_personas: idea.target_personas,
        differentiation_factors: idea.differentiation_factors,
        pricing_strategy: idea.pricing_strategy,
        technical_approach: idea.technical_approach,
        market_fit_score: idea.market_fit_score,
        technical_feasibility_score: idea.technical_feasibility_score,
        seo_scalability_score: idea.seo_scalability_score,
        novelty_score: idea.novelty_score,
        organic_discovery_queries: idea.organic_discovery_queries,
        programmatic_seo_opportunity: idea.programmatic_seo_opportunity,
        estimated_cac_organic: idea.estimated_cac_organic,
        source_niche: idea.source_niche,
        // Read the FULL list from the raw row: getIdeaBySlug filters
        // addressedPainTitles for non-entitled DISPLAY, but the seed goes to the
        // worker, not the page — a paying user's research must not be truncated
        // by display gating. (The locked/403 gate above still applies.)
        addressed_pain_titles:
          (
            await prisma.catalogIdea.findUnique({
              where: { id: idea.id },
              select: { addressedPainTitles: true },
            })
          )?.addressedPainTitles ?? [],
      };

      const selectionRationale =
        `Selected "${solutionName}" from the NicheIQ catalog for deep research. ` +
        `${idea.value_proposition ?? ''} ${(idea.description ?? '').slice(0, 240)}`.trim();

      // Create PENDING job + charge deep_research atomically.
      const stages = PIPELINE_STAGES.filter((s) => s.number !== 15);
      let jobId: string;
      let dispatchId: string;
      try {
        const created = await prisma.$transaction(async (tx) => {
          const job = await tx.job.create({
            data: {
              niche,
              userId,
              generateLandingPage: false,
              jobMode: 'interactive',
              entryMode: 'deep_idea',
              selectedSolutions: [solutionName],
              selectionRationale,
              status: JobStatus.QUEUED,
              queuedAt: new Date(),
              totalStages: stages.length,
              progress: {
                create: stages.map((stage) => ({
                  stageNumber: stage.number,
                  stageName: stage.name,
                  status: StageStatus.PENDING,
                })),
              },
            },
          });
          const charge = await chargeForStageInTx(tx, userId, job.id, 'deep_research', niche);
          const dispatchId = await openDispatch(tx, {
            jobId: job.id,
            kind: DispatchKind.DEEP_RESEARCH,
            segment: 'deep_research',
            chargeId: charge.transaction?.id ?? null,
            workPayload: {
              job_id: job.id,
              idea_seed: ideaSeed,
              niche,
              user_id: userId,
              task_type: 'catalog_deep_research',
              created_at: new Date().toISOString(),
            } as unknown as Prisma.InputJsonValue,
          });
          return { job, dispatchId };
        });
        jobId = created.job.id;
        dispatchId = created.dispatchId;
      } catch (error) {
        // 402 (and any tx failure) surface here; nothing to compensate (tx rolled back).
        respondCreditsOrError(res, error, 'Failed to start deep research');
        return;
      }

      // Best-effort interest counter (decoupled from the paid job): one row per
      // (idea, user); increment researchCount only on first-ever research by this user.
      try {
        await prisma.$transaction(async (tx) => {
          const existing = await tx.catalogIdeaResearch.findUnique({
            where: { ideaId_userId: { ideaId: idea.id, userId } },
            select: { id: true },
          });
          if (existing) {
            await tx.catalogIdeaResearch.update({
              where: { ideaId_userId: { ideaId: idea.id, userId } },
              data: { jobId },
            });
          } else {
            await tx.catalogIdeaResearch.create({ data: { ideaId: idea.id, userId, jobId } });
            await tx.catalogIdea.update({
              where: { id: idea.id },
              data: { researchCount: { increment: 1 } },
            });
          }
        });
      } catch (counterError) {
        if (
          counterError instanceof Prisma.PrismaClientKnownRequestError &&
          counterError.code === 'P2002'
        ) {
          // Concurrent first-time click lost the @@unique race — row exists, no increment.
        } else {
          console.error(`[CatalogResearch] researchCount update failed for idea ${idea.id}:`, counterError);
        }
      }

      let deliveryPending = false;
      try {
        await deliverDispatchWork(dispatchId);
      } catch (deliveryError) {
        deliveryPending = true;
        console.error(`[CatalogResearch] deep-research dispatch ${dispatchId} delivery pending:`, deliveryError);
      }

      // Telemetry (reuse existing signals — Job.entryMode + CatalogIdeaResearch).
      console.log(JSON.stringify({ event: 'deep_idea_research', userId, jobId, ideaId: idea.id }));

      res.status(201).json({
        id: jobId,
        status: 'queued',
        statusUrl: `${CONFIG.baseUrl}/jobs/${jobId}`,
        operationId: dispatchId,
        deliveryPending,
      });
    } catch (error) {
      respondCreditsOrError(res, error, 'Failed to start deep research');
    }
  },
);
