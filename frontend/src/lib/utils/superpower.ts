/**
 * Canonical superpower definitions and generic score helpers.
 *
 * Single source of truth for superpower labels, score key mappings,
 * and composite-score / superpower computation.
 */

type BadgeVariant = 'success' | 'accent' | 'info' | 'warning';

export interface SuperpowerEntry {
  label: string;
  variant: BadgeVariant;
}

// Canonical keys (framework-agnostic)
type CanonicalKey = 'marketFit' | 'seoScalability' | 'novelty' | 'techFeasibility' | 'soloDev';

// Every superpower is a positive strength, and only one badge shows per idea — so the
// color encodes valence (this is a strength), not which capability. All read as success;
// the label says which one. 'warning' (amber) is reserved for the severity/risk ramp,
// never for a positive trait.
/** Short labels for card context */
export const SUPERPOWERS: Record<CanonicalKey, SuperpowerEntry> = {
  marketFit: { label: 'Demand fit', variant: 'success' },
  seoScalability: { label: 'Organic discovery', variant: 'success' },
  novelty: { label: 'Distinct mechanism', variant: 'success' },
  techFeasibility: { label: 'Technically straightforward', variant: 'success' },
  soloDev: { label: 'Solo-manageable', variant: 'success' },
};

/** Longer labels for modal/detail context */
export const SUPERPOWERS_DETAILED: Record<CanonicalKey, SuperpowerEntry> = {
  marketFit: { label: 'Strong demand fit', variant: 'success' },
  seoScalability: { label: 'Strong organic discovery', variant: 'success' },
  novelty: { label: 'Distinct mechanism', variant: 'success' },
  techFeasibility: { label: 'Technically straightforward', variant: 'success' },
  soloDev: { label: 'Solo-manageable', variant: 'success' },
};

/**
 * A key mapping translates object field names to canonical keys.
 * Each entry is [fieldName, canonicalKey].
 */
export type KeyMapping = [string, CanonicalKey][];

/** snake_case SolutionPreview fields -> canonical keys */
export const SOLUTION_PREVIEW_KEYS: KeyMapping = [
  ['market_fit_score', 'marketFit'],
  ['seo_scalability_score', 'seoScalability'],
  ['novelty_score', 'novelty'],
  ['technical_feasibility_score', 'techFeasibility'],
  ['solo_dev_feasibility', 'soloDev'],
];

/**
 * Compute average of mapped score fields (null treated as 0, divides by total count).
 */
export function computeCompositeScore(
  obj: Record<string, unknown>,
  keyMapping: KeyMapping,
): number {
  const vals = keyMapping.map(([field]) => {
    const v = obj[field];
    return typeof v === 'number' ? v : 0;
  });
  return vals.reduce((a, b) => a + b, 0) / vals.length;
}

/** Minimum score to award a superpower badge */
export const SUPERPOWER_THRESHOLD = 0.7;

/**
 * Find the highest-scoring dimension and return its superpower entry,
 * or null if the top score is below threshold.
 */
export function getSuperpower(
  obj: Record<string, unknown>,
  keyMapping: KeyMapping,
  map: Record<string, SuperpowerEntry> = SUPERPOWERS,
  threshold: number = SUPERPOWER_THRESHOLD,
): SuperpowerEntry | null {
  const entries: [CanonicalKey, number][] = keyMapping.map(([field, canonical]) => [
    canonical,
    typeof obj[field] === 'number' ? (obj[field] as number) : 0,
  ]);
  entries.sort((a, b) => b[1] - a[1]);
  if (entries[0][1] < threshold) return null;
  return map[entries[0][0]];
}

/**
 * Backend strength keys (IdeaTags.strengths / primary_strength, hyphenated) → canonical key.
 * The backend now owns strength selection (margin above standardized cutoffs); this file keeps
 * only the display labels/variants.
 */
const STRENGTH_KEY_TO_CANONICAL: Record<string, CanonicalKey> = {
  'market-fit': 'marketFit',
  'seo-power': 'seoScalability',
  'innovator': 'novelty',
  'quick-build': 'techFeasibility',
  'solo-friendly': 'soloDev',
};

/** Resolve a backend strength key to its display entry (label + variant), or null. */
export function strengthEntry(
  key: string | null | undefined,
  map: Record<string, SuperpowerEntry> = SUPERPOWERS,
): SuperpowerEntry | null {
  if (!key) return null;
  const canonical = STRENGTH_KEY_TO_CANONICAL[key];
  return canonical ? map[canonical] : null;
}
