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
