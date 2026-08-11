/**
 * Public contract for the shared discovery endpoint.
 *
 * Strategy: the raw preview-report / discovery-data assets have evolving
 * shapes that aren't worth mirroring field-by-field in Zod. Instead, we
 * use top-level passthrough + an explicit FORBIDDEN-field strip pass, plus
 * a few narrow transforms (truncate quotes, scrub Reddit URLs/post_ids,
 * cap evidence appendix size).
 *
 * If a new internal field lands in the source data, it ships publicly by
 * default — but the forbidden-field list + nested strips catch the known
 * PII / competitive / operational leaks.
 *
 * The PREVIEW REPORT is the exception: `applyPreviewFieldAllowlist` runs on
 * every served payload and passes only keys that appear in `PREVIEW_FIELD_SCOPE`
 * (top level) or, for the containers listed in `NESTED_FIELD_SCOPE`, in that
 * container's second-level map. An unclassified upstream field never reaches a
 * public URL regardless of pool state, at either of those two levels. Only the
 * pool/niche DECISION varies — pool-scoped fields are served while the pool is
 * current and withheld once it is not.
 *
 * The classification is two levels deep, not arbitrarily deep: see the note on
 * `NESTED_FIELD_SCOPE` for which containers are covered and why the rest are not.
 */
import { z } from 'zod';

// ── Fields stripped at every level ─────────────────────────────────────

/** Keys that should NEVER appear in the public payload at any nesting level. */
const FORBIDDEN_KEYS = new Set<string>([
  // PII / identity
  'userId', 'user_id', 'email', 'session', 'sessionId',
  // Auth / billing
  'password', 'apiKey', 'api_key', 'stripe', 'stripeCustomerId',
  'creditBalance', 'credits',
  // Operational / internal
  'errors', 'fallback_stages', 'filtering_stats',
  'started_at', 'completed_at', 'completed_stages',
  'data_size_mb', 'collection_date',
  // Attribution-enabling
  'source_post_ids', 'post_id', 'post_ids',
  'key_influencers', 'influencers', 'influencers_followed',
]);

/** Strips forbidden keys recursively. Preserves arrays, objects, primitives. */
function stripForbidden(input: unknown): unknown {
  if (Array.isArray(input)) return input.map(stripForbidden);
  if (input !== null && typeof input === 'object') {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(input)) {
      if (FORBIDDEN_KEYS.has(k)) continue;
      out[k] = stripForbidden(v);
    }
    return out;
  }
  return input;
}

// ── Preview report ─────────────────────────────────────────────────────

const QUOTE_MAX_LEN = 280;

function truncateQuote(s: unknown): unknown {
  if (typeof s !== 'string') return s;
  return s.length > QUOTE_MAX_LEN ? s.slice(0, QUOTE_MAX_LEN) + '…' : s;
}

/** Walks the payload truncating known quote-carrying fields. */
function truncateQuotesDeep(input: unknown): unknown {
  if (Array.isArray(input)) return input.map(truncateQuotesDeep);
  if (input !== null && typeof input === 'object') {
    const obj = input as Record<string, unknown>;
    const out: Record<string, unknown> = { ...obj };
    if ('quote' in obj) out.quote = truncateQuote(obj.quote);
    if ('representative_quotes' in obj && Array.isArray(obj.representative_quotes)) {
      out.representative_quotes = (obj.representative_quotes as unknown[]).map(truncateQuote);
    }
    for (const k of Object.keys(out)) {
      if (k !== 'quote' && k !== 'representative_quotes') {
        out[k] = truncateQuotesDeep(out[k]);
      }
    }
    return out;
  }
  return input;
}

/** Scrubs author-reconstruction fields from Reddit-thread-like objects. */
function scrubThread(t: Record<string, unknown>): Record<string, unknown> {
  const { post_id, url, ...safe } = t;
  return safe;
}

