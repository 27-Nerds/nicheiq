/**
 * REGRESSION ORACLE — the strings under test are CAPTURED, never hand-written.
 *
 * Round 3's test lived in SelectionWorkbench.test.ts under the name "from the real
 * exemplar" while every em dash in its fixture had been rewritten to a colon so the
 * sanitizer's regex would match. That is how a rule keyed on `yet:` shipped green against a
 * pipeline that emits `yet —`, and how "a data research evidence that doesn't exist yet"
 * reached paying users.
 *
 * Round 4 replaced that with a byte-equality check against the run checkpoint on disk. But
 * `output/` is gitignored and this repo has NO frontend CI (`.github/workflows/` holds only
 * `backend.yml`, paths-filtered to `backend/**`), so the check ran on exactly one machine
 * and silently degraded to `expect(headline).toContain("Software Fit:")` everywhere else. A
 * test that skips itself is the doctored-fixture hole in a new costume.
 *
 * So the fixture is now anchored to the PRODUCER instead of to a run artifact:
 * `src/nicheiq/utils/niche_difficulty.py` is checked in, so `producerProse()` below always
 * runs, everywhere. It proves (a) the exact sentences this module rewrites are sentences
 * the producer actually authors, and (b) the separator family those rules are keyed on is
 * the family `_without_long_dashes` actually emits. Round 3 assumed a colon; round 4
 * assumed a dash; neither read the producer. This test reads it on every run.
 *
 * If the pipeline's wording moves, these tests fail — and they cannot be "fixed" by editing
 * the strings, because the strings are asserted against the pipeline.
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import ts from "typescript";
import {
  buyerFacingIdeaProse,
  buyerFacingNicheDifficultyVerdict,
  buyerFacingReport,
  buyerFacingResearchProse,
  buyerFacingSolutionPreview,
  buyerFacingVerdictHeadline,
  buyerFacingVerdictNarrative,
} from "$lib/selection/buyerFacingResearchProse";
import type { NicheDifficultyVerdict, Report } from "$lib/types/report";
import type { SolutionPreview } from "$lib/types/job";
import exemplar from "./fixtures/nicheDifficultyVerdict.exemplar.json";
import pipelineIdeaTheses from "$lib/types/__tests__/fixtures/pipelineIdeaTheses.json";
import captured from "./fixtures/runArtifacts.captured.json";

/** vitest runs with `frontend/` as cwd; the pipeline lives at the repo root. */
const PRODUCER = resolve(process.cwd(), "../src/nicheiq/utils/niche_difficulty.py");

/**
 * Everything the finding named, plus the em/en dashes that must never reach UI copy.
 * `cold[- ]start` covers the spaced form `niche_difficulty.py:1123` emits inside
 * "that's frictions (cold start, crowded tooling)", which the hyphen-only pattern missed.
 */
const PIPELINE_VOCABULARY =
  /\bcorpus\b|\bcorpora\b|cold[- ]start|web-verified|paid wedge|Thin early signal|seed it|scrape it|\bwedge\b/i;
const UI_DASHES = /[—–]/;

const rawVerdict = exemplar.niche_difficulty_verdict as NicheDifficultyVerdict;
const rawPortfolioSummary = exemplar.idea_portfolio_summary;

/** Exactly what NicheRealityCheck puts on screen for the headline. */
function renderedHeadline(headline: string): string {
  return headline.replace(/^software\s+fit:\s*[^—–-]+[—–-]\s*/i, "").trim() || headline;
}

/**
 * Every prose sentence the producer can author, with Python's implicit string
 * concatenation resolved — the constants are written as adjacent literals across several
 * source lines, so a naive literal scan would only ever see fragments.
 */
