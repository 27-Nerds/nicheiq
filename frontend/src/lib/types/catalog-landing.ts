/**
 * Type definitions matching the `/api/public/catalog/landing/:slug[:childSlug]`
 * payload returned by `getCategoryLanding` in `backend/src/services/catalogService.ts`.
 *
 * Keep these field names in sync with the backend response shape (snake_case
 * for idea/pain-point preview fields, camelCase for category fields). When
 * backend shapes change, update this file first and let `npm run check` find
 * downstream callsites.
 */

export interface CategoryLandingCategory {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  seoTitle: string | null;
  seoDescription: string | null;
  longDescription: string | null;
  faqJson: FaqEntry[] | null;
  tags: string[];
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface CategoryLandingChild {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  ideaCount: number;
  painPointCount: number;
}

export interface CategoryLandingSibling {
  id: string;
  name: string;
  slug: string;
}

export interface CategoryLandingParent {
  id: string;
  name: string;
  slug: string;
}

export interface CategoryLandingSuperGroup {
  id: string;
  name: string;
  slug: string;
}

/**
 * Phase 5: persisted projection of a source-job report.json. Shape mirrors
 * `backend/prisma/schema.prisma > CatalogResearchContext`. Json columns are
 * typed loosely here — section components downstream assert their own shapes.
 */
export interface CatalogResearchContext {
  sourceJobId: string;
  audienceMapping: unknown | null;
  marketSizing: unknown | null;
  trendLongevity: unknown | null;
  painPointAnalytics: unknown | null;
  competitiveAnalytics: unknown | null;
  competitorProfiles: unknown | null;
  // Phase 5.3 additions
  competitiveAnalysis: unknown | null;
  competitiveSummary: string | null;
  goToMarketBlueprint: unknown | null;
  pricingStrategy: unknown | null;
  trafficMonetization: unknown | null;
  detailedPainPoints: unknown | null;
  alternativeSolutions: unknown | null;
  selectedSolution: unknown | null;
  selectedSolutionName: string | null;
  contentCategorization: unknown | null;
  // Phase 5.4 — catalog rebuild additions.
  keywordClusters: unknown | null;
  themeSeverityScores: unknown | null;
  redditPostsAnalyzed: number | null;
  redditCommentsAnalyzed: number | null;
  twitterThreadsAnalyzed: number | null;
  genericPostsAnalyzed: number | null;
  topSubreddits: unknown | null;
  collectionDate: string | null;
  dataQualityTier: 'GOLD' | 'SILVER' | 'BRONZE' | 'INSUFFICIENT' | null;
  goNoGoVerdict: 'GO' | 'NO_GO' | 'MAYBE' | null;
  extractedAt: string;
  reportGeneratedAt: string | null;
}

export interface IdeaPreview {
  id: string;
  slug: string;
  solution_name: string;
  /** Human-readable display title (Pydantic BaseSolutionIdea.headline).
   *  Null on legacy rows — UI must fall back to `solution_name` (the code
   *  name). Use `solutionDisplayTitle()` from solution-utils.ts. */
  headline: string | null;
  /** Punchy 1-2 sentence card-friendly summary (Pydantic
   *  BaseSolutionIdea.short_description). Null on legacy rows — UI must
   *  fall back to `description`. Use `solutionCardDescription()` from
   *  solution-utils.ts. */
  short_description: string | null;
  description: string;
  value_proposition: string | null;
  project_type: string | null;
  format: string | null;
  core_features: string[] | null;
  target_personas: string[] | null;
  differentiation_factors: string[] | null;
  pricing_strategy: string | null;
  estimated_development_time: string | null;
  market_fit_score: number | null;
  technical_feasibility_score: number | null;
  seo_scalability_score: number | null;
  novelty_score: number | null;
  solo_dev_feasibility: number | null;
  estimated_cac_organic: string | null;
  programmatic_seo_opportunity: string | null;
  technical_approach: string | null;
  estimated_indexable_pages: number | null;
  source_niche: string;
  source_verdict: string | null;
  is_featured: boolean;
  category: { id: string; name: string; slug: string; parent?: { name: string; slug: string } | null };
  created_at: string;
  updated_at: string;
  // Phase 5: present on detail-page payloads (getIdeaBySlug); never on landing
  // top-N previews (those omit it to keep the payload compact).
  researchContext?: CatalogResearchContext | null;
}

export interface PainPointPreview {
  id: string;
  slug: string;
  title: string;
  description: string;
  mentionCount: number;
  severityScore: number;
  willingnessToPayScore: number;
  opportunityLevel: string;
  representativeQuotes: string[] | null;
  sourcePlatforms: string[] | null;
  categories: string[] | null;
  affectedSegments: string[] | null;
  solutionApproach: string | null;
  isFeatured: boolean;
  isActive: boolean;
  category: { id: string; name: string; slug: string; parent?: { name: string; slug: string } | null };
  sourceNiche: string;
  sourceItemIndex: number;
  sourceGeneratedAt: string | null;
  createdAt: string;
  updatedAt: string;
  // Phase 5: present on detail-page payloads (getPainPointBySlug); never on
  // landing top-N previews.
  researchContext?: CatalogResearchContext | null;
}

/**
 * Phase 5.4 — response shape for `/api/public/catalog/idea-by-slug/:slug` and
 * `/api/public/catalog/pain-point-by-slug/:slug`. Extends the preview with
 * flattened summaries (camelCase) appended by the backend's getIdeaBySlug /
 * getPainPointBySlug. Each summary field is null when the underlying
 * researchContext lacks it.
 */
export interface CatalogDetailExtras {
  themes: import('./publicCatalog.js').Theme[] | null;
  audienceSegments: import('./publicCatalog.js').AudienceSegment[] | null;
  competitors: import('./publicCatalog.js').Competitor[] | null;
  keywordClusters: import('./publicCatalog.js').KeywordCluster[] | null;
  subredditSources: import('./publicCatalog.js').SubredditSource[] | null;
  contentItemsMined: number;
  sourceCommunities: number;
  // Phase 5.5 — catalog page enrichment.
  nicheContext: import('./publicCatalog.js').NicheContext | null;
  audienceSignals: import('./publicCatalog.js').AudienceSignals | null;
  qualitySignals: import('./publicCatalog.js').QualitySignals | null;
  categorizationSummary: string | null;
  painAnalysisSummary: string | null;
  topPainCategories: string[] | null;
}

export type IdeaDetailResponse = IdeaPreview & CatalogDetailExtras;
export type PainPointDetailResponse = PainPointPreview & CatalogDetailExtras;

export interface CategoryLandingPayload {
  category: CategoryLandingCategory;
  parent: CategoryLandingParent | null;
  superGroup: CategoryLandingSuperGroup | null;
  children: CategoryLandingChild[];
  siblings: CategoryLandingSibling[];
  topIdeas: IdeaPreview[];
  topPainPoints: PainPointPreview[];
  totalIdeas: number;
  totalPainPoints: number;
  sources: string[];
  // Phase 5.4 — flattened summaries derived from the most-recent
  // researchContext for the category subtree. All nullable; frontend hides
  // sections when null. See `frontend/src/lib/types/publicCatalog.ts` for
  // shape definitions.
  themes: import('./publicCatalog.js').Theme[] | null;
  audienceSegments: import('./publicCatalog.js').AudienceSegment[] | null;
  competitors: import('./publicCatalog.js').Competitor[] | null;
  keywordClusters: import('./publicCatalog.js').KeywordCluster[] | null;
  subredditSources: import('./publicCatalog.js').SubredditSource[] | null;
  // Two-track sources metric (NOT a single mixed total — see scope rule).
  contentItemsMined: number;
  sourceCommunities: number;
  // Always null until pipeline produces per-category growth signal.
  growthPercent: number | null;
  // Phase 5.5 — catalog page enrichment. All null-safe; components hide
  // sections when data absent.
  nicheContext: import('./publicCatalog.js').NicheContext | null;
  audienceSignals: import('./publicCatalog.js').AudienceSignals | null;
  qualitySignals: import('./publicCatalog.js').QualitySignals | null;
  categorizationSummary: string | null;
  painAnalysisSummary: string | null;
  topPainCategories: string[] | null;
  // Phase 5: research context from the most-recent published item's source
  // job. Null when the category has zero published items, or when the source
  // job's report.json is missing (placeholder context row).
  researchContext: CatalogResearchContext | null;
}

export interface FaqEntry {
  q: string;
  a: string;
}

/**
 * Programmatic-SEO landing-page entry. Hardcoded in
 * `frontend/src/lib/data/programmaticIdeaPages.ts`. Slug must NOT collide with
 * any real `CatalogCategory` top-level slug (validated at deploy time, not
 * runtime — frontend has no Prisma access).
 */
export interface ProgrammaticIdeaPage {
  slug: string;
  title: string;
  seoTitle: string;
  seoDescription: string;
  longDescription: string;
  faqJson: FaqEntry[];
  featuredIdeaSlugs: string[];
  tags: string[];
}
