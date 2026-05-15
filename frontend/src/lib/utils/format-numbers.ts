export function formatCount(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

/**
 * Like `formatCount` but trims trailing `.0` (so `1000 → "1K"`, not `"1.0K"`)
 * and uses locale-aware formatting under 1K (so `1234567 → "1.2M"`,
 * `2500 → "2.5K"`, `999 → "999"`). Used by the catalog index hero kicker and
 * the /ideas SEO description template, where the dense mono dateline benefits
 * from the cleaner glyphs.
 */
export function formatCompact(n: number): string {
  if (n >= 1_000_000) {
    return `${(n / 1_000_000).toFixed(1).replace(/\.0$/, '')}M`;
  }
  if (n >= 1_000) {
    return `${(n / 1_000).toFixed(1).replace(/\.0$/, '')}K`;
  }
  return n.toLocaleString();
}

export function formatVolume(vol: number): string {
  return formatCount(vol);
}

export function tierVariant(
  tier: string | null | undefined,
): 'success' | 'warning' | 'error' | 'accent' | 'default' {
  if (!tier) return 'default';
  const t = tier.toUpperCase();
  if (t === 'EXCELLENT' || t === 'PLATINUM' || t === 'GOLD') return 'success';
  if (t === 'GOOD' || t === 'SILVER') return 'accent';
  if (t === 'MINIMAL' || t === 'BRONZE') return 'warning';
  return 'default';
}
