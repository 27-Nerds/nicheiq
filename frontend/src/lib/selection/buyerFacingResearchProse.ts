import type { SolutionPreview } from "$lib/types/job";
import type { NicheDifficultyVerdict, Report } from "$lib/types/report";
import { humanizeInternalJargon } from "$lib/utils/format";

/**
 * Converts pipeline-facing research prose into language suitable for buyers.
 * All surfaces that render a niche difficulty verdict must pass through this authority.
 *
 * THE SEPARATORS ARE LOAD-BEARING, AND THERE IS MORE THAN ONE.
 * `src/nicheiq/utils/niche_difficulty.py` authors every one of these sentences with a
 * SPACED EM DASH, but that is not the only form that reaches disk. On the paying-wallet
 * contract path `_without_long_dashes` (niche_difficulty.py:2210) rewrites the copy before
 * it is persisted:
 *
 *     " — " -> ": "      "—" -> ": "      " – " -> "-"      "–" -> "-"
 *
 * and it is applied to key_challenges (:2233), key_strengths (:2248), buyer notes (:2207)
 * and the headline + narrative (:2273-2274, :2436). `idea_portfolio_summary` is written
 * with a literal colon by `_wallet_positive_note` (:135-144). On top of that the narrative
 * is stored verbatim from the LLM (:2735), so a tight em dash or an en dash of the model's
 * own can arrive in any position.
 *
 * WHAT THIS MODULE REACHES, AND WHAT IT DOES NOT. A FIELD IS NOT COVERED BECAUSE IT IS
 * LISTED HERE — IT IS COVERED ON THE RENDER TREES THAT CALL IN. Three entry points, all
 * field-scoped, and each one only reaches what its callers hand it:
 *
 *   `buyerFacingResearchProse`, via `buyerFacingReport`, rewrites `niche_difficulty_verdict`
 *   (challenges / strengths / buyer note); its sibling `buyerFacingVerdictNarrative` takes
 *   the verdict's narrative and headline AND `idea_portfolio_summary`, all three of which
 *   read the word "corpus" the other way round — see `RESEARCH_CORPUS_GLOSS` for the
 *   per-field counts. `buyerFacingReport` is called at the REPORT boundary in
 *   ReportContent and ReportBrief; SelectionWorkbench, NicheRealityCheck and the job page
 *   reach the verdict through `buyerFacingNicheDifficultyVerdict` instead. It ALSO routes
 *   `data_quality_summary.quality_caveats` and `user_adjustments` through
 *   `buyerFacingCoverageNote` — see its own note.
 *
 *   `buyerFacingCoverageNote` rewrites one `quality_caveats` / `user_adjustments` entry. It
 *   is called on the shortlist by `ResearchContextNotes` and on the paid report by
 *   `buyerFacingReport`, which is what puts it in front of `CoverageNotes.svelte` and
 *   ReportContent's "How this run was shaped" note.
 *
 *   `buyerFacingIdeaProse` rewrites `angle_rationale`, `data_acquisition_notes`,
 *   `critic_concern`, `refine_binding_constraint`, the ruled-out reason, and
 *   `idea_theses[].fatal_assumptions[].assumption` — WHEREVER IT IS CALLED, WHICH IS NOT
 *   EVERYWHERE THOSE FIELDS ARE PRINTED.
 *
 *   `buyerFacingSolutionPreview` applies the second of those to a whole idea. It is called by
 *   the COMPONENTS that print it — SolutionDetailContent (and so all four of its mounts),
 *   AlternativesSection — and at the report boundary in ReportContent, which covers
 *   `alternative_solutions[]` and `selected_solution_details` for every consumer inside that
 *   tree, TechnicalBlueprint's data tooltip included. See its own note for why the call site
 *   moved into the render tree.
 *
 * SO THE HONEST SCOPE IS: the four idea fields are sanitised on the SolutionDetail render
 * tree, on the paid Deep Research report tree under ReportContent, in the compare table's
 * `evidenceNote`, in SelectionWorkbench's ruled-out reason and overlap notice, in
 * `ideaThesis.ts`'s fatal assumptions, and — since the D26 round — on the shortlist's
 * `data_quality_summary.quality_caveats` / `user_adjustments` in `ResearchContextNotes` and,
 * since the round after it, on the SAME two fields on the paid report, through
 * `buyerFacingReport`. They are NOT sanitised anywhere else, and
 * nothing in this module can make them be — a surface that reads `critic_concern` off a raw
 * job payload and prints it gets raw pipeline vocabulary. That is exactly how two leaks
 * survived every earlier round: AlternativesSection printed `critic_concern` through
 * `humanizeInternalJargon`, which knows nothing of this vocabulary (50 of the 210 distinct
 * corpus values affected), and the compare page's `evidenceNote` hand-rolled its own chain
 * ending in the blind dash replace this module was extracted to delete. When you add a
 * surface, add it to the list above or route it through a component that already calls in.
 *
 * NOTHING ELSE IS IN REACH AT ALL: `why_non_obvious`, `pricing_strategy`, `top_pain_points`,
 * `wtp_validation`, competitor descriptions and every other report field carry the same
 * vocabulary and are NOT sanitised on any surface: 7,855 instances of exactly these words,
 * spread over 128 field names, measured over every run under `output/`. That is a deliberate
 * scope, not an oversight; the note on `buyerFacingReport` records why an unconditional deep
 * walk was measured and rejected.
 *
 * THE HAND-ROLLED SIBLINGS ARE GONE, AND "GONE" IS A NARROWER CLAIM THAN IT LOOKS. There were
 * three chains that ended in a blind spaced-dash replace and did their own thin vocabulary:
 * SelectionWorkbench's (rounds 4-7), the compare page's `evidenceNote` (round 9), and
 * `ResearchContextNotes.svelte`'s `userFacingNote` — which additionally never called
 * `humanizeInternalJargon`, the function that owns `WTP`, and so printed `WTP`,
 * `pain_points_addressed`, `seo_analytics` and a whole interpolated PainPoint repr to the
 * reader across 10 of the 165 distinct `quality_caveats` / `user_adjustments` values under
 * `output/` (20 occurrences), plus 40 lower-cased sentence starts and 2 non-idempotent
 * values. All three now delegate their tail to `buyerFacingIdeaProse`; each keeps only the
 * rewrites that are genuinely its own surface's — and the third one's, the coverage-set and
 * calibration-note stanzas, moved INTO this module as `buyerFacingCoverageNote` once the paid
 * report turned out to print the same two fields.
 *
 * THREE DASH REPLACES REMAIN IN `src/` AND NONE OF THEM IS A LEAK — stated because this
 * finding has claimed exhaustiveness wrongly before. `NicheRealityCheck.svelte:79` and
 * `jobs/[jobId]/+page.svelte:1213` both strip the `FIT_HEADLINE` separator documented on
 * `buyerFacingVerdictHeadline` below, and both run on text that has ALREADY been through this
 * module — that separator is re-emitted here on purpose so their parse keeps working.
 * `seo/catalogSeo.ts:226` trims trailing punctuation off a clamped meta description and never
 * splits a clause. A new blind mid-string dash replace, on the other hand, is the defect.
 *
 * Round 3 keyed the cold-start rule on a colon only, so it never fired on the em-dash path
 * and the word-level fallbacks produced "a data research evidence that doesn't exist yet".
 * Round 4 keyed four clause-continuation rules on the dash only, so they never fired on the
 * colon path. Both rounds asserted a separator instead of reading the producer. Every rule
 * now accepts the whole family via `SEP`, and
 * `__tests__/buyerFacingResearchProse.test.ts` asserts that family against the producer
 * source itself — which is checked in, so that assertion always runs.
 *
 * PROSE IS NOT THE ONLY THING ON THESE SURFACES. `idea_portfolio_summary` names ideas by
 * construction, and 552 of the 8,745 `solution_name`/`idea_name` fields under `output/`
 * (6.3%) carry a spaced em dash of their own — "RageQuit Radar — Stack Exchange Rescue
 * Queue" is one of them, and it is named in a persisted summary. Round 5 had no concept of a
 * proper name, so it split those names into two sentences and rewrote the word "Cold-Start"
 * out of the ideas called after it. `maskProductNames` below borrows the producer's own
 * discriminator to hold most names out of the rules' reach. NOT ALL OF THEM: `isVocabularyRun`
 * un-masks any name whose TAIL is vocabulary, so "Coffee Safety Data" is exposed while
 * "Cold-Start Atlas" is protected. Its docstring measures exactly which names that is.
 *
 * Every rule must also be IDEMPOTENT: SelectionWorkbench sanitises the verdict before
 * handing it to NicheRealityCheck, NicheRealityCheck sanitises again as its own guarantee,
 * and `buyerFacingReport` sanitises at the report boundary. A caller that passes raw
 * pipeline data cannot leak through any of them, and a caller that pre-sanitised loses
 * nothing.
 */

