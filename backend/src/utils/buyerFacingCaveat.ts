/**
 * `data_quality_summary.quality_caveats` and `niche_difficulty_verdict`, read to the buyer —
 * on the BACKEND.
 *
 * THIS IS A PORT, NOT A SECOND OPINION. Every rule below is copied verbatim from the
 * frontend authority, which stays the authority:
 *
 *   frontend/src/lib/utils/format.ts                    `humanizeInternalJargon` and its table
 *   frontend/src/lib/selection/buyerFacingResearchProse.ts  `buyerFacingCoverageNote`,
 *       `buyerFacingResearchProse`, `buyerFacingVerdictHeadline` and their chain
 *
 * TWO ENTRY POINTS, ONE `SourceInput[]`. `selectionChallengeEvidence.caveatSources` builds one
 * evidence list out of `quality_caveats` AND `niche_difficulty_verdict`. Both take the DATASET
 * reading of "corpus", and they are still two entry points because the coverage note owns a
 * calibration/coverage stanza the verdict must not be run through.
 *
 * WHAT WAS MEASURED, after a round that shipped the fork the wrong way round. Run over the 28
 * distinct `niche_difficulty_verdict.narrative_summary` values under `output/`, the two entry
 * points differ on 2 — "requiring a new corpus" and "require a corpus that does not yet
 * exist" — and on BOTH the coverage-note reading ("a new dataset", "a dataset that does not
 * yet exist") is the correct one: all 21 corpus-bearing narratives mean the dataset a product
 * would have to build. The earlier "wrong noun on 19 of the 28" claim in this comment was
 * false in both its number and its direction. The EVIDENCE reading is right for
 * `key_challenges` ("The corpus drifts from the stated audience"), which this module ports but
 * `caveatSources` never reads. `RESEARCH_CORPUS_GLOSS` vs `IDEA_CORPUS_GLOSS` below is where
 * that fork lives, and it is the frontend's fork, not a backend invention.
 *
 * WHY A PORT AND NOT A SHARED MODULE. The frontend authority is reachable only through
 * SvelteKit's `$lib` alias and pulls `marked` + `isomorphic-dompurify` in at module scope
 * (`format.ts` renders markdown in the same file). The API compiles with `tsc`
 * `moduleResolution: NodeNext` and ships from `backend/dist` in a container that has neither
 * the alias, the frontend sources, nor those packages. Extracting the rules into a package both
 * sides import would mean editing the two frontend files, which are closed. So the rules are
 * copied, and the copy is held to the original BY TEST rather than by discipline.
 *
 * HOW THE TWO COPIES ARE STOPPED FROM DRIFTING. `__tests__/buyerFacingCaveat.drift.test.ts`
 * runs in the backend suite and does two things at RUNTIME, against the frontend's own source:
 *
 *   1. It IMPORTS `$lib/selection/buyerFacingResearchProse` (vitest resolves the alias; the
 *      npm deps resolve out of `frontend/node_modules`) and asserts this module's output is
 *      byte-identical to the frontend's over all 165 distinct `quality_caveats` /
 *      `user_adjustments` values under `output/`, plus an edge-case battery.
 *   2. It READS both source files as text and compares this file's copy of each rule
 *      table/function against the same-named region of the original, comments and whitespace
 *      stripped — so a frontend rule that no corpus value exercises still fails the build here.
 *
 * Keep the names and the bodies below identical to the originals; the second check is what
 * makes that requirement enforceable rather than aspirational.
 *
 * WHAT DELIBERATELY DID NOT PORT. `format.ts`'s `NON_PROSE_KEY` / `humanizeNode` /
 * `humanizeReportProse` guard a FIELD-BLIND deep walk over a whole report object, holding
 * scraped user text (`quote`, `body`, `selftext`, `excerpt`, …) out of the rules' reach. There
 * is no deep walk here: every backend caller hands this module ONE string from ONE named field,
 * so there is no key to gate on and nothing for the guard to protect. A user's own words inside
 * an interpolated repr still stay verbatim, because the repr rules rename the FIELD NAME in
 * front of the `=` and never touch the quoted value behind it. If a caller ever starts walking
 * an object here, that guard has to be ported with it.
 */

// ─────────────────────────────────────────────────────────────────────────────
// Ported verbatim from frontend/src/lib/utils/format.ts
// ─────────────────────────────────────────────────────────────────────────────

/** Magnitude suffixes used by the report's money strings, largest first. */
const MONEY_UNITS: { suffix: string; factor: number }[] = [
	{ suffix: 'B', factor: 1e9 },
	{ suffix: 'M', factor: 1e6 },
	{ suffix: 'K', factor: 1e3 },
	{ suffix: '', factor: 1 },
];

/**
 * A money expression ANYWHERE in a string. A magnitude suffix must not be followed by a
 * letter, and the upper end of a range must carry its own `$` unless the hyphen is tight.
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
 * Re-render every money expression in a string at a unit that suits its magnitude. Anything
 * that isn't money is returned UNCHANGED. Never invents a number and never rounds one away.
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
 * The PainPoint repr field names, read to the buyer. `willingness_to_pay_score` takes the
 * Commercial Intent name the `WTP` rules below already use, so one caveat cannot print the
 * metric under two names.
 */
