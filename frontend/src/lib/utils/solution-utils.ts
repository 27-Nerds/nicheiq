import type { SolutionPreview } from '$lib/types/job';
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