/**
 * Every separator the producer can leave at a clause boundary inside one of its
 * deterministic constants: the authored em dash, the colon and hyphen
 * `_without_long_dashes` turns it into, the en dash, and doubled runs of any of them.
 * `\s` covers the NBSP / thin-space / newline forms the same copy has been seen with.
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
  // THESE THREE ARE KEYED TO THE PRODUCER AS IT READS TODAY, NOT AS IT READ IN ROUND 7.
  // `_BUYER_CLASS_NOTES` and the episodic-use constant were reworded in
  // `niche_difficulty.py` ("bought around an event" -> "opened", "— a historically" ->
  // "— historically a low-price-ceiling segment, and …", "low price points, high support
  // load;" -> "low price points and high support load, and …"), which left all three rules
  // dead and the dash rule splitting each note into a fragment. The provenance test above
  // is what caught it, and it will catch the next rewording too.
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
  // A LABEL AND A LIST, NOT TWO CLAUSES. `idea_theses.py:282` writes
  // "Cold start: the product has no data until a customer supplies it — " + "; ".join(...),
  // so the tail is a run of source names ("User-provided CSV files; Owner-provided property-
  // management exports"). 61 of the corpus values carry it, and it is the single largest
  // source of dash splits in the whole corpus — every one printed a capitalised noun phrase
  // dangling after a full stop. No grammar rule can repair a list; naming what the list IS
  // can. This must precede the word rules, which would otherwise rewrite the "Cold start"
  // label into "Up-front data:" and leave the dangling list exactly where it was.
  sentenceRule(
    String.raw`Cold start: the product has no data until a customer supplies it%`,
    "The product has no data until a customer supplies it. It would run on: ",
  ),
  // ONE SURFACE OVER, THE SAME LABEL-AND-LIST SHAPE. `Already well-served — <partial|shipped>
  // by <incumbent>: <evidence>` is a verdict LABEL followed by the incumbent that earns it,
  // not two clauses, so the dash rule split it into "Already well-served. Partial by
  // Fieldproxy: …" — a capitalised fragment, on 9 of the 34 distinct `examined_ruled_out[]
  // .reason` values under `output/` (12 of the 65 distinct values of `reason` anywhere), and
  // 0 of them arrive already in the colon form. THE PRODUCER AGREES IT
  // IS A LABEL: `report/idea_validation_block.py:169` rewrites exactly this dash to a colon —
  // but only inside `_display_embedded`, which runs on `demotion_reason` and never on
  // `examined_ruled_out[].reason`, the field SelectionWorkbench's ruled-out panel prints.
  // Applying that call to this field too is the cleaner fix and it belongs in the producer,
  // which this round does not own; the rule below is idempotent against it, because `%`
  // accepts the colon the producer would leave.
  sentenceRule(
    String.raw`^Already well-served%(partial|shipped) by `,
    "Already well-served: $1 by ",
  ),
];

/**
 * Word-level vocabulary. Longest phrase first, so the generic fallback never mangles a
 * phrase that has its own reading ("a data corpus" is not "a data <corpus>").
 *
 * Two failure classes govern the ordering and the shape of every entry:
 *
 * ARTICLES. A replacement that changes the noun's shape also changes the article in front
 * of it. Round 3 shipped "a early data play"; round 4 reintroduced the same class with
 * `wedge` -> "entry point" and `corpus` -> "collected evidence". So every rule whose
 * replacement can follow an indefinite article carries the article-adjacent form too, and
 * that form is listed FIRST so it wins. `$1n` re-emits the captured article with its own
 * casing, so one case-insensitive rule covers "a" and "A".
 *
 * STACKING. Two rules that both match inside one phrase produce word salad: `cold-start
 * data corpus` fell through `data corpus` -> "body of data" and then `cold-start` ->
 * "up-front data", printing "an up-front data body of data". Every compound that can be
 * built out of two vocabulary terms therefore has its own entry, ahead of both parents.
 *
 * SENSE. This table runs ABOVE the per-field fork in `vocabularyRules`, so it is shared by
 * the evidence reading and the dataset reading alike — and that is exactly where three
 * consecutive rounds put a rule that could only be right for one of them. The last was
 * `enumerable corpus` -> "searchable evidence library": measured over `output/`, all 110
 * instances sit in idea fields (56 `calibration_notes`, 16 `differentiation_locus`, 22
 * `angle_rationale`, 4 `programmatic_seo_opportunity`, 12 in the ruled-out mirrors of those
 * three) and every one of them names the enumerable SET OF ENTITIES that yields programmatic
 * SEO pages — "an enumerable corpus (thousands of model × hardware combinations)", "the
 * enumerable corpus of broker entities". None reads as the run's own evidence, and the
 * evidence noun shipped to the buyer on `angle_rationale`.
 *
 * SO THE INVARIANT IS MECHANICAL, AND `buyerFacingResearchProse.test.ts` enforces it: a rule
 * here may only re-use a sense noun the PRODUCER already wrote inside the phrase it matches.
 * "data corpus" -> "body of data" and "corpus evidence gap" -> "gap in the collected
 * evidence" qualify — the producer chose the sense, this table only repairs the grammar. A
 * replacement that INTRODUCES "evidence", "dataset" or a synonym is a guess about a fork that
 * has not happened yet, and belongs in `RESEARCH_CORPUS_GLOSS` or `IDEA_CORPUS_GLOSS` below,
 * each of which knows which field it is reading. Three rules moved or died under that rule:
 * `cold-start corpus` (60 instances: 59 `data_acquisition_notes` and 1 `dev_time_rationale`)
 * went down to BOTH glosses,
 * because dropping it would let the `cold[-\s]start` tail rule stack; `initial corpus` (37,
 * all idea fields) and `enumerable corpus` were DELETED outright, because each gloss's own
 * bare-noun rules already produce the right reading for them with no compound at all.
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
  // THE PLURAL LEMMA IS UNREACHABLE FROM THE SINGULAR RULE. "corpus" is not a prefix of
  // "corpora" — they diverge at the fifth letter — so `\bcorpus\b` can never see it, and
  // neither gloss below could either. It shipped VERBATIM in 2 of the 28 distinct
  // `niche_difficulty_verdict.narrative_summary` values under `output/`: "require data
  // corpora that do not currently exist" and "build data corpora that do not currently
  // exist". Both are the plural of the compound directly below, which is where the reading
  // belongs; the bare plural gets a backstop in each gloss, next to the bare singular.
  [/\bdata corpora\b/gi, "bodies of data"],
  [/\bdata corpus\b/gi, "body of data"],
];

/**
 * THE BARE NOUN MEANS DIFFERENT THINGS IN DIFFERENT PLACES, so it has two glosses — and
 * INSIDE THE VERDICT THE FORK IS PER FIELD, NOT PER SURFACE. Counted over every distinct
 * value of each `niche_difficulty_verdict` field under `output/`:
 *
 *   `narrative_summary` — 21 of its 28 distinct values say "corpus"/"corpora", and all 21
 *   mean THE DATASET A PRODUCT WOULD HAVE TO BUILD. Every one co-occurs with "require",
 *   "seed", "cold-start" or "does not yet exist": "many effective solutions require data
 *   corpora that do not currently exist", "plan a clear strategy to seed the necessary data
 *   corpus". Two of them reach the bare noun — "those requiring a new corpus" and "many
 *   concepts require a corpus that does not yet exist" — and the evidence gloss printed
 *   "requiring a new collected evidence" on the first. `headline` says neither word in any
 *   of its 28 values; it travels with the narrative because it is the same sentence, cut.
 *
 *   `key_challenges` — 3 of its 25 distinct values, and the only one that reaches the bare
 *   noun is "The corpus drifts from the stated audience", which is THE RESEARCH EVIDENCE:
 *   "the dataset drifts from the stated audience" names the wrong thing. `key_strengths` (4
 *   values) and `buyer_class_note` (5) say neither word and stay with `key_challenges`,
 *   because all three are statements about the research rather than about the product.
 *
 * An earlier round put the WHOLE verdict on the evidence gloss on the strength of "The
 * corpus drifts…" alone — one value of one field, generalised to four others that do not
 * read that way. `buyerFacingVerdictNarrative` below is the dataset reading of the two
 * fields that need it; `buyerFacingResearchProse` keeps the evidence reading for the rest.
 *
 * On the idea cards it is the DATASET the product would be built from, and it is almost
 * always the head of a compound the pipeline coins on the spot: "the recipe corpus", "a
 * document corpus", "the GDELT bulk news corpus", "the exemplar corpus". Measured over the
 * idea fields under `output/`, 108 bare-corpus instances read that way and NONE read as
 * collected evidence, so "the recipe collected evidence" would be wrong in every one.
 */
