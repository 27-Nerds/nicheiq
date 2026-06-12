/**
 * Compact relative-time formatter for the saved page (e.g. "2d", "5h", "1w").
 * Pure function — no external dep, JetBrains-Mono-friendly output.
 */
export function formatDistanceToNow(iso: string): string {
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return '—';
  const diff = Math.max(0, Date.now() - t);
  const sec = Math.floor(diff / 1000);
  if (sec < 60) return 'now';
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h`;
  const day = Math.floor(hr / 24);
  if (day < 7) return `${day}d`;
  const wk = Math.floor(day / 7);
  if (wk < 4) return `${wk}w`;
  const mo = Math.floor(day / 30);
  if (mo < 12) return `${mo}mo`;
  const yr = Math.floor(day / 365);
  return `${yr}y`;
}

/**
 * Long-form variant for prose surfaces (stat tiles) where "1mo" reads as
 * unit soup — returns "1 month ago", "3 weeks ago", etc. Table cells keep
 * the compact form above.
 */
export function formatDistanceToNowLong(iso: string): string {
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return '—';
  const diff = Math.max(0, Date.now() - t);
  const sec = Math.floor(diff / 1000);
  if (sec < 60) return 'just now';
  const plural = (n: number, unit: string) => `${n} ${unit}${n === 1 ? '' : 's'} ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return plural(min, 'minute');
  const hr = Math.floor(min / 60);
  if (hr < 24) return plural(hr, 'hour');
  const day = Math.floor(hr / 24);
  if (day < 7) return plural(day, 'day');
  const wk = Math.floor(day / 7);
  if (wk < 4) return plural(wk, 'week');
  const mo = Math.floor(day / 30);
  if (mo < 12) return plural(mo, 'month');
  const yr = Math.floor(day / 365);
  return plural(yr, 'year');
}
