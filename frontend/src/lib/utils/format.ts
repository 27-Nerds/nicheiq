// Formatting utilities for report data

import { marked } from 'marked';
import DOMPurify from 'isomorphic-dompurify';

// Configure marked for safe rendering
marked.setOptions({
	gfm: true,
	breaks: true
});

/**
 * Phase 15.0 — strict allow-list for sanitizing rendered markdown HTML before
 * `{@html ...}`. Tags not on this list are stripped; attributes other than
 * `class` are stripped. Disallows: <script>, <style>, <iframe>, <form>,
 * <input>, event-handler attributes (onclick=, etc.), javascript: URLs.
 *
 * Used by `renderMarkdown` and `renderTechnicalContent` — both render through
 * `{@html ...}` in catalog SEO pages and must not allow XSS payloads from
 * LLM output or future ingest paths.
 */
const SANITIZER_ALLOWED_TAGS = [
	'p', 'br', 'span', 'em', 'strong', 'b', 'i',
	'ul', 'ol', 'li',
	'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
	'code', 'pre', 'blockquote',
	'hr',
];
const SANITIZER_ALLOWED_ATTR = ['class'];

// One-time hook: force safe rel/target on any sanitized anchor (only fires when
// `a` is on the allow-list — i.e. the allowLinks path below). DOMPurify already
// strips javascript:/data: hrefs; this just hardens external links. Relative,
// same-origin hrefs (e.g. the chat analyst's `/new?niche=...` pivot links) stay
// in the current tab — they're app navigation, not an outbound link — so only
// absolute (http/https/protocol-relative) hrefs get target=_blank.
let _linkHookInstalled = false;
function ensureLinkHook(): void {
	if (_linkHookInstalled) return;
	DOMPurify.addHook('afterSanitizeAttributes', (node: Element) => {
		if (node.tagName === 'A' && node.hasAttribute('href')) {
			const href = node.getAttribute('href') || '';
			const isRelative = href.startsWith('/') && !href.startsWith('//');
			if (isRelative) {
				node.removeAttribute('target');
				node.removeAttribute('rel');
			} else {
				node.setAttribute('target', '_blank');
				node.setAttribute('rel', 'noopener noreferrer nofollow');
			}
		}
	});
	_linkHookInstalled = true;
}

function sanitizeHtml(html: string, opts: { allowLinks?: boolean; allowImages?: boolean } = {}): string {
	const { allowLinks = false, allowImages = false } = opts;
	if (allowLinks) ensureLinkHook();
	let allowedTags = [...SANITIZER_ALLOWED_TAGS];
	let allowedAttr = [...SANITIZER_ALLOWED_ATTR];
	if (allowLinks) {
		allowedTags.push('a');
		allowedAttr.push('href', 'target', 'rel');
	}
	// Images are only enabled for author-controlled content (blog/help). DOMPurify
	// strips javascript:/data: srcs and any event-handler attrs (onerror, etc.).
	// Width/height let markdown ![..](url =WxH) hints flow through for layout stability.
	if (allowImages) {
		allowedTags.push('img');
		allowedAttr.push('src', 'alt', 'width', 'height');
	}
	return DOMPurify.sanitize(html, {
		ALLOWED_TAGS: allowedTags,
		ALLOWED_ATTR: allowedAttr,
		// Defense-in-depth: strip any data-* / aria-* not on allow-list.
		ALLOW_DATA_ATTR: false,
		ALLOW_ARIA_ATTR: false,
	});
}

/**
 * Render markdown to sanitized HTML.
 *
 * `opts.allowLinks` opts into `<a href>` (sanitized; external links get
 * target=_blank rel=noopener). Off by default so existing call sites are
 * unchanged — only the help pages, whose content is author-controlled, enable it.
 *
 * `opts.allowImages` opts into `<img>` (src/alt/width/height only; DOMPurify
 * strips onerror/javascript: srcs). Used by the blog renderer for author-
 * controlled content. Requires allowLinks when links are also needed.
 */
export function renderMarkdown(
	content: string | undefined | null,
	opts: { allowLinks?: boolean; allowImages?: boolean } = {},
): string {
	if (!content) return '';
	const html = marked.parse(content, { async: false }) as string;
	return sanitizeHtml(html, opts);
}