const RESEARCH_CORPUS_GLOSS: [RegExp, string][] = [
  // ── Compounds that carry a SENSE. They live below the fork, not in
  //    `CORPUS_COMPOUND_RULES`, because the noun they choose is only right for this branch.
  //    `cold-start corpus` needs a compound on BOTH branches rather than the bare rules: the
  //    `cold[-\s]start` rule in `VOCABULARY_TAIL_RULES` runs after this gloss, so the two
  //    would stack into "a up-front data body of evidence".
  [/\b(a)(\s+)cold[-\s]start corpus\b/gi, "$1n$2up-front body of evidence"],
  [/\bcold[-\s]start corpus\b/gi, "up-front body of evidence"],
  // "Strong corpus purchase-intent signal" is about intent found IN the collected
  // discussions; the bare-noun rewrite below would read as a corpus made of intent. THE
  // PRODUCER AUTHORS IT AND `output/` DOES NOT HOLD IT, which is not the contradiction it
  // looks like: `niche_difficulty.py:1013,1016` writes both the "Strong" and the "Moderate"
  // wording, but its only caller is guarded by `commercial_intent_max < 0.6` (line 868) while
  // both of those returns require `>= 0.6`, so the branch is producer-side dead code today.
  // It is gated in this gloss and not the idea one because `_wtp_judgment`'s output is
  // appended to `key_points`, which reaches the buyer as `key_challenges`.
  [
    /\bcorpus purchase([- ])intent(\s+signal)?\b/gi,
    "purchase$1intent$2 in the captured discussions",
  ],
  // THE ARTICLE RULE MUST SURVIVE AN INTERVENING MODIFIER RUN. "collected evidence" is a
  // MASS noun and cannot head an indefinite noun phrase, so the count head below exists —
  // but keyed on an ADJACENT article it missed "a new corpus" and "a new, unproven corpus",
  // which fell through to the mass rule and shipped "a new collected evidence". The article
  // itself is re-emitted UNCHANGED here: what it has to agree with is the modifier, and the
  // modifier is not being rewritten ("an unproven corpus" -> "an unproven body of evidence").
  // The run is bounded at three words and excludes the determiners, prepositions,
  // conjunctions and copulas that mean the article's own noun phrase already ended — without
  // that, "a tool that indexes the corpus" matches as far as the noun and takes the count
  // head it must not have.
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
  // The dataset reading of the one compound that cannot fall through to the bare rules —
  // see the note on its evidence twin above. `enumerable corpus` and `initial corpus` have
  // NO entry here on purpose: "enumerable dataset" and "initial dataset" are what the bare
  // rules below already produce, and a compound that only restates its parents is a rule
  // whose sense can drift away from them, which is how "searchable evidence library" shipped.
  [/\b(a)(\s+)cold[-\s]start corpus\b/gi, "$1n$2up-front dataset"],
  [/\bcold[-\s]start corpus\b/gi, "up-front dataset"],
  // "a dataset" needs no article repair, so one rule covers both positions.
  [/\bcorpora\b/gi, "datasets"],
  [/\bcorpus\b/gi, "dataset"],
];

