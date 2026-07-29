import type { SolutionPreview, StrengthKey } from '$lib/types/job';
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
 * Tells the user whether the niche rewards being FOUND (distribution/SEO), being DIFFERENT (a distinct
 * mechanism), or OWNING a workflow. Computed from the ideas' winning_angle; null when too few are
 * classified to be meaningful. The angles are peers — this describes the niche, not a quality verdict.
 */
const _ANGLE_SHAPE: Record<string, { word: string; why: string }> = {
  distribution_seo: { word: 'distribution-leaning', why: 'win by being found (SEO), not by an unusual mechanism' },
  novel_differentiation: { word: 'differentiation-leaning', why: "win on a distinct mechanism rivals can't easily copy" },
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

/**
 * Returns a composite score only when the report contains at least one valid
 * score input. This keeps legacy or partially failed reports from presenting
 * missing data as a real 0 score.
 */
export function displayCompositeScore(solution: SolutionPreview): number | null {
  const adjusted = solution.adjusted_composite_score;
  if (
    typeof adjusted === "number"
    && Number.isFinite(adjusted)
    && adjusted >= 0
    && adjusted <= 1
  ) {
    return adjusted;
  }

  const sanitized: Record<string, unknown> = {};
  let hasScoreInput = false;
  for (const [field] of SOLUTION_PREVIEW_KEYS) {
    const value = (solution as unknown as Record<string, unknown>)[field];
    const valid = typeof value === "number"
      && Number.isFinite(value)
      && value >= 0
      && value <= 1;
    sanitized[field] = valid ? value : 0;
    hasScoreInput ||= valid;
  }

  return hasScoreInput ? _computeComposite(sanitized, SOLUTION_PREVIEW_KEYS) : null;
}

export function solutionDisplayTitle(s: { headline?: string | null; solution_name: string }): string {
  return s.headline?.trim() || s.solution_name;
}

export function solutionCardDescription(s: { short_description?: string | null; description: string }): string {
  return s.short_description?.trim() || s.description;
}

/**
 * Unified distinctiveness metric for current and legacy reports.
 *
 * - When the idea has the independent novelty critic's `obviousness_score` (lower = more
 *   original), the value is `1 - obviousness_score`.
 * - Legacy data falls back to novelty_score. Both are presented as **Distinctiveness** because
 *   that is the user decision the measure supports; source provenance stays internal.
 * - When neither exists, `value`/`label` are null → callers render "—" or hide the row.
 */
export type OriginalityMetric = {
  /** 0-1, higher = better. Null when no source score exists. */
  value: number | null;
  /** User-facing label shared by current and legacy records. */
  label: 'Distinctiveness' | null;
  /** Compact label for dense scorecards. */
  short: 'Distinct' | null;
  /** True only when the value came from obviousness_score (real originality signal). */
  isOriginality: boolean;
};

export function originalityMetric(
  idea: { obviousness_score?: number | null; novelty_score?: number | null },
): OriginalityMetric {
  if (idea?.obviousness_score != null) {
    return {
      value: Math.max(0, Math.min(1, 1 - idea.obviousness_score)),
      label: 'Distinctiveness',
      short: 'Distinct',
      isOriginality: true,
    };
  }
  if (idea?.novelty_score != null) {
    return { value: idea.novelty_score, label: 'Distinctiveness', short: 'Distinct', isOriginality: false };
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

const STRENGTH_RULES: ReadonlyArray<{
  key: StrengthKey;
  field: keyof SolutionPreview;
  cutoff: number;
}> = [
  { key: "market-fit", field: "market_fit_score", cutoff: 0.82 },
  { key: "seo-power", field: "seo_scalability_score", cutoff: 0.85 },
  { key: "innovator", field: "novelty_score", cutoff: 0.70 },
  { key: "quick-build", field: "technical_feasibility_score", cutoff: 0.85 },
  { key: "solo-friendly", field: "solo_dev_feasibility", cutoff: 0.78 },
];

/** Strengths that are still supported by the scores currently shown for this report. */
export function validatedStrengthKeys(solution: SolutionPreview): StrengthKey[] {
  return STRENGTH_RULES
    .filter(({ field, cutoff }) => {
      const value = solution[field];
      return typeof value === "number" && Number.isFinite(value) && value >= cutoff;
    })
    .map(({ key }) => key);
}

function validScore(value: number | null | undefined): value is number {
  return typeof value === "number"
    && Number.isFinite(value)
    && value >= 0
    && value <= 1;
}

/**
 * Build-complexity bucket supported by the scores currently shown for this report.
 * Falls back to the persisted tag only when no usable source score exists.
 */
export function validatedBuildComplexity(
  solution: SolutionPreview,
): "low" | "medium" | "high" | null {
  const score = [
    solution.solo_dev_feasibility,
    solution.build_feasibility_score,
    solution.technical_feasibility_score,
  ].find(validScore);

  if (score != null) {
    if (score >= 0.78) return "low";
    if (score >= 0.65) return "medium";
    return "high";
  }

  const persisted = solution.tags?.build_complexity;
  return persisted === "low" || persisted === "medium" || persisted === "high"
    ? persisted
    : null;
}

/**
 * Distinctiveness bucket supported by the scores currently shown for this report.
 * Current records prefer inverse obviousness; legacy records use novelty.
 */
export function validatedNoveltyLevel(
  solution: SolutionPreview,
): "novel" | "moderate" | "conventional" | null {
  if (validScore(solution.obviousness_score)) {
    if (solution.obviousness_score <= 0.30) return "novel";
    if (solution.obviousness_score >= 0.60) return "conventional";
    return "moderate";
  }

  if (validScore(solution.novelty_score)) {
    if (solution.novelty_score >= 0.70) return "novel";
    if (solution.novelty_score <= 0.40) return "conventional";
    return "moderate";
  }

  const persisted = solution.tags?.novelty_level;
  return persisted === "novel" || persisted === "moderate" || persisted === "conventional"
    ? persisted
    : null;
}

/** Most exceptional current strength, using the same max-margin rule as the pipeline. */
export function solutionPrimaryStrengthKey(solution: SolutionPreview): StrengthKey | null {
  let primary: StrengthKey | null = null;
  let largestMargin = Number.NEGATIVE_INFINITY;

  for (const { key, field, cutoff } of STRENGTH_RULES) {
    const value = solution[field];
    if (typeof value !== "number" || !Number.isFinite(value) || value < cutoff) continue;
    const margin = value - cutoff;
    if (margin > largestMargin) {
      primary = key;
      largestMargin = margin;
    }
  }

  return primary;
}

/**
 * Card strength badge derived from the scores displayed in the same report. Recomputing
 * defensively keeps older persisted tags from contradicting a later score sync.
 */
export function solutionStrengthBadge(
  solution: SolutionPreview,
  detailed = false,
): SuperpowerEntry | null {
  return strengthEntry(
    solutionPrimaryStrengthKey(solution),
    detailed ? SUPERPOWERS_DETAILED : SUPERPOWERS,
  );
}
