export function formatCount(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
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
