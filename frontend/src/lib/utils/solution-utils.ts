import type { SolutionPreview } from '$lib/types/job';

type BadgeVariant = 'success' | 'accent' | 'info' | 'warning';

export interface SuperpowerEntry {
  label: string;
  variant: BadgeVariant;
}

/** Short labels for card context */
export const SUPERPOWER_MAP: Record<string, SuperpowerEntry> = {
  market_fit_score: { label: 'Market Fit', variant: 'success' },
  seo_scalability_score: { label: 'SEO Power', variant: 'accent' },
  novelty_score: { label: 'Innovator', variant: 'info' },
  technical_feasibility_score: { label: 'Quick Build', variant: 'warning' },
  solo_dev_feasibility: { label: 'Solo-Friendly', variant: 'success' },
};

/** Longer labels for modal/detail context */
export const SUPERPOWER_MAP_DETAILED: Record<string, SuperpowerEntry> = {
  market_fit_score: { label: 'Strong Market Fit', variant: 'success' },
  seo_scalability_score: { label: 'SEO Powerhouse', variant: 'accent' },
  novelty_score: { label: 'Innovator', variant: 'info' },
  technical_feasibility_score: { label: 'Quick to Build', variant: 'warning' },
  solo_dev_feasibility: { label: 'Solo-Friendly', variant: 'success' },
};

const SCORE_KEYS: (keyof SolutionPreview)[] = [
  'market_fit_score',
  'seo_scalability_score',
  'novelty_score',
  'technical_feasibility_score',
  'solo_dev_feasibility',
];

export function computeCompositeScore(solution: SolutionPreview): number {
  if (solution.adjusted_composite_score != null) return solution.adjusted_composite_score;
  const vals = SCORE_KEYS.map((k) => (solution[k] as number | null | undefined) ?? 0);
  return vals.reduce((a, b) => a + b, 0) / vals.length;
}

export function getSuperpower(
  solution: SolutionPreview,
  map: Record<string, SuperpowerEntry> = SUPERPOWER_MAP,
): SuperpowerEntry {
  const entries: [string, number][] = SCORE_KEYS.map((k) => [
    k as string,
    (solution[k] as number | null | undefined) ?? 0,
  ]);
  entries.sort((a, b) => b[1] - a[1]);
  return map[entries[0][0]];
}