/** Caps evidence_appendix to <=5 threads and <=5 pain-point quote groups (each <=3 quotes). */
function capEvidence(raw: unknown): unknown {
  if (raw === null || typeof raw !== 'object') return raw;
  const obj = raw as Record<string, unknown>;
  const out: Record<string, unknown> = { ...obj };
  if (Array.isArray(obj.top_reddit_threads)) {
    out.top_reddit_threads = obj.top_reddit_threads
      .slice(0, 5)
      .map(t => (t && typeof t === 'object' ? scrubThread(t as Record<string, unknown>) : t));
  }
  if (Array.isArray(obj.pain_point_quote_sources)) {
    out.pain_point_quote_sources = obj.pain_point_quote_sources.slice(0, 5).map(g => {
      if (!g || typeof g !== 'object') return g;
      const group = g as Record<string, unknown>;
      const quotes = Array.isArray(group.quotes_with_sources)
        ? group.quotes_with_sources.slice(0, 3)
        : group.quotes_with_sources;
      return { ...group, quotes_with_sources: quotes };
    });
  }
  return out;
}

export type SharedPreviewReport = Record<string, unknown>;
export type SharedDiscoveryData = Record<string, unknown>;

/**
 * Scope of a top-level preview-report field.
 *
 * `pool` — a claim ABOUT one specific candidate list: it names, counts, groups, ranks or
 *   grades the ideas that existed when the run wrote it. Beside a pool that has since
 *   changed it is actively misleading (finding D2: guidance written against 6 ideas
 *   steering a 12-idea pool).
 * `niche` — true of the market regardless of which candidates exist.
 */
export type PreviewFieldScope = 'niche' | 'pool';

const POOL_SCOPED_PREVIEW_FIELDS = [
  'alternative_solutions',        // full ranked snapshot of the pool, scores and verdicts
  'data_quality_summary',         // quality_caveats carries per-idea calibration notes
  'examined_ruled_out',
  'idea_portfolio_summary',
  'idea_portfolio_summary_fingerprint',
  'idea_theses',
  'idea_validation',              // bound to seed_idea_id / seed_idea_revision
  'overlap_groups',
] as const;

const NICHE_SCOPED_PREVIEW_FIELDS = [
  'audience_mapping',
  'content_categorization',
  'detailed_pain_points',
  'evidence_appendix',
  'generated_at',
  'market_reality',
  'niche',
  'niche_context',
  'niche_difficulty_verdict',
  'overall_competitive_insights',
  'pain_analysis_summary',
  'pain_point_analytics',
  'pain_total_mentions',
  'research_metadata',
  'top_pain_categories',
  'user_adjusted',
  'user_adjustments',
] as const;

/**
 * Every top-level key the preview-report writer produces, classified.
 *
 * This is an ALLOWLIST, not a denylist, on BOTH branches: `applyPreviewFieldAllowlist`
 * serves only keys present in this map, so a field added upstream without a classification
 * is withheld whether the pool is current or stale. `previewReportTopLevelKeys.json`
 * enumerates the real key universe and the test beside it fails on any key missing here.
 */
export const PREVIEW_FIELD_SCOPE: ReadonlyMap<string, PreviewFieldScope> = new Map<
  string,
  PreviewFieldScope
>([
  ...POOL_SCOPED_PREVIEW_FIELDS.map((key) => [key, 'pool'] as [string, PreviewFieldScope]),
  ...NICHE_SCOPED_PREVIEW_FIELDS.map((key) => [key, 'niche'] as [string, PreviewFieldScope]),
]);

