/**
 * Pure helpers for matching/canonicalizing pain-point titles. Used by:
 *   - catalog-pain-points-ready (workers.ts) — pain-point dedup at insert
 *   - publishIdea (catalogService.ts) — addressed-titles validation at idea publish
 *   - catalog-ideas-ready (workers.ts) — addressed-titles validation at worker bulk insert
 *   - backfillAddressedPains (script) — historical row migration
 *
 * `normalizeTitle` and `bigramSimilarity` were lifted from workers.ts so all
 * callers share one canonical implementation. `canonicalizeAddressedTitles` is
 * new — maps LLM-emitted pain titles to canonical titles from the same job's
 * pain list, with audit-friendly drop/correction outputs.
 */

/**
 * Bigram similarity (Dice coefficient) for fuzzy title matching.
 */
export function bigramSimilarity(a: string, b: string): number {
  if (a.length < 2 || b.length < 2) return a === b ? 1 : 0;
  const bigramsA = new Set(Array.from({ length: a.length - 1 }, (_, i) => a.slice(i, i + 2)));
  const bigramsB = new Set(Array.from({ length: b.length - 1 }, (_, i) => b.slice(i, i + 2)));
  const intersection = [...bigramsA].filter((bg) => bigramsB.has(bg)).length;
  return (2 * intersection) / (bigramsA.size + bigramsB.size) || 0;
}

/**
 * Normalize a title for fuzzy comparison: lowercase, strip punctuation, collapse whitespace.
 */
export function normalizeTitle(title: string): string {
  return title.toLowerCase().replace(/[^\w\s]/g, '').replace(/\s+/g, ' ').trim();
}

/** Bigram threshold mirrors the pain-points dedup logic at workers.ts. */
const FUZZY_THRESHOLD = 0.7;

export interface CanonicalizationResult {
  /** Canonical pain titles, deduped keep-first, in input order. */
  canonical: string[];
  /** LLM-emitted titles that failed even fuzzy matching. */
  dropped: string[];
  /** Audit log of fuzzy corrections (normalized form was unequal but bigram ≥ threshold). */
  corrected: Array<{ original: string; canonical: string; score: number }>;
}

/**
 * Map LLM-emitted pain titles to canonical titles from the same job's pain list.
 *
 * Resolution order per LLM-emitted title:
 *   1. Direct hit on normalized form → resolve to canonical, no `corrected` entry
 *   2. Bigram similarity ≥ FUZZY_THRESHOLD → resolve to highest-scoring canonical, add to `corrected`
 *   3. No match → add original to `dropped`
 *
 * `canonicalPains` shape is loose so it accepts both `report.detailed_pain_points`
 * (raw JSON from disk) and persisted `CatalogResearchContext.detailedPainPoints`
 * (Prisma loose type).
 */
export function canonicalizeAddressedTitles(
  llmTitles: string[],
  canonicalPains: Array<{ title?: unknown }>,
): CanonicalizationResult {
  const result: CanonicalizationResult = { canonical: [], dropped: [], corrected: [] };

  // Build canonical title list + normalize map (keep-first canonical on collision).
  const canonicalTitles: string[] = [];
  const normalizedToCanonical = new Map<string, string>();
  for (const p of canonicalPains) {
    if (!p || typeof p.title !== 'string') continue;
    const canonical = p.title;
    if (!canonical) continue;
    canonicalTitles.push(canonical);
    const norm = normalizeTitle(canonical);
    if (!normalizedToCanonical.has(norm)) {
      normalizedToCanonical.set(norm, canonical);
    }
  }

  if (canonicalTitles.length === 0) {
    for (const t of llmTitles) {
      if (typeof t === 'string' && t) result.dropped.push(t);
    }
    return result;
  }

  const seen = new Set<string>();

  for (const t of llmTitles) {
    if (typeof t !== 'string' || !t) continue;
    const norm = normalizeTitle(t);

    const direct = normalizedToCanonical.get(norm);
    if (direct) {
      if (!seen.has(direct)) {
        seen.add(direct);
        result.canonical.push(direct);
      }
      continue;
    }

    let bestScore = 0;
    let bestCanonical: string | null = null;
    for (const c of canonicalTitles) {
      const score = bigramSimilarity(norm, normalizeTitle(c));
      if (score > bestScore) {
        bestScore = score;
        bestCanonical = c;
      }
    }
    if (bestCanonical && bestScore >= FUZZY_THRESHOLD) {
      result.corrected.push({ original: t, canonical: bestCanonical, score: bestScore });
      if (!seen.has(bestCanonical)) {
        seen.add(bestCanonical);
        result.canonical.push(bestCanonical);
      }
      continue;
    }

    result.dropped.push(t);
  }

  return result;
}
