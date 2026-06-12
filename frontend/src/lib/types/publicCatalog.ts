/**
 * Phase 5.4 — Shared domain types for the public catalog UI rebuild.
 *
 * These mirror the camelCase shapes returned by the backend's flatten helpers
 * in `backend/src/services/catalogService.ts` (CatalogThemeSummary,
 * CatalogCompetitorSummary, etc.). When the backend shape changes, update
 * here first and let `npm run check` find downstream component callsites.
 *
 * Convention: top-level landing/detail-payload fields are camelCase. Idea +
 * pain-point preview interfaces (in catalog-landing.ts) follow the legacy
 * snake_case convention documented at the top of that file.
 */

export type Verdict = 'GO' | 'CONDITIONAL' | 'NO-GO';

/**
 * Map backend goNoGoVerdict ('GO' | 'NO_GO' | 'MAYBE') to the UI label set.
 * Single source of truth — every component should call this rather than
 * inlining the mapping.
 */
export function mapVerdict(raw: string | null | undefined): Verdict | null {
  if (!raw) return null;
  const v = raw.trim().toUpperCase();
  if (v === 'GO') return 'GO';
  if (v === 'NO_GO' || v === 'NO-GO') return 'NO-GO';
  if (v === 'MAYBE' || v === 'CONDITIONAL') return 'CONDITIONAL';
  return null;
}

/**
 * Pain-point severity_score is stored 0-1 in the backend; theme severity is
 * stored 0-100 (Phase 5.4 contract). This helper centralises the asymmetry —
 * always call it rather than multiplying inline. See plan §scope-decisions.
 */
export function scaleSeverity(value: number | null | undefined, source: 'pain' | 'theme'): number | null {
  if (value == null || !Number.isFinite(value)) return null;
  if (source === 'pain') return Math.round(value * 100);
  // 'theme' is already 0-100; clamp defensively.
  return Math.max(0, Math.min(100, Math.round(value)));
}

/**
 * Phase 14 — /job-page parity: derive Critical/High/Medium tier from a 0-1
 * severity score. Mirrors the logic in
 * frontend/src/lib/components/preview/PainPointSummaryCard.svelte:18-22.
 * Pure frontend computation — no backend storage.
 */
export type SeverityTier = 'critical' | 'high' | 'medium';

export function severityTier(score: number | null | undefined): SeverityTier | null {
  if (score == null || !Number.isFinite(score)) return null;
  if (score >= 0.7) return 'critical';
  if (score >= 0.5) return 'high';
  return 'medium';
}

/**
 * Catalog pain-table rail/row tier from a 0-100 SCALED severity (i.e. the
 * output of `scaleSeverity()`). Cutoffs match SeverityBar's bar-color tones
 * (>=75 error red, >=60 accent orange, else info blue) so a row's left rail
 * and its severity bar can never disagree.
 *
 * NOT the same as `severityTier()` above — that one takes the RAW 0-1 score
 * and feeds the job-page Critical/High/Medium labels. Don't swap them.
 */
export type SeverityRailTier = 'high' | 'med' | 'low';

export function severityRailTier(scaled: number | null | undefined): SeverityRailTier {
  if (scaled == null || !Number.isFinite(scaled)) return 'low';
  if (scaled >= 75) return 'high';
  if (scaled >= 60) return 'med';
  return 'low';
}

/** Difficulty bucket assigned server-side by `bucketKeywordDifficulty`. */
export type DifficultyBucket = 'easy' | 'medium' | 'hard';

/** Theme summary entry. severity is 0-100 — DO NOT multiply on the frontend.
 *  Phase 5.5 adds description/frequency/primaryUserSegments. `sources` retained
 *  as a deprecated alias of `primaryUserSegments`; remove after consumer audit. */
export interface Theme {
  title: string;
  /** Stable slug auto-derived from title in the Python pipeline. Used by the
   *  catalog UI to group pain points (whose `themeId` matches this `id`) under
   *  their source theme. Null on legacy rows ingested before the field existed. */
  id: string | null;
  severity: number | null;
  mentionCount: number | null;
  sources: string[];                           // deprecated — same value as primaryUserSegments
  description: string | null;                  // NEW — from theme.definition
  frequency: 'High' | 'Medium' | 'Low' | string | null;  // NEW — verbatim from crew
  primaryUserSegments: string[];               // NEW — from theme.primary_user_segments
  /** Phase 17 / Wave 3 — only set on parent payloads when themes are
   *  aggregated across multiple child sub-niches' research. Sub-niche
   *  payloads leave this null. */
  sourceSubNiche?: AudienceSourceSubNiche | null;
}

export interface AudienceSourceSubNiche {
  slug: string;
  name: string;
  parentSlug: string;
}

/** Audience segment summary entry. Phase 5.5 adds expertiseLevel + budgetSensitivity. */
export interface AudienceSegment {
  name: string;
  sizeLabel: string | null;
  bullets: string[];
  expertiseLevel: string | null;     // 'Beginner' | 'Intermediate' | 'Advanced' (verbatim)
  budgetSensitivity: string | null;  // 'High' | 'Medium' | 'Low'
  /** Present on parent payloads when audience segments are aggregated across
   *  child sub-niches. Sub-niche payloads omit it. */
  sourceSubNiche?: AudienceSourceSubNiche | null;
}