const REPR_FIELD_LABELS: Record<string, string> = {
	title: 'problem title',
	severity_score: 'severity score',
	willingness_to_pay_score: 'commercial-intent score',
	representative_quote: 'representative quote',
	source_platform: 'source platform',
};

/**
 * The FIFTH repr key, and the only one with no underscore. IT CANNOT SHARE THE `=` GATE,
 * BECAUSE A BARE `title` IS NOT OURS — an SEO recommendation's `<a title="…">` and an Open
 * Graph `og:title = "…"` both satisfy that lookahead exactly. Gated on the repr CONTEXT
 * instead: a quoted value followed by one of the sibling keys. It must run BEFORE the shared
 * repr rule, which renames the sibling this lookahead reads — which is also what makes it
 * idempotent.
 */
const PAIN_REPR_TITLE =
	/\btitle(?==(?:'[^']*'|"[^"]*")\s+(?:severity_score|willingness_to_pay_score|representative_quote|source_platform)=)/g;

/**
 * Ordered pattern -> replacement table for internal names the backend writes into
 * user-facing prose. Conservative by construction: a rule that doesn't match changes nothing.
 *
 * THE `=` LOOKAHEAD ON THE REPR NAMES IS LOAD-BEARING. `severity_score` is not only ours: one
 * `technical_approach` value names it as a COLUMN of a JSON schema the PRODUCT itself would
 * define, beside `pay_signal` and `source_url` that this table does not own. A bare word rule
 * would leave that list half-translated.
 *
 * The pipeline's research vocabulary ("corpus", "cold-start", "wedge", "web-verified") is
 * deliberately NOT here — it is ambiguous, and this function has no idea which field it is in.
 * Those rules live below, applied per surface.
 */
const INTERNAL_JARGON_RULES: JargonRule[] = [
	// Raw field name from a calibration note: "(data_access_model: unverified)".
	{ pattern: /\bdata_access_model\b/g, replacement: 'data route' },

	// More raw field names, all of them from `data_quality_summary.quality_caveats`.
	{ pattern: /\bpain_points_addressed\b/g, replacement: 'addressed problems' },
	{ pattern: /\bseo_analytics\b/g, replacement: 'SEO analytics' },

	// THE REPR DUMP. The coverage checker interpolates a whole PainPoint repr into its caveat.
	{ pattern: PAIN_REPR_TITLE, replacement: REPR_FIELD_LABELS.title },
	{
		pattern: /\b(?:severity_score|willingness_to_pay_score|representative_quote|source_platform)(?=\s*=)/g,
		replacement: (match) => REPR_FIELD_LABELS[match] ?? match,
	},

	// WTP was renamed Commercial Intent, and its bare 0-1 number needs a scale.
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

	// Gate codenames from market_sizing.viability_rationale.
	{ pattern: /\bthe\s+mandatory\s+stop\s+rule\b/gi, replacement: 'our mandatory minimum-demand rule' },
	{ pattern: /\bstop\s+condition\b/gi, replacement: 'blocker' },
	{ pattern: /\bIncome\s+Potential\s+criterion\b/g, replacement: 'venture-scale revenue bar' },
	{ pattern: /\bIncome\s+Potential\b/g, replacement: 'venture-scale revenue' },
	// The "E" of the STRIVE checklist, printed as a bare criterion name.
	{ pattern: /\bEnterable\b/g, replacement: 'market-entry feasibility' },

	// Aggregate keyword volume is category reach, not demand for this idea.
	{ pattern: /\baggregate\s+demand\b/gi, replacement: 'category reach' },
];

/**
 * Rewrite internal field names, renamed metrics and gate codenames that leak from backend
 * prose, and re-unit any money it quotes. Text with no match is returned untouched.
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

// ─────────────────────────────────────────────────────────────────────────────
// Ported verbatim from frontend/src/lib/selection/buyerFacingResearchProse.ts
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Every separator the producer can leave at a clause boundary inside one of its
 * deterministic constants: the authored em dash, the colon and hyphen
 * `_without_long_dashes` turns it into, the en dash, and doubled runs of any of them.
 */
const SEP = String.raw`\s*[—–:-]+\s*`;

/** Builds a whole-sentence rule whose `%` markers stand for a producer separator. */
function sentenceRule(pattern: string, replacement: string): [RegExp, string] {
  return [new RegExp(pattern.split("%").join(SEP), "gi"), replacement];
}

// ── Whole-sentence rewrites. These run before the word-level rules, because a word-level
//    substitution inside one of them would stop it matching. They also run before the
//    product-name mask, because "Deep Research" is a title-cased name and masking it first
//    would stop the "Thin early signal" rule from matching the sentence that contains it.
const SENTENCE_RULES: [RegExp, string][] = [
  sentenceRule(
    String.raw`Most ideas need a data corpus that doesn['’]t exist yet%plan a cold[- ]start play \(seed it, scrape it, or partner\) before the product is useful\.`,
    "Most ideas need a body of data that does not exist yet. Plan how to collect, create, "
      + "or obtain access to it before the product is useful.",
  ),
  sentenceRule(
    String.raw`Usable data is reachable without a heavy cold[- ]start lift\.`,
    "Usable data is reachable without a heavy up-front data-collection lift.",
  ),
  // The dash normalisation below turns "X — y" into "X. Y", which is right whenever the
  // clause after the separator can stand alone. These four pipeline constants continue the
  // preceding clause instead, so a period would leave a sentence fragment.
  sentenceRule(
    String.raw`Most products in this niche would be used episodically%opened around an event, idle between events\.`,
    "Most products in this niche would be used episodically, opened around an event, idle "
      + "between events.",
  ),
  sentenceRule(
    String.raw`Buyers here are small-business operators%price-aware but used to paying`,
    "Buyers here are small-business operators. They are price-aware but used to paying",
  ),
  sentenceRule(
    String.raw`Buyers here are indie/hobbyist builders spending personal money episodically%historically a low-price-ceiling segment`,
    "Buyers here are indie/hobbyist builders spending personal money episodically, "
      + "historically a low-price-ceiling segment",
  ),
  sentenceRule(
    String.raw`Buyers here are consumers%low price points and high support load,`,
    "Buyers here are consumers, with low price points and high support load,",
  ),
  [
    /Thin early signal; Deep Research validates\./gi,
    "Early evidence is limited. Deep Research can validate it.",
  ],
  // A LABEL AND A LIST, NOT TWO CLAUSES. `idea_theses.py:282` writes a run of source names
  // after the dash, so no grammar rule can repair it — naming what the list IS can. This must
  // precede the word rules, which would otherwise rewrite the "Cold start" label.
  sentenceRule(
    String.raw`Cold start: the product has no data until a customer supplies it%`,
    "The product has no data until a customer supplies it. It would run on: ",
  ),
  // ONE SURFACE OVER, THE SAME LABEL-AND-LIST SHAPE: `Already well-served — <partial|shipped>
  // by <incumbent>: <evidence>` is a label, not two clauses. `idea_validation_block.py`'s
  // `_display_embedded` rewrites this dash to a colon itself, but only on `demotion_reason`.
  // (Cited by symbol: the line number this carried had gone stale and pointed elsewhere.)
  sentenceRule(
    String.raw`^Already well-served%(partial|shipped) by `,
    "Already well-served: $1 by ",
  ),
];

/**
 * Word-level vocabulary. Longest phrase first, so the generic fallback never mangles a
 * phrase that has its own reading. ARTICLES: every rule whose replacement can follow an
 * indefinite article carries the article-adjacent form too, listed FIRST so it wins.
 * STACKING: every compound that can be built out of two vocabulary terms has its own entry,
 * ahead of both parents.
 *
 * SENSE: this table runs ABOVE the per-field fork, so a rule here may only re-use a sense
 * noun the PRODUCER already wrote inside the phrase it matches ("data corpus" -> "body of
 * data"). A replacement that INTRODUCES "evidence" or "dataset" is a guess about a fork that
 * has not happened yet and belongs in one of the two glosses below — that is how
 * `enumerable corpus` -> "searchable evidence library" reached the buyer on `angle_rationale`
 * when all 110 instances under `output/` mean the enumerable SET OF ENTITIES behind
 * programmatic SEO pages. See the frontend authority for the per-field counts.
 */
const CORPUS_COMPOUND_RULES: [RegExp, string][] = [
  [/\bcorpus evidence gap\b/gi, "gap in the collected evidence"],
  // ── cold-start compounds. These MUST precede both `data corpus` and the bare cold-start
  //    rules; measured on the run corpus, "cold-start data corpus" and "cold-start data"
  //    are the two forms the pipeline actually writes.
  [/\b(a)(\s+)cold[-\s]start data corpus\b/gi, "$1n$2up-front body of data"],
  [/\bcold[-\s]start data corpus\b/gi, "up-front body of data"],
  [/\b(a)(\s+)cold[-\s]start data\b/gi, "$1n$2up-front data"],
  [/\bcold[-\s]start data\b/gi, "up-front data"],
  // THE PLURAL LEMMA IS UNREACHABLE FROM THE SINGULAR RULE: "corpus" is not a prefix of
  // "corpora", so `\bcorpus\b` can never see it. It shipped verbatim in 2 of the 28 distinct
  // verdict narratives under `output/`. Both are the plural of the compound below.
  [/\bdata corpora\b/gi, "bodies of data"],
  [/\bdata corpus\b/gi, "body of data"],
];

/**
 * THE BARE NOUN MEANS DIFFERENT THINGS IN DIFFERENT PLACES, so it has two glosses, and BOTH
 * are reached from here. INSIDE THE VERDICT THE FORK IS PER FIELD, NOT PER SURFACE. Counted
 * over every distinct value of each `niche_difficulty_verdict` field under `output/`:
 *
 *   `narrative_summary` — 21 of 28 distinct values say "corpus"/"corpora", and all 21 mean
 *   THE DATASET A PRODUCT WOULD HAVE TO BUILD ("require data corpora that do not currently
 *   exist", "seed the necessary data corpus"). `headline` says neither word in any of its 28.
 *
 *   `key_challenges` — 3 of 25, and the only one reaching the bare noun is "The corpus
 *   drifts from the stated audience", which is THE RESEARCH EVIDENCE. `key_strengths` (4)
 *   and `buyer_class_note` (5) say neither word and stay with it.
 *
 * `caveatSources` in services/selectionChallengeEvidence.ts reads only the first two, so on
 * the backend the verdict takes `buyerFacingVerdictNarrative`; the caveat path keeps
 * `buyerFacingCoverageNote`. The evidence gloss is still ported because it is one of the
 * declarations the drift gate holds, and because the two entry points must stay distinct.
 */
const RESEARCH_CORPUS_GLOSS: [RegExp, string][] = [
  // ── Compounds that carry a SENSE live below the fork, not above it. `cold-start corpus`
  //    needs one on BOTH branches: the `cold[-\s]start` tail rule runs after this gloss and
  //    would otherwise stack into "a up-front data body of evidence".
  [/\b(a)(\s+)cold[-\s]start corpus\b/gi, "$1n$2up-front body of evidence"],
  [/\bcold[-\s]start corpus\b/gi, "up-front body of evidence"],
  // "Strong corpus purchase-intent signal" is about intent found IN the collected discussions.
  // `niche_difficulty.py:1013,1016` authors it; `output/` holds none because its only caller
  // is guarded by `commercial_intent_max < 0.6` while both returns need `>= 0.6`. It is gated
  // on THIS branch because `_wtp_judgment`'s output reaches the buyer as `key_challenges`.
  [
    /\bcorpus purchase([- ])intent(\s+signal)?\b/gi,
    "purchase$1intent$2 in the captured discussions",
  ],
  // THE ARTICLE RULE MUST SURVIVE AN INTERVENING MODIFIER RUN. "collected evidence" is a MASS
  // noun and cannot head an indefinite noun phrase, so the count head exists — but keyed on
  // an ADJACENT article it missed "a new corpus" and shipped "a new collected evidence". The
  // article is re-emitted UNCHANGED: it agrees with the modifier, which is not rewritten. The
  // run is bounded and excludes the function words that end the article's own noun phrase.
  [
    /\b(a|an)(\s+(?:(?!(?:the|an?|of|in|on|to|that|which|and|or|for|with|from|by|is|are|was|were|as)\b)[A-Za-z][\w'’-]*,?\s+){1,3})corpus\b/gi,
    "$1$2body of evidence",
  ],
  // ADJACENT, so the article agrees with the REPLACEMENT and narrows to the consonant form.
  [/\b(?:a|an)(\s+)corpus\b/gi, "a$1body of evidence"],
  [/\bcorpora\b/gi, "bodies of evidence"],
  [/\bcorpus\b/gi, "collected evidence"],
];
const IDEA_CORPUS_GLOSS: [RegExp, string][] = [
  // The dataset twin of the compound above. `enumerable corpus` and `initial corpus` get NO
  // entry here: the bare rules below already produce "enumerable dataset" / "initial dataset".
  [/\b(a)(\s+)cold[-\s]start corpus\b/gi, "$1n$2up-front dataset"],
  [/\bcold[-\s]start corpus\b/gi, "up-front dataset"],
  // "a dataset" needs no article repair, so one rule covers both positions.
  [/\bcorpora\b/gi, "datasets"],
  [/\bcorpus\b/gi, "dataset"],
];

const VOCABULARY_TAIL_RULES: [RegExp, string][] = [
  [/\bweb-verified prices\b/gi, "published prices checked on the web"],
  // ATTRIBUTIVE vs POSTPOSITIVE. Before a noun the modifier slot cannot hold "checked on the
  // web" without recasting the phrase, so the attributive form drops to a bare "verified".
  [/\bweb-verified(?=\s+[a-z])/gi, "verified"],
  [/\bweb-verified\b/gi, "checked on the web"],
  [/\bpaid wedge\b/gi, "paid offer"],
  // Bare "wedge" is strategy jargon on its own. Must stay AFTER the "paid wedge" rule.
  [/\b(a)(\s+)wedge\b/gi, "$1n$2entry point"],
  [/\bwedge\b/gi, "entry point"],
  // On the idea path `humanizeInternalJargon` has already turned the acronym into
  // "commercial intent" and this never fires; the verdict path reaches the vocabulary
  // without that pass, so the rule has to be here too.
  [/\bWTP\b/g, "willingness to pay"],
  // Backstop for the cold-start uses the sentence rules above don't cover. All four are
  // case-INSENSITIVE; `maskProductNames` — not letter case — is what protects "Cold-Start
  // Atlas".
  [/\b(a)(\s+)cold[-\s]start(?=\s+[a-z])/gi, "$1n$2up-front data"],
  [/\b(a)(\s+)cold[-\s]start\b/gi, "$1n$2up-front data-collection effort"],
  [/\bcold[-\s]start\b/gi, "up-front data"],
];

/**
 * `extras` are surface-specific rules that need the same mask and must not be pre-empted by
 * a parent here, so they lead. The corpus gloss sits between the compounds that own a
 * two-word reading and the rules that have nothing to do with it.
 */
function vocabularyRules(
  corpusGloss: [RegExp, string][],
  extras: [RegExp, string][] = [],
): [RegExp, string][] {
  return [...extras, ...CORPUS_COMPOUND_RULES, ...corpusGloss, ...VOCABULARY_TAIL_RULES];
}

const RESEARCH_RULES = vocabularyRules(RESEARCH_CORPUS_GLOSS);

/**
 * The verdict's `narrative_summary` / `headline` reading. Identical to `RESEARCH_RULES` in
 * every rule except the corpus gloss — see the gloss note above for the per-field counts.
 */
const VERDICT_NARRATIVE_RULES = vocabularyRules(IDEA_CORPUS_GLOSS);

/**
 * Sentence rewrites, then the word rules with every proper name masked out of their reach,
 * then the clause-dash break — which runs while the names are still masked, because it must
 * not split "RageQuit Radar — Stack Exchange Rescue Queue" in half.
 */
function sanitize(value: string, rules: [RegExp, string][]): string {
  let out = value;
  for (const [pattern, replacement] of SENTENCE_RULES) out = out.replace(pattern, replacement);
  const { text, names } = maskProductNames(out);
  out = normalizeClauseDashes(applyWordRules(text, rules));
  return restoreProductNames(out, names);
}

export function buyerFacingResearchProse(value: string): string {
  return sanitize(value, RESEARCH_RULES);
}

/**
 * The verdict's narrative and headline tail. NOT `buyerFacingIdeaProse`: that entry point
 * also runs `humanizeInternalJargon`, the `DATA_ROUTE_UNVERIFIED` stanza and
 * `IDEA_WORD_RULES`, none of which the verdict fields carry.
 */
export function buyerFacingVerdictNarrative(value: string): string {
  return sanitize(value, VERDICT_NARRATIVE_RULES);
}

// ─────────────────────────────────────────────────────────────────────────────
// Idea-card prose
// ─────────────────────────────────────────────────────────────────────────────

/**
 * The producer's canonical "we could not confirm the data route" stanza. It is a paragraph
 * rather than a sentence, and the buyer only needs the instruction inside it.
 */
const DATA_ROUTE_UNVERIFIED = /^Data route UNVERIFIED\s*[—–-]/i;

/**
 * Vocabulary specific to the idea cards: internal field names (`build_feas`), pipeline
 * scoring labels ("mechanism parity") and two whole-sentence verdicts the ranker writes.
 */
const IDEA_WORD_RULES: [RegExp, string][] = [
  [/\bdata representation\b/gi, "content structure"],
  // "an SEO surface" is correct ("ess-ee-oh"), "an search opportunity" is not.
  [/\b(an)(\s+)SEO surface\b/gi, "a$2search opportunity"],
  [/\bSEO surface\b/gi, "search opportunity"],
  [/\bmechanism parity\b/gi, "feature overlap"],
  [/\bdata_access\b/gi, "data access"],
  [/\bbuild_feas of (limited|good|strong)\b/gi, "$1 build feasibility"],
  [/\bbuild_feas (limited|good|strong)\b/gi, "$1 build feasibility"],
  [/\bdata_feas (limited|good|strong)\b/gi, "$1 data feasibility"],
  [/\bbuild_feas\b/gi, "build feasibility"],
  [/\bdata_feas\b/gi, "data feasibility"],
  [
    /Distribution\s*\/\s*SEO is the least-wrong angle/gi,
    "Distribution and SEO are the clearest available angle",
  ],
  // THE POSITION GUARD IS LOAD-BEARING: 18 corpus occurrences sit MID-CLAUSE, where an
  // unguarded rule substitutes a finite clause into an object slot. The separator is kept in
  // `$1` so the clause-dash pass still sees it.
  [
    /(^|[—–:;.]\s*)vertical[_ ]workflow by elimination/gi,
    "$1The strongest available angle is a focused workflow",
  ],
  [
    /(^|[—–:;.]\s*)(?:novel[_ -]differentiation|a distinct mechanism) by elimination/gi,
    "$1The strongest available angle is a distinct mechanism",
  ],
  // The raw internal key in running prose. These three run LAST so the boundary rules above
  // still see the key they are written against.
  [/\bdistribution[_ ]seo\b/gi, "distribution / SEO"],
  [/\bnovel[_ -]differentiation\b/gi, "distinct mechanism"],
  [/\bvertical[_ ]workflow\b/gi, "focused workflow"],
  // `unified_solution_crew.py:4439` appends this verbatim and then truncates the field to
  // 120 characters, so the suffix arrives cut off at six different points — BOTH words have
  // to be matched to any prefix.
  [
    /([^\s.;])[.;]?\s*[—–]\s*no bulk route confirmed;\s*per-ID\/unv[a-z]*(?:\s+acc?e?s?s?|\s+a)?/gi,
    "$1, with no bulk download route confirmed and per-record access that is unverified.",
  ],
];

const IDEA_RULES = vocabularyRules(IDEA_CORPUS_GLOSS, IDEA_WORD_RULES);

/**
 * The buyer-facing reading of the idea-prose fields. `humanizeInternalJargon` runs first
 * because it owns the money re-unit and the renamed metrics.
 */
export function buyerFacingIdeaProse(value: string | null | undefined): string {
  if (!value?.trim()) return "";
  if (DATA_ROUTE_UNVERIFIED.test(value.trim())) {
    return "Data access has not been verified. Confirm that the required source is available "
      + "before building.";
  }
  const humanized = humanizeInternalJargon(value).replace(
    /\[NEEDS-VERIFY:\s*([^\]]+)\]/gi,
    (_match, question: string) => (
      `Source question: ${question.trim().replace(/^./, (character) => character.toUpperCase())}`
    ),
  );
  return sanitize(humanized, IDEA_RULES);
}

// ─────────────────────────────────────────────────────────────────────────────
// Coverage notes: `data_quality_summary.quality_caveats` + `user_adjustments`
// ─────────────────────────────────────────────────────────────────────────────

const DATA_ACCESS_LABELS: Record<string, string> = {
  public: "Public source available",
  freemium: "Free tier available",
  paywalled: "Paid access required",
  unofficial: "Unofficial access route",
  restricted: "Restricted access",
  blocked: "Access blocked",
  unverified: "Not verified",
};

/**
 * THE COVERAGE NOTE HAS TWO CLAUSES, AND BOTH ARE OPTIONAL AT THE PRODUCER.
 * `unified_solution_crew.py:9583-9592` builds this sentence from a LIST — a concentration
 * note and an uncovered-pains note, `"; ".join`-ed under one "Idea-set coverage — " head — so
 * a pattern that requires the uncovered clause to follow the head IMMEDIATELY misses every
 * value that carries both. `top || uncovered` keeps a head with neither from being rewritten
 * into a bare closing sentence.
 */
const COVERAGE_NOTE =
  /^Idea-set coverage\s*[—–-]\s*(?:(\d+) of (\d+) ideas address "([^"]*)")?(?:;\s*)?(?:validated pains with no idea:\s*(.+?))?\.\s*Concentration may reflect where the real opportunity is, not a defect\s*[—–-]\s*shown for your judgment\.$/i;

/**
 * THE CALIBRATION STANZA IS LOAD-BEARING AND MUST NOT BE THINNED. Its eight rules cover seven
 * producer phrases (`Calibration note`, `route verifier`, `cites … data route`, `as market-fit
 * support`, `data_access_model: <status>` and its bare form, `market-fit score`, `unverified on
 * the data-route dimension`) that are ONE producer sentence: all eight fire on exactly the same
 * 20 corpus inputs, and NO shared authority owns any of them. Dropping any one prints
 * "Calibration note … cites data route … as market-fit support" verbatim, and a residual-TOKEN
 * metric reads 0 in exactly that state, because producer PROSE carries no internal token. They
 * must also run BEFORE the delegation, because the dash normaliser would otherwise split the
 * very sentences they are keyed to.
 *
 * THE STATUS RULE ACCEPTS BOTH SPELLINGS. Read off a raw preview report the field name is
 * `data_access_model`; read after a pass that already renamed it, it is "data route".
 */
function coverageNoteStanza(value: string): string {
  const coverage = value.trim().match(COVERAGE_NOTE);
  const [, top, total, topPain, uncovered] = coverage ?? [];
  if (coverage && (top || uncovered)) {
    const sentences: string[] = [];
    if (top) sentences.push(`${top} of ${total} ideas address "${topPain}".`);
    if (uncovered) {
      const pains = uncovered.split(";").map((pain) => pain.trim()).filter(Boolean);
      sentences.push(
        `${pains.length} validated ${pains.length === 1 ? "problem has" : "problems have"} no matching idea yet: ${pains.join("; ")}.`,
      );
    }
    sentences.push(
      "This concentration may point to the strongest opportunity, so review it before "
      + "narrowing the shortlist.",
    );
    return sentences.join(" ");
  }

  return value.trim()
    .replace(
      /was prioritised for ideation as the closest match to your niche focus;\s*research scored a related pain higher on severity \((.+?),\s*0\.(\d+)\s+vs\s+0\.(\d+)\)\./gi,
      "was used as the main idea focus because it best matched your niche. A related pain, $1, received a higher severity score: $2 versus $3.",
    )
    .replace(
      /Novelty\/obviousness collapsed to exact complements this run\s*[—–-]\s*treat the two originality axes as one signal\./gi,
      "Distinctiveness and conventionality produced duplicate signals in this research. Treat them as one signal.",
    )
    .replace(/\bCalibration note\b/gi, "Research caveat")
    .replace(/\broute verifier\b/gi, "source check")
    .replace(/\bcites? (?:a )?data route\b/gi, "uses a data source")
    .replace(/\bas market-fit support\b/gi, "to support market fit")
    .replace(/\b(?:data_access_model|data route)\s*:\s*([a-z-]+)\b/gi, (_match, status: string) => (
      `Data access: ${DATA_ACCESS_LABELS[status.toLowerCase()] ?? "Not verified"}`
    ))
    .replace(/\bdata_access_model\b/gi, "data access")
    .replace(/\bmarket-fit score\b/gi, "market fit")
    .replace(/\bunverified on the data-route dimension\b/gi, "not verified for data access");
}

/**
 * The buyer-facing reading of one `data_quality_summary.quality_caveats` /
 * `user_adjustments` entry.
 */
export function buyerFacingCoverageNote(value: string | null | undefined): string {
  if (!value?.trim()) return "";
  const surfaced = coverageNoteStanza(value);
  // Fall back to the surfaced value: a rule that emptied a caveat would lose the buyer's
  // content, the same guard `buyerFacingSolutionPreview` applies per field.
  return buyerFacingIdeaProse(surfaced) || surfaced;
}

// ─────────────────────────────────────────────────────────────────────────────
// Proper names
// ─────────────────────────────────────────────────────────────────────────────

/**
 * The shapes the PRODUCER already uses to tell a product name from vocabulary:
 * `_PRODUCT_NAME_RE` at `src/nicheiq/utils/niche_difficulty.py:1448` — CamelCase, or a run
 * of two or more Title Cased words. The producer's sentence-position guard is deliberately
 * DROPPED: a false negative there costs nothing, here it renames somebody's product.
 */
const PRODUCT_NAME_SPAN = new RegExp(
  String.raw`\b\w*[a-z]\w*[A-Z]\w*\b`               // CamelCase: PayoutClarity, RageQuit
  + "|"
  + String.raw`\b(?:[A-Z][a-z]+[\s-])+[A-Z][a-z]+\b`, // Title Case Multi Word
  "g",
);

const VOCABULARY_WORD = /^(?:cold|start|data|corpus|wedge|web|verified|paid|prices|initial)$/i;

/**
 * True when the run ENDS in a stretch of nothing but vocabulary words. This is a SUFFIX test,
 * not a whole-run test: a title-cased run absorbs the determiner in front of it, so "The Cold
 * Start problem" is scanned as "The Cold Start" and a whole-run test would call it a name on
 * the strength of the word "The".
 */
function isVocabularyRun(span: string): boolean {
  const words = span.split(/[\s-]+/).filter(Boolean);
  return words.some(
    (_word, index) => words.slice(index).every((word) => VOCABULARY_WORD.test(word)),
  );
}

/**
 * A name can span a dash: "RageQuit Radar — Stack Exchange Rescue Queue" is ONE idea. Two name
 * spans separated by nothing but title-cased words and a single spaced dash are one name, so
 * the dash ends up INSIDE the mask and the clause-breaker never sees it.
 */
const NAME_INTERNAL_GAP = /^(?:\s+[A-Z][\w'’]*)*\s*[—–]\s*(?:[A-Z][\w'’]*\s+)*$/;

/** U+0001 is not `\w`, not `\s` and not `[A-Za-z]`, so no rule below can match into it. */
const MASK_TOKEN = /\x01(\d+)\x01/g;

function maskProductNames(text: string): { text: string; names: string[] } {
  const spans: [number, number][] = [];
  PRODUCT_NAME_SPAN.lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = PRODUCT_NAME_SPAN.exec(text))) {
    if (isVocabularyRun(match[0])) continue;
    const start = match.index;
    const end = start + match[0].length;
    const previous = spans[spans.length - 1];
    if (previous && NAME_INTERNAL_GAP.test(text.slice(previous[1], start))) {
      previous[1] = end;
    } else {
      spans.push([start, end]);
    }
  }
  if (!spans.length) return { text, names: [] };

  const names: string[] = [];
  let out = "";
  let cursor = 0;
  for (const [start, end] of spans) {
    out += text.slice(cursor, start) + `\x01${names.length}\x01`;
    names.push(text.slice(start, end));
    cursor = end;
  }
  return { text: out + text.slice(cursor), names };
}