/** Strip markdown syntax from raw text, returning clean plain text. */
export function stripMarkdown(content: string | undefined | null): string {
	if (!content) return '';
	return content
		.replace(/^#{1,6}\s+/gm, '')          // header prefixes: ### Title
		.replace(/\*\*(.+?)\*\*/g, '$1')      // bold: **text**
		.replace(/__(.+?)__/g, '$1')           // bold alt: __text__
		.replace(/\*(.+?)\*/g, '$1')           // italic: *text*
		.replace(/_(.+?)_/g, '$1')             // italic alt: _text_
		.replace(/~~(.+?)~~/g, '$1')           // strikethrough: ~~text~~
		.replace(/`([^`]+)`/g, '$1')           // inline code: `code`
		.replace(/^\s*[-*+]\s+/gm, '')         // unordered list markers
		.replace(/^\s*\d+\.\s+/gm, '')         // ordered list markers
		.replace(/^\s*>\s?/gm, '')             // blockquote markers
		.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1') // links: [text](url) → text
		.replace(/  +/g, ' ')                  // collapse multiple spaces
		.trim();
}

export function renderTechnicalContent(content: string | undefined | null): string {
	if (!content) return '';

	let processed = content;

	// 1. Wrap JSON-LD blocks in code fences
	// Find JSON-LD patterns starting with {"@ and extract complete balanced JSON
	const jsonLdPattern = /\{\s*"@/g;
	let jsonMatch;
	while ((jsonMatch = jsonLdPattern.exec(processed)) !== null) {
		const startIdx = jsonMatch.index;
		let depth = 0;
		let endIdx = startIdx;
		let inString = false;
		let escaped = false;

		// Find matching closing brace by counting depth
		for (let i = startIdx; i < processed.length; i++) {
			const char = processed[i];
			if (escaped) {
				escaped = false;
				continue;
			}
			if (char === '\\') {
				escaped = true;
				continue;
			}
			if (char === '"') {
				inString = !inString;
				continue;
			}
			if (inString) continue;

			if (char === '{' || char === '[') depth++;
			else if (char === '}' || char === ']') {
				depth--;
				if (depth === 0) {
					endIdx = i + 1;
					break;
				}
			}
		}

		if (endIdx > startIdx) {
			const jsonStr = processed.slice(startIdx, endIdx);
			const replacement = '\n```json\n' + jsonStr.trim() + '\n```\n';
			processed = processed.slice(0, startIdx) + replacement + processed.slice(endIdx);
			// Adjust pattern index for the replacement
			jsonLdPattern.lastIndex = startIdx + replacement.length;
		}
	}

	// 2. Highlight URL paths (e.g., /library/, /templates/[slug]/)
	processed = processed.replace(
		/([\s(,])(\/[a-z0-9\-_\/\[\]]+\/?)(?=[\s,):]|$)/gi,
		'$1`$2`'
	);

	// Parse markdown to HTML first
	let html = marked.parse(processed, { async: false }) as string;

	// 3. Remove ALL <a> tags from technical content
	// Technical SEO recommendations contain code examples (JSON-LD, URLs) that shouldn't be clickable
	html = html.replace(/<a[^>]*>([^<]*)<\/a>/gi, '$1');

	// Phase 15.0 — strict-allow-list sanitize BEFORE week-highlight insertion
	// (DOMPurify would otherwise strip the <span class="week-highlight"> we
	// add next). Anything not on SANITIZER_ALLOWED_TAGS — including <script>,
	// <iframe>, event-handler attributes, javascript: URLs — gets stripped.
	html = sanitizeHtml(html);

	// 4. Post-process HTML: highlight week references inline (simple color only)
	// Handles: "Sprint-zero", "Week 1", "Week 1:", "Weeks 1–4", "Weeks 5–8", etc.
	// Re-injected AFTER sanitize because the <span class="week-highlight"> is
	// trusted (we generate it; it's not from user input). The substituted
	// content is the original matched text, which is plain alphanumerics and
	// punctuation — no XSS surface.
	html = html.replace(
		/(Sprint-zero|Weeks?\s*\d+(?:[–-]\d+)?:?)/gi,
		'<span class="week-highlight">$1</span>'
	);

	return html;
}

export function formatNumber(num: number | undefined | null): string {
	if (num === undefined || num === null) return 'N/A';
	if (num >= 1_000_000) return `${(num / 1_000_000).toFixed(1)}M`;
	if (num >= 1_000) return `${(num / 1_000).toFixed(1)}K`;
	return num.toLocaleString();
}

export function formatPercent(num: number | undefined | null, decimals = 0): string {
	if (num === undefined || num === null) return 'N/A';
	// If number is between 0 and 1, multiply by 100
	const value = num <= 1 ? num * 100 : num;
	return `${value.toFixed(decimals)}%`;
}

export function formatScore(num: number | undefined | null): string {
	if (num === undefined || num === null) return 'N/A';
	// Scores are typically 0-1, display as decimal
	return num.toFixed(2);
}

/** Format a 0-1 score as "XX%" (e.g. 0.85 -> "85%") */
export function formatScorePercent(
	score: number | undefined | null,
	decimals = 0,
	fallback = 'N/A'
): string {
	if (score === undefined || score === null || Number.isNaN(score)) return fallback;
	return `${(score * 100).toFixed(decimals)}%`;
}

/** Format a 0-1 score as "X.Y/10" (e.g. 0.85 -> "8.5/10") */
export function formatScoreOutOf10(score: number | undefined | null): string {
	if (score === undefined || score === null || Number.isNaN(score)) return 'N/A';
	return `${(score * 10).toFixed(1)}/10`;
}

/** Format a 0-1 score as "X.Y" on a 10 scale, without "/10" suffix (e.g. 0.85 -> "8.5") */
export function formatScoreOn10(score: number | undefined | null): string {
	if (score === undefined || score === null || Number.isNaN(score)) return '-';
	const clamped = Math.max(0, Math.min(1, score));
	return (clamped * 10).toFixed(1);
}

/** Strip a leading "the " (case-insensitive) from a string */
export function stripLeadingArticle(s: string): string {
	return s.replace(/^the\s+/i, '');
}

/** Title-case a string (capitalize first letter of each word) */
export function titleCase(s: string | null | undefined): string {
	if (!s) return '';
	return s.replace(/\b\w/g, c => c.toUpperCase());
}

/**
 * The opening sentence of a longer passage, for use as a deck/lede.
 *
 * The report header fell back to the full `executive_summary` when no short field was
 * stored — 1,093 characters of prose as the page's first paint (live audit 2026-08-03,
 * where `tagline` and `short_description` were both empty). A deck is a one-line answer;
 * the full passage belongs in a section. Returns the first sentence when that is a
 * reasonable length, otherwise a clamped prefix broken on a word.
 */
export function leadSentence(text: string | null | undefined, maxLength = 240): string {
	const trimmed = (text ?? '').trim();
	if (!trimmed) return '';
	if (trimmed.length <= maxLength) return trimmed;
	// Sentence end followed by whitespace — avoids splitting "U.S." or "$1.03M".
	const match = trimmed.match(/^[\s\S]*?[.!?](?=\s)/);
	const sentence = match?.[0]?.trim();
	if (sentence && sentence.length <= maxLength) return sentence;
	const clipped = trimmed.slice(0, maxLength);
	const lastSpace = clipped.lastIndexOf(' ');
	return `${(lastSpace > maxLength * 0.6 ? clipped.slice(0, lastSpace) : clipped).trimEnd()}…`;
}

/** Magnitude suffixes used by the report's money strings, largest first. */
const MONEY_UNITS: { suffix: string; factor: number }[] = [
	{ suffix: 'B', factor: 1e9 },
	{ suffix: 'M', factor: 1e6 },
	{ suffix: 'K', factor: 1e3 },
	{ suffix: '', factor: 1 },
];

/**
 * A money expression ANYWHERE in a string: "$12K", "$1.03-$2.06M", the second
 * half of "…in Year 1; $0.000011-$0.000045M in Year 3".
 *
 * Scanning rather than anchoring matters: the backend writes several amounts into
 * one field, and an anchored match normalised the first and shipped the rest raw.
 *
 * A magnitude suffix must not be followed by a letter, so "$50 Million" keeps its
 * word. The upper end of a range must carry its own `$` unless the hyphen is tight
 * ("$5-10"), so "$19 - 3 seats" is one amount followed by prose, not a range.
 */
const MONEY_IN_TEXT =
	/\$\s*([\d,]+(?:\.\d+)?)(?:\s*([KMB])(?![A-Za-z]))?(?:(?:\s*(?:-|–|—|to)\s*\$\s*|-)([\d,]+(?:\.\d+)?)(?:\s*([KMB])(?![A-Za-z]))?)?/gi;

function moneyAmount(raw: string, suffix: string | undefined): number {
	const n = Number(raw.replace(/[$,\s]/g, ''));
	if (!Number.isFinite(n)) return Number.NaN;
	const unit = MONEY_UNITS.find((u) => u.suffix === (suffix ?? '').toUpperCase());
	return n * (unit?.factor ?? 1);
}

/** Value at the chosen unit, at most 2 decimals, trailing zeros dropped. */
function moneyDigits(value: number, factor: number): string {
	return String(Math.round((value / factor) * 100) / 100);
}

/**
 * Re-render every money expression in a string at a unit that suits its magnitude,
 * so the backend's "$0.000227-$0.000454M" reads as "$227-$454" instead of
 * contradicting the prose beside it. Both ends of a range share one unit, picked
 * from the larger end.
 *
 * Anything that isn't money — "N/A", "2-5 years" — is returned UNCHANGED, and so
 * is the text around an amount ("$29/mo" keeps its suffix). Nullish input returns
 * ''. Never invents a number and never rounds one away.
 */
export function formatMoneyRange(value: string | null | undefined): string {
	if (typeof value !== 'string') return '';
	return value.replace(
		MONEY_IN_TEXT,
		(match, lowRaw: string, lowSuffix: string | undefined, highRaw: string | undefined, highSuffix: string | undefined) => {
			// A range often writes its magnitude suffix once, on whichever end carries it:
			// "$1.03-$2.06M" means 1.03M to 2.06M. But a bare low bound can also be
			// genuinely smaller than a suffixed high one — "$400-$3K" is 400 to 3,000, and
			// blindly propagating the K rendered it as "$400K-$3K" (live report 8f35ea6b:
			// "First-year target $400K-$3K", inverted AND three orders of magnitude out).
			// The disambiguator is that propagation must not invert the range.
			const high = highRaw === undefined
				? moneyAmount(lowRaw, lowSuffix)
				: moneyAmount(highRaw, highSuffix || lowSuffix);
			let low = moneyAmount(lowRaw, lowSuffix || highSuffix);
			if (!lowSuffix && highSuffix && Number.isFinite(low) && Number.isFinite(high) && low > high) {
				low = moneyAmount(lowRaw, undefined);
			}
			if (!Number.isFinite(low) || !Number.isFinite(high)) return match;

			const magnitude = Math.max(Math.abs(low), Math.abs(high));
			const unit =
				MONEY_UNITS.find((u) => magnitude >= u.factor) ?? MONEY_UNITS[MONEY_UNITS.length - 1];
			return highRaw === undefined
				? `$${moneyDigits(low, unit.factor)}${unit.suffix}`
				: `$${moneyDigits(low, unit.factor)}${unit.suffix}-$${moneyDigits(high, unit.factor)}${unit.suffix}`;
		},
	);
}

/**
 * Money for display. Numbers get a `$` and thousands separators; strings are
 * backend-authored money values, normalised to a sensible unit by
 * `formatMoneyRange` (and passed through verbatim when they aren't money).
 */
export function formatCurrency(value: string | number | undefined | null): string {
	if (value === undefined || value === null) return 'N/A';
	if (typeof value === 'string') return formatMoneyRange(value) || value;
	return `$${value.toLocaleString()}`;
}

/** Preserve the source phrase's leading capitalisation on its replacement. */
function matchCase(source: string, replacement: string): string {
	return /^[A-Z]/.test(source)
		? replacement.charAt(0).toUpperCase() + replacement.slice(1)
		: replacement;
}

/** "0.43" -> "43/100"; empty when the value isn't a 0-1 score we can label. */
function labelledIntentScale(raw: string): string {
	const n = Number(raw);
	if (!Number.isFinite(n) || n < 0 || n > 1) return '';
	return `${Math.round(n * 100)}/100`;
}

/**
 * The WTP phrase can start with the always-uppercase acronym, so its casing can't be
 * copied from the match — capitalise from the surrounding sentence instead.
 */
function commercialIntentPhrase(
	match: string,
	avg: string | undefined,
	num: string,
	offset: number,
	source: string,
): string {
	const scale = labelledIntentScale(num);
	if (!scale) return match;
	const phrase = `${avg ? 'average ' : ''}commercial-intent score of ${scale}`;
	const before = source.slice(0, offset).trimEnd();
	const atSentenceStart = before === '' || /[.!?:]$/.test(before);
	return atSentenceStart ? phrase.charAt(0).toUpperCase() + phrase.slice(1) : phrase;
}

type JargonReplacer = (
	match: string,
	groups: (string | undefined)[],
	offset: number,
	source: string,
) => string;

type JargonRule = { pattern: RegExp; replacement: string | JargonReplacer };

/**
 * Ordered pattern -> replacement table for internal names the backend writes into
 * user-facing prose (risk factors, calibration notes, pricing rationales).
 * Conservative by construction: a rule that doesn't match changes nothing.
 */
const INTERNAL_JARGON_RULES: JargonRule[] = [
	// Raw field name from a calibration note: "(data_access_model: unverified)".
	{ pattern: /\bdata_access_model\b/g, replacement: 'data route' },

	// WTP was renamed Commercial Intent, and its bare 0-1 number needs a scale.
	// The score can lead the acronym with no "score" noun behind it — "the 0.43
	// average WTP" — which is how the pricing rationale and the commercial-intent
	// validation both write it.
	{
		pattern: /\b(\d?\.\d+)\s+(average\s+)?WTP(?:\s+scores?)?\b/gi,
		replacement: (match, [num, avg], offset, source) =>
			commercialIntentPhrase(match, avg, num ?? '', offset, source),
	},
	{
		// The parenthesised alternative is matched whole, so "(WTP score 0.35)" keeps
		// its wrapping parens while "WTP (0.35)" absorbs its own.
		pattern:
			/\b(average\s+)?WTP(?:\s+scores?)?\s*(?:of|averaging|:)?\s*(?:\((\d?\.\d+)\)|(\d?\.\d+))/gi,
		replacement: (match, [avg, parenNum, bareNum], offset, source) =>
			commercialIntentPhrase(match, avg, parenNum ?? bareNum ?? '', offset, source),
	},
	{ pattern: /\bWTP\b/g, replacement: 'commercial intent' },

	// Internal gate codenames from market_sizing.risk_factors. Numbers stay exact.
	{
		pattern: /\bthe\s+([\d,]+)-search\s+stop-condition\s+threshold\b/gi,
		replacement: (match, [count]) => matchCase(match, `our ${count}-search minimum-demand bar`),
	},
	{
		pattern: /\bthe\s+(\$[\d.,]+\s*[KMB]?)\s+Income\s+Potential\s+threshold\b/gi,
		replacement: (match, [amount]) =>
			matchCase(match, `the ${amount} scale bar we use for venture-scale opportunities`),
	},
	{
		pattern: /\bthe\s+([\d,]+)-search\s+STRIVE\s+threshold\b/gi,
		replacement: (match, [count]) => matchCase(match, `our ${count}-search high-growth bar`),
	},
	{ pattern: /\bSTRIVE\s+criteria\b/g, replacement: 'market-readiness criteria' },
	{ pattern: /\bSTRIVE\b/g, replacement: 'market-readiness' },

	// Gate codenames from market_sizing.viability_rationale. Same family as the
	// thresholds above, but written as criterion names rather than numbers.
	{ pattern: /\bthe\s+mandatory\s+stop\s+rule\b/gi, replacement: 'our mandatory minimum-demand rule' },
	{ pattern: /\bstop\s+condition\b/gi, replacement: 'blocker' },
	{ pattern: /\bIncome\s+Potential\s+criterion\b/g, replacement: 'venture-scale revenue bar' },
	{ pattern: /\bIncome\s+Potential\b/g, replacement: 'venture-scale revenue' },
	// The "E" of the STRIVE checklist, printed as a bare criterion name.
	{ pattern: /\bEnterable\b/g, replacement: 'market-entry feasibility' },

	// Aggregate keyword volume is category reach, not demand for this idea — the
	// label every other surface now uses for the same number.
	{ pattern: /\baggregate\s+demand\b/gi, replacement: 'category reach' },
];

/**
 * Rewrite internal field names, renamed metrics and gate codenames that leak from
 * backend prose into the report UI, and re-unit any money it quotes so a sentence
 * cannot contradict the tile above it. Text with no match is returned untouched.
 */
export function humanizeInternalJargon(text: string | null | undefined): string {
	if (!text) return '';
	let out = formatMoneyRange(text);
	for (const { pattern, replacement } of INTERNAL_JARGON_RULES) {
		if (typeof replacement === 'string') {
			out = out.replace(pattern, replacement);
			continue;
		}
		out = out.replace(pattern, (match: string, ...rest: unknown[]) =>
			replacement(
				match,
				rest.slice(0, -2) as (string | undefined)[],
				rest[rest.length - 2] as number,
				rest[rest.length - 1] as string,
			),
		);
	}
	return out;
}

/** Keys that hold machine values rather than prose — never rewritten. */
const NON_PROSE_KEY = /(^|_)(id|ids|url|urls|href|link|slug|domain|email|permalink)$/i;

function humanizeNode(value: unknown, key: string | undefined): unknown {
	if (typeof value === 'string') {
		if (key && NON_PROSE_KEY.test(key)) return value;
		return humanizeInternalJargon(value);
	}
	if (Array.isArray(value)) {
		let changed = false;
		const next = value.map((item) => {
			const out = humanizeNode(item, key);
			if (out !== item) changed = true;
			return out;
		});
		return changed ? next : value;
	}
	if (value && typeof value === 'object') {
		let changed = false;
		const next: Record<string, unknown> = {};
		for (const [childKey, childValue] of Object.entries(value)) {
			const out = humanizeNode(childValue, childKey);
			if (out !== childValue) changed = true;
			next[childKey] = out;
		}
		return changed ? next : value;
	}
	return value;
}

/**
 * Apply `humanizeInternalJargon` to every prose string in a report, once, at the
 * boundary where it enters the UI.
 *
 * The summary views humanised at each call site, so the `detail=full` appendix —
 * which renders the same report through the older section components with raw
 * fields — kept printing `WTP`, `data_access_model`, gate codenames and
 * micro-unit money. Normalising the whole object here means a section component
 * cannot forget, and a new one cannot regress.
 *
 * Returns the input untouched when nothing matched, so identity comparisons and
 * `$derived` memoisation downstream still hold.
 */
export function humanizeReportProse<T>(report: T): T {
	return humanizeNode(report, undefined) as T;
}

/**
 * Drop a markdown heading that only repeats the title of the section already
 * wrapping it — the backend writes "## CAC Breakdown" into a field the UI renders
 * under its own "CAC Breakdown" header, printing the name twice at two levels.
 */
export function stripLeadingHeading(content: string | null | undefined, title: string): string {
	if (!content) return '';
	const normalize = (s: string) => s.trim().toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
	return content.replace(/^\s*#{1,6}\s+(.+?)\s*(?:\n|$)/, (match, heading: string) =>
		normalize(heading) === normalize(title) ? '' : match,
	);
}

export function formatDate(dateStr: string | undefined | null): string {
	if (!dateStr) return 'N/A';
	try {
		const date = new Date(dateStr);
		return date.toLocaleDateString('en-US', {
			year: 'numeric',
			month: 'short',
			day: 'numeric',
			hour: '2-digit',
			minute: '2-digit'
		});
	} catch {
		return dateStr;
	}
}

export function parseCompetition(competition: string): number {
	// Parse competition strings like "MEDIUM (51)" -> 0.51
	if (!competition) return 0;
	const match = competition.match(/\((\d+)\)/);
	if (match) {
		return parseInt(match[1]) / 100;
	}
	// Handle text-only competition levels
	const levels: Record<string, number> = {
		'VERY_LOW': 0.1,
		'LOW': 0.25,
		'MEDIUM': 0.5,
		'HIGH': 0.75,
		'VERY_HIGH': 0.9
	};
	const level = competition.split(' ')[0].toUpperCase();
	return levels[level] || 0.5;
}

export function getTierLabel(tier: number): string {
	const labels: Record<number, string> = {
		0: 'Premium',
		1: 'Quick Win',
		2: 'High Value',
		3: 'Geographic',
		4: 'Category'
	};
	return labels[tier] || `Tier ${tier}`;
}

export function getTierClass(tier: number): string {
	return `tier-${tier}`;
}

export function getVerdictClass(verdict: string): string {
	const v = verdict?.toLowerCase();
	if (v === 'go') return 'verdict-go';
	if (v === 'no-go') return 'verdict-no-go';
	return 'badge-warning';
}

export function getRiskClass(risk: string): string {
	const r = risk?.toLowerCase();
	if (r === 'low') return 'badge-success';
	if (r === 'high') return 'badge-error';
	return 'badge-warning';
}

export function getScoreClass(score: number | null | undefined): string {
	if (score === null || score === undefined) return 'text-muted';
	if (score >= 0.7) return 'text-success';
	if (score >= 0.4) return 'text-warning';
	return 'text-error';
}

export function getScoreBarClass(score: number | null | undefined): string {
	if (score === null || score === undefined) return 'score-bar-fill-muted';
	if (score >= 0.7) return 'score-bar-fill-success';
	if (score >= 0.4) return 'score-bar-fill-accent';
	return 'score-bar-fill-error';
}

export function truncateText(text: string, maxLength: number): string {
	if (!text) return '';
	if (text.length <= maxLength) return text;
	return text.slice(0, maxLength).trim() + '...';
}

export function slugify(text: string): string {
	return text
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, '-')
		.replace(/(^-|-$)/g, '');
}

export function capitalizeFirst(text: string): string {
	if (!text) return '';
	return text.charAt(0).toUpperCase() + text.slice(1);
}

/**
 * Repair the historical Stage 14 prompt bug that printed a normalized 0-1 SEO score as /10.
 * Only rewrite a numerator that exactly matches the retained normalized score, so an intentional
 * low x/10 assessment is left untouched.
 */
export function normalizeSeoScalabilityNarrative(
	text: string,
	normalizedScore?: number | null,
): string {
	if (
		!text ||
		typeof normalizedScore !== 'number' ||
		!Number.isFinite(normalizedScore) ||
		normalizedScore < 0 ||
		normalizedScore > 1
	) {
		return text;
	}

	return text.replace(
		/(\bseo scalability(?: assessment)?(?:\s+(?:score\s+)?is|\s*:)\s*)(\d+(?:\.\d+)?)\/10\b/gi,
		(match, prefix: string, rawNumerator: string) => {
			const numerator = Number(rawNumerator);
			if (!Number.isFinite(numerator) || Math.abs(numerator - normalizedScore) > 0.0001) {
				return match;
			}
			const scaled = normalizedScore * 10;
			return `${prefix}${Number.isInteger(scaled) ? scaled : scaled.toFixed(1)}/10`;
		},
	);
}

export function getPriorityClass(priority: string): string {
	const p = priority?.toLowerCase();
	if (p === 'high') return 'badge-success';
	if (p === 'medium') return 'badge-warning';
	return 'badge-muted';
}

export function getOpportunityClass(level: string): string {
	const l = level?.toLowerCase();
	if (l === 'high') return 'badge-success';
	if (l === 'medium') return 'badge-warning';
	return 'badge-muted';
}

export interface RationaleMetric {
	label: string;
	value: string;
	type: 'score' | 'number' | 'range' | 'text';
}

export interface ParsedRationale {
	metrics: RationaleMetric[];
	narrative: string;
	highlightedText: string;
}

export function parseRationaleMetrics(text: string): ParsedRationale {
	if (!text) return { metrics: [], narrative: '', highlightedText: '' };

	const patterns: Array<{ regex: RegExp; label: string; type: RationaleMetric['type'] }> = [
		{ regex: /market_fit_score\s*(?:of\s*)?([\d.]+)/i, label: 'Market Fit', type: 'score' },
		// Handles: seo_scalability_score is moderate (0.56), seo scores 0.84
		{ regex: /seo_scalability_score\s*(?:is\s+\w+\s*)?(?:of\s*)?\(?([\d.]+)\)?/i, label: 'SEO Scale', type: 'score' },
		// Handles: technical_feasibility_score 0.78, technical_feasibility_score: 0.78
		{ regex: /technical_feasibility_score\s*[=:\s]*\(?([\d.]+)\)?/i, label: 'Tech Feasibility', type: 'score' },
		// Handles: competitive_advantage_score 0.72, (0.72)
		{ regex: /competitive_advantage_score\s*(?:of\s*)?[=:\s]*\(?([\d.]+)\)?/i, label: 'Competitive Adv.', type: 'score' },
		{ regex: /estimated_indexable_pages\s*[=:]\s*([\d,]+)/i, label: 'SEO Pages', type: 'number' },
		{ regex: /estimated_cac_organic\s*(?:of\s*)?\$?([\d\-$\/\w]+)/i, label: 'Organic CAC', type: 'range' },
		{ regex: /estimated_development_time\s*([\d\-]+\s*weeks?)/i, label: 'Dev Time', type: 'range' },
		{ regex: /composite\s*score\s*\(?([\d.]+)\)?/i, label: 'Composite', type: 'score' },
		{ regex: /reward\s*score[:\s]*([\d.]+\/10)/i, label: 'Reward', type: 'text' },
		// Handles: solo_dev_feas 0.74, solo_dev_feasibility 0.74
		{ regex: /solo_dev_feas(?:ibility)?\s*[=:\s]*\(?([\d.]+)\)?/i, label: 'Solo Dev', type: 'score' },
	];

	const metrics: RationaleMetric[] = [];

	for (const { regex, label, type } of patterns) {
		const match = text.match(regex);
		if (match && match[1]) {
			let value = match[1].trim();

			// Format scores as percentages (0.65 -> 65%)
			if (type === 'score') {
				const num = parseFloat(value);
				if (!isNaN(num) && num <= 1) {
					value = `${Math.round(num * 100)}%`;
				}
			}

			// Format numbers with commas
			if (type === 'number') {
				value = value.replace(/,/g, '');
				const num = parseInt(value);
				if (!isNaN(num)) {
					value = num.toLocaleString();
				}
			}

			// Add $ prefix for CAC if not present
			if (label === 'Organic CAC' && !value.startsWith('$')) {
				value = `$${value}`;
			}

			metrics.push({ label, value, type });
		}
	}

	// Clean narrative: remove the technical metric mentions for cleaner reading
	let narrative = text;

	// Remove inline metric patterns that clutter the narrative
	const cleanPatterns = [
		/\s*\(?\s*market_fit_score\s*(?:of\s*)?[\d.]+\s*\)?\s*/gi,
		/\s*\(?\s*seo_scalability_score\s*(?:of\s*)?[\d.]+\s*\)?\s*/gi,
		/\s*\(?\s*technical_feasibility_score\s*[=:]\s*[\d.]+\s*,?\s*/gi,
		/\s*\(?\s*competitive_advantage_score\s*(?:of\s*)?[\d.]+\s*\)?\s*/gi,
		/\s*\(?\s*estimated_indexable_pages\s*[=:]\s*[\d,]+\s*,?\s*/gi,
		/\s*\(?\s*estimated_cac_organic\s*(?:of\s*)?\$?[\d\-$\/\w]+\s*\)?\s*/gi,
		/\s*\(?\s*estimated_development_time\s*[\d\-]+\s*weeks?\s*\)?\s*,?\s*/gi,
		/\s*\(?\s*composite\s*score\s*\(?[\d.]+\)?\s*\)?\s*/gi,
		/\s*\(?\s*solo_dev_feasibility\s*[=:]\s*[\d.]+\s*\)?\s*/gi,
	];

	for (const pattern of cleanPatterns) {
		narrative = narrative.replace(pattern, ' ');
	}

	// Clean up double spaces and orphaned punctuation
	narrative = narrative
		.replace(/\s+/g, ' ')
		.replace(/\s+,/g, ',')
		.replace(/,\s*,/g, ',')
		.replace(/\(\s*\)/g, '')
		.replace(/\s+\./g, '.')
		.trim();

	// Create highlighted version: wrap metric values in styled spans
	let highlightedText = text;

	// Patterns to highlight with their formatted replacements
	// Each formatter receives: full match, prefix capture group, value capture group
	const highlightPatterns: Array<{ regex: RegExp; formatter: (match: string, prefix: string, val: string) => string }> = [
		{
			regex: /(market_fit_score\s*(?:of\s*)?)([\d.]+)/gi,
			formatter: (_match: string, prefix: string, val: string) => {
				const num = parseFloat(val);
				const formatted = !isNaN(num) && num <= 1 ? `${Math.round(num * 100)}%` : val;
				return `<span class="inline-metric-label">${prefix}</span><span class="inline-metric">${formatted}</span>`;
			}
		},
		{
			// Handles: seo_scalability_score 0.56, seo_scalability_score is moderate (0.56), seo scores 0.84
			regex: /(seo_scalability_score\s*(?:is\s+\w+\s*)?(?:of\s*)?\(?|seo\s+scores?\s*)([\d.]+)\)?/gi,
			formatter: (_match: string, prefix: string, val: string) => {
				const num = parseFloat(val);
				const formatted = !isNaN(num) && num <= 1 ? `${Math.round(num * 100)}%` : val;
				return `<span class="inline-metric-label">${prefix}</span><span class="inline-metric">${formatted}</span>`;
			}
		},
		{
			// Handles: technical_feasibility_score 0.78, technical_feasibility_score: 0.78, (0.78)
			regex: /(technical_feasibility_score\s*[=:\s]*\(?)([\d.]+)\)?/gi,
			formatter: (_match: string, prefix: string, val: string) => {
				const num = parseFloat(val);
				const formatted = !isNaN(num) && num <= 1 ? `${Math.round(num * 100)}%` : val;
				return `<span class="inline-metric-label">${prefix}</span><span class="inline-metric">${formatted}</span>`;
			}
		},
		{
			// Handles: competitive_advantage_score 0.72, competitive_advantage_score of 0.72
			regex: /(competitive_advantage_score\s*(?:of\s*)?[=:\s]*\(?)([\d.]+)\)?/gi,
			formatter: (_match: string, prefix: string, val: string) => {
				const num = parseFloat(val);
				const formatted = !isNaN(num) && num <= 1 ? `${Math.round(num * 100)}%` : val;
				return `<span class="inline-metric-label">${prefix}</span><span class="inline-metric">${formatted}</span>`;
			}
		},
		{
			regex: /(estimated_indexable_pages\s*[=:]\s*)([\d,]+)/gi,
			formatter: (_match: string, prefix: string, val: string) => {
				const num = parseInt(val.replace(/,/g, ''));
				const formatted = !isNaN(num) ? num.toLocaleString() : val;
				return `<span class="inline-metric-label">${prefix}</span><span class="inline-metric">${formatted}</span>`;
			}
		},
		{
			regex: /(estimated_cac_organic\s*(?:of\s*)?)(\$?[\d\-$\/\w]+)/gi,
			formatter: (_match: string, prefix: string, val: string) => {
				const formatted = val.startsWith('$') ? val : `$${val}`;
				return `<span class="inline-metric-label">${prefix}</span><span class="inline-metric">${formatted}</span>`;
			}
		},
		{
			regex: /(estimated_development_time\s*)([\d\-]+\s*weeks?)/gi,
			formatter: (_match: string, prefix: string, val: string) => `<span class="inline-metric-label">${prefix}</span><span class="inline-metric">${val}</span>`
		},
		{
			regex: /(composite\s*score\s*)\(?([\d.]+)\)?/gi,
			formatter: (_match: string, prefix: string, val: string) => {
				const num = parseFloat(val);
				const formatted = !isNaN(num) && num <= 1 ? `${Math.round(num * 100)}%` : val;
				return `<span class="inline-metric-label">${prefix}</span><span class="inline-metric">${formatted}</span>`;
			}
		},
		{
			regex: /(reward\s*score[:\s]*)([\d.]+\/10)/gi,
			formatter: (_match: string, prefix: string, val: string) => `<span class="inline-metric-label">${prefix}</span><span class="inline-metric">${val}</span>`
		},
		{
			// Handles: solo_dev_feas 0.74, solo_dev_feasibility 0.74, solo_dev_feas: 0.74
			regex: /(solo_dev_feas(?:ibility)?\s*[=:\s]*\(?)([\d.]+)\)?/gi,
			formatter: (_match: string, prefix: string, val: string) => {
				const num = parseFloat(val);
				const formatted = !isNaN(num) && num <= 1 ? `${Math.round(num * 100)}%` : val;
				return `<span class="inline-metric-label">${prefix}</span><span class="inline-metric">${formatted}</span>`;
			}
		},
	];

	for (const { regex, formatter } of highlightPatterns) {
		highlightedText = highlightedText.replace(regex, formatter);
	}

	return { metrics, narrative, highlightedText };
}