const VOCABULARY_TAIL_RULES: [RegExp, string][] = [
  [/\bweb-verified prices\b/gi, "published prices checked on the web"],
  // ATTRIBUTIVE vs POSTPOSITIVE. Round 4's comment claimed the producer only ever writes
  // this postpositively ("10 tools web-verified, 3 with published pricing"). That is FALSE:
  // `solution_landscapes[].competitors[].description` carries "user-provided web-verified
  // incumbent list", and the postpositive replacement turns that into "a checked on the web
  // competitor". Before a noun the modifier slot cannot hold "checked on the web" without
  // recasting the whole phrase, so the attributive form drops to a bare "verified"; the web
  // provenance is carried by the postpositive form, which keeps it.
  [/\bweb-verified(?=\s+[a-z])/gi, "verified"],
  [/\bweb-verified\b/gi, "checked on the web"],
  [/\bpaid wedge\b/gi, "paid offer"],
  // Bare "wedge" is strategy jargon on its own ("tighten the wedge", "a sharper wedge").
  // Must stay AFTER the "paid wedge" rule, which has its own reading.
  [/\b(a)(\s+)wedge\b/gi, "$1n$2entry point"],
  [/\bwedge\b/gi, "entry point"],
  // On the idea path `humanizeInternalJargon` has already turned the acronym into
  // "commercial intent" and this never fires; the verdict path reaches the vocabulary
  // without that pass, so the rule has to be here too.
  [/\bWTP\b/g, "willingness to pay"],
  // Backstop for the cold-start uses the sentence rules above don't cover. Before a noun it
  // reads as a modifier ("up-front data seeding"), which is where the pipeline mostly uses
  // it; standing alone it is a noun ("design for a cold-start, as many ideas…"), and
  // "an up-front data," is not English, so that position gets a noun head of its own.
  // The spaced form is real: niche_difficulty.py:1123 emits "frictions (cold start, crowded
  // tooling)". All four are case-INSENSITIVE; `maskProductNames` — not letter case — is what
  // protects "Cold-Start Atlas".
  //
  // WHERE THE CAPITALISED FORMS ACTUALLY ARE. Round 5 matched the spaced form
  // case-SENSITIVELY to protect that idea name, and round 6 made it case-blind on the
  // strength of a corpus count that was never broken down by field. Counted per field over
  // every run under `output/`, the capitalised forms ("Cold start", "Cold-Start",
  // "COLD START") appear 0 times in `niche_difficulty_verdict` + `idea_portfolio_summary` —
  // the only two fields round 6 shipped the change to — and 75 / 132 / 171 times in the four
  // idea fields `buyerFacingIdeaProse` covers, in `idea_theses[].fatal_assumptions[]
  // .assumption`, and in fields NO sanitizer reaches and this module does not claim to
  // (`rationale`, `pricing_strategy`, competitor descriptions; see the header). Round 6's
  // case fix was therefore a NO-OP where it shipped. It starts paying here, because
  // `buyerFacingIdeaProse` now covers the first two of those three groups — the third stays
  // uncovered.
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
 * every rule except the corpus gloss, because those two fields are the only research prose
 * that talks about the dataset a product would have to build rather than about the run's own
 * evidence — see the gloss note above for the per-field counts.
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
 * THE DATASET READING OF RESEARCH PROSE. Named for the verdict's narrative and headline
 * because that is what it was extracted for, but `idea_portfolio_summary` takes it too — the
 * name is the surface, the gloss is the contract.
 *
 * NOT `buyerFacingIdeaProse`: that entry point also runs `humanizeInternalJargon`, the
 * `DATA_ROUTE_UNVERIFIED` stanza and `IDEA_WORD_RULES`, none of which these three fields
 * carry — measured over the 26 distinct `idea_portfolio_summary` values under `output/`, not
 * one holds an `IDEA_WORD_RULES` term. Only the corpus gloss differs from
 * `buyerFacingResearchProse`.
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
 * Everything these fields share with the rest of the pipeline is deliberately NOT repeated
 * here — it comes from `vocabularyRules`, which runs straight after this list under the same
 * mask.
 */
const IDEA_WORD_RULES: [RegExp, string][] = [
  [/\bdata representation\b/gi, "content structure"],
  // "an SEO surface" is correct ("ess-ee-oh"), "an search opportunity" is not — the same
  // narrowing the enumerable-corpus rule above needs, for the same reason. Three instances.
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
  // THE "BY ELIMINATION" FAMILY HAS FOUR MEMBERS, NOT ONE, AND ONLY FIRES AT A CLAUSE
  // BOUNDARY. `unified_solution_crew.py:4889` instructs the model to write
  // "weak moat — <angle> by elimination" for any of its angle names, so the tail after that
  // dash is a verbless label — the largest single fragment class left in the corpus after
  // the participial rule. Round 7 covered only the spaced `vertical workflow` spelling; the
  // prompt says "never the snake_case key", and the model writes it anyway.
  //
  // THE POSITION GUARD IS LOAD-BEARING, AND ROUND 7 DID NOT HAVE IT. 103 of the 121 corpus
  // occurrences sit after a separator or at the start of the field, where a whole sentence
  // is the right reading. The other 18 sit MID-CLAUSE — "This wins on vertical workflow by
  // elimination", "Assigned novel_differentiation by elimination as a weak moat" — and an
  // unguarded rule substitutes a finite clause into an object slot: "This wins on the
  // strongest available angle is a focused workflow". The separator is kept in `$1` so the
  // clause-dash pass still sees it and still turns it into a full stop.
  [
    /(^|[—–:;.]\s*)vertical[_ ]workflow by elimination/gi,
    "$1The strongest available angle is a focused workflow",
  ],
  [
    /(^|[—–:;.]\s*)(?:novel[_ -]differentiation|a distinct mechanism) by elimination/gi,
    "$1The strongest available angle is a distinct mechanism",
  ],
  // WHAT IS LEFT IS A RAW INTERNAL KEY IN RUNNING PROSE. 84 corpus values print
  // "Angle: distribution_seo." or "Assigned novel_differentiation by elimination as a weak
  // moat" to the buyer — the snake_case enum the pipeline stores in `winning_angle`, which
  // every OTHER surface renders through `angleLabel`. These three run LAST so the
  // boundary rules above still see the key they are written against; the replacements carry
  // no article, so the phrase is never left worse formed than the key it replaces.
  [/\bdistribution[_ ]seo\b/gi, "distribution / SEO"],
  [/\bnovel[_ -]differentiation\b/gi, "distinct mechanism"],
  [/\bvertical[_ ]workflow\b/gi, "focused workflow"],
  // `unified_solution_crew.py:4439` appends this to `data_acquisition_notes` verbatim and
  // then truncates the whole field to 120 characters, so the suffix arrives cut off at six
  // different points ("per-ID/unver" … "per-ID/unverified access") — 45 instances, every one
  // of them printing a verbless clause after a full stop. It is joined rather than split
  // because it qualifies the route named in front of it; the pattern eats the head's own
  // terminal punctuation so "…no bulk source exists." does not become "…exists., with…".
  [
    // The 120-char cut lands anywhere: the corpus holds "per-ID/unver", "…/unverified a",
    // "…/unverified acc" and three more, so BOTH words have to be matched to any prefix.
    // Matching only whole words left a dangling " a" after the rewritten sentence.
    /([^\s.;])[.;]?\s*[—–]\s*no bulk route confirmed;\s*per-ID\/unv[a-z]*(?:\s+acc?e?s?s?|\s+a)?/gi,
    "$1, with no bulk download route confirmed and per-record access that is unverified.",
  ],
];

const IDEA_RULES = vocabularyRules(IDEA_CORPUS_GLOSS, IDEA_WORD_RULES);

/**
 * The buyer-facing reading of `angle_rationale`, `data_acquisition_notes`, `critic_concern`,
 * `refine_binding_constraint`, the ruled-out reason, and
 * `idea_theses[].fatal_assumptions[].assumption`.
 *
 * WHY IT MOVED OUT OF SelectionWorkbench. It ended with a blind replace of every spaced
 * em/en dash by ". " — no product-name mask, no sentence casing, no pair detection.
 * Measured over the 2,113 distinct values of the four idea fields under `output/`, that one
 * line produced 990 degraded instances: lower-cased sentence starts ("Differentiation is in
 * the mechanism — using AI…" -> "…mechanism. using AI…") and destroyed parenthetical dash
 * PAIRS ("The nearest competitors — Upwork and Fiverr — offer…" -> "The nearest competitors.
 * Upwork and Fiverr. offer…"), which is the exact defect `normalizeClauseDashes` was written
 * to fix, one function away. It also carried its own thin corpus rules and no cold-start
 * rule at all, leaving 304 jargon instances on the page.
 *
 * `humanizeInternalJargon` runs first because it owns the money re-unit and the renamed
 * metrics. It does NOT apply this vocabulary — see the note on `buyerFacingReport`.
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
 * THE COVERAGE NOTE HAS TWO CLAUSES, AND ROUND 1 KEYED ON ONE OF THEM.
 * `unified_solution_crew.py:9583-9592` builds this sentence from a LIST: a concentration note
 * (`f'{top_n} of {n} ideas address "{top_pain}"'`, emitted only when one pain takes at least
 * three ideas and half the set) and an uncovered-pains note, `"; ".join`-ed in that order
 * under one "Idea-set coverage — " head. Round 1's pattern required the uncovered clause to
 * follow the head IMMEDIATELY, so the four corpus values that carry both clauses did not
 * match, fell through to the word rules, and printed "Idea-set coverage — 3 of 5 ideas
 * address …" with the producer's own em dash to the buyer — on the shortlist AND, once
 * `buyerFacingReport` started calling in, on the paid report. Both clauses are optional here,
 * exactly as they are at the producer; `top || uncovered` is the guard that keeps a head with
 * neither from being rewritten into a bare closing sentence.
 */
const COVERAGE_NOTE =
  /^Idea-set coverage\s*[—–-]\s*(?:(\d+) of (\d+) ideas address "([^"]*)")?(?:;\s*)?(?:validated pains with no idea:\s*(.+?))?\.\s*Concentration may reflect where the real opportunity is, not a defect\s*[—–-]\s*shown for your judgment\.$/i;