function restoreProductNames(text: string, names: string[]): string {
  if (!names.length) return text;
  return text.replace(MASK_TOKEN, (whole, index: string) => names[Number(index)] ?? whole);
}

// ─────────────────────────────────────────────────────────────────────────────
// Word rules
// ─────────────────────────────────────────────────────────────────────────────

/** True when `offset` is where a sentence begins — start of the field, or after `.`/`!`/`?`. */
function startsSentence(source: string, offset: number): boolean {
  return /(^|[.!?]["'’”)\]]?\s+)$/.test(source.slice(0, offset));
}

/**
 * Apply the vocabulary, PRESERVING SENTENCE-INITIAL CAPITALISATION. A capital is re-applied
 * only when the match both starts a sentence AND was capitalised itself, so mid-sentence prose
 * keeps its own casing.
 */
function applyWordRules(text: string, rules: [RegExp, string][]): string {
  let out = text;
  for (const [pattern, replacement] of rules) {
    out = out.replace(pattern, (...args: unknown[]) => {
      const source = args[args.length - 1] as string;
      const offset = args[args.length - 2] as number;
      const matched = args[0] as string;
      const groups = args.slice(1, -2) as (string | undefined)[];
      const expanded = replacement.replace(
        /\$(\d)/g,
        (_marker, index: string) => groups[Number(index) - 1] ?? "",
      );
      return startsSentence(source, offset) && /^[A-Z]/.test(matched)
        ? expanded.charAt(0).toUpperCase() + expanded.slice(1)
        : expanded;
    });
  }
  return out;
}

// ─────────────────────────────────────────────────────────────────────────────
// Dashes
// ─────────────────────────────────────────────────────────────────────────────

/**
 * A SPACED em/en dash between two words is a clause break. Every OTHER dash is left exactly as
 * it is, because all of these are live inputs:
 *
 *   "Incumbents charge $99 – 399 per month."        numeric range — tail is not a clause
 *   "The buyer — a clinic owner — signs the check." parenthetical — a pair, not a break
 *   "cost—benefit tradeoffs matter here."           tight dash — a compound, not a break
 *   "Priced $99–399/mo across the incumbents."      tight en dash — a range
 *   "RageQuit Radar — Stack Exchange Rescue Queue"  inside a name — masked before we get here
 */
function normalizeClauseDashes(text: string): string {
  // Split on sentence boundaries (keeping them) so a PAIR of dashes can be recognised
  // inside the sentence that owns it. The ROUND-BRACKET depth is carried ACROSS that split,
  // because a parenthetical can hold a full stop.
  let depth = 0;
  return text
    .split(/([.!?][\s ]+)/)
    .map((chunk, index) => {
      const out = index % 2 === 0 ? breakLoneClauseDash(chunk, depth) : chunk;
      depth = bracketDepth(chunk, chunk.length, depth);
      return out;
    })
    .join("");
}

/**
 * Unclosed `(` count at `end`. Clamped at zero so a stray `)` — the pipeline writes
 * "per-ID/unverified)" with no opener — cannot drive the count negative.
 */
function bracketDepth(text: string, end: number, from = 0): number {
  let depth = from;
  for (let i = 0; i < end; i += 1) {
    if (text[i] === "(") depth += 1;
    else if (text[i] === ")") depth = Math.max(0, depth - 1);
  }
  return depth;
}

/** A dash flanked by whitespace on both sides, however many dash characters it runs to. */
const SPACED_DASH = /\S\s+[—–]+\s+\S/g;
/** …plus the following word, which decides whether the tail is a plausible clause start. */
const SPACED_DASH_CLAUSE = /(\S)\s+[—–]+\s+([A-Za-z][\w'’-]*|\x01\d+\x01)/;

/**
 * RELATIVE PRONOUNS CANNOT OPEN A SENTENCE. A tail that starts with one modifies the noun
 * phrase the dash just interrupted, so a period leaves a fragment; a COMMA is the correct
 * joint. Subordinating conjunctions are deliberately NOT here — those tails are complete
 * sentences that SHOULD split.
 */
const RELATIVE_PRONOUN = /^(?:which|who|whom|whose)$/i;

/**
 * A PARTICIPIAL TAIL IS A FRAGMENT TOO. The two readings — participial adjunct vs gerund
 * SUBJECT — are separated by a finite BE outside any relative clause. The BE test only looks
 * for a relative clause, and that is as far as it can go: widening `RELATIVE_MARKER` to the
 * subordinators would flip the measured gerund-subject case into a comma splice.
 */
const PARTICIPLE_TAIL = /^[a-z][a-z'’-]*ing$/;
const FINITE_BE = /\b(?:is|are|was|were)\b/i;
const RELATIVE_MARKER = /\b(?:that|which|who|whom|whose|where)\b/i;

/**
 * `-ing`-final words that are COMMON NOUNS in this domain, never participles. The shape test
 * above is purely orthographic. The `-ing`-final PRONOUNS (something, nothing, …) and the
 * preposition `during` are deliberately NOT here: a tail opening with one is an APPOSITIVE,
 * where the comma this function produces is the correct reading.
 */
const NOUN_TAIL = new RegExp(
  "^(?:pricing|marketing|training|onboarding|engineering|accounting|billing"
  + "|staffing|funding|tooling|messaging|branding|housing|planning|manufacturing"
  + "|wiring|plumbing|ceiling|morning|evening)$",
  "i",
);

function isParticipialAdjunct(word: string, tail: string): boolean {
  if (!PARTICIPLE_TAIL.test(word) || NOUN_TAIL.test(word)) return false;
  const be = tail.search(FINITE_BE);
  if (be < 0) return true;
  const marker = tail.search(RELATIVE_MARKER);
  return marker >= 0 && marker < be;
}

function breakLoneClauseDash(sentence: string, openBrackets = 0): string {
  // Two dashes in one sentence are parenthetical ("the buyer — a clinic owner — signs"),
  // and every deterministic producer constant carries exactly one. Leaving a paired dash
  // alone costs a design-system nit; splitting it costs the sentence.
  if ((sentence.match(SPACED_DASH) ?? []).length !== 1) return sentence;
  return sentence.replace(
    SPACED_DASH_CLAUSE,
    (whole: string, before: string, word: string, offset: number) => {
      // A DASH INSIDE AN UNCLOSED BRACKET IS NOT A SENTENCE BOUNDARY. `offset + 1` because
      // the match STARTS on the character before the dash, and on the commonest shape in the
      // data that character is the closing bracket itself.
      if (bracketDepth(sentence, offset + 1, openBrackets) > 0) return whole;
      const tail = sentence.slice(offset + whole.length - word.length);
      if (RELATIVE_PRONOUN.test(word) || isParticipialAdjunct(word, tail)) {
        return `${before}, ${word}`;
      }
      // A masked product name starting the tail owns its own casing, and there is nothing to
      // sentence-case: "Two vendors dominate — iOS-first tools own it."
      return `${before}. ${word.startsWith("\x01") ? word : sentenceCase(word)}`;
    },
  );
}

/** "price-aware" -> "Price-aware", but "iOS-first" and "eCFR" keep the casing they own. */
function sentenceCase(word: string): string {
  return /[A-Z]/.test(word.slice(1)) ? word : word.charAt(0).toUpperCase() + word.slice(1);
}

/**
 * The headline carries a STRUCTURAL separator: "Software Fit: Strong — <what a tool owns>".
 * The frontend's two consumers split on it, so normalising that one dash away would break
 * their parsing and lose the rating word; it is re-emitted in its canonical spaced form and
 * only the TAIL is sanitised. The backend surface has no such splitter — it prints the
 * headline as the evidence card's `<strong>` title — but the separator is kept anyway,
 * because this is a PORT and a second reading of one producer field is the defect class the
 * drift gate exists to prevent.
 */
const FIT_HEADLINE = /^(software\s+fit:\s*)([^—–:-]+?)\s*[—–:-]+\s*([\s\S]*)$/i;

export function buyerFacingVerdictHeadline(value: string): string {
  const match = value.match(FIT_HEADLINE);
  if (!match) return buyerFacingVerdictNarrative(value);
  return `${match[1]}${match[2].trim()} — ${buyerFacingVerdictNarrative(match[3])}`;
}
