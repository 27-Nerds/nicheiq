import type { SolutionPreview, ReportSummary } from '$lib/types/job';
import {
  getSuperpower as _getSuperpower,
  computeCompositeScore as _computeComposite,
  SUPERPOWERS,
  SUPERPOWERS_DETAILED,
  SOLUTION_PREVIEW_KEYS,
  type SuperpowerEntry,
} from './superpower';

/**
 * Short labels keyed by snake_case field name (backward-compat re-export).
 */
export const SUPERPOWER_MAP: Record<string, SuperpowerEntry> = Object.fromEntries(
  SOLUTION_PREVIEW_KEYS.map(([field, canonical]) => [field, SUPERPOWERS[canonical]]),
);

/**
 * Longer labels keyed by snake_case field name (backward-compat re-export).
 */
export const SUPERPOWER_MAP_DETAILED: Record<string, SuperpowerEntry> = Object.fromEntries(
  SOLUTION_PREVIEW_KEYS.map(([field, canonical]) => [field, SUPERPOWERS_DETAILED[canonical]]),
);

export type { SuperpowerEntry };

export function computeCompositeScore(solution: SolutionPreview): number {
  if (solution.adjusted_composite_score != null) return solution.adjusted_composite_score;
  return _computeComposite(solution as unknown as Record<string, unknown>, SOLUTION_PREVIEW_KEYS);
}

export function solutionDisplayTitle(s: { headline?: string | null; solution_name: string }): string {
  return s.headline?.trim() || s.solution_name;
}

export interface TrifectaScores {
  demand: number | null;
  feasibility: number | null;
  opportunity: number | null;
}

/**
 * Scale a ReportSummary's 0-1 scores to the 0-100 dial range. Returns null
 * when all three dials would be empty, so callers can skip rendering an empty
 * Trifecta. Shared by the dashboard page and JobsListTable.
 */
export function summaryToScores(s: ReportSummary | undefined | null): TrifectaScores | null {
  if (!s) return null;
  const scale01 = (v: number | null | undefined) => (v == null ? null : Math.round(v * 100));
  const out: TrifectaScores = {
    demand: scale01(s.market_fit_score),
    feasibility: scale01(s.technical_feasibility_score),
    opportunity: scale01(s.opportunity_score),
  };
  if (out.demand == null && out.feasibility == null && out.opportunity == null) return null;
  return out;
}

export function solutionCardDescription(s: { short_description?: string | null; description: string }): string {
  return s.short_description?.trim() || s.description;
}

/**
 * Adaptive originality metric for the bar that replaces the old "Novelty" display.
 *
 * - When the idea has the independent novelty critic's `obviousness_score` (lower = more
 *   original), we surface **Originality** = `1 - obviousness_score`.
 * - For legacy data with only `novelty_score` (older reports / catalog rows published before
 *   obviousness existed, or a concept name that didn't match in carry-through), we fall back to
 *   the refiner's score AND keep the honest **Novelty** label — we never relabel a pure novelty
 *   score as originality.
 * - When neither exists, `value`/`label` are null → callers render "—" or hide the row.
 */
export type OriginalityMetric = {
  /** 0-1, higher = better. Null when no source score exists. */
  value: number | null;
  /** Full label: "Originality" (obviousness-derived) | "Novelty" (legacy) | null. */
  label: 'Originality' | 'Novelty' | null;
  /** Compact label for dense scorecards: "Orig" | "Nov" | null. */
  short: 'Orig' | 'Nov' | null;
  /** True only when the value came from obviousness_score (real originality signal). */
  isOriginality: boolean;
};

export function originalityMetric(
  idea: { obviousness_score?: number | null; novelty_score?: number | null },
): OriginalityMetric {
  if (idea?.obviousness_score != null) {
    return {
      value: Math.max(0, Math.min(1, 1 - idea.obviousness_score)),
      label: 'Originality',
      short: 'Orig',
      isOriginality: true,
    };
  }
  if (idea?.novelty_score != null) {
    return { value: idea.novelty_score, label: 'Novelty', short: 'Nov', isOriginality: false };
  }
  return { value: null, label: null, short: null, isOriginality: false };
}

/**
 * Value-only convenience wrapper over {@link originalityMetric} — returns the 0-1 score
 * (obviousness-derived, falling back to novelty), or null → renders "—". Use
 * `originalityMetric()` when you also need the adaptive label.
 */
export function originalityScore(
  idea: { obviousness_score?: number | null; novelty_score?: number | null },
): number | null {
  return originalityMetric(idea).value;
}

/** Human-readable fit label from market_fit_score (0-1 scale) */
export function fitLabel(score: number | null | undefined): { text: string; variant: 'success' | 'warning' | 'muted' } {
  if (score == null) return { text: '', variant: 'muted' };
  if (score >= 0.7) return { text: 'HIGH FIT', variant: 'success' };
  if (score >= 0.4) return { text: 'MOD FIT', variant: 'warning' };
  return { text: 'LOW FIT', variant: 'muted' };
}

export function getSuperpower(
  solution: SolutionPreview,
  map: Record<string, SuperpowerEntry> = SUPERPOWER_MAP,
): SuperpowerEntry | null {
  // If caller passes the old snake_case-keyed map, convert to canonical
  const isSnakeKeyed = Object.keys(map).some((k) => k.includes('_'));
  if (isSnakeKeyed) {
    // Build canonical map from snake-keyed map
    const canonicalMap: Record<string, SuperpowerEntry> = {};
    for (const [field, canonical] of SOLUTION_PREVIEW_KEYS) {
      if (map[field]) canonicalMap[canonical] = map[field];
    }
    return _getSuperpower(solution as unknown as Record<string, unknown>, SOLUTION_PREVIEW_KEYS, canonicalMap);
  }
  return _getSuperpower(solution as unknown as Record<string, unknown>, SOLUTION_PREVIEW_KEYS, map);
}