// ============================================
// Phase 5.5 — niche / audience-signals / quality
// ============================================

/** Niche-context blob for hero lede + boundary chips. */
export interface NicheContext {
  description: string | null;
  industryBoundaries: string | null;     // STRING — Pydantic NicheContext.industry_boundaries: str (NOT a list)
  marketSegments: string[] | null;
}

/** Eight rich audience-mapping sub-fields, all 11/11 in real preview reports. */
export interface AudienceSignals {
  vocabulary: string[];
  frustrations: string[];
  currentTools: string[];
  communityHubs: string[];
  recommendedChannels: string[];
  messagingFrameworks: string[];
  contentPreferences: string | null;     // STRING — not list
  earlyAdopterTactics: string | null;    // Optional[str]
}

/**
 * Quality + engagement signals. contentTier values match the backend Pydantic
 * comment (research_state.py:92): EXCELLENT | GOOD | MINIMAL | INSUFFICIENT.
 * overallDataQuality is FinalReport-only; null on preview-backed catalog rows.
 */
export interface QualitySignals {
  contentTier: 'EXCELLENT' | 'GOOD' | 'MINIMAL' | 'INSUFFICIENT' | null;
  painPointTier: 'GOLD' | 'SILVER' | 'BRONZE' | 'INSUFFICIENT' | null;
  confidenceScore: number | null;        // 0-1 numeric
  overallDataQuality: 'HIGH' | 'MEDIUM' | 'LOW' | null;
  engagementMetrics: { totalEngagement: number; avgEngagementPerSource: number } | null;
}

/** Competitor summary. position is the Phase 5.4 addition. */
export interface Competitor {
  name: string;
  url: string | null;
  competitorType: string | null;
  description: string;
  keyFeatures: string[];
  pricingModel: string | null;
  strengths: string[];
  weaknesses: string[];
  position: 'leader' | 'challenger' | 'niche' | null;
}

/** Keyword cluster summary. Per-keyword volume/difficulty are placeholders
 *  in v1 — pipeline doesn't yet emit per-keyword metrics on TopicCluster. */
export interface KeywordCluster {
  name: string;
  primaryKeyword: string | null;
  totalSearchVolume: number;
  contentRecommendation: string | null;
  estimatedTrafficPotential: string | null;
  priority: number | null;
  keywords: Array<{
    term: string;
    volume: number;
    difficulty: DifficultyBucket;
  }>;
}

/** Per-platform-community source signal. */
export interface SubredditSource {
  name: string;
  postCount: number;
}

/** Cross-catalog top pain point row for the /ideas SEO landing surface.
 *  Mirrors `CatalogTopPainPoint` exposed by the backend's
 *  `GET /api/public/catalog/top-pain-points` endpoint. */
export interface CatalogTopPainPoint {
  id: string;
  slug: string;
  title: string;
  mentionCount: number;
  severityScore: number;
  opportunityLevel: string;
  category: {
    id: string;
    name: string;
    slug: string;
    parent: { name: string; slug: string } | null;
  };
}

/** Catalog index hero stat strip — total counts. */
export interface CatalogTotals {
  totalIdeas: number;
  totalCategories: number;
  totalSubcategories: number;
  contentItemsMined: number;
  /** Sum of Reddit comments analyzed across contexts ("Comments analyzed" tile). */
  commentsAnalyzed: number;
  /** ISO timestamp of the most recent active idea or pain-point update.
   *  Drives the hero kicker dateline on /ideas. */
  lastUpdated: string | null;
}

// ============================================
// Featured collections (Phase 5)
// ============================================

/** Listed on the index page. No items hydrated. */
export interface CatalogCollectionSummary {
  slug: string;
  name: string;
  description: string | null;
  tagline: string | null;
  colorAccent: string | null;
  sortOrder: number;
  itemCount: number;
  /** Distinct category slugs touched by the collection's items (server-computed
   *  union of `idea.category.slug` and `painPoint.category.slug`). Drives the
   *  "Featured collection" placement on category pages — the route picks the
   *  first collection whose `categorySlugs.includes(currentCategory.slug)`.
   *  Empty for collections with no items. */
  categorySlugs: string[];
}

/** Item inside a collection — exactly one of `idea` or `painPoint` populated. */
export interface CatalogCollectionItem {
  position: number;
  kind: 'idea' | 'pain-point';
  // Loose `unknown` here to avoid a circular import with catalog-landing.ts.
  // Components import IdeaPreview / PainPointPreview directly when consuming.
  idea?: unknown;
  painPoint?: unknown;
}

/** Returned by `/api/public/catalog/collections/:slug`. */
export interface CatalogCollectionDetail extends CatalogCollectionSummary {
  items: CatalogCollectionItem[];
}
