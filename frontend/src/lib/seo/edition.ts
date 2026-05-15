// Editorial freshness label for SEO surfaces ("May 2026", "Latest edition").
//
// Returns a literal `Month YYYY` string when the catalog snapshot is recent
// (≤ 45 days), or the safe phrase `"Latest edition"` when `lastUpdated` is
// null, unparseable, or stale. Stale-but-month-stamped headers fabricate
// freshness, which falls afoul of Google's "helpful content" guidance —
// hence the guardrail rather than a silent `new Date()` fallback.

const STALE_THRESHOLD_MS = 45 * 24 * 60 * 60 * 1000;

const FORMATTER = new Intl.DateTimeFormat("en-US", {
  month: "long",
  year: "numeric",
});

export const LATEST_EDITION_FALLBACK = "Latest edition";

export function editionLabel(lastUpdated: string | null | undefined): string {
  if (!lastUpdated) return LATEST_EDITION_FALLBACK;
  const d = new Date(lastUpdated);
  const ts = d.getTime();
  if (Number.isNaN(ts)) return LATEST_EDITION_FALLBACK;
  if (Date.now() - ts > STALE_THRESHOLD_MS) return LATEST_EDITION_FALLBACK;
  return FORMATTER.format(d);
}

export function isFallbackEdition(label: string): boolean {
  return label === LATEST_EDITION_FALLBACK;
}