/**
 * `quality_caveats` / `user_adjustments` carry the same pipeline vocabulary, dashes and raw
 * field names as every other prose field, so the TAIL of this function is
 * `buyerFacingIdeaProse` — the shared authority — and not a fourth hand-rolled chain.
 *
 * WHY IT LIVES HERE AND NOT ON A COMPONENT. It was written on `ResearchContextNotes.svelte`,
 * which prints these two fields on the SHORTLIST. They are printed a second time on the PAID
 * Deep Research report — `quality_caveats` through `CoverageNotes.svelte`, `user_adjustments`
 * as a raw `.join(" ")` in ReportContent's "How this run was shaped" note — and that surface
 * had none of this. Measured over the 165 distinct values of the two fields under `output/`,
 * 71 still printed a producer phrase there ("Calibration note … cites data route … as
 * market-fit support", "Idea-set coverage — …", "Novelty/obviousness collapsed …") and 73
 * still carried a raw em/en dash. Fixing that surface by copying the stanza would have made a
 * fourth hand-rolled sibling; both surfaces now call in here, so they cannot drift.
 *
 * WHAT THIS FUNCTION USED TO BE, AND WHAT IT COST. It ended in a blind replace of every
 * "optional-space, em/en dash, optional-space" run by ". ", and never called
 * `humanizeInternalJargon`, which is the function that owns `WTP`. Measured over the same 165
 * values, that one line produced 40 lower-cased sentence starts ("…for 11 of 13 ideas. this
 * usually means…", "…not a defect. shown for your judgment.") and 2 non-idempotent values,
 * because the optional space on both sides matches a TIGHT en dash too, turning "15–20
 * minutes" into "15. 20 minutes" on the second pass. 10 values printed a raw internal token
 * to the reader across 20 occurrences (`pain_points_addressed` x7, `WTP` x6, `seo_analytics`
 * x3, plus the four repr-dump names in one value — round 1's comment said "20 values", which
 * was the count of a DIFFERENT set: the 20 values the calibration stanza below fires on).
 * `normalizeClauseDashes` inside the shared authority is the function that already solves the
 * dash case properly — sentence casing, parenthetical PAIRS, numeric ranges and product names
 * all intact.
 *
 * EVERYTHING ABOVE THE DELEGATION IS SURFACE-SPECIFIC AND STAYS. The coverage-set stanza and
 * the calibration-note stanza — whose EIGHT rules cover seven phrases (`Calibration note`,
 * `route verifier`, `cites … data route`, `as market-fit support`, `data_access_model:
 * <status>` and its bare form, `market-fit score`, `unverified on the data-route dimension`)
 * — are ONE producer sentence: over the same 165 values all eight fire on exactly the same 20
 * inputs, and NO shared authority owns any of them, so dropping any one of them would print
 * "Calibration note … cites data route … as market-fit support" verbatim. A round that
 * validated the deletion on a residual-token metric read 0 in exactly that state, because
 * producer PROSE carries no internal token. They must also run BEFORE the delegation, because
 * the dash normaliser would otherwise split the very sentences they are keyed to.
 *
 * THE STATUS RULE HAS TO ACCEPT THE DEEP WALK'S OUTPUT TOO. On the shortlist this function
 * sees the raw preview report and reads `data_access_model: unverified`. On the paid report
 * `humanizeReportProse` has already walked the whole object and rewritten that field name to
 * "data route", so the raw form never arrives and the status was left printing "(data route:
 * unverified)" — a producer phrase, reached from the other side. Both spellings are matched.
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
 * `user_adjustments` entry, for the shortlist (`ResearchContextNotes`) and the paid report
 * (`CoverageNotes`, and ReportContent's "How this run was shaped" note) alike.
 */
export function buyerFacingCoverageNote(value: string | null | undefined): string {
  if (!value?.trim()) return "";
  const surfaced = coverageNoteStanza(value);
  // Fall back to the surfaced value: a rule that emptied a caveat would lose the buyer's
  // content, the same guard `buyerFacingSolutionPreview` applies per field.
  return buyerFacingIdeaProse(surfaced) || surfaced;
}

/** The four idea fields whose prose this module owns, in one place. */
const IDEA_PROSE_FIELDS = [
  "angle_rationale",
  "data_acquisition_notes",
  "critic_concern",
  "refine_binding_constraint",
] as const satisfies readonly (keyof SolutionPreview)[];

