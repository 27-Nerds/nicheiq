import { existsSync, readFileSync } from 'fs';
import { AssetType, Prisma, type CatalogResearchContext } from '@prisma/client';
import { prisma } from './db.js';
import { getJobAsset } from './jobService.js';
import { resolveAssetPath } from '../utils/assetPath.js';

// =============================================================================
// CatalogResearchContext extraction — INGESTION ONLY
//
// THIS MODULE MUST NEVER BE IMPORTED FROM PUBLIC CATALOG ROUTES.
// Public catalog runtime is DB-only; the projected `CatalogResearchContext`
// row IS the public surface. Worker/admin/backfill flows are the only
// callers permitted to invoke `extractOrCreateResearchContext` /
// `loadReportJson`. ESLint `no-restricted-imports` enforces this for
// `routes/publicCatalog.ts`; a guardrail test enforces it for the public
// rendering exports of `catalogService.ts`.
//
// Design notes:
// - The customer's literal `report.niche` query string is NEVER projected
//   for `commissioned` source. Catalog flows pass `sourceKind: 'catalog'`
//   to suppress this scrub since their niche IS a public category name.
// - Prose summaries (executive_summary, etc.) are NEVER projected — they
//   contain personal pronouns aimed at the customer who ran the research.
// - Each Json subtree flows through `rejectIfContainsBannedContent` as a
//   defense-in-depth pass. Privacy-leakage patterns are always active;
//   AI-marketing patterns are tone-scrubs and only active for `commissioned`.
// =============================================================================

/** Active for ALL source kinds — these phrases leak customer-facing prose. */
const PRIVACY_LEAKAGE_PATTERNS: RegExp[] = [
  /your business/i,
  /we recommend/i,
];

/** Tone scrub for commissioned reports only — legitimate in catalog products. */
const AI_MARKETING_PATTERNS: RegExp[] = [
  /AI-powered/i,
  /AI-generated/i,
  /powered by AI/i,
];

export type SourceKind = 'commissioned' | 'catalog';

interface RejectOptions {
  sourceKind?: SourceKind;
  /**
   * When true, the niche-literal substring scrub does not run. Catalog jobs
   * use public category names as niche; suppressing the literal scrub is
   * correct because the phrase is intentionally public. Banned-pattern
   * scrubs still apply.
   */
  suppressNicheLiteralScrub?: boolean;
}

/**
 * Defense-in-depth content guard. Each Json subtree is stringified and scanned
 * for the customer's literal niche query (case-insensitive) and known
 * privacy-leakage / AI-marketing phrases. A subtree that fails any check is
 * nulled — adjacent columns still persist.
 */
export function rejectIfContainsBannedContent(
  value: unknown,
  fieldName: string,
  niche: string,
  options: RejectOptions = {},
): unknown {
  if (value == null) return null;

  const sourceKind: SourceKind = options.sourceKind ?? 'commissioned';
  const serialized = JSON.stringify(value);
  const serializedLower = serialized.toLowerCase();

  // Niche-literal scrub: only when not suppressed.
  if (!options.suppressNicheLiteralScrub) {
    const nicheLower = (niche ?? '').toLowerCase().trim();
    if (nicheLower.length >= 4 && serializedLower.includes(nicheLower)) {
      console.warn(`[researchContext] field=${fieldName} contains report.niche — scrubbing`);
      return null;
    }
  }

  for (const pattern of PRIVACY_LEAKAGE_PATTERNS) {
    if (pattern.test(serialized)) {
      console.warn(`[researchContext] field=${fieldName} matched ${pattern} — scrubbing`);
      return null;
    }
  }
  if (sourceKind === 'commissioned') {
    for (const pattern of AI_MARKETING_PATTERNS) {
      if (pattern.test(serialized)) {
        console.warn(`[researchContext] field=${fieldName} matched ${pattern} — scrubbing`);
        return null;
      }
    }
  }
  return value;
}

// =============================================================================
// Empty / projected helpers
// =============================================================================

export function isJsonEmpty(value: unknown): boolean {
  if (value == null) return true;
  if (Array.isArray(value)) return value.length === 0;
  if (typeof value === 'object') return Object.keys(value as Record<string, unknown>).length === 0;
  return false;
}

/**
 * "Did extraction write anything renderable OR audit-relevant?"
 *
 * Used as a write-guard in the `forceRefreshAll` downgrade path: if the
 * existing row has any projected data (including timestamps, zero metrics)
 * and the loader returned null, preserve the row rather than overwriting
 * with `emptyProjection()`. Zero counts DO count here — they prove
 * extraction RAN against a real report.
 */