function producerProse(source: string): string {
  const LITERAL = /"((?:[^"\\\n]|\\.)*)"/g;
  const sentences: string[] = [];
  let buffer = "";
  let previousEnd = -1;
  let match: RegExpExecArray | null;
  while ((match = LITERAL.exec(source))) {
    // Whitespace joins two literals, and so does an `f`/`r` prefix on the continuation —
    // `_incumbent_density_challenge` is three f-string lines, and treating the `f` as a
    // break left the interpolated sentence permanently in fragments.
    const adjacent = previousEnd >= 0
      && /^\s*[frbu]{0,2}$/i.test(source.slice(previousEnd, match.index));
    if (adjacent) {
      buffer += match[1];
    } else {
      if (buffer) sentences.push(buffer);
      buffer = match[1];
    }
    previousEnd = LITERAL.lastIndex;
  }
  if (buffer) sentences.push(buffer);
  return sentences.join("\n").replace(/\\(["\\])/g, "$1");
}

const producerSource = readFileSync(PRODUCER, "utf8");
const producer = producerProse(producerSource);

/**
 * The provenance test above can only anchor a fixture field the producer authors as a
 * CONSTANT. Two of the exemplar's fields are f-strings with an interpolated count
 * (`_incumbent_density_challenge`, niche_difficulty.py:242), so `toContain` can never match
 * them and a doctored fixture there would have passed unnoticed — round 5's stated
 * limitation. Turning the templated sentence into a matcher (`{expr}` -> `.+?`) closes it:
 * the numbers are free, every other character is the producer's.
 *
 * It has to be the RIGHT template, found by a literal the producer owns and ANCHORED at both
 * ends. A first cut asked whether ANY templated line matched, and every producer f-string
 * that begins or ends with a slot collapses to a `.+?` that matches anything — so a
 * doctored fixture still passed. That is the same vacuity this file exists to prevent.
 */
function producerTemplate(anchor: string): RegExp {
  const line = producer
    .split("\n")
    .find((candidate) => candidate.includes(anchor) && /\{[^{}]+\}/.test(candidate));
  if (!line) throw new Error(`the producer no longer authors an f-string around: ${anchor}`);
  const escaped = line.replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/\\\{[^{}]*\\\}/g, ".+?");
  return new RegExp(`^${escaped}$`);
}

/** Look the capture up by the artifact path it was copied from, never by index. */
function capturedField(path: string, needle: string): string {
  const hit = captured.find((entry) => entry.path === path && entry.value.includes(needle));
  if (!hit) throw new Error(`fixture lost its capture: ${path} / ${needle}`);
  return hit.value;
}

describe("the producer this module is keyed on", () => {
  it("authors every sentence the whole-sentence rules rewrite", () => {
    // Each entry is the AUTHORED form (spaced em dash). If a constant is reworded or its
    // separator changes, the matching rule in buyerFacingResearchProse.ts is now dead and
    // this fails — which is the failure round 3 shipped instead of.
    const authored = [
      "Most ideas need a data corpus that doesn't exist yet — plan a cold-start play "
        + "(seed it, scrape it, or partner) before the product is useful.",
      "Usable data is reachable without a heavy cold-start lift.",
      "Most products in this niche would be used episodically — opened around an event, "
        + "idle between events.",
      "Buyers here are small-business operators — price-aware but used to paying",
      "Buyers here are indie/hobbyist builders spending personal money episodically — "
        + "historically a low-price-ceiling segment",
      "Buyers here are consumers — low price points and high support load,",
      "Thin early signal; Deep Research validates.",
    ];
    for (const sentence of authored) expect(producer).toContain(sentence);
  });

  it("authors every word-level term the vocabulary rules rewrite", () => {
    for (const term of [
      "data corpus",
      "corpus evidence gap",
      "corpus purchase-intent signal",
      "web-verified prices",
      "tools web-verified",
      "paid wedge",
      "tighten the wedge before choosing a product.",
      "pick the wedge carefully.",
      "cold-start",
      // The SPACED form the hyphen-only rule missed (niche_difficulty.py:1123).
      "(cold start, crowded tooling)",
    ]) {
      expect(producer).toContain(term);
    }
  });

  it("emits every separator the rules accept, and no other", () => {
    // `_without_long_dashes` (niche_difficulty.py:2210) is applied on the paying-wallet
    // contract path to key_challenges, key_strengths, buyer notes, headline and narrative.
    // These four rewrites ARE the separator family `SEP` encodes. Round 4's four
    // clause-continuation rules were keyed on `[—–]` only, so none of them could fire on
    // copy that had been through this function.
    expect(producerSource).toContain('.replace(" — ", ": ")');
    expect(producerSource).toContain('.replace("—", ": ")');
    expect(producerSource).toContain('.replace(" – ", "-")');
    expect(producerSource).toContain('.replace("–", "-")');
  });

  it("authors the exemplar fixture's deterministic strings verbatim", () => {
    // The fixture cannot be edited to suit the code: these four came out of the producer
    // and the producer is the thing being asserted against.
    for (const field of [
      rawVerdict.key_challenges[1],
      rawVerdict.key_strengths![0],
      rawVerdict.key_strengths![1],
      rawVerdict.buyer_class_note!,
    ]) {
      expect(producer).toContain(field);
    }
  });

  it("anchors the INTERPOLATED fixture field too, which toContain never could", () => {
    // "…(10 tools web-verified, 3 with published pricing) — …" is an f-string
    // (`_incumbent_density_challenge`, niche_difficulty.py:242). Only the counts are free.
    expect(rawVerdict.key_challenges[2]).toMatch(producerTemplate("dense tool ecosystem"));
  });
});

describe("buyerFacingResearchProse — real pipeline exemplar", () => {
  it("captures the separator the pipeline actually emits (em dash, never a colon)", () => {
    // The bug this file exists to prevent: a multi-word rule keyed on the wrong separator
    // never fires, and the word-level fallbacks produce broken English instead.
    expect(rawVerdict.key_challenges[1]).toBe(
      "Most ideas need a data corpus that doesn't exist yet — plan a cold-start "
        + "play (seed it, scrape it, or partner) before the product is useful.",
    );
  });

  it("rewrites the cold-start challenge into grammatical buyer-facing English", () => {
    expect(buyerFacingResearchProse(rawVerdict.key_challenges[1])).toBe(
      "Most ideas need a body of data that does not exist yet. Plan how to collect, "
        + "create, or obtain access to it before the product is useful.",
    );
  });

  it("leaves no pipeline vocabulary in any verdict field", () => {
    const verdict = buyerFacingNicheDifficultyVerdict(rawVerdict)!;
    const rendered = [
      renderedHeadline(verdict.headline),
      verdict.narrative_summary,
      verdict.buyer_class_note ?? "",
      ...verdict.key_challenges,
      ...(verdict.key_strengths ?? []),
      buyerFacingResearchProse(rawPortfolioSummary),
    ];

    for (const field of rendered) {
      expect(field).not.toMatch(PIPELINE_VOCABULARY);
      expect(field).not.toMatch(UI_DASHES);
    }
  });

  it("produces the exact buyer-facing prose for every exemplar challenge and strength", () => {
    const verdict = buyerFacingNicheDifficultyVerdict(rawVerdict)!;

    expect(verdict.key_challenges).toEqual([
      "The collected evidence drifts from the stated audience. Tighten the entry point "
        + "or the product will end up serving the wrong user.",
      "Most ideas need a body of data that does not exist yet. Plan how to collect, "
        + "create, or obtain access to it before the product is useful.",
      "The niche already runs a dense tool ecosystem (10 tools checked on the web, "
        + "3 with published pricing). New products compete for attention inside an "
        + "existing stack. Early evidence is limited. Deep Research can validate it.",
      "The captured discussions in this run contain no explicit purchase intent. Treat "
        + "this as a gap in the collected evidence, not proof of weak market willingness "
        + "to pay: published prices checked on the web show buyers already pay for "
        + "tooling, so subscription pricing remains viable. Validate which pain and paid "
        + "offer will convert. Early evidence is limited. Deep Research can validate it.",
    ]);

    expect(verdict.key_strengths).toEqual([
      "Most pains are workflow or data problems a tool can directly own.",
      "There's room for a genuinely novel angle, not just a clone.",
      "Buyers in this niche demonstrably pay for tooling ($99-399/mo DaySmart Vet, "
        + "$299/mo single-vet, $290/mo IDEXX Neo, $300/mo VetSnap). Willingness-to-pay is "
        + "not the primary risk. Early evidence is limited. Deep Research can validate it.",
    ]);

    expect(verdict.buyer_class_note).toBe(
      "Buyers here are small-business operators. They are price-aware but used to paying "
        + "for tools that save time or win customers.",
    );
  });

  it("keeps the headline's structural separator so both consumers can still split it", () => {
    // The job page turns "Software Fit: Strong — x" into "Strong: x"; NicheRealityCheck drops
    // the prefix. Normalising THAT dash away would lose the rating word on the job page.
    const verdict = buyerFacingNicheDifficultyVerdict(rawVerdict)!;
    expect(verdict.headline).toBe(
      "Software Fit: Strong — automating inventory and controlled substance compliance",
    );
    expect(renderedHeadline(verdict.headline)).toBe(
      "automating inventory and controlled substance compliance",
    );
  });

  it("is idempotent — a second pass changes nothing", () => {
    const once = buyerFacingNicheDifficultyVerdict(rawVerdict)!;
    expect(buyerFacingNicheDifficultyVerdict(once)).toEqual(once);
  });
});

/**
 * THE GLOSS FORKS PER FIELD, AND THE FORK IS MEASURED, NOT ASSERTED. An earlier round put all
 * five verdict fields on the evidence reading on the strength of ONE `key_challenges` value.
 * Counted over every distinct value of each field under `output/`: 21 of the 28
 * `narrative_summary` values say "corpus"/"corpora" and every one means the dataset a product
 * would have to build; `headline` says neither word in any of its 28; `key_challenges` carries
 * the evidence reading in the one value below. Every input here is verbatim from `output/`.
 */
describe("buyerFacingVerdictNarrative — the narrative's corpus is a dataset", () => {
  it("glosses the bare noun as a dataset, article-adjacent or not", () => {
    expect(buyerFacingVerdictNarrative(
      "Focus your efforts on ideas that utilize existing reachable data rather than those "
        + "requiring a new corpus, and consider usage-based pricing models.",
    )).toBe(
      "Focus your efforts on ideas that utilize existing reachable data rather than those "
        + "requiring a new dataset, and consider usage-based pricing models.",
    );
    expect(buyerFacingVerdictNarrative(
      "Many concepts require a corpus that does not yet exist to be truly useful.",
    )).toBe("Many concepts require a dataset that does not yet exist to be truly useful.");
  });

  it("matches the PLURAL lemma, which no rule reached before", () => {
    // `\bcorpus\b` cannot match "corpora" — they diverge at the fifth letter — so both of the
    // narratives carrying it shipped the producer's own word to the buyer.
    expect(buyerFacingVerdictNarrative(
      "Many effective solutions require data corpora that do not currently exist.",
    )).toBe("Many effective solutions require bodies of data that do not currently exist.");
    expect(buyerFacingResearchProse("The corpora disagree.")).toBe(
      "The bodies of evidence disagree.",
    );
  });

  it("leaves key_challenges on the evidence reading, on the same verdict", () => {
    const verdict = buyerFacingNicheDifficultyVerdict({
      ...rawVerdict,
      narrative_summary:
        "Many concepts require a corpus that does not yet exist to be truly useful.",
      key_challenges: [
        "The corpus drifts from the stated audience — tighten the wedge or the product will "
          + "end up serving the wrong user.",
      ],
    })!;
    expect(verdict.narrative_summary).toContain("require a dataset that does not yet exist");
    expect(verdict.key_challenges[0]).toBe(
      "The collected evidence drifts from the stated audience. Tighten the entry point or the "
        + "product will end up serving the wrong user.",
    );
  });

  it("never leaves a mass noun under an indefinite article", () => {
    // "a new collected evidence" is what the adjacency-bound article rule shipped. The count
    // head is owed through a modifier run, and the article agrees with what now follows it.
    expect(buyerFacingResearchProse("Ideas requiring a new corpus are the risky ones.")).toBe(
      "Ideas requiring a new body of evidence are the risky ones.",
    );
    expect(buyerFacingResearchProse("Ideas requiring a new, unproven corpus are risky.")).toBe(
      "Ideas requiring a new, unproven body of evidence are risky.",
    );
    expect(buyerFacingResearchProse("This needs an unproven corpus.")).toBe(
      "This needs an unproven body of evidence.",
    );
    // A determiner ends the article's own noun phrase: no count head is owed here.
    expect(buyerFacingResearchProse("Build a tool that indexes the corpus.")).toBe(
      "Build a tool that indexes the collected evidence.",
    );
  });
});

describe("buyerFacingVerdictHeadline — every separator the producer can leave", () => {
  // The job page converts `\s+[-–—]\s+`, so a TIGHT dash escapes it and reaches the reader
  // as "Strong—automating inventory". The paying-wallet path leaves a colon instead
  // (`_without_long_dashes`), which that conversion never sees either. All three shapes must
  // leave here as the one canonical spaced form both consumers parse.
  const CANONICAL = "Software Fit: Strong — automating inventory";

  it.each([
    ["tight em dash", "Software Fit: Strong—automating inventory"],
    ["spaced em dash", "Software Fit: Strong — automating inventory"],
    ["paying-wallet colon", "Software Fit: Strong: automating inventory"],
    ["en dash", "Software Fit: Strong – automating inventory"],
  ])("normalises the %s form", (_label, input) => {
    expect(buyerFacingVerdictHeadline(input)).toBe(CANONICAL);
    expect(buyerFacingVerdictHeadline(CANONICAL)).toBe(CANONICAL);
  });

  it("leaves a headline with no separator alone", () => {
    expect(buyerFacingVerdictHeadline("Software Fit: Moderate")).toBe("Software Fit: Moderate");
  });

  it("still sanitises the tail, on the NARRATIVE's reading of the noun", () => {
    // The headline and the narrative are one LLM pair in `niche_difficulty.py`, and the
    // verdict's narrative means the dataset a product would have to build — see
    // `RESEARCH_CORPUS_GLOSS`. No real headline says "corpus" (0 of the 28 distinct values
    // under `output/`); this input is here for the tight separator.
    expect(buyerFacingVerdictHeadline("Software Fit: Hard—a paid wedge over a corpus")).toBe(
      "Software Fit: Hard — a paid offer over a dataset",
    );
  });
});

describe("buyerFacingResearchProse — pipeline constants outside this exemplar", () => {
  // Captured from src/nicheiq/utils/niche_difficulty.py. Every one of these can reach a
  // verdict on a different niche. Each is exercised twice: as AUTHORED (spaced em dash),
  // and as the producer's own `_without_long_dashes` rewrite (colon), which is what lands
  // on disk whenever the paying-wallet commercial contract applies.
  //
  // The third column is the colon path's expected output. It differs from the second
  // wherever the sentence has no dedicated rewrite and only the generic dash break would
  // have fired: a producer colon is grammatical punctuation on its own, so it is LEFT
  // ALONE. Rewriting every colon would be the same over-broad mistake the em-dash rule
  // made. What must never differ is that both paths are free of pipeline vocabulary.
  const CASES: [string, string, string][] = [
    [
      "The stated audience is too broad to support one coherent buyer recommendation — "
        + "tighten the wedge before choosing a product.",
      "The stated audience is too broad to support one coherent buyer recommendation. "
        + "Tighten the entry point before choosing a product.",
      "The stated audience is too broad to support one coherent buyer recommendation: "
        + "tighten the entry point before choosing a product.",
    ],
    [
      "Most products in this niche would be used episodically — opened around an event, "
        + "idle between events. Engagement restarts at each event rather than running "
        + "continuously.",
      "Most products in this niche would be used episodically, opened around an event, "
        + "idle between events. Engagement restarts at each event rather than running "
        + "continuously.",
      "Most products in this niche would be used episodically, opened around an event, "
        + "idle between events. Engagement restarts at each event rather than running "
        + "continuously.",
    ],
    [
      "Usable data is reachable without a heavy cold-start lift.",
      "Usable data is reachable without a heavy up-front data-collection lift.",
      "Usable data is reachable without a heavy up-front data-collection lift.",
    ],
    [
      "Community spend norms point to a free-tool culture (free plugins dominate) — a paid "
        + "wedge must beat the free route. Thin early signal; Deep Research validates.",
      "Community spend norms point to a free-tool culture (free plugins dominate). A paid "
        + "offer must beat the free route. Early evidence is limited. Deep Research can "
        + "validate it.",
      "Community spend norms point to a free-tool culture (free plugins dominate): a paid "
        + "offer must beat the free route. Early evidence is limited. Deep Research can "
        + "validate it.",
    ],
    [
      "Buyers here are consumers — low price points and high support load, and the "
        + "products already serving them carry a wide range of commercial shapes.",
      "Buyers here are consumers, with low price points and high support load, and the "
        + "products already serving them carry a wide range of commercial shapes.",
      "Buyers here are consumers, with low price points and high support load, and the "
        + "products already serving them carry a wide range of commercial shapes.",
    ],
    [
      "Buyers here are indie/hobbyist builders spending personal money episodically — "
        + "historically a low-price-ceiling segment, and the person who uses the tool is "
        + "the person whose own money funds it.",
      "Buyers here are indie/hobbyist builders spending personal money episodically, "
        + "historically a low-price-ceiling segment, and the person who uses the tool is "
        + "the person whose own money funds it.",
      "Buyers here are indie/hobbyist builders spending personal money episodically, "
        + "historically a low-price-ceiling segment, and the person who uses the tool is "
        + "the person whose own money funds it.",
    ],
    [
      "Buyers here are small-business operators — price-aware but used to paying for tools "
        + "that save time or win customers.",
      "Buyers here are small-business operators. They are price-aware but used to paying "
        + "for tools that save time or win customers.",
      "Buyers here are small-business operators. They are price-aware but used to paying "
        + "for tools that save time or win customers.",
    ],
    [
      "This niche is a moderate fit for software. A tool earns its keep, but the easy "
        + "framings are weaker than they look — pick the wedge carefully. Overall "
        + "difficulty still rates high — that's frictions (cold start, crowded tooling), "
        + "not a worse fit; see the factors below.",
      "This niche is a moderate fit for software. A tool earns its keep, but the easy "
        + "framings are weaker than they look. Pick the entry point carefully. Overall "
        + "difficulty still rates high. That's frictions (up-front data, crowded tooling), "
        + "not a worse fit; see the factors below.",
      "This niche is a moderate fit for software. A tool earns its keep, but the easy "
        + "framings are weaker than they look: pick the entry point carefully. Overall "
        + "difficulty still rates high: that's frictions (up-front data, crowded tooling), "
        + "not a worse fit; see the factors below.",
    ],
  ];

  /** Exactly what `_without_long_dashes` (niche_difficulty.py:2210) does to persisted copy. */
  function asWalletContractCopy(text: string): string {
    return text
      .split(" — ").join(": ")
      .split("—").join(": ")
      .split(" – ").join("-")
      .split("–").join("-");
  }

  it.each(CASES)("rewrites the authored form of case %#", (input, expected) => {
    const output = buyerFacingResearchProse(input);
    expect(output).toBe(expected);
    expect(output).not.toMatch(PIPELINE_VOCABULARY);
    expect(output).not.toMatch(UI_DASHES);
    expect(buyerFacingResearchProse(output)).toBe(output);
  });

  it.each(CASES)(
    "rewrites the paying-wallet colon form of case %#",
    (input, _authored, colonExpected) => {
      const persisted = asWalletContractCopy(input);
      const output = buyerFacingResearchProse(persisted);
      expect(output).toBe(colonExpected);
      expect(output).not.toMatch(PIPELINE_VOCABULARY);
      expect(output).not.toMatch(UI_DASHES);
      expect(buyerFacingResearchProse(output)).toBe(output);
    },
  );

  it("does not split a tight en-dash price range into two sentences", () => {
    expect(buyerFacingResearchProse("Priced $99–399/mo across the incumbents.")).toBe(
      "Priced $99–399/mo across the incumbents.",
    );
  });

  it("expands the WTP abbreviation", () => {
    expect(buyerFacingResearchProse("Its WTP is unknown.")).toBe(
      "Its willingness to pay is unknown.",
    );
  });
});

describe("article agreement — the defect round 3 shipped and round 4 reintroduced", () => {
  // Round 3: "plan a cold-start play" -> "plan a early data play".
  // Round 4: `wedge` -> "entry point" and `corpus` -> "collected evidence" put the same
  // mismatch back, on rules added by the round that fixed it.
  it.each([
    ["Find a wedge into the workflow.", "Find an entry point into the workflow."],
    ["A wedge is needed here.", "An entry point is needed here."],
    [
      "You must assemble a corpus before launch.",
      "You must assemble a body of evidence before launch.",
    ],
    ["Plan a cold-start play before launch.", "Plan an up-front data play before launch."],
    ["A cold-start play is unavoidable.", "An up-front data play is unavoidable."],
    // The article is only wrong when the replaced noun sits right after it.
    ["Find a sharper wedge, or move on.", "Find a sharper entry point, or move on."],
    ["Validate which paid wedge converts.", "Validate which paid offer converts."],
    ["Treat this as a corpus evidence gap.", "Treat this as a gap in the collected evidence."],
    ["The corpus drifts from the audience.", "The collected evidence drifts from the audience."],
  ])("rewrites %j without breaking the article", (input, expected) => {
    const output = buyerFacingResearchProse(input);
    expect(output).toBe(expected);
    expect(output).not.toMatch(/\ba (?=[aeiou])/i);
    expect(buyerFacingResearchProse(output)).toBe(output);
  });

  it("keeps a title-cased product name out of the vocabulary rules", () => {
    // "Cold Start Atlas" is an idea NAME. A case-insensitive spaced rule renamed it.
    expect(
      buyerFacingResearchProse("Cold Start Atlas was killed during the portfolio review."),
    ).toBe("Cold Start Atlas was killed during the portfolio review.");
  });

  it("keeps the corpus purchase-intent phrase in the right word order", () => {
    expect(
      buyerFacingResearchProse(
        "Strong corpus purchase-intent signal: buyers carry purchase intent across pains.",
      ),
    ).toBe(
      "Strong purchase-intent signal in the captured discussions: buyers carry purchase "
        + "intent across pains.",
    );
  });
});

describe("dash normalisation only breaks a real clause boundary", () => {
  // `narrative_summary` is stored verbatim from the LLM (niche_difficulty.py:2735), so
  // paired, tight and numeric dashes are live inputs. Rewriting EVERY em dash produced the
  // left column below.
  it.each([
    ["numeric range", "Incumbents charge $99 – 399 per month."],
    ["parenthetical pair", "The buyer — a clinic owner — signs the check."],
    ["tight compound", "cost—benefit tradeoffs matter here."],
    ["quoted aside", 'Operators say — "we already pay" — every time.'],
    ["tight en-dash range", "Priced $99–399/mo across the incumbents."],
  ])("leaves the %s untouched", (_label, input) => {
    expect(buyerFacingResearchProse(input)).toBe(input);
  });

  it("does not uppercase a token that already owns its casing", () => {
    expect(buyerFacingResearchProse("Two vendors dominate — iOS-first tools own it.")).toBe(
      "Two vendors dominate. iOS-first tools own it.",
    );
  });

  it("consumes a doubled dash rather than leaving one behind", () => {
    expect(buyerFacingResearchProse("Costs rise —— margins fall.")).toBe(
      "Costs rise. Margins fall.",
    );
  });

  it("still breaks a lone spaced clause dash", () => {
    expect(buyerFacingResearchProse("Two vendors dominate — nobody serves clinics.")).toBe(
      "Two vendors dominate. Nobody serves clinics.",
    );
  });
});

describe("a relative-pronoun tail is joined, not split", () => {
  /**
   * The fragment class the dash rule introduced on LLM prose, which no whole-sentence
   * constant can cover. `pipelineIdeaTheses.json` is a byte-exact capture of one run's
   * `idea_theses`; this assumption is the value SelectionWorkbench renders in its thesis
   * band, so the render test and this unit test are reading the same bytes.
   */
  const CAPTURED_ASSUMPTION = (pipelineIdeaTheses.theses as { fatal_assumptions?: { assumption: string }[] }[])
    .flatMap((thesis) => thesis.fatal_assumptions ?? [])
    .map((entry) => entry.assumption)
    .find((assumption) => / [—–] which\b/.test(assumption));

  it("keeps the captured relative clause attached to the noun it modifies", () => {
    // Not hand-written: if the capture stops carrying this shape, the guard is unexercised
    // and this fails rather than passing vacuously.
    expect(CAPTURED_ASSUMPTION).toBeDefined();
    const output = buyerFacingIdeaProse(CAPTURED_ASSUMPTION);
    expect(output).toContain("at the tablet, which means the modal case");
    expect(output).not.toContain(". Which means");
    expect(output).not.toContain("—");
  });

  it.each(["which", "who", "whom", "whose"])(
    "joins a %s tail with a comma instead of opening a sentence with it",
    (pronoun) => {
      expect(buyerFacingIdeaProse(`Two vendors dominate — ${pronoun} both charge $99.`)).toBe(
        `Two vendors dominate, ${pronoun} both charge $99.`,
      );
    },
  );

  /**
   * The exclusions, each quoted from the corpus the rule was cut against. These tails ARE
   * independent sentences, so demoting them to a comma would introduce a splice — the
   * mirror-image defect. `that` is the determiner here, not a relative pronoun.
   */
  it.each([
    [
      "a demonstrative determiner",
      "Rivals report overall cooking performance but never hot-spot maps — that missing data "
        + "slice is the moat.",
      "Rivals report overall cooking performance but never hot-spot maps. That missing data "
        + "slice is the moat.",
    ],
    [
      "a conditional",
      "The rules engine is a decision tree — if vLLM upstream improves docs, the SEO moat "
        + "erodes.",
      "The rules engine is a decision tree. If vLLM upstream improves docs, the SEO moat "
        + "erodes.",
    ],
    [
      "a temporal clause with its own main clause",
      "Bake in a duty-swap marketplace — when a parent can't complete their shift, the tool "
        + "reposts it.",
      "Bake in a duty-swap marketplace. When a parent can't complete their shift, the tool "
        + "reposts it.",
    ],
  ])("still splits %s", (_label, input, expected) => {
    expect(buyerFacingIdeaProse(input)).toBe(expected);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// Round 6. Every string below was COPIED out of a real run artifact by
// `r6_fixture.py` into `fixtures/runArtifacts.captured.json`, which records the file and
// the JSON path each one came from. `output/` is gitignored, so the copy is the only thing
// that can be checked in — but nothing here is an approximation of the pipeline's wording,
// and `capturedField` looks each one up by its artifact path so a silent edit that moves a
// string to a different field throws instead of passing.
// ─────────────────────────────────────────────────────────────────────────────

describe("proper names are not vocabulary", () => {
  // Round 5 had no concept of a name. It split idea names in half at their own em dash and
  // rewrote the word "Cold-Start" out of the ideas named after it.
  const RAGEQUIT_NAME = capturedField(
    ".alternative_solutions[5].solution_name",
    "RageQuit Radar",
  );
  const RAGEQUIT_SUMMARY = capturedField(".idea_portfolio_summary", "RageQuit Radar");
  const VET_SUMMARY = capturedField(".idea_portfolio_summary", "VetCSReconciliationLog");

  it("keeps an idea name whose own separator is a spaced em dash", () => {
    // The name and the prose that names it are two separate captures from the SAME run, so
    // this cannot be satisfied by an expectation written to match the code.
    expect(RAGEQUIT_NAME).toBe("RageQuit Radar — Stack Exchange Rescue Queue");
    expect(RAGEQUIT_SUMMARY).toContain(RAGEQUIT_NAME);

    const output = buyerFacingResearchProse(RAGEQUIT_SUMMARY);
    expect(output).toContain(RAGEQUIT_NAME);
    expect(output).not.toContain("RageQuit Radar. Stack Exchange");
  });

  it("keeps every name in a LIST of ideas, including the one carrying a dash", () => {
    const output = buyerFacingResearchProse(VET_SUMMARY);
    for (const name of [
      "VetCSReconciliationLog — Offline-First Audit Ledger",
      "VetUnitEconomics Validator",
      "RxNormPIMSMismatch",
      "VetDrugMigrationMapper",
      "NarcVault Vet",
      "VetControlled Closebook",
      "Inventory Ally",
    ]) {
      expect(output).toContain(name);
    }
    expect(output).not.toContain("VetCSReconciliationLog. Offline-First");
  });

  it("rewrites the vocabulary in the same field it protects the names in", () => {
    // Both halves must hold at once, which is the whole difficulty: this summary ends
    // "…weak buyer payability and high cold-start data requirements."
    const output = buyerFacingResearchProse(VET_SUMMARY);
    expect(output).toContain("high up-front data requirements");
    expect(output).not.toContain("cold-start");
    expect(output).not.toContain("data corpus");
    expect(buyerFacingResearchProse(output)).toBe(output);
  });

  it("does not rename an idea called after the vocabulary", () => {
    // The exact rename the round-5 case hack existed to prevent, and re-introduced by
    // keying on case: this one starts the sentence, so the producer's own position guard
    // would have let it through.
    expect(buyerFacingResearchProse("Cold-Start Atlas is the strongest idea.")).toBe(
      "Cold-Start Atlas is the strongest idea.",
    );
    expect(buyerFacingResearchProse("Cold Start Atlas was killed in review.")).toBe(
      "Cold Start Atlas was killed in review.",
    );
  });

  it("leaves a real competitor named out of this module's vocabulary alone", () => {
    const competitor = capturedField(
      ".solution_landscapes[0].competitors[2].name",
      "Cold Start",
    );
    expect(competitor).toBe("BentoML Cold Start Optimization");
    expect(buyerFacingResearchProse(competitor)).toBe(competitor);
  });

  it("still breaks a clause dash when a name merely FOLLOWS it", () => {
    // A name after the dash is not a name-internal dash. Masking must not swallow the
    // break, and the name keeps the casing it owns.
    expect(buyerFacingResearchProse("Two vendors dominate — iOS-first tools own it.")).toBe(
      "Two vendors dominate. iOS-first tools own it.",
    );
  });
});

describe("cold-start is matched case-insensitively", () => {
  // Round 5 matched the spaced form case-SENSITIVELY to protect "Cold Start Atlas", and so
  // never fired on the capitalised forms. The corpus carries 259 of them; the mask above is
  // the discriminator that lets the rules be case-blind.
  it("rewrites the sentence-initial form the pipeline writes into fatal assumptions", () => {
    const assumption = capturedField(
      ".idea_theses.theses[0].fatal_assumptions[2].assumption",
      "Cold start:",
    );
    expect(assumption).toBe(
      "Cold start: the product has no data until a customer supplies it "
        + "— User-submitted bot recipes",
    );
    // The whole stanza is a producer constant (idea_theses.py:282) whose tail is a "; "-joined
    // LIST of source names, so it is rewritten as a label rather than word by word. Round 7
    // rewrote only the "Cold start" token and left "User-submitted bot recipes" dangling
    // after a full stop.
    expect(buyerFacingResearchProse(assumption)).toBe(
      "The product has no data until a customer supplies it. It would run on: "
        + "User-submitted bot recipes",
    );
  });

  it("rewrites the sentence-initial form the pipeline writes into acquisition notes", () => {
    const notes = capturedField(
      ".solution_ideas[0].data_acquisition_notes",
      "Cold-start corpus",
    );
    // THROUGH THE ENTRY POINT THAT ACTUALLY READS THIS FIELD. `data_acquisition_notes` is an
    // idea field — `buyerFacingSolutionPreview` hands it to `buyerFacingIdeaProse`, never to
    // the evidence entry point. It was asserted here on `buyerFacingResearchProse` while
    // `cold-start corpus` sat above the per-field fork and both branches answered "dataset";
    // now that the compound has moved into each gloss the two branches differ, and this test
    // has to name the branch this field is on or it certifies the wrong one.
    expect(buyerFacingIdeaProse(notes)).toContain("Up-front dataset needed.");
    // The other branch reads the same words as the run's own evidence, which is why the
    // compound could not simply be deleted: without it the `cold[-\s]start` tail rule stacks.
    expect(buyerFacingResearchProse(notes)).toContain("Up-front body of evidence needed.");
    expect(buyerFacingResearchProse(notes)).not.toMatch(/\b(\w+)\s+\1\b/i);
  });

  it.each([
    ["Cold start costs dominate the first year.", "Up-front data costs dominate the first year."],
    ["The Cold Start problem is real.", "The up-front data problem is real."],
    ["COLD START RISK IS HIGH.", "Up-front data RISK IS HIGH."],
    ["A Cold-start lift is needed.", "An up-front data lift is needed."],
  ])("rewrites %j", (input, expected) => {
    const output = buyerFacingResearchProse(input);
    expect(output).toBe(expected);
    expect(buyerFacingResearchProse(output)).toBe(output);
  });
});

describe("no two rules stack inside one phrase", () => {
  const NARRATIVE = capturedField(
    ".niche_difficulty_verdict.narrative_summary",
    "cold-start data corpus",
  );

  it("rewrites a real narrative carrying both a compound and a bare wedge", () => {
    expect(buyerFacingResearchProse(NARRATIVE)).toBe(
      "You should build a free tool with built-in distribution, such as a lead-generation "
        + "feature or a sponsorship model, because the niche lacks strong buying signals "
        + "for subscription pricing. While software can directly own most of these pains, "
        + "you face high difficulty due to a dense tool ecosystem and the need for an "
        + "up-front body of data that does not yet exist. Focus on a specific entry point "
        + "to avoid drifting away from your target audience, as the current market is "
        + "crowded with shipping incumbents that make differentiation your primary "
        + "challenge.",
    );
  });

  it.each([
    // `data corpus` -> "body of data" then `cold-start` -> "up-front data" = word salad.
    ["high cold-start data requirements", "high up-front data requirements"],
    [
      "Focus on solving the cold-start data problem early",
      "Focus on solving the up-front data problem early",
    ],
    [
      "Most ideas require a cold-start data play, so prefer existing data.",
      "Most ideas require an up-front data play, so prefer existing data.",
    ],
    // The EVIDENCE reading — this block runs `buyerFacingResearchProse`. The dataset reading
    // of the same phrase is pinned on `buyerFacingIdeaProse` above.
    ["a cold-start corpus is unavoidable", "an up-front body of evidence is unavoidable"],
    // Standing alone it is a noun, and "an up-front data," is not English.
    [
      "Design for a cold-start, as many viable ideas fail there.",
      "Design for an up-front data-collection effort, as many viable ideas fail there.",
    ],
  ])("rewrites %j without doubling a word", (input, expected) => {
    const output = buyerFacingResearchProse(input);
    expect(output).toBe(expected);
    expect(output).not.toMatch(/\b(\w+)\s+\1\b/i);
    expect(output).not.toMatch(/\ba (?=[aeiou])/i);
    expect(buyerFacingResearchProse(output)).toBe(output);
  });
});

describe("a replacement keeps the sentence's capital letter", () => {
  // Round 5 replaced the matched span verbatim, so any field OPENING with a vocabulary term
  // lost its capital: "entry point selection matters."
  it.each([
    ["Wedge selection matters.", "Entry point selection matters."],
    ["Corpus coverage is thin.", "Collected evidence coverage is thin."],
    ["Web-verified prices are listed.", "Published prices checked on the web are listed."],
    ["WTP is unknown for this pain.", "Willingness to pay is unknown for this pain."],
    // Mid-sentence keeps its own casing — this is preservation, not capitalisation.
    ["The wedge matters. The corpus is thin.", "The entry point matters. The collected evidence is thin."],
  ])("rewrites %j", (input, expected) => {
    const output = buyerFacingResearchProse(input);
    expect(output).toBe(expected);
    expect(output).not.toMatch(/(^|[.!?]\s+)[a-z]/);
    expect(buyerFacingResearchProse(output)).toBe(output);
  });
});

describe("web-verified is used attributively too, whatever round 4's comment said", () => {
  it("does not produce 'a checked on the web competitor'", () => {
    expect(buyerFacingResearchProse("a web-verified competitor")).toBe("a verified competitor");
  });

  it("rewrites the real competitor description that carries the attributive form", () => {
    const description = capturedField(
      ".solution_landscapes[1].competitors[0].description",
      "web-verified incumbent list",
    );
    const output = buyerFacingResearchProse(description);
    expect(output).toContain("Source: user-provided verified incumbent list.");
    expect(output).not.toContain("checked on the web incumbent");
    expect(buyerFacingResearchProse(output)).toBe(output);
  });

  it("keeps the postpositive form, which reads correctly as it is", () => {
    expect(buyerFacingResearchProse("10 tools web-verified, 3 with published pricing")).toBe(
      "10 tools checked on the web, 3 with published pricing",
    );
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// Round 8
// ─────────────────────────────────────────────────────────────────────────────

describe("the article-adjacent form runs in BOTH directions", () => {
  // Rounds 3, 4 and 7 each shipped a rule whose replacement changed the noun's shape and
  // left the article behind. The survivor narrows "an" to "a" rather than widening it — the
  // vowel is in the word being REPLACED, which is why the doctrine's "$1n" shape never caught
  // it. `enumerable corpus` was the other member of this pair until its replacement was found
  // to be the wrong NOUN; the phrase now takes each branch's bare gloss, and "an enumerable
  // dataset" keeps the article it arrived with, so there is nothing left here to repair.
  it("does not print 'an search opportunity'", () => {
    const out = buyerFacingIdeaProse("Model-level aggregation as an SEO surface.");
    expect(out).toContain("a search opportunity");
    expect(out).not.toMatch(/\ban search/i);
  });

  it("keeps the bare form for positions with no article", () => {
    expect(buyerFacingIdeaProse("The SEO surface is thin.")).toContain(
      "The search opportunity is thin.",
    );
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// Round 9 — the NOUN, not the vocabulary and not the article
// ─────────────────────────────────────────────────────────────────────────────

/**
 * WHY THIS BLOCK EXISTS AND WHY IT ASSERTS WHAT IT DOES. Reverting round 8's
 * `enumerable corpus` -> "searchable evidence library" rule and re-running the whole suite
 * moved the two token/grammar oracles this module is otherwise policed by — the mass-noun
 * -under-article check and the vocabulary token list — by ZERO on all 28 narratives. They
 * cannot see this defect class: every candidate noun is a well-formed count noun spelled with
 * ordinary words, so the phrase stays grammatical and jargon-free while meaning the wrong
 * thing. Only a semantic assertion catches it, and an assertion that checks the ARTICLE in
 * front of the noun — which is what the two tests deleted above did — passes on any noun at
 * all. So these pin the noun itself, on the producer's own strings.
 */
describe("`enumerable corpus` keeps the SEO-enumeration sense on the idea path", () => {
  const UNDER_AN = capturedField(
    ".alternative_solutions[3].angle_rationale",
    "an enumerable corpus",
  );
  const UNDER_THE = capturedField(
    ".alternative_solutions[11].angle_rationale",
    "the enumerable corpus",
  );
  const BOTH_SENSES = capturedField(
    ".alternative_solutions[6].angle_rationale",
    "a finite evidence corpus, not a scalable enumerable corpus",
  );

  // `angle_rationale` is printed to the buyer at SolutionDetailContent.svelte, through
  // `buyerFacingSolutionPreview` -> `buyerFacingIdeaProse`. Measured over `output/`, all 110
  // `enumerable corpus` instances live in idea fields and every one names the enumerable set
  // of ENTITIES that yields programmatic-SEO pages; none names the run's own evidence.
  it.each([
    ["under an indefinite article", UNDER_AN],
    ["under a definite article", UNDER_THE],
  ])("reads it as a dataset %s", (_label, value) => {
    const out = buyerFacingIdeaProse(value);
    expect(out).toContain("enumerable dataset");
    // THE NOUN, PINNED. Round 8 shipped "searchable evidence library" here and both tests
    // that covered it passed, because both asserted only the article in front of it.
    expect(out).not.toMatch(/evidence|library|archive/i);
  });

  // "enumerable" is the load-bearing claim: enumerability is what the SEO score is about
  // ("The 0.85 SEO scalability reflects a genuinely enumerable corpus"). A gloss that keeps
  // the right sense but drops the adjective loses the reason the score is what it is.
  it.each([
    ["under an indefinite article", UNDER_AN],
    ["under a definite article", UNDER_THE],
  ])("keeps the word 'enumerable' %s", (_label, value) => {
    expect(buyerFacingIdeaProse(value)).toMatch(/\benumerable\b/);
  });

  it("keeps the two senses apart when one clause carries both", () => {
    // The producer contrasts them itself: a finite EVIDENCE corpus against a scalable
    // ENUMERABLE one. Round 8 printed "a finite evidence dataset, not a scalable searchable
    // evidence library" — which inverts the contrast, since the evidence word ends up on the
    // side the producer meant as the dataset.
    const out = buyerFacingIdeaProse(BOTH_SENSES);
    expect(out).toContain("a finite evidence dataset, not a scalable enumerable dataset");
    expect(out).not.toContain("evidence library");
  });

  // The phrase never occurs in an evidence-gloss field, so there is no measured reading to
  // pin on that branch — but the branch must still answer with ITS noun and not the other's.
  it("answers with the evidence noun on the evidence branch", () => {
    expect(buyerFacingResearchProse("Ideas that target an enumerable corpus of parts."))
      .toBe("Ideas that target an enumerable body of evidence of parts.");
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// The structural gate on every rule table that runs ABOVE the per-field fork
// ─────────────────────────────────────────────────────────────────────────────

/**
 * THE THREE TABLES `vocabularyRules` COMPOSES ABOVE THE CORPUS GLOSS, so each of them is
 * shared by `RESEARCH_RULES`, `VERDICT_NARRATIVE_RULES` and `IDEA_RULES` alike. Round 9 gated
 * one of the three; the other two were as exposed as it was.
 */
const SHARED_TABLES = ["SENTENCE_RULES", "CORPUS_COMPOUND_RULES", "VOCABULARY_TAIL_RULES"];

/** The two tables the fork chooses BETWEEN. Read to prove what the fork is actually about. */
const GLOSS_TABLES = ["RESEARCH_CORPUS_GLOSS", "IDEA_CORPUS_GLOSS"];

type ParsedRule = { table: string; index: number; pattern: string; replacement: string };

/**
 * WHY THIS IS AN AST WALK AND NOT A REGEX OVER THE SOURCE TEXT.
 *
 * Round 9's gate pulled the table out of the file with one single-line regex,
 * `/\[(\/.+?\/[gi]*), "(.*?)"\],/g`, and reported `offenders: []` — the passing answer — for
 * four different ways of writing the very rule it exists to reject:
 *
 *   1. the rule written across MULTIPLE LINES. `.` does not cross a newline, so the rule was
 *      never parsed at all. THREE sibling tables in this same module are written that way, so
 *      this is the house style, not an evasion.
 *   2. a SINGLE-QUOTED replacement. The pattern demanded a `"`.
 *   3. a replacement built by CONCATENATION, which every sentence rule in the file uses.
 *   4. the count check was `rules.length === 0`, so a parser that silently found 5 of 7 rules
 *      passed — the same blind metric the whole finding is about.
 *
 * `ts.createSourceFile` reads the declaration the compiler reads. Every element of the array
 * literal is decoded or THROWN on, and the decoded count is asserted against the element count,
 * so "the parser did not see it" is not a reachable state.
 *
 * `backend/src/utils/__tests__/buyerFacingCaveat.drift.test.ts` is the in-repo precedent.
 */
function patternSource(node: ts.Node, source: ts.SourceFile): string {
  // A regex literal's own SOURCE TEXT: `\b` must stay two characters, not become a backspace.
  if (node.kind === ts.SyntaxKind.RegularExpressionLiteral) return node.getText(source);
  if (
    ts.isTaggedTemplateExpression(node)
    && node.tag.getText(source) === "String.raw"
    && ts.isNoSubstitutionTemplateLiteral(node.template)
  ) {
    return node.template.getText(source).slice(1, -1);
  }
  if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) return node.text;
  if (ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.PlusToken) {
    return patternSource(node.left, source) + patternSource(node.right, source);
  }
  throw new Error(`the gate cannot read this rule PATTERN: ${node.getText(source)}`);
}

function stringValue(node: ts.Node, source: ts.SourceFile): string {
  if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) return node.text;
  if (ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.PlusToken) {
    return stringValue(node.left, source) + stringValue(node.right, source);
  }
  throw new Error(`the gate cannot read this rule REPLACEMENT: ${node.getText(source)}`);
}

/** `[/x/gi, "y"]` and `sentenceRule("x", "y")` are the two shapes these tables are written in. */
function decodeRule(
  element: ts.Expression,
  source: ts.SourceFile,
): { pattern: string; replacement: string } {
  if (ts.isArrayLiteralExpression(element) && element.elements.length === 2) {
    return {
      pattern: patternSource(element.elements[0], source),
      replacement: stringValue(element.elements[1], source),
    };
  }
  if (
    ts.isCallExpression(element)
    && element.expression.getText(source) === "sentenceRule"
    && element.arguments.length === 2
  ) {
    return {
      pattern: patternSource(element.arguments[0], source),
      replacement: stringValue(element.arguments[1], source),
    };
  }
  throw new Error(`the gate cannot read this rule SHAPE: ${element.getText(source)}`);
}

function parseTables(sourceText: string, tables: string[]): ParsedRule[] {
  const source = ts.createSourceFile(
    "buyerFacingResearchProse.ts",
    sourceText,
    ts.ScriptTarget.Latest,
    /* setParentNodes */ true,
  );
  const rules: ParsedRule[] = [];
  const seen = new Set<string>();
  for (const statement of source.statements) {
    if (!ts.isVariableStatement(statement)) continue;
    for (const declaration of statement.declarationList.declarations) {
      if (!ts.isIdentifier(declaration.name) || !tables.includes(declaration.name.text)) continue;
      const table = declaration.name.text;
      seen.add(table);
      const initializer = declaration.initializer;
      if (!initializer || !ts.isArrayLiteralExpression(initializer)) {
        throw new Error(`${table} is no longer an array literal`);
      }
      const before = rules.length;
      initializer.elements.forEach((element, index) => {
        rules.push({ table, index, ...decodeRule(element, source) });
      });
      // THE COUNT CHECK THAT MATTERS: every element of the declared table, not "more than
      // zero". `decodeRule` throws rather than skipping, so this can only fail if that
      // contract is ever loosened — and then it fails LOUDLY instead of under-reporting.
      if (rules.length - before !== initializer.elements.length) {
        throw new Error(
          `${table}: parsed ${rules.length - before} of ${initializer.elements.length} rules`,
        );
      }
    }
  }
  const missing = tables.filter((table) => !seen.has(table));
  if (missing.length) throw new Error(`renamed, removed or reshaped: ${missing.join(", ")}`);
  return rules;
}

/**
 * A LOOKAROUND IS AN ASSERTION, NOT A MATCH. `/\b(?!dataset)seed corpus\b/gi -> "dataset"`
 * places the sense noun in a NEGATIVE lookahead — the producer never wrote it, the rule
 * asserts its ABSENCE — and round 9's word scan read it as "the pattern already contains
 * dataset" and cleared the rule. Lookaheads and lookbehinds are dropped before any word is
 * read from a pattern.
 */
function stripLookarounds(pattern: string): string {
  let out = "";
  for (let index = 0; index < pattern.length; index += 1) {
    if (pattern[index] === "\\") {
      out += pattern.slice(index, index + 2);
      index += 1;
      continue;
    }
    if (/^\(\?<?[=!]/.test(pattern.slice(index, index + 4))) {
      let depth = 0;
      let end = index;
      for (; end < pattern.length; end += 1) {
        if (pattern[end] === "\\") { end += 1; continue; }
        if (pattern[end] === "(") depth += 1;
        else if (pattern[end] === ")") { depth -= 1; if (depth === 0) break; }
      }
      out += " ";
      index = end;
      continue;
    }
    out += pattern[index];
  }
  return out;
}

/**
 * Words of at least two letters. The pattern is read as SOURCE TEXT, so `\b` must be blanked
 * before the scan or `\bdata corpora\b` reads as "bdata"; `$1`/`$2` are blanked in a
 * replacement for the same reason, and the one-letter residue of `$1n` (the article-agreement
 * suffix) falls out with the length bound. Hyphenated compounds split, so "up-front" is
 * adjudicated as "up" and "front" rather than as an atom the next rewording would rename.
 */
const ruleWords = (text: string) => (text.toLowerCase().match(/[a-z]+/g) ?? [])
  .filter((word) => word.length > 1);
const patternWords = (pattern: string) => ruleWords(stripLookarounds(pattern).replace(/\\./g, " "));
const replacementWords = (replacement: string) => ruleWords(replacement.replace(/\$\d/g, " "));

/** The noun the per-field fork exists to resolve. Pinned against the glosses below. */
const AMBIGUOUS_NOUN = /\b(?:corpus|corpora)\b/;

/**
 * THE EXCEPTION CENSUS, AND WHY IT IS SMALL ENOUGH TO ADJUDICATE ONE WORD AT A TIME.
 *
 * The predicate is: an in-scope rule's replacement may contain no word that its own pattern
 * does not supply. That is strictly stronger than round 9's closed list of "sense nouns",
 * which let `"body of research quotes"` through simply because nobody had thought of
 * "quotes". The cost is that grammar repair — the whole point of these rules — introduces
 * words too, so the words repair legitimately needs are enumerated here and NOWHERE else.
 *
 * Every entry is adjudicated, and the census is pinned in BOTH directions: an unlisted word
 * fails the gate below, and a listed word that no rule needs any more fails it too, so the
 * list cannot rot into a rubber stamp the way a list-as-contract has twice on this finding.
 */
const SENSE_NEUTRAL_REPAIR = new Set([
  // Function words. Syntax only: they name nothing and cannot pick a reading of "corpus".
  "in", "the", "of", "to", "not", "does", "how",
  // COUNT HEADS. "collected evidence" and "data" are MASS nouns and cannot follow an
  // indefinite article or take a plural, so "body of …" / "bodies of …" is the article
  // repair this table exists for. The noun itself still has to come from the pattern.
  "body", "bodies",
  // The modifier on the evidence noun the pattern ALREADY supplies — `corpus evidence gap`
  // names "evidence" itself, so "collected" qualifies a sense the producer chose, it does
  // not choose one.
  "collected",
  // The two halves of "up-front", which is the gloss of "cold-start" — a word the pattern
  // supplies in every rule that uses it. It says WHEN the data is needed, not what it is.
  "up", "front",
  // The verbs of the instruction clause in the one whole-sentence rule in scope ("Plan how to
  // collect, create, or obtain access to it"). They name an ACTION to take about the body of
  // data the pattern already named; none of them is a name for the corpus.
  "collect", "create", "obtain", "access",
]);

describe("no rule above the per-field fork may choose a corpus SENSE", () => {
  /**
   * THE STRUCTURAL GATE, not another instance fix. Three rounds in a row put a sense-bearing
   * rule where the sense is not yet known — these tables run above the fork in
   * `vocabularyRules` and are shared by both glosses — and each round only removed the one
   * instance the previous critic named.
   *
   * THE SCOPE PROPERTY, AND THE FALSE POSITIVE IT EXISTS TO AVOID. Widening the gate to all
   * three shared tables under round 9's predicate immediately flags
   * `[/\bcold[-\s]start\b/gi, "up-front data"]`, which introduces "data" and is entirely
   * correct: "cold start" is unambiguous, and the rule cannot land on either side of a fork
   * about a word it never matches. The usual response is to loosen the predicate until
   * nothing fires, which yields a decorative gate. Instead the SCOPE is cut on a property:
   *
   *     only a rule whose pattern can match the ambiguous noun can resolve it.
   *
   * and that property is not an assumption — the test below reads both gloss tables and
   * proves the fork is about `corpus`/`corpora` and nothing else. Add a second ambiguous term
   * to the glosses and that test fails until this gate's scope is widened with it.
   */
  const proseSource = () => readFileSync(
    resolve(process.cwd(), "src/lib/selection/buyerFacingResearchProse.ts"),
    "utf8",
  );

  /** The gate itself, as a function, so the tests below can run it on a MUTATED source. */
  function gateOffenders(sourceText: string): string[] {
    return parseTables(sourceText, SHARED_TABLES)
      .filter((rule) => AMBIGUOUS_NOUN.test(patternWords(rule.pattern).join(" ")))
      .flatMap((rule) => {
        const supplied = new Set(patternWords(rule.pattern));
        const introduced = [...new Set(replacementWords(rule.replacement))]
          .filter((word) => !supplied.has(word) && !SENSE_NEUTRAL_REPAIR.has(word));
        if (!introduced.length) return [];
        return [`${rule.table}[${rule.index}] ${rule.pattern} -> "${rule.replacement}"`
          + ` introduces ${introduced.join(", ")}`];
      });
  }

  it("is keyed on the fork's real subject: both glosses match `corpus`/`corpora`, nothing else", () => {
    // THIS IS WHAT LICENSES THE SCOPE CUT ABOVE. If a gloss ever forks a second word, a
    // shared rule could choose ITS sense while matching no corpus at all, and the scope test
    // would wave it through. Then this fails first.
    for (const rule of parseTables(proseSource(), GLOSS_TABLES)) {
      expect(
        patternWords(rule.pattern).join(" "),
        `${rule.table}[${rule.index}] forks a word this gate's scope does not cover`,
      ).toMatch(AMBIGUOUS_NOUN);
    }
  });

  it("parses every rule of every shared table, or throws", () => {
    const rules = parseTables(proseSource(), SHARED_TABLES);
    // Not `> 0`: the count is asserted per table against the array literal's own element
    // count inside `parseTables`, and the tables must all be non-trivial here as well.
    for (const table of SHARED_TABLES) {
      expect(rules.filter((rule) => rule.table === table).length, table).toBeGreaterThan(1);
    }
    expect(new Set(rules.map((rule) => rule.table))).toEqual(new Set(SHARED_TABLES));
  });

  it("re-uses only the words the producer already wrote in the matched phrase", () => {
    expect(
      gateOffenders(proseSource()),
      "a rule above the per-field fork chose a corpus sense — move it into "
        + "RESEARCH_CORPUS_GLOSS and IDEA_CORPUS_GLOSS, which know which field they are reading",
    ).toEqual([]);
  });

  it("carries no exception the rules no longer need", () => {
    // The other direction of the census pin. Delete or reword a rule and the entry that
    // justified its repair word has to go with it, so the list cannot silently accumulate
    // permission for rules nobody reviewed.
    const inScope = parseTables(proseSource(), SHARED_TABLES)
      .filter((rule) => AMBIGUOUS_NOUN.test(patternWords(rule.pattern).join(" ")));
    const unused = [...SENSE_NEUTRAL_REPAIR].filter((word) => !inScope.some((rule) => {
      const supplied = new Set(patternWords(rule.pattern));
      return !supplied.has(word) && replacementWords(rule.replacement).includes(word);
    }));
    expect(unused, "census entries no in-scope rule needs any more").toEqual([]);
  });
});

/**
 * THE GATE ABOVE, GATED. Round 9's gate had no test of its own: `it("has teeth")` re-ran the
 * PREDICATE on a hardcoded pair and never touched the parser, which is the part that broke.
 * Each case below mutates the real source — in memory, so the checked-in file is never
 * touched — and asserts the gate NAMES the injected rule.
 */
describe("the structural gate catches what it is supposed to catch", () => {
  const proseSource = () => readFileSync(
    resolve(process.cwd(), "src/lib/selection/buyerFacingResearchProse.ts"),
    "utf8",
  );

  /** Where a new compound would naturally be written: at the head of the table. */
  const ANCHOR = "const CORPUS_COMPOUND_RULES: [RegExp, string][] = [";

  function withRule(table: string, rule: string): string {
    const source = proseSource();
    const anchor = table === "CORPUS_COMPOUND_RULES"
      ? ANCHOR
      : `const ${table}: [RegExp, string][] = [`;
    expect(source.includes(anchor), `${table} was reshaped — re-key this mutation`).toBe(true);
    return source.replace(anchor, `${anchor}\n${rule}`);
  }

  function gateOffenders(sourceText: string): string[] {
    return parseTables(sourceText, SHARED_TABLES)
      .filter((rule) => AMBIGUOUS_NOUN.test(patternWords(rule.pattern).join(" ")))
      .flatMap((rule) => {
        const supplied = new Set(patternWords(rule.pattern));
        const introduced = [...new Set(replacementWords(rule.replacement))]
          .filter((word) => !supplied.has(word) && !SENSE_NEUTRAL_REPAIR.has(word));
        return introduced.length ? [`${rule.table}[${rule.index}]`] : [];
      });
  }

  it.each([
    // 1. THE MULTI-LINE FORM, which three sibling tables in this module already use — the
    //    single-line regex parsed 7 rules and reported no offender.
    [
      "written across multiple lines",
      "  [\n    /\\benumerable corpus\\b/gi,\n    \"searchable evidence library\",\n  ],",
    ],
    // 2. A SINGLE-QUOTED replacement. Same rule, one character of quoting different.
    ["with a single-quoted replacement", "  [/\\benumerable corpus\\b/gi, 'searchable evidence library'],"],
    // 3. THE SENSE NOUN INSIDE A NEGATIVE LOOKAHEAD — textually present in the pattern,
    //    asserted ABSENT by it. The old word scan read it as licensed.
    ["hiding its sense noun in a lookahead", "  [/\\b(?!dataset)seed corpus\\b/gi, \"dataset\"],"],
    // 4. A SENSE NOUN THAT WAS NOT ON THE OLD CLOSED LIST. The predicate no longer has a list
    //    of nouns to be incomplete about: anything the pattern does not supply is an offender.
    ["choosing a noun no list anticipated", "  [/\\bseed corpus\\b/gi, \"body of research quotes\"],"],
    // 5. THE REPLACEMENT BUILT BY CONCATENATION, which every sentence rule in the file uses.
    [
      "with a concatenated replacement",
      "  [/\\bseed corpus\\b/gi, \"searchable evidence \"\n    + \"library\"],",
    ],
  ])("names a compound rule %s", (_label, rule) => {
    expect(gateOffenders(proseSource())).toEqual([]);
    expect(gateOffenders(withRule("CORPUS_COMPOUND_RULES", rule))).toEqual(["CORPUS_COMPOUND_RULES[0]"]);
  });

  it("covers the other two shared tables, not only the compounds", () => {
    // `SENTENCE_RULES` and `VOCABULARY_TAIL_RULES` are composed above the fork by
    // `vocabularyRules` exactly as the compounds are, and round 9's gate read neither.
    expect(gateOffenders(withRule("VOCABULARY_TAIL_RULES", "  [/\\bseed corpus\\b/gi, \"seed dataset\"],")))
      .toEqual(["VOCABULARY_TAIL_RULES[0]"]);
    expect(gateOffenders(withRule(
      "SENTENCE_RULES",
      "  sentenceRule(String.raw`The corpus is thin%tighten the wedge\\.`, \"The evidence base is thin. Tighten the wedge.\"),",
    ))).toEqual(["SENTENCE_RULES[0]"]);
  });

  it("does NOT fire on the sense-neutral rule a naive widening would flag", () => {
    // `[/\bcold[-\s]start\b/gi, "up-front data"]` introduces "data", which its own pattern
    // does not contain — and it is correct. It ships today, inside the widened scope, and the
    // gate is green above, so this is asserted directly rather than only by that greenness.
    const coldStart = parseTables(proseSource(), SHARED_TABLES)
      .find((rule) => rule.pattern === String.raw`/\bcold[-\s]start\b/gi`);
    expect(coldStart?.replacement).toBe("up-front data");
    expect(AMBIGUOUS_NOUN.test(patternWords(coldStart!.pattern).join(" "))).toBe(false);
  });

  it("refuses a rule shape it cannot read instead of skipping it", () => {
    // The failure mode round 9 shipped: a rule the parser did not understand simply vanished
    // from the count, and the gate reported the passing answer.
    const mutated = withRule("CORPUS_COMPOUND_RULES", "  ...EXTRA_COMPOUNDS,");
    expect(() => parseTables(mutated, SHARED_TABLES)).toThrow(/cannot read this rule SHAPE/);
  });
});

describe("a dash inside an unclosed bracket is not a sentence boundary", () => {
  it("does not split a parenthetical aside into two sentences", () => {
    expect(buyerFacingIdeaProse("Angle: novel_differentiation (weak moat — by elimination)."))
      .toContain("(weak moat — by elimination)");
  });

  it("does not split a bracketed source list", () => {
    const out = buyerFacingIdeaProse(
      "Product depends on user-submitted content (Reddit, GitHub issues, forums — all public).",
    );
    expect(out).toContain("(Reddit, GitHub issues, forums — all public)");
  });

  it("STILL splits when the bracket closed before the dash", () => {
    // The bracket scan starts on the character before the dash, and on the commonest
    // shape in the corpus that character IS the closing bracket.
    expect(buyerFacingIdeaProse("Stripe Connect API (official) — revenue events follow."))
      .toBe("Stripe Connect API (official). Revenue events follow.");
  });

  it("carries the depth across a full stop inside the bracket", () => {
    const out = buyerFacingIdeaProse("(Route not confirmed. The verifier failed — access is unverified)");
    expect(out).toContain("failed — access");
  });
});

describe("a participial tail is a fragment, and a gerund subject is not", () => {
  // Round 7 counted function words and found 13 tails, all `which`. Reading the tails
  // instead turns up 28 that open with an -ing word, 23 of them participial adjuncts.
  it("joins the adjunct that shipped as 'This wins on vertical workflow. Owning…'", () => {
    expect(buyerFacingIdeaProse(
      "This wins on vertical workflow — owning the multi-entity consolidation process that "
      + "sits between basic bookkeeping tools and expensive ERPs.",
    )).toBe(
      // "vertical workflow" is also de-jargoned by the angle-key rule; the assertion is on
      // the JOINT, which is the defect under test.
      "This wins on focused workflow, owning the multi-entity consolidation process that "
      + "sits between basic bookkeeping tools and expensive ERPs.",
    );
  });

  it("joins an adjunct whose only finite verb sits inside a relative clause", () => {
    expect(buyerFacingIdeaProse(
      "What rivals miss is the explainable evidence queue — clustering and routing mentions "
      + "into a small, reviewed queue where human approval is a first-class control.",
    )).toContain(
      "evidence queue, clustering and routing mentions",
    );
  });

  it("SPLITS a gerund subject that reaches its own predicate", () => {
    // "The pain is severe, losing reviews … is a … loss" would be a comma splice.
    expect(buyerFacingIdeaProse(
      "The pain is severe — losing reviews when a listing vanishes is an irreversible loss.",
    )).toBe(
      "The pain is severe. Losing reviews when a listing vanishes is an irreversible loss.",
    );
  });

  it("SPLITS a tail whose -ing word is an attributive participle, not a gerund", () => {
    expect(buyerFacingIdeaProse(
      "No incumbent covers it — existing tools are all image-processing software.",
    )).toBe(
      "No incumbent covers it. Existing tools are all image-processing software.",
    );
  });

  // The shape test is orthographic, so an -ing-final NOUN in the subject slot read as a
  // participle and was joined into a comma splice. The BE test does not catch it: the
  // predicate is not a BE. Zero corpus instances, one LLM rephrasing away.
  it("SPLITS a tail whose -ing word is a noun subject with a non-BE predicate", () => {
    expect(buyerFacingIdeaProse("The moat is thin — marketing owns the channel.")).toBe(
      "The moat is thin. Marketing owns the channel.",
    );
    expect(buyerFacingIdeaProse(
      "The moat is thin — pricing drives the whole decision.",
    )).toBe("The moat is thin. Pricing drives the whole decision.");
  });

  // The -ing-final PRONOUNS look like the same class and are not: a dash tail opening with
  // one is an appositive, where the comma is right. This is the one real corpus instance,
  // captured verbatim from
  // output/checkpoints/preview_report_… .alternative_solutions[].angle_rationale — a
  // stop-list that swept the pronouns in would print a capitalised fragment here.
  it("keeps the comma on an -ing-final PRONOUN appositive", () => {
    expect(buyerFacingIdeaProse(
      "The edge is the unified workflow that ties costing to batch-level SOPs — something "
      + "no single incumbent connects.",
    )).toBe(
      "The edge is the unified workflow that ties costing to batch-level SOPs, something "
      + "no single incumbent connects.",
    );
  });
});

describe("producer stanzas that end in a list or a label", () => {
  it("names the list rather than leaving it dangling after a full stop", () => {
    // idea_theses.py:282 — a label and a "; "-joined list of source names, 61 corpus values.
    const out = buyerFacingIdeaProse(
      "Cold start: the product has no data until a customer supplies it — User-provided CSV "
      + "files; Owner-provided property-management exports",
    );
    expect(out).toBe(
      "The product has no data until a customer supplies it. It would run on: "
      + "User-provided CSV files; Owner-provided property-management exports",
    );
  });

  it("keeps the ruled-out verdict label attached to the incumbent it names", () => {
    // Captured verbatim from `examined_ruled_out[].reason` under `output/`. The dash rule read
    // the label as a clause and printed "Already well-served. Partial by Fieldproxy: …".
    const out = buyerFacingIdeaProse(
      "Already well-served — partial by Fieldproxy: AI predicts parts needs before jobs, "
      + "adapts to technician performance. A new entrant here competes head-on with an "
      + "incumbent rather than filling a gap.",
    );
    expect(out).toBe(
      "Already well-served: partial by Fieldproxy: AI predicts parts needs before jobs, "
      + "adapts to technician performance. A new entrant here competes head-on with an "
      + "incumbent rather than filling a gap.",
    );
    expect(out).not.toContain("Already well-served. Partial");
    // Idempotent against the producer-side fix, which leaves the colon this rule emits.
    expect(buyerFacingIdeaProse(out)).toBe(out);
  });

  it("covers the `shipped by` member of the same family", () => {
    expect(buyerFacingIdeaProse(
      "Already well-served — shipped by Hootsuite: Hootsuite ships live previews.",
    )).toBe("Already well-served: shipped by Hootsuite: Hootsuite ships live previews.");
  });

  it("never leaves the snake_case angle key the pipeline stores in `winning_angle`", () => {
    // 84 corpus values print the raw enum in running prose; every other surface renders it
    // through `angleLabel`.
    expect(buyerFacingIdeaProse("Angle: distribution_seo. Nearest competitor is the docs."))
      .toBe("Angle: distribution / SEO. Nearest competitor is the docs.");
    expect(buyerFacingIdeaProse("Distribution_seo wins because the edge is a data slice."))
      .toBe("Distribution / SEO wins because the edge is a data slice.");
    expect(buyerFacingIdeaProse("Angle: novel_differentiation. The rivals are thin."))
      .toBe("Angle: distinct mechanism. The rivals are thin.");
    expect(buyerFacingIdeaProse("The edge lives in vertical_workflow depth."))
      .toBe("The edge lives in focused workflow depth.");
  });

  it("does NOT substitute a finite clause into an object slot mid-sentence", () => {
    // Round 7's unguarded rule turned 18 corpus values into "This wins on the strongest
    // available angle is a focused workflow". The label is de-jargoned; the clause is not
    // moved into a slot that cannot hold one.
    expect(buyerFacingIdeaProse("This wins on vertical workflow by elimination, as SEO is thin."))
      .toBe("This wins on focused workflow by elimination, as SEO is thin.");
    expect(buyerFacingIdeaProse("Assigned novel_differentiation by elimination as a weak moat."))
      .toBe("Assigned distinct mechanism by elimination as a weak moat.");
  });

  it("rewrites every angle name in the 'by elimination' family, snake_case included", () => {
    // unified_solution_crew.py:4889 tells the model to write the PLAIN name and it writes
    // the snake_case key anyway; round 7 covered only the spaced vertical-workflow form.
    expect(buyerFacingIdeaProse("Weak moat — novel differentiation by elimination."))
      .toBe("Weak moat. The strongest available angle is a distinct mechanism.");
    expect(buyerFacingIdeaProse("Weak moat — novel_differentiation by elimination."))
      .toBe("Weak moat. The strongest available angle is a distinct mechanism.");
    expect(buyerFacingIdeaProse("Weak moat — vertical_workflow by elimination."))
      .toBe("Weak moat. The strongest available angle is a focused workflow.");
  });

  it("joins the truncated bulk-route suffix however the 120-char cut lands", () => {
    // unified_solution_crew.py:4439 appends the suffix and then truncates the whole field.
    for (const cut of ["unver", "unverified", "unverified a", "unverified acc", "unverified access"]) {
      expect(buyerFacingIdeaProse(`Per-payer responses (per-ID lookup) — no bulk route confirmed; per-ID/${cut}`))
        .toBe(
          "Per-payer responses (per-ID lookup), with no bulk download route confirmed and "
          + "per-record access that is unverified.",
        );
    }
  });

  it("eats the head's own terminal punctuation rather than doubling it", () => {
    expect(buyerFacingIdeaProse("No bulk source exists. — no bulk route confirmed; per-ID/unverified access"))
      .toBe(
        "No bulk source exists, with no bulk download route confirmed and per-record access "
        + "that is unverified.",
      );
  });
});

describe("buyerFacingSolutionPreview — the choke point the render sites read through", () => {
  const raw: SolutionPreview = {
    solution_name: "AuditFlowPM",
    description: "Passive audit overlay.",
    angle_rationale: "The SEO surface is thin.",
    data_acquisition_notes: "Cold-start corpus required.",
    critic_concern: "build_feas of limited signals risk.",
    refine_binding_constraint: "Sharpen the wedge.",
    value_proposition: "untouched",
  };

  it("rewrites exactly the four prose fields and nothing else", () => {
    const out = buyerFacingSolutionPreview(raw);
    expect(out.angle_rationale).toBe("The search opportunity is thin.");
    expect(out.data_acquisition_notes).toBe("Up-front dataset required.");
    // NOTE the lower-case start: the pipeline writes `build_feas` in lower case, and
    // `applyWordRules` re-capitalises only a match that was capitalised itself. Asserted as
    // it actually renders rather than as it ought to read — see the report's residue list.
    expect(out.critic_concern).toBe("limited build feasibility signals risk.");
    expect(out.refine_binding_constraint).toBe("Sharpen the entry point.");
    expect(out.value_proposition).toBe("untouched");
    expect(out.solution_name).toBe("AuditFlowPM");
  });

  it("returns the SAME object when nothing changed, so identity checks downstream hold", () => {
    const clean: SolutionPreview = {
      solution_name: "AuditFlowPM",
      description: "Nothing to rewrite.",
      value_proposition: "Nothing to rewrite.",
    };
    expect(buyerFacingSolutionPreview(clean)).toBe(clean);
    const once = buyerFacingSolutionPreview(raw);
    expect(buyerFacingSolutionPreview(once)).toBe(once);
  });

  it("keeps the raw value when a rule would empty the field", () => {
    const empty: SolutionPreview = {
      solution_name: "X",
      description: "d",
      value_proposition: "v",
      critic_concern: "   ",
    };
    expect(buyerFacingSolutionPreview(empty)).toBe(empty);
  });
});

/**
 * THE REPORT BOUNDARY'S OWN ROUTING, PINNED ON A VALUE THAT DISCRIMINATES.
 *
 * `idea_portfolio_summary` reaches the buyer through TWO independent routes — this one, and
 * a `$derived` in `SelectionWorkbench.svelte` — and both were covered only against NOT BEING
 * SANITISED. Neither was covered against being on the WRONG BRANCH. Measured over the 26
 * distinct `idea_portfolio_summary` values under `output/` and the module's own fixtures, the
 * two glosses produce ZERO differences: every corpus occurrence in that field arrives as the
 * `data corpus` compound, which is resolved ABOVE the fork and so reads the same either way.
 * So swapping either route back to `buyerFacingResearchProse` left the whole suite green.
 *
 * A BARE `corpus` is the value that separates them: the dataset reading says "the recipe
 * dataset", the evidence reading says "the recipe collected evidence". It is not hypothetical
 * — 108 bare-corpus instances in the idea fields under `output/` read exactly that way, and
 * `idea_portfolio_summary` is prose ABOUT those ideas.
 */
describe("buyerFacingReport — the report boundary routes each field to its own gloss", () => {
  const BARE_CORPUS_SUMMARY =
    "The strongest candidates already own their inputs; the rest lack the recipe corpus.";

  function report(overrides: Record<string, unknown>) {
    return buyerFacingReport(overrides as unknown as Report);
  }

  it("reads `idea_portfolio_summary` as the DATASET, not as collected evidence", () => {
    const out = report({ idea_portfolio_summary: BARE_CORPUS_SUMMARY });
    expect(out.idea_portfolio_summary).toBe(
      "The strongest candidates already own their inputs; the rest lack the recipe dataset.",
    );
    // The failure this pins: `buyerFacingResearchProse` on this field prints the other noun.
    expect(buyerFacingResearchProse(BARE_CORPUS_SUMMARY))
      .toContain("the recipe collected evidence");
    expect(out.idea_portfolio_summary).not.toContain("collected evidence");
  });

  it("keeps the verdict's per-field fork at the boundary too", () => {
    const out = report({
      idea_portfolio_summary: BARE_CORPUS_SUMMARY,
      niche_difficulty_verdict: {
        headline: "Software Fit: Strong — the corpus is thin",
        narrative_summary: "Many concepts require a corpus that does not yet exist.",
        key_challenges: ["The corpus drifts from the stated audience."],
      },
    });
    const verdict = out.niche_difficulty_verdict!;
    expect(verdict.narrative_summary).toBe("Many concepts require a dataset that does not yet exist.");
    expect(verdict.headline).toBe("Software Fit: Strong — the dataset is thin");
    // …and the SAME word on the same object, one field away, keeps the evidence reading.
    expect(verdict.key_challenges[0]).toBe("The collected evidence drifts from the stated audience.");
  });

  it("routes the two caveat fields through the coverage note, not the verdict reading", () => {
    const out = report({
      data_quality_summary: { quality_caveats: ["Calibration note: the recipe corpus is thin."] },
      user_adjustments: ["Gate 2 (audience & pains): the recipe corpus is thin."],
    });
    expect(out.data_quality_summary!.quality_caveats![0])
      .toBe("Research caveat: the recipe dataset is thin.");
    expect(out.user_adjustments![0])
      .toBe("Gate 2 (audience & pains): the recipe dataset is thin.");
  });

  it("returns the SAME object when nothing changed", () => {
    const clean = { idea_portfolio_summary: "Nothing to rewrite." } as unknown as Report;
    expect(buyerFacingReport(clean)).toBe(clean);
  });
});