/**
 * Sanitise a whole idea ONCE, where it enters a render tree, instead of at each `{...}`.
 *
 * Rounds 4-7 fixed this leak at a call site and watched it reappear one layer up. The last
 * one moved it to SelectionWorkbench, which is exactly one of FOUR mounts:
 * `/selection/review` builds its ideas from `resolveSelectionWorkspace` and passes them to
 * SolutionDetail raw, and SelectedSolutionsSummary does the same from `job.solutionIdeas` on
 * both the job page and the research-progress screen. All four render through
 * `SolutionDetailContent`, which printed `angle_rationale`, `data_acquisition_notes`,
 * `critic_concern` and `refine_binding_constraint` verbatim — so 534 measured jargon
 * instances reached the page on three of the four paths. That component now calls this on
 * its own prop, so every current AND FUTURE mount is covered by construction and a caller
 * cannot forget.
 *
 * `scoreRationale` reads `data_acquisition_notes` off the same object, so its "the caller
 * already sanitised it" premise is only true because the component sanitises before reading.
 *
 * Returns the input UNTOUCHED when nothing changed, so `$derived` identity comparisons and
 * the `matches[0] === solution` selection checks downstream still hold.
 */
export function buyerFacingSolutionPreview<T extends SolutionPreview>(solution: T): T {
  let next: T | null = null;
  for (const field of IDEA_PROSE_FIELDS) {
    const value = solution[field];
    if (typeof value !== "string" || !value.trim()) continue;
    // Fall back to the raw value: a rule that empties a field would lose the buyer's content.
    const clean = buyerFacingIdeaProse(value) || value;
    if (clean === value) continue;
    next ??= { ...solution };
    (next as Record<string, unknown>)[field] = clean;
  }
  return next ?? solution;
}

// ─────────────────────────────────────────────────────────────────────────────
// Proper names
// ─────────────────────────────────────────────────────────────────────────────

/**
 * The shapes the PRODUCER already uses to tell a product name from vocabulary:
 * `_PRODUCT_NAME_RE` at `src/nicheiq/utils/niche_difficulty.py:1448` — CamelCase, or a run
 * of two or more Title Cased words joined by spaces or hyphens.
 *
 * ONE DELIBERATE DIVERGENCE: the producer guards its Title Case branch with
 * `(?<![.!?]\s)(?<!^)` so a sentence's first word is never mistaken for a name. That guard
 * is right for the producer's question ("does this SENTENCE make a commercial claim?"),
 * where a false negative costs nothing. It is wrong for ours ("may I rewrite this SPAN?"),
 * where a false negative renames somebody's product: `Cold-Start Atlas is the strongest
 * idea.` starts a sentence, and with the guard in place the vocabulary rules turn it into
 * "up-front data Atlas". So position is dropped and the shapes are kept.
 */
const PRODUCT_NAME_SPAN = new RegExp(
  String.raw`\b\w*[a-z]\w*[A-Z]\w*\b`               // CamelCase: PayoutClarity, RageQuit
  + "|"
  + String.raw`\b(?:[A-Z][a-z]+[\s-])+[A-Z][a-z]+\b`, // Title Case Multi Word
  "g",
);

const VOCABULARY_WORD = /^(?:cold|start|data|corpus|wedge|web|verified|paid|prices|initial)$/i;

/**
 * True when the run ENDS in a stretch of nothing but vocabulary words, so the words this
 * module owns are the last thing in it.
 *
 * THE SHIPPED RULE, STATED EXACTLY. This is a SUFFIX test, not a whole-run test: a span is
 * un-masked when SOME suffix of it — possibly the whole run, possibly only its last word —
 * is entirely vocabulary. The suffix form is required because a title-cased run absorbs the
 * determiner in front of it, so "The Cold Start problem" is scanned as the run "The Cold
 * Start" and a whole-run test would call it a name on the strength of the word "The".
 *
 * WHAT THAT COSTS, MEASURED. Any name whose LAST word is one of the vocabulary words is
 * un-masked and exposed to the rules — not only a name made ENTIRELY of vocabulary, which is
 * what rounds 5 and 6 claimed here. Over the 1,530 distinct `solution_name` / `idea_name` /
 * `display_label` values under `output/` (round 7's "4,794" counted OCCURRENCES across the
 * 3,413 artifacts, not distinct names — the 8,745 / 552 / 6.3% figures beside it in the
 * header are occurrence counts and are correct as stated), replaying `PRODUCT_NAME_SPAN` and
 * this predicate over every value un-masks NOTHING: zero spans qualify, so the shipped
 * exposure is not "two harmless names", it is empty.
 *
 * ROUND 8 NAMED THE WRONG EVIDENCE FOR THE RIGHT CONCLUSION. It cited "Coffee Safety Data"
 * and "Inventory and Product Data" as the two qualifying values of those three fields. Both
 * strings are real and both DO satisfy this predicate, but neither appears in any of the
 * three fields: they are SEO cluster labels, in `keywords[].cluster` (24 and 5 occurrences)
 * and `topic_clusters[].name` (3 and 1), and no entry point of this module reads either. They
 * are still the right shape to keep in mind — a name ending in a bare vocabulary word is the
 * exposure to weigh before adding a rule for a bare "data" — but nothing is exposed today.
 *
 * Anything that FOLLOWS the vocabulary — "Cold Start Optimization", "Cold-Start Atlas",
 * "Pedal Wedge Generator" — is a real name and keeps its mask.
 */
function isVocabularyRun(span: string): boolean {
  const words = span.split(/[\s-]+/).filter(Boolean);
  return words.some(
    (_word, index) => words.slice(index).every((word) => VOCABULARY_WORD.test(word)),
  );
}

/**
 * A name can span a dash: "RageQuit Radar — Stack Exchange Rescue Queue" is ONE idea, and
 * `idea_portfolio_summary` lists names like that in prose. Two name spans separated by
 * nothing but title-cased words and a single spaced dash are one name, so the dash ends up
 * INSIDE the mask and the clause-breaker never sees it.
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
 * Apply the vocabulary, PRESERVING SENTENCE-INITIAL CAPITALISATION. Round 5 replaced the
 * matched span verbatim, so `Wedge selection matters.` became "entry point selection
 * matters." and `Corpus coverage is thin.` became "collected evidence coverage is thin." —
 * a lower-cased first word on every field that opens with a vocabulary term. A capital is
 * re-applied only when the match both starts a sentence AND was capitalised itself, so
 * mid-sentence prose keeps its own casing.
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
 * A SPACED em/en dash between two words is a clause break, and em/en dashes are a
 * design-system violation in UI copy. Every OTHER dash is left exactly as it is, because
 * `narrative_summary` is stored verbatim from the LLM and all of these are live inputs:
 *
 *   "Incumbents charge $99 – 399 per month."        numeric range — tail is not a clause
 *   "The buyer — a clinic owner — signs the check." parenthetical — a pair, not a break
 *   "cost—benefit tradeoffs matter here."           tight dash — a compound, not a break
 *   "Priced $99–399/mo across the incumbents."      tight en dash — a range
 *   "RageQuit Radar — Stack Exchange Rescue Queue"  inside a name — masked before we get here
 *
 * Rewriting those produced "Incumbents charge $99. 399 per month.",
 * "The buyer. A clinic owner. Signs the check." and a renamed product.
 */