export function hasProjectedData(ctx: CatalogResearchContext): boolean {
  return (
    !isJsonEmpty(ctx.audienceMapping) ||
    !isJsonEmpty(ctx.painPointAnalytics) ||
    !isJsonEmpty(ctx.detailedPainPoints) ||
    !isJsonEmpty(ctx.marketSizing) ||
    !isJsonEmpty(ctx.trendLongevity) ||
    !isJsonEmpty(ctx.competitiveAnalytics) ||
    !isJsonEmpty(ctx.competitorProfiles) ||
    !isJsonEmpty(ctx.competitiveAnalysis) ||
    !isJsonEmpty(ctx.alternativeSolutions) ||
    !isJsonEmpty(ctx.selectedSolution) ||
    !isJsonEmpty(ctx.topSubreddits) ||
    !isJsonEmpty(ctx.goToMarketBlueprint) ||
    !isJsonEmpty(ctx.pricingStrategy) ||
    !isJsonEmpty(ctx.trafficMonetization) ||
    !isJsonEmpty(ctx.keywordClusters) ||
    !isJsonEmpty(ctx.themeSeverityScores) ||
    !isJsonEmpty(ctx.nicheContext) ||
    !isJsonEmpty(ctx.qualitySignals) ||
    !isJsonEmpty(ctx.topPainCategories) ||
    ctx.competitiveSummary != null ||
    ctx.selectedSolutionName != null ||
    ctx.categorizationSummary != null ||
    ctx.painAnalysisSummary != null ||
    ctx.redditPostsAnalyzed != null ||
    ctx.redditCommentsAnalyzed != null ||
    ctx.twitterThreadsAnalyzed != null ||
    ctx.genericPostsAnalyzed != null ||
    ctx.collectionDate != null ||
    ctx.goNoGoVerdict != null ||
    ctx.reportGeneratedAt != null
  );
}

/**
 * Narrow structural type containing only the fields `hasMeaningfulResearchContext`
 * reads. Lets the predicate accept Prisma `select`-narrowed results (e.g. from
 * `adminCatalog.ts`'s pain-points list) without TS complaining about the
 * absence of unselected fields.
 */
export type MeaningfulResearchContextFields = Pick<
  CatalogResearchContext,
  | 'audienceMapping'
  | 'painPointAnalytics'
  | 'detailedPainPoints'
  | 'marketSizing'
  | 'trendLongevity'
  | 'competitiveAnalytics'
  | 'competitorProfiles'
  | 'competitiveAnalysis'
  | 'alternativeSolutions'
  | 'selectedSolution'
  | 'topSubreddits'
  | 'goToMarketBlueprint'
  | 'pricingStrategy'
  | 'trafficMonetization'
  | 'keywordClusters'
  | 'themeSeverityScores'
  | 'nicheContext'
  | 'qualitySignals'
  | 'topPainCategories'
  | 'competitiveSummary'
  | 'selectedSolutionName'
  | 'categorizationSummary'
  | 'painAnalysisSummary'
  | 'redditPostsAnalyzed'
  | 'redditCommentsAnalyzed'
  | 'twitterThreadsAnalyzed'
  | 'genericPostsAnalyzed'
  | 'goNoGoVerdict'
>;

/**
 * "Is there RENDERABLE content?" — used for placeholder detection AND public
 * landing-page gating. Excludes timestamps, zero-value metrics, and tier
 * alone. Without this distinction, every preview-derived row would lock as
 * "real" forever (materializer always writes `generated_at` + `collection_date`).
 */
export function hasMeaningfulResearchContext(ctx: MeaningfulResearchContextFields): boolean {
  return (
    !isJsonEmpty(ctx.audienceMapping) ||
    !isJsonEmpty(ctx.painPointAnalytics) ||
    !isJsonEmpty(ctx.detailedPainPoints) ||
    !isJsonEmpty(ctx.marketSizing) ||
    !isJsonEmpty(ctx.trendLongevity) ||
    !isJsonEmpty(ctx.competitiveAnalytics) ||
    !isJsonEmpty(ctx.competitorProfiles) ||
    !isJsonEmpty(ctx.competitiveAnalysis) ||
    !isJsonEmpty(ctx.alternativeSolutions) ||
    !isJsonEmpty(ctx.selectedSolution) ||
    !isJsonEmpty(ctx.topSubreddits) ||
    !isJsonEmpty(ctx.goToMarketBlueprint) ||
    !isJsonEmpty(ctx.pricingStrategy) ||
    !isJsonEmpty(ctx.trafficMonetization) ||
    !isJsonEmpty(ctx.keywordClusters) ||
    !isJsonEmpty(ctx.themeSeverityScores) ||
    !isJsonEmpty(ctx.nicheContext) ||
    !isJsonEmpty(ctx.qualitySignals) ||
    !isJsonEmpty(ctx.topPainCategories) ||
    (ctx.competitiveSummary?.trim() ?? '') !== '' ||
    (ctx.selectedSolutionName?.trim() ?? '') !== '' ||
    (ctx.categorizationSummary?.trim() ?? '') !== '' ||
    (ctx.painAnalysisSummary?.trim() ?? '') !== '' ||
    (ctx.redditPostsAnalyzed ?? 0) > 0 ||
    (ctx.redditCommentsAnalyzed ?? 0) > 0 ||
    (ctx.twitterThreadsAnalyzed ?? 0) > 0 ||
    (ctx.genericPostsAnalyzed ?? 0) > 0 ||
    ctx.goNoGoVerdict != null
  );
}

