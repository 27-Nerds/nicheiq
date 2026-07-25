/**
 * Cleans scraped-markdown artifacts out of evidence excerpts before they are
 * rendered inside quotation marks as verbatim quotes.
 *
 * - Strips backslash escapes left over from markdown scraping (`\-`, `\[`, ...)
 * - Converts list-marker sequences (flattened bullet lines) into ` · ` separators
 * - Marks leading/trailing mid-word cuts with an ellipsis instead of presenting
 *   a truncated token as verbatim text
 * - Collapses whitespace
 */
export function cleanEvidenceExcerpt(raw: string): string {
  // (a) Strip backslash escapes before markdown punctuation.
  let text = raw.replace(/\\([\\`*_{}[\]()#+\-.!>~|])/g, "$1");

  // (b) List markers: drop a leading marker, turn inline markers into separators.
  text = text.replace(/^\s*(?:[-*+•]|\d+[.)])\s+/, "");
  text = text.replace(/\s+[-*+•]\s+/g, " · ");

  // (d) Collapse whitespace (flattened list line-breaks included).
  text = text.replace(/\s+/g, " ").trim();

  if (text.length === 0) return "";

  // (c) Leading mid-word cut: a lowercase first character means the snippet
  // starts mid-word/mid-sentence — drop up to the first space and mark the cut.
  if (/^[a-z]/.test(text)) {
    const firstSpace = text.indexOf(" ");
    if (firstSpace !== -1) {
      text = "…" + text.slice(firstSpace + 1);
    } else {
      text = "…" + text;
    }
  }

  // (c) Trailing mid-word cut: ends on a letter with no sentence punctuation —
  // trim to the last complete word and mark the cut.
  if (/[a-zA-Z]$/.test(text)) {
    const lastSpace = text.lastIndexOf(" ");
    if (lastSpace !== -1) {
      text = text.slice(0, lastSpace).replace(/[\s·]+$/, "") + "…";
    } else {
      text = text + "…";
    }
  }

  return text;
}