/**
 * Second-level classification for the three niche-scoped containers that are known to
 * carry pool-scoped values inside them.
 *
 * `research_metadata.funnel_counts` carries `candidates_shown` — a count of the snapshot
 * pool. Both `audience_drift_notice` copies describe "the recommendation", which
 * `_refresh_recommendation_audience_drift` computes from the recommended candidates.
 *
 * These maps are ALLOWLISTS with the same rule as the top level: a nested key that is not
 * classified here is dropped on both dispositions. A hand-maintained list of the three
 * pool-scoped names would have been the same denylist shape the top level replaced — the
 * next pool-scoped value nested into one of these containers would ship by omission, and
 * the producer-side `{text, scope}` change queued upstream does not cover a brand-new key.
 *
 * Key universes (all three are flat, closed, model-backed):
 *  - `research_metadata` — the dict literal in `ResearchFlow._materialize_preview_report`
 *    plus `models/research_state.py:ResearchMetadata`. `collection_date`, `filtering_stats`,
 *    `started_at`, `completed_stages`, `fallback_stages` and `data_size_mb` are in
 *    FORBIDDEN_KEYS and never survive `sanitizePreviewReport`, so they are not listed.
 *  - `niche_difficulty_verdict` — `models/research_state.py:NicheDifficultyVerdict`.
 *  - `audience_mapping` — `models/research_state.py:AudienceMapping`, minus the forbidden
 *    `key_influencers`.
 * Each list was cross-checked against the 60 real PREVIEW_REPORT assets under
 * output/checkpoints/, which contribute no key outside it.
 *
 * DELIBERATELY NOT CLASSIFIED: the third level and below (`audience_segments[]` element
 * fields, `top_subreddits[]`, `detailed_pain_points[]`, `evidence_appendix.*`, …). Those
 * are open, list-shaped, churn every pipeline change, and would over-block real assets on
 * the serve path the first time a model gains a field. The two levels covered here are the
 * ones where a pool-scoped value has ever actually been found nested beside niche-scoped
 * siblings; deeper leaks remain a residual this boundary does not catch.
 */
export const NESTED_FIELD_SCOPE: ReadonlyMap<string, ReadonlyMap<string, PreviewFieldScope>> = new Map<
  string,
  ReadonlyMap<string, PreviewFieldScope>
>([
  ['research_metadata', new Map<string, PreviewFieldScope>([
    ['funnel_counts', 'pool'],
    ['generic_posts_analyzed', 'niche'],
    ['reddit_comments_analyzed', 'niche'],
    ['reddit_posts_analyzed', 'niche'],
    ['top_subreddits', 'niche'],
    ['twitter_threads_analyzed', 'niche'],
  ])],
  ['niche_difficulty_verdict', new Map<string, PreviewFieldScope>([
    ['audience_drift_notice', 'pool'],
    ['buyer_class', 'niche'],
    ['buyer_class_note', 'niche'],
    ['difficulty_level', 'niche'],
    ['headline', 'niche'],
    ['key_challenges', 'niche'],
    ['key_strengths', 'niche'],
    ['low_confidence', 'niche'],
    ['narrative_summary', 'niche'],
    ['software_addressability', 'niche'],
  ])],
  ['audience_mapping', new Map<string, PreviewFieldScope>([
    ['audience_drift_notice', 'pool'],
    ['audience_segments', 'niche'],
    ['common_vocabulary', 'niche'],
    ['community_hubs', 'niche'],
    ['content_preferences', 'niche'],
    ['early_adopter_tactics', 'niche'],
    ['frustrations_with_existing', 'niche'],
    ['messaging_frameworks', 'niche'],
    ['primary_target_segment', 'niche'],
    ['recommended_channels', 'niche'],
    ['segment_prioritization_rationale', 'niche'],
    ['tools_currently_used', 'niche'],
  ])],
]);

/**
 * Applies the second-level classification to one niche-scoped container.
 *
 * Unclassified nested keys are collected into the caller's `unclassified` list — reported
 * as `container.key` in the same single warning as the top-level ones — and dropped on
 * both dispositions, exactly as at the top level.
 */
function applyNestedFieldScope(
  key: string,
  value: unknown,
  poolScoped: PoolScopedDisposition,
  unclassified: string[],
): unknown {
  const nested = NESTED_FIELD_SCOPE.get(key);
  if (!nested || value === null || typeof value !== 'object' || Array.isArray(value)) {
    return value;
  }
  const out: Record<string, unknown> = {};
  for (const [nestedKey, nestedValue] of Object.entries(value as Record<string, unknown>)) {
    const scope = nested.get(nestedKey);
    if (scope === undefined) {
      unclassified.push(`${key}.${nestedKey}`);
      continue;
    }
    if (scope === 'pool' && poolScoped === 'withhold') continue;
    out[nestedKey] = nestedValue;
  }
  return out;
}