// =============================================================================
// Verdict / tier normalization
// =============================================================================

function normalizeVerdict(verdict: unknown): string | null {
  if (typeof verdict !== 'string') return null;
  const v = verdict.trim().toLowerCase();
  if (v === 'go') return 'GO';
  if (v === 'no-go' || v === 'no_go' || v === 'nogo') return 'NO_GO';
  if (v === 'conditional' || v === 'maybe') return 'MAYBE';
  return null;
}

function normalizeQualityTier(tier: unknown): string | null {
  if (typeof tier !== 'string') return null;
  const t = tier.trim().toUpperCase();
  if (t === 'GOLD' || t === 'SILVER' || t === 'BRONZE' || t === 'INSUFFICIENT') return t;
  return null;
}

function safeInt(val: unknown): number | null {
  if (val == null) return null;
  const n = Number(val);
  return Number.isFinite(n) ? Math.round(n) : null;
}

function safeDate(val: unknown): Date | null {
  if (val == null || typeof val !== 'string') return null;
  const d = new Date(val);
  return Number.isFinite(d.getTime()) ? d : null;
}

// =============================================================================
// Projection — the allow-list of fields that survive into the public surface.
// =============================================================================

type JsonInput = Prisma.InputJsonValue | typeof Prisma.JsonNull;

interface ProjectedFields {
  audienceMapping: JsonInput;
  marketSizing: JsonInput;
  trendLongevity: JsonInput;
  painPointAnalytics: JsonInput;
  competitiveAnalytics: JsonInput;
  competitorProfiles: JsonInput;
  competitiveAnalysis: JsonInput;
  competitiveSummary: string | null;
  goToMarketBlueprint: JsonInput;
  pricingStrategy: JsonInput;
  trafficMonetization: JsonInput;
  detailedPainPoints: JsonInput;
  alternativeSolutions: JsonInput;
  selectedSolution: JsonInput;
  selectedSolutionName: string | null;
  contentCategorization: JsonInput;
  // Catalog rebuild (Phase 5.4) — new projected fields for the public catalog UI.
  keywordClusters: JsonInput;
  themeSeverityScores: JsonInput;
  redditPostsAnalyzed: number | null;
  redditCommentsAnalyzed: number | null;
  twitterThreadsAnalyzed: number | null;
  genericPostsAnalyzed: number | null;
  topSubreddits: JsonInput;
  collectionDate: Date | null;
  dataQualityTier: string | null;
  goNoGoVerdict: string | null;
  reportGeneratedAt: Date | null;
  // Phase 5.5 — catalog page enrichment.
  nicheContext: JsonInput;
  qualitySignals: JsonInput;
  categorizationSummary: string | null;
  painAnalysisSummary: string | null;
  topPainCategories: JsonInput;
  // Phase 14 — source-grounded evidence projected from evidence_appendix.
  painPointQuoteSources: JsonInput;
  topRedditThreads: JsonInput;
}

/**
 * Extract a flattened theme-severity summary from the content_categorization
 * subtree. Returns `[{title, severity, mention_count, sources}]` or null when
 * the source isn't available. Used to populate `themeSeverityScores` for fast
 * read access without unwrapping the full content_categorization JSON.
 *
 * Logs a warning when content_categorization exists but no theme has a
 * numeric severity_score (likely a legacy report or a crew that didn't
 * populate the new field).
 */
function extractThemeSeverityScores(
  contentCategorization: unknown,
  jobId: string,
): unknown {
  if (!contentCategorization || typeof contentCategorization !== 'object') return null;
  const themes = (contentCategorization as Record<string, unknown>).theme_categories;
  if (!Array.isArray(themes) || themes.length === 0) return null;

  const result: Array<{
    title: string;
    theme_id: string | null;
    severity: number | null;
    mention_count: number | null;
    sources: string[];
    // Phase 5.5 — additional fields for ThemeCard render.
    description: string | null;
    frequency: string | null;
    primary_user_segments: string[];
  }> = [];
  let hasAnySeverity = false;

  for (const theme of themes) {
    if (!theme || typeof theme !== 'object') continue;
    const t = theme as Record<string, unknown>;
    const title = typeof t.category_name === 'string' ? t.category_name : null;
    if (!title) continue;
    // theme_id is auto-derived from category_name by the Pydantic ThemeCategory
    // model_validator. Pass through verbatim so the catalog frontend can group
    // pain points (whose parent_theme_id matches this slug) under their source theme.
    const themeId = typeof t.theme_id === 'string' && t.theme_id ? t.theme_id : null;
    const severity = typeof t.severity_score === 'number' ? t.severity_score : null;
    if (severity != null) hasAnySeverity = true;
    const mention = typeof t.mention_count === 'number' ? t.mention_count : null;
    const segments = Array.isArray(t.primary_user_segments)
      ? (t.primary_user_segments as unknown[]).filter((s): s is string => typeof s === 'string')
      : [];
    const description = typeof t.definition === 'string' ? t.definition : null;
    const frequency = typeof t.frequency === 'string' ? t.frequency : null;
    result.push({
      title,
      theme_id: themeId,
      severity,
      mention_count: mention,
      // `sources` retained for backward-compat; same value as primary_user_segments today.
      // Tracked for cleanup once frontend consumers migrate to primary_user_segments.
      sources: segments,
      description,
      frequency,
      primary_user_segments: segments,
    });
  }

  if (result.length === 0) return null;
  if (!hasAnySeverity) {
    console.warn(
      `[projectReport] missing field=themeSeverityScores.severity jobId=${jobId} ` +
        `(content_categorization present but no numeric severity_score on any theme — legacy report?)`,
    );
  }
  return result;
}

