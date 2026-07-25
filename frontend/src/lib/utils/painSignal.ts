/**
 * Normalize a raw Discovery pain-signal string for display.
 *
 * Legacy runs stored `pain_points_addressed` entries verbatim from the ranked
 * pain list, e.g.:
 *   "1. Adverse Reactions… (Severity 8.0/10, Mentions 10): reduces risk by…"
 * Facts and bundle lists want only the pain title, so strip, in order:
 *   1. the leading rank prefix ("1. ")
 *   2. the "(Severity …)" metadata parenthetical
 *   3. the ": rationale" tail (first ": " after the parenthetical)
 * Clean strings (modern `source_pain`) pass through unchanged — in particular
 * a ": " inside a pain title without severity metadata is left alone.
 */
export function normalizePainSignal(raw: string): string {
  let text = raw.trim().replace(/^\d+\.\s*/, "");
  const meta = text.match(/\s*\(Severity[^)]*\)/i);
  if (meta?.index != null) {
    let tail = text.slice(meta.index + meta[0].length);
    const colon = tail.indexOf(": ");
    if (colon !== -1) tail = tail.slice(0, colon);
    text = (text.slice(0, meta.index) + tail).trim();
  }
  return text;
}