/** What to do with fields classified `pool` — the only thing pool staleness decides. */
export type PoolScopedDisposition = 'serve' | 'withhold';

/**
 * The single gate every public preview report passes through.
 *
 * UNCLASSIFIED keys are dropped on BOTH dispositions, at the top level and inside the
 * containers `NESTED_FIELD_SCOPE` covers. An unclassified key is a field this boundary has
 * never reasoned about; guessing that it is safe is exactly how the five-name denylist this
 * replaced leaked `alternative_solutions` and `research_metadata.funnel_counts`, and a pool
 * that happens to be current is no evidence about a field nobody has classified.
 *
 * `poolScoped` decides only the pool half: while the served candidate list still is the one
 * the snapshot describes, its pool-scoped claims are true and ship unchanged (including the
 * nested pool-scoped values inside niche-scoped containers). Once it is not, they go.
 */
export function applyPreviewFieldAllowlist(
  report: SharedPreviewReport | null,
  poolScoped: PoolScopedDisposition,
): SharedPreviewReport | null {
  if (report === null) return null;
  const out: SharedPreviewReport = {};
  const unclassified: string[] = [];
  for (const [key, value] of Object.entries(report)) {
    const scope = PREVIEW_FIELD_SCOPE.get(key);
    if (scope === undefined) {
      unclassified.push(key);
      continue;
    }
    if (scope === 'pool') {
      if (poolScoped === 'withhold') continue;
      out[key] = value;
      continue;
    }
    out[key] = applyNestedFieldScope(key, value, poolScoped, unclassified);
  }
  if (unclassified.length > 0) {
    console.warn(
      '[SharedDiscovery] withheld unclassified preview field(s): '
      + `${unclassified.join(', ')} — classify them in PREVIEW_FIELD_SCOPE `
      + '(top level) or NESTED_FIELD_SCOPE (container.key)',
    );
  }
  return out;
}

export function sanitizePreviewReport(raw: unknown): SharedPreviewReport | null {
  if (raw === null || raw === undefined || typeof raw !== 'object') return null;
  let out = stripForbidden(raw);
  out = truncateQuotesDeep(out);
  if (out && typeof out === 'object' && 'evidence_appendix' in (out as Record<string, unknown>)) {
    (out as Record<string, unknown>).evidence_appendix = capEvidence(
      (out as Record<string, unknown>).evidence_appendix,
    );
  }
  return out as SharedPreviewReport;
}

// ── Discovery data ─────────────────────────────────────────────────────

/** Caps social_posts_sample to <=10 and strips URLs. */
function capSocialPosts(raw: unknown): unknown {
  if (!Array.isArray(raw)) return raw;
  return raw.slice(0, 10).map(p => {
    if (!p || typeof p !== 'object') return p;
    const { url, ...safe } = p as Record<string, unknown>;
    return safe;
  });
}

export function sanitizeDiscoveryData(raw: unknown): SharedDiscoveryData | null {
  if (raw === null || raw === undefined || typeof raw !== 'object') return null;
  let out = stripForbidden(raw);
  if (out && typeof out === 'object') {
    const obj = out as Record<string, unknown>;
    if ('social_posts_sample' in obj) {
      obj.social_posts_sample = capSocialPosts(obj.social_posts_sample);
    }
    // Drop hero_quote and quotes entirely — verbatim text with attribution risk
    delete obj.hero_quote;
    delete obj.quotes;
    delete obj.audience; // superseded by previewReport.audience_mapping
    delete obj.data_attribution;
    out = obj;
  }
  return out as SharedDiscoveryData;
}

// ── Zod schemas retained for type inference + optional strict mode ────
// Kept as z.record(z.unknown()) shells so imports that depend on these
// types continue to compile. The real safety is in sanitize* above.

export const SharedPreviewReportSchema = z.record(z.unknown());
export const SharedDiscoveryDataSchema = z.record(z.unknown());