/**
 * Phase 5.5 — flatten niche_context into a small projected blob for the
 * landing payload's hero lede + boundary chips. Pydantic NicheContext fields
 * (research_state.py:35-43): niche_input, niche_description, market_segments
 * (list[str]), industry_boundaries (str — NOT a list).
 */
function extractNicheContext(nicheContext: unknown): unknown {
  if (!nicheContext || typeof nicheContext !== 'object') return null;
  const c = nicheContext as Record<string, unknown>;
  const description = typeof c.niche_description === 'string' ? c.niche_description : null;
  const industryBoundaries = typeof c.industry_boundaries === 'string' ? c.industry_boundaries : null;
  const marketSegments = Array.isArray(c.market_segments)
    ? (c.market_segments as unknown[]).filter((s): s is string => typeof s === 'string')
    : null;
  if (!description && !industryBoundaries && !marketSegments) return null;
  return { description, industryBoundaries, marketSegments };
}

/**
 * Phase 5.5 — flatten data_quality_summary + research_metadata.social_content_metrics
 * into a single qualitySignals blob. All sub-fields are optional and null-safe.
 *   contentTier         ← social_content_quality_tier ('EXCELLENT'|'GOOD'|'MINIMAL'|'INSUFFICIENT')
 *   painPointTier       ← pain_point_quality_tier      ('GOLD'|'SILVER'|'BRONZE'|'INSUFFICIENT')
 *   confidenceScore     ← pain_point_confidence_score (number 0-1)
 *   overallDataQuality  ← overall_data_quality        ('HIGH'|'MEDIUM'|'LOW') — FinalReport-only
 *   engagementMetrics   ← social_content_metrics      ({ totalEngagement, avgEngagementPerSource })
 */
function extractQualitySignals(
  dataQuality: unknown,
  researchMetadata: unknown,
): unknown {
  const d = (dataQuality && typeof dataQuality === 'object')
    ? dataQuality as Record<string, unknown>
    : {};
  const contentTier = typeof d.social_content_quality_tier === 'string' ? d.social_content_quality_tier : null;
  const painPointTier = typeof d.pain_point_quality_tier === 'string' ? d.pain_point_quality_tier : null;
  const confidenceScore = typeof d.pain_point_confidence_score === 'number' ? d.pain_point_confidence_score : null;
  const overallDataQuality = typeof d.overall_data_quality === 'string' ? d.overall_data_quality : null;

  // social_content_metrics may live on dataQuality (newer materializer) or
  // research_metadata (legacy). Try both.
  let metrics: Record<string, unknown> | null = null;
  if (d.social_content_metrics && typeof d.social_content_metrics === 'object') {
    metrics = d.social_content_metrics as Record<string, unknown>;
  } else if (researchMetadata && typeof researchMetadata === 'object') {
    const rm = researchMetadata as Record<string, unknown>;
    if (rm.social_content_metrics && typeof rm.social_content_metrics === 'object') {
      metrics = rm.social_content_metrics as Record<string, unknown>;
    }
  }
  let engagementMetrics: { totalEngagement: number; avgEngagementPerSource: number } | null = null;
  if (metrics) {
    const total = typeof metrics.total_engagement === 'number' ? metrics.total_engagement : null;
    const avg = typeof metrics.avg_engagement_per_source === 'number' ? metrics.avg_engagement_per_source : null;
    if (total != null) {
      engagementMetrics = { totalEngagement: total, avgEngagementPerSource: avg ?? 0 };
    }
  }

  if (!contentTier && !painPointTier && confidenceScore == null && !overallDataQuality && !engagementMetrics) {
    return null;
  }
  return { contentTier, painPointTier, confidenceScore, overallDataQuality, engagementMetrics };
}

