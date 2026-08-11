/**
 * Normalizes "Check my idea" pitch text: curly quotes, apostrophes, and
 * dashes collapse to their ASCII equivalents, and zero-width characters are
 * stripped. Applied on paste/blur and on committed "Other..." clarify
 * answers - deliberately NOT on every keystroke, so it never fights the
 * user's cursor position while they're still typing.
 *
 * This exists because iOS/macOS auto-curl quotes as you type, which
 * silently broke the old niche charset regex on every entry mode (curly
 * apostrophe 400s today) and would otherwise make lexical word-matching
 * (ideaCoverage, the clarify chip vocabulary) miss contractions like
 * "can't".
 *
 * The character classes below are built from numeric code points (not
 * pasted literals) so the exact characters are unambiguous on review -
 * several are zero-width and impossible to eyeball in a diff.
 */

// Left single quote, right single quote, single low-9 quote, single
// high-reversed-9 quote.
const APOSTROPHE_CODE_POINTS = [0x2018, 0x2019, 0x201a, 0x201b];
// Left double quote, right double quote, double low-9 quote, double
// high-reversed-9 quote.
const DOUBLE_QUOTE_CODE_POINTS = [0x201c, 0x201d, 0x201e, 0x201f];
// En dash, em dash, minus sign.
const DASH_CODE_POINTS = [0x2013, 0x2014, 0x2212];
// Zero-width space, zero-width non-joiner, zero-width joiner, word joiner,
// BOM / zero-width no-break space.
const ZERO_WIDTH_CODE_POINTS = [0x200b, 0x200c, 0x200d, 0x2060, 0xfeff];

function charClassRegExp(codePoints: number[]): RegExp {
  const chars = codePoints.map((codePoint) => String.fromCharCode(codePoint)).join("");
  return new RegExp(`[${chars}]`, "g");
}

const APOSTROPHE_RE = charClassRegExp(APOSTROPHE_CODE_POINTS);
const DOUBLE_QUOTE_RE = charClassRegExp(DOUBLE_QUOTE_CODE_POINTS);
const DASH_RE = charClassRegExp(DASH_CODE_POINTS);
const ZERO_WIDTH_RE = charClassRegExp(ZERO_WIDTH_CODE_POINTS);

export function normalizeIdeaText(text: string): string {
  return text
    .replace(APOSTROPHE_RE, "'")
    .replace(DOUBLE_QUOTE_RE, '"')
    .replace(DASH_RE, "-")
    .replace(ZERO_WIDTH_RE, "");
}