function normalizeClauseDashes(text: string): string {
  // Split on sentence boundaries (keeping them) so a PAIR of dashes can be recognised
  // inside the sentence that owns it rather than across the whole passage. The ROUND-BRACKET
  // depth is carried ACROSS that split, because a parenthetical can hold a full stop:
  // "(QuickBooks, Xero. Which lack consolidation)" would otherwise start the next chunk at
  // depth 0 and read as unbracketed prose.
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
 * "per-ID/unverified)" with no opener — cannot drive the count negative and re-enable the
 * split for the rest of the field.
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
 * RELATIVE PRONOUNS CANNOT OPEN A SENTENCE. A tail that starts with one is not a clause of
 * its own — it modifies the noun phrase the dash just interrupted — so a period leaves a
 * fragment: `…still requires TWO people physically present at the tablet — which means the
 * modal case…` became "…at the tablet. Which means the modal case…", the same dangling-phrase
 * defect the four whole-sentence rules above exist to prevent, in LLM prose no constant can
 * cover. A COMMA is the correct joint for a non-restrictive relative clause, so these tails
 * keep their clause AND still lose the em dash — the sentence rules' outcome, reached by rule.
 *
 * WHAT THE CORPUS ACTUALLY CONTAINS, STATED WITHOUT THE ROUND-7 GLOSS. Over the 2,113
 * distinct idea-field values plus the 137 `fatal_assumptions[].assumption` values under
 * `output/`, 13 tails open with a relative pronoun and all 13 are `which`. `who`, `whom` and
 * `whose` occur ZERO times as a tail — round 7 said this list was "cut from the corpus", and
 * for three of its four members that is simply not true; they are here from grammar, against
 * a latent hazard. They stay, because the cost of a member that never fires is nothing and
 * the cost of a missing one is a shipped fragment.
 *
 * The subordinating conjunctions are deliberately NOT here: `because` occurs twice and both
 * times inside a parenthetical PAIR the rule already declines to touch,
 * `while`/`although`/`whereas`/`though` occur zero times, and the tails that look like
 * subordinators in the data are complete sentences that SHOULD split — `If vLLM upstream
 * improves docs, the SEO moat erodes.`, `When a parent can't complete their assigned shift,
 * RakeProof lets them post it…`. `that` is excluded for the same reason: its one occurrence
 * is the determiner in `That missing data slice is the moat`, and demoting that to a comma
 * would be a splice.
 */
const RELATIVE_PRONOUN = /^(?:which|who|whom|whose)$/i;

/**
 * A PARTICIPIAL TAIL IS A FRAGMENT TOO, AND THE PRONOUN CLASS NEVER SAW IT. Reading all 572
 * tails rather than counting function words, 28 open with an `-ing` word and 23 of those are
 * participial adjuncts on the clause the dash interrupted — shipped verbatim as
 *
 *     "This wins on vertical workflow. Owning the multi-entity consolidation process…"
 *     "GapSignal's edge is the coverage-gap methodology. Comparing GDELT news volume…"
 *     "What rivals miss is the explainable evidence queue. Clustering and routing mentions…"
 *
 * The other 5 are GERUND SUBJECTS of a clause that stands on its own, and a comma there is a
 * splice: "The pain is severe. Losing reviews when a listing vanishes is a high-severity,
 * irreversible loss." is right exactly as it is.
 *
 * The two readings are separated by a finite BE outside any relative clause: the gerund
 * subject always reaches its own predicate ("…legitimacy IS a creative inversion"), the
 * adjunct only ever reaches one inside a relative ("…queue WHERE human approval IS a
 * first-class control"). Measured on those 28: 21 adjuncts joined, 5 gerund subjects left to
 * split, and TWO residual errors that are stated here rather than papered over —
 * "scraping for factual pricing data poses low ToS risk" is a gerund subject whose predicate
 * is not a BE, so it is joined into a splice; "resolving aliases and company relationships
 * before feedback is clustered, producing…" reaches a BE inside a `before` clause, so it
 * keeps its fragment. Separating those two needs a parser, not a longer word list.
 *
 * THE BE TEST ONLY LOOKS FOR A RELATIVE CLAUSE, AND THAT IS AS FAR AS IT CAN GO. A BE
 * reached through any OTHER kind of subordinate or coordinated clause is not the `-ing`
 * head's own predicate either, so "— routing mentions when the reviewer is offline." and
 * "— clustering mentions, and the result is faster triage." are adjuncts that this function
 * splits. Widening `RELATIVE_MARKER` to the subordinators and coordinators (when, while,
 * after, before, unless, because, and, but) is the obvious fix and it is WRONG: the module's
 * own measured gerund-subject case, "Losing reviews when a listing vanishes is a
 * high-severity, irreversible loss.", reaches its BE through exactly that `when`, and would
 * flip from a correct split to a comma splice. A modifier inside the subject NP and a
 * subordinate clause after the predicate are the same token sequence; only a parse
 * separates them. Both shapes are absent from the corpus and both are left alone.
 */
const PARTICIPLE_TAIL = /^[a-z][a-z'’-]*ing$/;
const FINITE_BE = /\b(?:is|are|was|were)\b/i;
const RELATIVE_MARKER = /\b(?:that|which|who|whom|whose|where)\b/i;

/**
 * `-ing`-final words that are COMMON NOUNS in this domain, never participles. The shape test
 * above is purely orthographic, so "The moat is thin — marketing owns the channel" reads as
 * an adjunct and is joined into a comma splice. The BE test does not save it: "marketing IS
 * the channel" is caught, "marketing OWNS the channel" is not — the same hole as the
 * disclosed "scraping … poses low ToS risk" residual, reached from the other side.
 *
 * ZERO corpus instances today, in either direction: no value under `output/` opens a dash
 * tail with any of these, so this list changes nothing that ships and costs nothing to carry.
 * It is here because one LLM rephrasing puts a noun in that slot.
 *
 * WHAT IS DELIBERATELY NOT ON IT, AND WHY. The `-ing`-final PRONOUNS (something, nothing,
 * anything, everything) and the preposition `during` look like the same class and are not:
 * a dash tail opening with one of them is an APPOSITIVE or a fronted adjunct, where the comma
 * this function produces is the correct reading. The corpus has exactly one, and it is right
 * as it stands — "…ties costing to batch-level SOPs — something no single incumbent
 * connects." joins to "…SOPs, something no single incumbent connects." Stop-listing it would
 * print a capitalised fragment instead. A noun SUBJECT is the risk; a pronoun APPOSITIVE is
 * not.
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
      // A DASH INSIDE AN UNCLOSED BRACKET IS NOT A SENTENCE BOUNDARY. The pipeline writes
      // "user-submitted content (Reddit, GitHub issues, forums, pastebins — all public,
      // free)" and "Angle: novel_differentiation (weak moat — by elimination)"; splitting
      // there printed "(weak moat. By elimination)" — a full stop inside a parenthesis, and
      // a fragment on both sides of it.
      // `offset + 1` because the match STARTS on the character before the dash, and on the
      // commonest shape in the data that character is the closing bracket itself:
      // "Stripe Connect API (official) — revenue events". Measuring to `offset` alone left
      // that bracket open and declined 6 splits that were never inside one.
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
 * Both consumers split on it (NicheRealityCheck drops the prefix, the job page turns it
 * into "Strong: …"), so normalising that one dash away here would break their parsing and
 * lose the rating word.
 *
 * The producer emits it in three shapes: the authored " — ", the ": " that
 * `_without_long_dashes` leaves on the paying-wallet path, and the tight "Strong—x" the LLM
 * can return. Only the spaced form survives the job page's `\s+[-–—]\s+` conversion, so a
 * tight dash reached the reader as "Strong—automating inventory". Re-emit the canonical
 * spaced form and sanitise the tail; the dash is gone by the time either consumer renders.
 */
const FIT_HEADLINE = /^(software\s+fit:\s*)([^—–:-]+?)\s*[—–:-]+\s*([\s\S]*)$/i;

export function buyerFacingVerdictHeadline(value: string): string {
  const match = value.match(FIT_HEADLINE);
  if (!match) return buyerFacingVerdictNarrative(value);
  return `${match[1]}${match[2].trim()} — ${buyerFacingVerdictNarrative(match[3])}`;
}

export function buyerFacingNicheDifficultyVerdict(
  verdict: NicheDifficultyVerdict | null | undefined,
): NicheDifficultyVerdict | null {
  if (!verdict) return null;
  return {
    ...verdict,
    headline: buyerFacingVerdictHeadline(verdict.headline),
    // THE GLOSS FORKS HERE, PER FIELD. The narrative and the headline talk about the dataset
    // a product would have to build; the three below talk about the run's own evidence. One
    // gloss for all five printed the wrong noun to the buyer — see `RESEARCH_CORPUS_GLOSS`.
    narrative_summary: buyerFacingVerdictNarrative(verdict.narrative_summary),
    key_challenges: (verdict.key_challenges ?? []).map(buyerFacingResearchProse),
    key_strengths: verdict.key_strengths?.map(buyerFacingResearchProse),
    buyer_class_note: verdict.buyer_class_note
      ? buyerFacingResearchProse(verdict.buyer_class_note)
      : verdict.buyer_class_note,
  };
}

/**
 * Sanitise the report ONCE, where it enters the UI, instead of at each render site.
 *
 * Three consecutive rounds fixed this leak at a call site and watched it reappear one
 * layer up: SelectionWorkbench, then NicheRealityCheck, then ReportBrief's
 * "Decision-changing risks" list and ReportContent's portfolio note — the last two on the
 * paid Deep Research brief, printing "The corpus drifts from the stated audience — tighten
 * the wedge…" verbatim. Rewriting at the boundary makes every current AND future consumer
 * of these fields safe without knowing this module exists.
 *
 * FOUR FIELDS, NOT TWO, AND THE OTHER TWO WERE A SIBLING SURFACE OF THE SHORTLIST'S. The
 * report also carries `data_quality_summary.quality_caveats` and `user_adjustments`, printed
 * here by `CoverageNotes.svelte` and by ReportContent's `user_adjustments?.join(" ")`. Both
 * printed the string as it arrived: over the 165 distinct values of those two fields under
 * `output/`, 71 carried a producer phrase and 73 a raw em/en dash on this surface, while the
 * SAME values were already being sanitised on the shortlist. They go through
 * `buyerFacingCoverageNote`, which is the shortlist's own function, moved into this module so
 * the two surfaces cannot answer differently.
 *
 * WHY ONLY THESE FIELDS, AND WHY THIS VOCABULARY IS NOT IN `humanizeReportProse`. It is not
 * because the rest of the report is clean: ~8,800 jargon instances live in fields no
 * sanitizer reaches. Lifting these rules into `humanizeReportProse`'s deep walk was measured
 * over every run under `output/` and REJECTED — the words are not unambiguous. "Cold start"
 * is the pipeline's term for "no data yet" in the fields above, and Kubernetes/serverless
 * terminology in `rationale`, `pricing_strategy` and `differentiation_factors` on
 * infrastructure niches, where the walk turned "reducing cold start and inference latency"
 * into "reducing up-front data and inference latency" — 161 instances. "Corpus" splits the
 * same way, which is why the gloss above is chosen per surface. A field-scoped sanitizer can
 * know which sense it is reading; an unconditional deep walk cannot.
 *
 * Returns the input untouched when nothing changed, so identity comparisons and `$derived`
 * memoisation downstream still hold.
 */
export function buyerFacingReport<T extends Report>(report: T): T {
  const verdict = report.niche_difficulty_verdict;
  const summary = report.idea_portfolio_summary;
  const nextVerdict = verdict ? buyerFacingNicheDifficultyVerdict(verdict) : verdict;
  // THE DATASET READING, NOT THE EVIDENCE ONE. `idea_portfolio_summary` is the Stage-5
  // analyst narrative ABOUT the ideas, and its "corpus" is the dataset a product would have
  // to build, exactly as `narrative_summary`'s is: all 3 corpus occurrences over the 26
  // distinct values under `output/` read "requiring a massive new data corpus", "tools that
  // seed a data corpus", "lack the necessary data corpus". It sat on the evidence gloss and
  // was safe only by accident — every one of those 3 arrives as the `data corpus` compound,
  // which is resolved above the fork and so reads the same on either branch. A bare or
  // modified "corpus" in this field would have printed "collected evidence" to the buyer.
  const nextSummary = summary ? buyerFacingVerdictNarrative(summary) : summary;

  const verdictChanged =
    !!verdict && JSON.stringify(nextVerdict) !== JSON.stringify(verdict);
  const summaryChanged = nextSummary !== summary;

  const caveats = report.data_quality_summary?.quality_caveats;
  // Fall back to the raw entry: a rule that emptied a caveat would lose the buyer's content.
  const nextCaveats = caveats?.map((note) => buyerFacingCoverageNote(note) || note);
  const caveatsChanged = !!caveats && !!nextCaveats
    && nextCaveats.some((note, index) => note !== caveats[index]);

  const adjustments = report.user_adjustments;
  const nextAdjustments = adjustments?.map((note) => buyerFacingCoverageNote(note) || note);
  const adjustmentsChanged = !!adjustments && !!nextAdjustments
    && nextAdjustments.some((note, index) => note !== adjustments[index]);

  if (!verdictChanged && !summaryChanged && !caveatsChanged && !adjustmentsChanged) {
    return report;
  }

  return {
    ...report,
    ...(verdictChanged ? { niche_difficulty_verdict: nextVerdict! } : {}),
    ...(summaryChanged ? { idea_portfolio_summary: nextSummary } : {}),
    ...(caveatsChanged
      ? {
        data_quality_summary: {
          ...report.data_quality_summary!,
          quality_caveats: nextCaveats!,
        },
      }
      : {}),
    ...(adjustmentsChanged ? { user_adjustments: nextAdjustments! } : {}),
  };
}