function toJsonInput(value: unknown): JsonInput {
  if (value == null) return Prisma.JsonNull;
  return value as Prisma.InputJsonValue;
}

/**
 * Phase 14 — project per-pain quote sources from evidence_appendix.
 * Normalizes `score` from string ("200") → number (200) — verified against
 * preview_report shape. Returns the full map keyed by pain index, OR null
 * when the appendix is absent / empty.
 */
function normalizeQuoteSources(evidenceAppendix: unknown): unknown {
  if (!evidenceAppendix || typeof evidenceAppendix !== 'object') return null;
  const sources = (evidenceAppendix as Record<string, unknown>).pain_point_quote_sources;
  if (!sources || typeof sources !== 'object') return null;
  const normalized: Record<string, unknown> = {};
  for (const [idx, entry] of Object.entries(sources as Record<string, unknown>)) {
    if (!entry || typeof entry !== 'object') continue;
    const e = entry as Record<string, unknown>;
    const quotes = Array.isArray(e.quotes_with_sources) ? e.quotes_with_sources : [];
    const cleaned = quotes
      .filter((q): q is Record<string, unknown> => !!q && typeof q === 'object')
      .map((q) => ({
        quote: typeof q.quote === 'string' ? q.quote : '',
        post_id: typeof q.post_id === 'string' ? q.post_id : '',
        subreddit: typeof q.subreddit === 'string' ? q.subreddit : '',
        score: typeof q.score === 'number' ? q.score : Number(q.score) || 0,
      }))
      .filter((q) => q.quote && q.post_id && q.subreddit);
    if (cleaned.length === 0) continue;
    normalized[idx] = {
      pain_point_title: typeof e.pain_point_title === 'string' ? e.pain_point_title : '',
      quotes_with_sources: cleaned,
    };
  }
  return Object.keys(normalized).length > 0 ? normalized : null;
}

/**
 * Phase 14 — project top Reddit threads from evidence_appendix.
 * URLs are full https://reddit.com/r/.../comments/... already; pass through.
 * Returns array OR null when the appendix is absent / empty.
 */
function extractTopRedditThreads(evidenceAppendix: unknown): unknown {
  if (!evidenceAppendix || typeof evidenceAppendix !== 'object') return null;
  const threads = (evidenceAppendix as Record<string, unknown>).top_reddit_threads;
  if (!Array.isArray(threads)) return null;
  const cleaned = threads
    .filter((t): t is Record<string, unknown> => !!t && typeof t === 'object')
    .map((t) => ({
      post_id: typeof t.post_id === 'string' ? t.post_id : '',
      title: typeof t.title === 'string' ? t.title : '',
      subreddit: typeof t.subreddit === 'string' ? t.subreddit : '',
      score: typeof t.score === 'number' ? t.score : Number(t.score) || 0,
      num_comments: typeof t.num_comments === 'number' ? t.num_comments : Number(t.num_comments) || 0,
      url: typeof t.url === 'string' ? t.url : '',
      key_insight: typeof t.key_insight === 'string' ? t.key_insight : '',
    }))
    .filter((t) => t.post_id && t.title && t.url);
  return cleaned.length > 0 ? cleaned : null;
}

