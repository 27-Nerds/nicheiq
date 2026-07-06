import type { SolutionPreview, ReportSummary } from '$lib/types/job';
import {
  getSuperpower as _getSuperpower,
  computeCompositeScore as _computeComposite,
  strengthEntry,
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

/**
 * Opportunity shape — a one-line read on how this niche's viable ideas split across GTM angles.
 * Tells the user whether the niche rewards being FOUND (distribution/SEO), being DIFFERENT (a novel
 * mechanism), or OWNING a workflow. Computed from the ideas' winning_angle; null when too few are
 * classified to be meaningful. The angles are peers — this describes the niche, not a quality verdict.
 */
const _ANGLE_SHAPE: Record<string, { word: string; why: string }> = {
  distribution_seo: { word: 'distribution-leaning', why: 'win by being found (SEO), not by a novel mechanism' },
  novel_differentiation: { word: 'novelty-leaning', why: "win on a novel mechanism rivals can't easily copy" },
  vertical_workflow: { word: 'workflow-leaning', why: 'win by owning a deep workflow for a specific user' },
};

export function opportunityShape(
  solutions: SolutionPreview[] | null | undefined,
): { dominant: string; counts: Record<string, number>; line: string } | null {
  const angled = (solutions ?? []).filter((s) => s.winning_angle);
  if (angled.length < 3) return null; // too little signal to characterize the niche

  const counts: Record<string, number> = {};
  for (const s of angled) counts[s.winning_angle!] = (counts[s.winning_angle!] ?? 0) + 1;
  const ranked = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  const [dominant, n] = ranked[0];
  const total = angled.length;

  // A clear lean needs a plurality AND a real edge over the runner-up; otherwise it's a mixed niche.
  const runnerUp = ranked[1]?.[1] ?? 0;
  const shape = _ANGLE_SHAPE[dominant];
  const line = (!shape || n === runnerUp)
    ? `Mixed niche: viable plays span ${ranked.length} angles, no single dominant approach.`
    : `${shape.word.charAt(0).toUpperCase() + shape.word.slice(1)} niche: ${n} of ${total} viable ideas ${shape.why}.`;

  return { dominant, counts, line };
}

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

/**
 * Card strength badge. Prefers the backend-computed `tags.primary_strength` (margin above
 * standardized cutoffs — see docs/IDEA_TAGS.md); falls back to the legacy client-side argmax
 * only for older reports that predate tags. Returns null when no strength clears its cutoff.
 */
export function solutionStrengthBadge(
  solution: SolutionPreview,
  detailed = false,
): SuperpowerEntry | null {
  const primary = solution.tags?.primary_strength;
  if (primary) return strengthEntry(primary, detailed ? SUPERPOWERS_DETAILED : SUPERPOWERS);
  // Legacy fallback (pre-tags reports): client-side selection.
  if (solution.tags) return null; // tags present but no strength cleared → honestly show none
  return getSuperpower(solution, detailed ? SUPERPOWER_MAP_DETAILED : SUPERPOWER_MAP);
}