function projectReport(
  report: Record<string, unknown>,
  sourceKind: SourceKind = 'commissioned',
  jobId: string = 'unknown',
): ProjectedFields {
  const niche = typeof report.niche === 'string' ? report.niche : '';
  const guardOptions: RejectOptions = {
    sourceKind,
    suppressNicheLiteralScrub: sourceKind === 'catalog',
  };
  const guard = (value: unknown, fieldName: string) =>
    rejectIfContainsBannedContent(value, fieldName, niche, guardOptions);

  // Catalog rebuild (Phase 5.4): warn when expected new fields are absent so
  // silent regressions in the pipeline surface as grep-able log lines.
  // Pre-compute presence here so warnings fire BEFORE the privacy scrub may
  // null the field for content reasons.
  const warnIfMissing = (value: unknown, fieldName: string): void => {
    const empty =
      value == null ||
      (Array.isArray(value) && value.length === 0) ||
      (typeof value === 'object' && Object.keys(value as Record<string, unknown>).length === 0);
    if (empty) {
      console.warn(`[projectReport] missing field=${fieldName} jobId=${jobId}`);
    }
  };
  warnIfMissing(report.keyword_clusters, 'keyword_clusters');
  warnIfMissing(report.content_categorization, 'content_categorization');
  // marketSizing.total_addressable_market is the catalog-UI TAM string; warn
  // when the broader market_sizing object is present but the TAM string isn't.
  if (report.market_sizing && typeof report.market_sizing === 'object') {
    const tam = (report.market_sizing as Record<string, unknown>).total_addressable_market;
    if (tam == null || (typeof tam === 'string' && tam.trim() === '')) {
      console.warn(`[projectReport] missing field=market_sizing.total_addressable_market jobId=${jobId}`);
    }
  }
  // competitor_profiles[*].position warning — counts profiles with null position.
  if (Array.isArray(report.competitor_profiles)) {
    const profiles = report.competitor_profiles as Array<Record<string, unknown>>;
    const missingPos = profiles.filter(p => p && p.position == null).length;
    if (missingPos > 0) {
      console.warn(
        `[projectReport] missing field=competitor_profiles[*].position jobId=${jobId} count=${missingPos}/${profiles.length}`,
      );
    }
  }

  // Scalar string fields also pass through the banned-pattern guard.
  const guardString = (value: unknown, fieldName: string): string | null => {
    if (typeof value !== 'string') return null;
    if (value.trim() === '') return null;
    return guard(value, fieldName) == null ? null : value;
  };

  const meta = (report.research_metadata as Record<string, unknown> | undefined) ?? {};
  const dashboard = (report.executive_dashboard as Record<string, unknown> | undefined) ?? {};
  const verdictBlock = (dashboard.go_no_go_verdict as Record<string, unknown> | undefined) ?? {};
  const dataQuality = (report.data_quality_summary as Record<string, unknown> | undefined) ?? {};

  const selectedSolution = report.selected_solution_details as
    | Record<string, unknown>
    | undefined
    | null;
  const rawSelectedName =
    (selectedSolution?.solution_name as string | undefined) ??
    (typeof report.selected_solution_name === 'string' ? report.selected_solution_name : null) ??
    null;
  const selectedSolutionName = guardString(rawSelectedName, 'selectedSolutionName');

  const tierCandidate =
    normalizeQualityTier(dataQuality.pain_point_quality_tier) ??
    normalizeQualityTier(dataQuality.overall_data_quality);

  return {
    audienceMapping: toJsonInput(guard(report.audience_mapping, 'audienceMapping')),
    marketSizing: toJsonInput(guard(report.market_sizing, 'marketSizing')),
    trendLongevity: toJsonInput(guard(report.trend_longevity, 'trendLongevity')),
    painPointAnalytics: toJsonInput(guard(report.pain_point_analytics, 'painPointAnalytics')),
    competitiveAnalytics: toJsonInput(guard(report.competitive_analytics, 'competitiveAnalytics')),
    competitorProfiles: toJsonInput(guard(report.competitor_profiles, 'competitorProfiles')),
    competitiveAnalysis: toJsonInput(guard(report.competitive_analysis, 'competitiveAnalysis')),
    competitiveSummary: guardString(report.competitive_summary, 'competitiveSummary'),
    goToMarketBlueprint: toJsonInput(guard(report.go_to_market_blueprint, 'goToMarketBlueprint')),
    pricingStrategy: toJsonInput(guard(report.pricing_strategy, 'pricingStrategy')),
    trafficMonetization: toJsonInput(guard(report.traffic_monetization, 'trafficMonetization')),
    detailedPainPoints: toJsonInput(guard(report.detailed_pain_points, 'detailedPainPoints')),
    alternativeSolutions: toJsonInput(guard(report.alternative_solutions, 'alternativeSolutions')),
    selectedSolution: toJsonInput(guard(selectedSolution, 'selectedSolution')),
    selectedSolutionName,
    contentCategorization: toJsonInput(guard(report.content_categorization, 'contentCategorization')),
    // Catalog rebuild (Phase 5.4) — new fields. Both flow through the same
    // privacy scrub as the rest of the projection; null is the safe default.
    keywordClusters: toJsonInput(guard(report.keyword_clusters, 'keywordClusters')),
    themeSeverityScores: toJsonInput(
      guard(extractThemeSeverityScores(report.content_categorization, jobId), 'themeSeverityScores'),
    ),
    redditPostsAnalyzed: safeInt(meta.reddit_posts_analyzed),
    redditCommentsAnalyzed: safeInt(meta.reddit_comments_analyzed),
    twitterThreadsAnalyzed: safeInt(meta.twitter_threads_analyzed),
    genericPostsAnalyzed: safeInt(meta.generic_posts_analyzed),
    topSubreddits: toJsonInput(guard(meta.top_subreddits, 'topSubreddits')),
    collectionDate: safeDate(meta.collection_date),
    // Tier never null on disk — placeholder rows get 'INSUFFICIENT'. Real
    // rows extracted from a report without quality metadata also fall back
    // to 'INSUFFICIENT'. Tier is a quality label, NOT a placeholder signal —
    // use `hasMeaningfulResearchContext` for that.
    dataQualityTier: tierCandidate ?? 'INSUFFICIENT',
    goNoGoVerdict: normalizeVerdict(verdictBlock.verdict),
    reportGeneratedAt: safeDate(report.generated_at),
    // Phase 5.5 — catalog page enrichment.
    nicheContext: toJsonInput(guard(extractNicheContext(report.niche_context), 'nicheContext')),
    qualitySignals: toJsonInput(guard(extractQualitySignals(report.data_quality_summary, meta), 'qualitySignals')),
    categorizationSummary: typeof (report.content_categorization as Record<string, unknown> | null)?.executive_summary === 'string'
      ? ((report.content_categorization as Record<string, unknown>).executive_summary as string)
      : null,
    painAnalysisSummary: typeof report.pain_analysis_summary === 'string' ? report.pain_analysis_summary : null,
    topPainCategories: toJsonInput(
      guard(
        Array.isArray(report.top_pain_categories)
          ? (report.top_pain_categories as unknown[]).filter((s): s is string => typeof s === 'string')
          : null,
        'topPainCategories',
      ),
    ),
    // Phase 14 — source-grounded evidence.
    painPointQuoteSources: toJsonInput(
      guard(normalizeQuoteSources(report.evidence_appendix), 'painPointQuoteSources'),
    ),
    topRedditThreads: toJsonInput(
      guard(extractTopRedditThreads(report.evidence_appendix), 'topRedditThreads'),
    ),
  };
}

function emptyProjection(): ProjectedFields {
  return {
    audienceMapping: Prisma.JsonNull,
    marketSizing: Prisma.JsonNull,
    trendLongevity: Prisma.JsonNull,
    painPointAnalytics: Prisma.JsonNull,
    competitiveAnalytics: Prisma.JsonNull,
    competitorProfiles: Prisma.JsonNull,
    competitiveAnalysis: Prisma.JsonNull,
    competitiveSummary: null,
    goToMarketBlueprint: Prisma.JsonNull,
    pricingStrategy: Prisma.JsonNull,
    trafficMonetization: Prisma.JsonNull,
    detailedPainPoints: Prisma.JsonNull,
    alternativeSolutions: Prisma.JsonNull,
    selectedSolution: Prisma.JsonNull,
    selectedSolutionName: null,
    contentCategorization: Prisma.JsonNull,
    // Catalog rebuild (Phase 5.4) defaults.
    keywordClusters: Prisma.JsonNull,
    themeSeverityScores: Prisma.JsonNull,
    redditPostsAnalyzed: null,
    redditCommentsAnalyzed: null,
    twitterThreadsAnalyzed: null,
    genericPostsAnalyzed: null,
    topSubreddits: Prisma.JsonNull,
    collectionDate: null,
    dataQualityTier: 'INSUFFICIENT',
    goNoGoVerdict: null,
    reportGeneratedAt: null,
    // Phase 5.5 defaults.
    nicheContext: Prisma.JsonNull,
    qualitySignals: Prisma.JsonNull,
    categorizationSummary: null,
    painAnalysisSummary: null,
    topPainCategories: Prisma.JsonNull,
    // Phase 14 defaults.
    painPointQuoteSources: Prisma.JsonNull,
    topRedditThreads: Prisma.JsonNull,
  };
}

// =============================================================================
// Public API
// =============================================================================

export interface ExtractOptions {
  /**
   * When true, an existing PLACEHOLDER row is re-extracted if its report
   * asset is now available on disk. Real (non-placeholder) rows are still
   * returned unchanged.
   *
   * Placeholder is defined as `!hasMeaningfulResearchContext(row)` — a row
   * with only timestamps + zero metrics still counts as a placeholder.
   */
  forceRefreshPlaceholders?: boolean;
  /**
   * When true, re-projects ALL existing rows from the report asset regardless
   * of placeholder status — except when the loader returns null AND the row
   * has any projected data (downgrade guard, see implementation below).
   */
  forceRefreshAll?: boolean;
  /** 'catalog' suppresses niche-literal scrub + AI-marketing scrub. */
  sourceKind?: SourceKind;
}

/**
 * INGESTION ONLY. Read & parse a report asset for a given sourceJobId.
 *
 * Precedence: REPORT_JSON wins over PREVIEW_REPORT. If REPORT_JSON exists
 * but is corrupt/missing AND the caller is in `forceRefreshAll` mode, we
 * return null without falling back — so the caller's downgrade guard can
 * preserve the existing row instead of nuking it with `emptyProjection()`.
 *
 * MUST NOT be called from public catalog runtime paths.
 */
async function loadReportJson(
  sourceJobId: string,
  options: { forceRefreshAll?: boolean } = {},
): Promise<Record<string, unknown> | null> {
  type LoadResult = Record<string, unknown> | null | 'corrupt';
  const tryLoad = (asset: { filePath: string } | null): LoadResult => {
    if (!asset) return null;
    try {
      const resolvedPath = resolveAssetPath(asset.filePath);
      if (!existsSync(resolvedPath)) return 'corrupt';
      const raw = readFileSync(resolvedPath, 'utf-8');
      const parsed = JSON.parse(raw);
      return parsed && typeof parsed === 'object'
        ? (parsed as Record<string, unknown>)
        : 'corrupt';
    } catch (err) {
      console.warn(`[researchContext] failed to load asset for ${sourceJobId}:`, err);
      return 'corrupt';
    }
  };

  const reportAsset = await getJobAsset(sourceJobId, AssetType.REPORT_JSON);
  if (reportAsset) {
    const result = tryLoad(reportAsset);
    if (result && result !== 'corrupt') return result;
    if (result === 'corrupt' && options.forceRefreshAll) {
      console.error(
        `[researchContext] REPORT_JSON unloadable for ${sourceJobId} during forceRefreshAll; returning null to preserve existing row`,
      );
      return null;
    }
    // No REPORT_JSON content: fall through to PREVIEW_REPORT.
  }

  const previewAsset = await getJobAsset(sourceJobId, AssetType.PREVIEW_REPORT);
  const previewResult = tryLoad(previewAsset);
  return previewResult && previewResult !== 'corrupt' ? previewResult : null;
}

/**
 * INGESTION ONLY. Idempotent. Always returns a row — extraction failures
 * produce a placeholder row instead of null (so callers can rely on
 * FK-target existence). Safe to call before the related CatalogIdea /
 * CatalogPainPoint insert.
 *
 * MUST NOT be called from public catalog runtime paths. Public routes read
 * `CatalogResearchContext` only via Prisma relations on `getCategoryLanding`,
 * `getIdeaBySlug`, and `getPainPointBySlug`.
 *
 * Behavior:
 * - Real (non-placeholder) row exists → return unchanged.
 * - Placeholder row exists, `forceRefreshPlaceholders` false → return unchanged.
 * - Placeholder row exists, `forceRefreshPlaceholders` true → re-attempt
 *   extraction. If a report asset is now available, upsert; otherwise
 *   return the placeholder unchanged.
 * - `forceRefreshAll` true: re-project regardless, but with a DOWNGRADE
 *   GUARD — if the loader returns null and the existing row has any
 *   projected data, return existing unchanged. Never overwrite real data
 *   with `emptyProjection()`.
 * - No row exists → attempt extraction. On success, persist the projection.
 *   On failure, persist a placeholder row.
 */
export async function extractOrCreateResearchContext(
  sourceJobId: string,
  options: ExtractOptions = {},
): Promise<CatalogResearchContext> {
  const existing = await prisma.catalogResearchContext.findUnique({
    where: { sourceJobId },
  });

  // Placeholder = no MEANINGFUL data. A row with only timestamps + zero
  // metrics IS a placeholder (refresh-eligible). hasProjectedData is used
  // ONLY in the downgrade-preservation guard below.
  const isPlaceholder = existing != null && !hasMeaningfulResearchContext(existing);

  if (existing && !isPlaceholder && !options.forceRefreshAll) {
    return existing;
  }
  if (
    existing &&
    isPlaceholder &&
    !options.forceRefreshPlaceholders &&
    !options.forceRefreshAll
  ) {
    return existing;
  }

  const report = await loadReportJson(sourceJobId, {
    forceRefreshAll: options.forceRefreshAll,
  });

  // Downgrade guard: never overwrite a row that has projected data with
  // an empty projection. If the loader returned null but the row already
  // exists with any extraction-stamped fields, preserve it.
  if (existing && report == null && hasProjectedData(existing)) {
    return existing;
  }

  const projection = report
    ? projectReport(report, options.sourceKind ?? 'commissioned', sourceJobId)
    : emptyProjection();

  return prisma.catalogResearchContext.upsert({
    where: { sourceJobId },
    create: { sourceJobId, ...projection },
    update: { ...projection, extractedAt: new Date() },
  });
}

/**
 * Phase 5.5 — backfill helper for the `--from-checkpoints` script. Takes a
 * pre-synthesized report blob (built by the script from
 * `output/checkpoints/checkpoint_<jobId>...` stage_*.json files) and projects
 * + upserts it like the asset-driven path does. Bypasses the asset loader
 * because checkpoint dirs aren't first-class job assets.
 *
 * BACKFILL ONLY. Do NOT call from production runtime — it can overwrite real
 * data with synthesized blobs of unknown completeness.
 */
export async function projectFromBlob(
  sourceJobId: string,
  report: Record<string, unknown>,
  options: { sourceKind?: SourceKind } = {},
): Promise<CatalogResearchContext> {
  const projection = projectReport(report, options.sourceKind ?? 'catalog', sourceJobId);
  return prisma.catalogResearchContext.upsert({
    where: { sourceJobId },
    create: { sourceJobId, ...projection },
    update: { ...projection, extractedAt: new Date() },
  });
}

/**
 * Admin tool, rare; not wired into any automatic flow. Use to manually nuke a
 * row (e.g., a placeholder that should be re-extracted from a now-available
 * report) so the next call rebuilds it from scratch.
 */
export async function deleteResearchContext(sourceJobId: string): Promise<void> {
  await prisma.catalogResearchContext.deleteMany({ where: { sourceJobId } });
}
