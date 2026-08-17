import { describe, expect, it } from "vitest";
import type { RedTeamFinding } from "$lib/types/job";
import {
  adversarialReviewFinding,
  adversarialReviewSummary,
  adversarialReviewVerdictSummary,
  directIncumbentParity,
  incumbentParityPhrase,
  isPremiseUnproven,
  noDirectIncumbentFound,
  NONE_SURFACED_PHRASE,
  recommendationSplitNote,
  resolveAdversarialReviewPrimaryFinding,
} from "./adversarialReview";

describe("adversarial review classification", () => {
  it("keeps finding kinds closed at the TypeScript boundary", () => {
    const invalidFinding: RedTeamFinding = {
      claim: "No free tool was found.",
      // @ts-expect-error untyped prose categories must not enter the report contract
      kind: "no_free_tool_found",
    };
    expect(invalidFinding.claim).toBe("No free tool was found.");
  });

  it("renders a typed affirmative kill as verified counterevidence", () => {
    const finding = adversarialReviewFinding({
      red_team_verdict: "killed",
      red_team_findings: [{
        claim: "The incumbent already ships the same weekly compliance feed.",
        kind: "verified_incumbent_overlap",
      }],
    });

    expect(finding).toEqual({
      label: "Adversarial review: Verified incumbent overlap",
      chipLabel: "Incumbent overlap",
      details: ["The incumbent already ships the same weekly compliance feed."],
      severity: "killed",
      primary: {
        basis: "counterevidence",
        kind: "verified_incumbent_overlap",
        claim: "The incumbent already ships the same weekly compliance feed.",
        label: "Verified incumbent overlap",
        chipLabel: "Incumbent overlap",
        summaryOpener: "The adversarial review found verified incumbent overlap",
      },
    });
    expect(adversarialReviewSummary(finding!)).toContain(
      "The adversarial review found verified incumbent overlap",
    );
  });

  it("renders a typed evidence-gap weakening as incomplete evidence", () => {
    const finding = adversarialReviewFinding({
      red_team_verdict: "weakened",
      red_team_findings: [{
        claim: "The review did not establish a reachable payer.",
        kind: "evidence_gap",
      }],
    });

    expect(finding).toEqual({
      label: "Adversarial review: Evidence incomplete",
      chipLabel: "Evidence incomplete",
      details: ["The review did not establish a reachable payer."],
      severity: "weakened",
      primary: {
        basis: "incomplete_evidence",
        kind: "evidence_gap",
        claim: "The review did not establish a reachable payer.",
        label: "Evidence incomplete",
        chipLabel: "Evidence incomplete",
        summaryOpener: "The adversarial review found the decision-critical evidence incomplete",
      },
    });
    expect(adversarialReviewSummary(finding!)).toContain(
      "The adversarial review found the decision-critical evidence incomplete",
    );
  });

  it("treats a raw typed gap-only kill as an effective weakening", () => {
    const idea = {
      red_team_verdict: "killed",
      red_team_findings: [{
        claim: "The review did not establish a reachable payer.",
        kind: "evidence_gap",
      }],
    };

    expect(isPremiseUnproven(idea)).toBe(false);
    expect(adversarialReviewFinding(idea)).toMatchObject({
      label: "Adversarial review: Evidence incomplete",
      chipLabel: "Evidence incomplete",
      severity: "weakened",
      primary: { basis: "incomplete_evidence" },
    });
    expect(adversarialReviewVerdictSummary(idea)).toContain(
      "decision-critical evidence incomplete",
    );
  });

  it.each([
    {
      name: "empty typed array",
      findings: [],
      expectedLabel: "Adversarial review: Evidence incomplete",
      expectedSeverity: "weakened",
      expectedPremise: false,
      expectedDetail: "The review did not establish decision-critical evidence.",
    },
    {
      name: "all-invalid typed array",
      findings: [{ kind: "invented_kind", claim: "Injected claim." }],
      expectedLabel: "Adversarial review: Evidence incomplete",
      expectedSeverity: "weakened",
      expectedPremise: false,
      expectedDetail: "The review did not establish decision-critical evidence.",
    },
    {
      name: "evidence gap",
      findings: [{ kind: "evidence_gap", claim: "The review did not establish a payer." }],
      expectedLabel: "Adversarial review: Evidence incomplete",
      expectedSeverity: "weakened",
      expectedPremise: false,
      expectedDetail: "The review did not establish a payer.",
    },
    {
      name: "legacy null",
      findings: null,
      expectedLabel: "Adversarial review: Premise unproven",
      expectedSeverity: "killed",
      expectedPremise: true,
      expectedDetail: undefined,
    },
    {
      name: "mixed affirmative",
      findings: [
        { kind: "evidence_gap", claim: "The review did not establish a payer." },
        { kind: "verified_payer_mismatch", claim: "The user and payer are different roles." },
      ],
      expectedLabel: "Adversarial review: Verified payer mismatch",
      expectedSeverity: "killed",
      expectedPremise: true,
      expectedDetail: "The user and payer are different roles.",
    },
    {
      name: "legacy non-array",
      findings: "not a typed findings array",
      expectedLabel: "Adversarial review: Premise unproven",
      expectedSeverity: "killed",
      expectedPremise: true,
      expectedDetail: undefined,
    },
  ])("applies the shared typed-findings matrix for $name", ({
    findings,
    expectedLabel,
    expectedSeverity,
    expectedPremise,
    expectedDetail,
  }) => {
    const idea = { red_team_verdict: "killed", red_team_findings: findings };
    const finding = adversarialReviewFinding(idea);

    expect(isPremiseUnproven(idea)).toBe(expectedPremise);
    expect(finding?.label).toBe(expectedLabel);
    expect(finding?.severity).toBe(expectedSeverity);
    expect(finding?.details[0]).toBe(expectedDetail);
    if (!expectedPremise) {
      expect(adversarialReviewSummary(finding!)).toContain(
        "decision-critical evidence incomplete",
      );
      expect(adversarialReviewSummary(finding!)).not.toMatch(
        /material|objection|premise unproven/i,
      );
    }
  });

  it("uses affirmative counterevidence for a mixed killed review", () => {
    const finding = adversarialReviewFinding({
      red_team_verdict: "killed",
      red_team_findings: [
        { claim: "No free tool was found.", kind: "evidence_gap" },
        {
          claim: "A bundled incumbent alternative covers the workflow.",
          kind: "verified_free_or_bundled_alternative",
        },
      ],
    });

    expect(finding?.primary).toMatchObject({
      basis: "counterevidence",
      kind: "verified_free_or_bundled_alternative",
      claim: "A bundled incumbent alternative covers the workflow.",
    });
    expect(finding?.label).toBe(
      "Adversarial review: Verified free or bundled alternative",
    );
    expect(finding?.details[0]).toBe(
      "A bundled incumbent alternative covers the workflow.",
    );
    const summary = adversarialReviewSummary(finding!);
    expect(summary).toContain(
      "verified free or bundled alternative: A bundled incumbent alternative covers the workflow.",
    );
    expect(summary).not.toContain("verified free or bundled alternative: No free tool was found");
  });

  it("does not turn a no-free-tool evidence gap into counterevidence", () => {
    const finding = adversarialReviewFinding({
      red_team_verdict: "weakened",
      red_team_findings: [{ claim: "No free tool was found.", kind: "evidence_gap" }],
    });

    expect(finding?.primary?.basis).toBe("incomplete_evidence");
    expect(adversarialReviewSummary(finding!)).not.toContain("verified free");
  });

  it("returns one atomic primary finding for mixed gap-first input", () => {
    expect(resolveAdversarialReviewPrimaryFinding([
      { claim: "No free tool was found.", kind: "evidence_gap" },
      {
        claim: "The incumbent bundles the same workflow.",
        kind: "verified_free_or_bundled_alternative",
      },
    ])).toMatchObject({
      basis: "counterevidence",
      kind: "verified_free_or_bundled_alternative",
      claim: "The incumbent bundles the same workflow.",
      label: "Verified free or bundled alternative",
    });
  });

  it("separates a red-team evidence objection from actual incumbent parity", () => {
    const idea = {
      incumbent_parity: "shipped by evidence: the proposed source misses the buyer",
      red_team_verdict: "killed",
      red_team_caveats: ["The buyer has no public filing."],
    };

    expect(directIncumbentParity(idea)).toBeNull();
    expect(adversarialReviewFinding(idea)).toEqual({
      label: "Adversarial review: Premise unproven",
      chipLabel: "Premise unproven",
      details: [
        "The buyer has no public filing.",
        "the proposed source misses the buyer",
      ],
      severity: "killed",
    });
  });

  it("preserves actual incumbent and no-incumbent findings", () => {
    expect(directIncumbentParity({
      incumbent_parity: "shipped by Karbon: workflow automation",
    })).toBe("shipped by Karbon: workflow automation");
    expect(noDirectIncumbentFound({ incumbent_parity: "none found" })).toBe(true);
  });

  it("renders a weakened review with a citable caveat", () => {
    expect(adversarialReviewFinding({
      incumbent_parity: "partial by Karbon: workflow automation",
      red_team_verdict: "weakened",
      red_team_caveats: ["The edge may be thin."],
    })).toEqual({
      label: "Adversarial review: Weakened",
      chipLabel: "Weakened",
      details: ["The edge may be thin."],
      severity: "weakened",
    });
  });

  it("renders a killed verdict with zero caveats and no evidence marker (today's behavior)", () => {
    expect(adversarialReviewFinding({
      incumbent_parity: "none found",
      red_team_verdict: "killed",
      red_team_caveats: [],
    })).toEqual({
      label: "Adversarial review: Premise unproven",
      chipLabel: "Premise unproven",
      details: [],
      severity: "killed",
    });
  });

  it("suppresses a bare weakened verdict with no caveats and no marker", () => {
    expect(adversarialReviewFinding({
      incumbent_parity: "none found",
      red_team_verdict: "weakened",
      red_team_caveats: [],
    })).toBeNull();
  });

  it("classifies a survives verdict with an evidence marker as weakened (defensive)", () => {
    expect(adversarialReviewFinding({
      incumbent_parity: "shipped by evidence: X",
      red_team_verdict: "survives",
      red_team_caveats: [],
    })).toEqual({
      label: "Adversarial review: Survives",
      chipLabel: "Weakened",
      details: ["X"],
      severity: "weakened",
    });
  });

  it("returns null for a survives verdict without an evidence marker", () => {
    expect(adversarialReviewFinding({
      incumbent_parity: "shipped by Karbon: workflow automation",
      red_team_verdict: "survives",
      red_team_caveats: ["Some caveat that should not surface."],
    })).toBeNull();
  });

  it("rejects malformed runtime fields without calling string methods on them", () => {
    for (const malformed of [42, { unexpected: true }, null]) {
      const idea = {
        incumbent_parity: malformed,
        red_team_verdict: malformed,
        red_team_caveats: malformed,
        red_team_findings: malformed,
      };

      expect(isPremiseUnproven(idea)).toBe(false);
      expect(directIncumbentParity(idea)).toBeNull();
      expect(noDirectIncumbentFound(idea)).toBe(false);
      expect(incumbentParityPhrase(malformed)).toBe("");
      expect(adversarialReviewFinding(idea)).toBeNull();
      expect(adversarialReviewVerdictSummary(idea)).toBeNull();
    }
  });

  it("fails a malformed typed findings array soft as an effective weakening", () => {
    const idea = {
      red_team_verdict: " KILLED ",
      red_team_caveats: [null, 7, {}, "   "],
      red_team_findings: [
        null,
        7,
        { kind: "verified_incumbent_overlap", claim: 12 },
        { kind: "invented_kind", claim: "Invented evidence." },
        { kind: "evidence_gap", claim: "   " },
      ],
    };

    expect(isPremiseUnproven(idea)).toBe(false);
    expect(adversarialReviewFinding(idea)).toMatchObject({
      label: "Adversarial review: Evidence incomplete",
      chipLabel: "Evidence incomplete",
      severity: "weakened",
    });
    expect(adversarialReviewVerdictSummary(idea)).toContain(
      "decision-critical evidence incomplete",
    );
  });

  it("normalizes only valid non-empty caveats and typed finding claims", () => {
    expect(adversarialReviewFinding({
      red_team_verdict: " weakened ",
      red_team_caveats: [null, 3, {}, "  A citable caveat.  ", ""],
      red_team_findings: [
        { kind: "evidence_gap", claim: "  A missing payer link.  " },
        { kind: "verified_payer_mismatch", claim: {} },
      ],
    })).toMatchObject({
      label: "Adversarial review: Evidence incomplete",
      details: ["A missing payer link.", "A citable caveat."],
      severity: "weakened",
      primary: {
        kind: "evidence_gap",
        claim: "A missing payer link.",
      },
    });
  });

  it("classifies a weakened verdict with an evidence marker as weakened", () => {
    expect(adversarialReviewFinding({
      incumbent_parity: "shipped by evidence: the moat is a public dataset",
      red_team_verdict: "weakened",
      red_team_caveats: [],
    })).toEqual({
      label: "Adversarial review: Weakened",
      chipLabel: "Weakened",
      details: ["the moat is a public dataset"],
      severity: "weakened",
    });
  });
});

describe("adversarialReviewSummary", () => {
  const finding = (details: string[]) => ({
    label: "Adversarial review: Weakened",
    chipLabel: "Weakened",
    details,
    severity: "weakened" as const,
  });
  const killedFinding = (details: string[]) => ({
    label: "Adversarial review: Premise unproven",
    chipLabel: "Premise unproven",
    details,
    severity: "killed" as const,
  });

  it("uses the first objection's opening sentence and counts the rest", () => {
    expect(
      adversarialReviewSummary(
        finding([
          "The vocabulary misses the category language. Buyers search for review management instead.",
          "Free alternatives already occupy the workflow.",
          "The mechanism does not address the modal pain.",
        ]),
      ),
    ).toBe(
      "The vocabulary misses the category language. +2 more objections — open the idea for the full review.",
    );
  });

  it("hard-truncates a first objection with no early sentence break", () => {
    const long = "a".repeat(260);
    const summary = adversarialReviewSummary(finding([long]));
    expect(summary.startsWith(`${"a".repeat(200)}…`)).toBe(true);
    expect(summary.endsWith("— open the idea for the full review.")).toBe(true);
  });

  it("keeps a single short objection intact", () => {
    expect(adversarialReviewSummary(finding(["No moat."]))).toBe(
      "No moat. — open the idea for the full review.",
    );
  });

  it("falls back to a generic line when there are no details", () => {
    expect(adversarialReviewSummary(finding([]))).toBe(
      "The adversarial review recorded a decision-critical objection — open the idea for the full review.",
    );
  });

  it("leads a premise-unproven summary with what the verdict means, then the objection", () => {
    expect(
      adversarialReviewSummary(
        killedFinding([
          "The modal buyer has no SEC filing.",
          "The mechanism does not address the modal pain.",
        ]),
      ),
    ).toBe(
      "The adversarial review could not find evidence for this idea's premise: The modal "
      + "buyer has no SEC filing. +1 more objection. The other scores describe how well it "
      + "would work if the premise holds. Open the idea for the full review.",
    );
  });

  it("still explains a premise-unproven verdict that cites no caveat", () => {
    expect(adversarialReviewSummary(killedFinding([]))).toBe(
      "The adversarial review could not find evidence for this idea's premise. The other "
      + "scores describe how well it would work if the premise holds. Open the idea for the "
      + "full review.",
    );
  });
});

describe("premise-unproven helpers", () => {
  it("reads the internal killed verdict, and nothing else, as an unproven premise", () => {
    expect(isPremiseUnproven({ red_team_verdict: "killed" })).toBe(true);
    expect(isPremiseUnproven({ red_team_verdict: " KILLED " })).toBe(true);
    expect(isPremiseUnproven({ red_team_verdict: "weakened" })).toBe(false);
    expect(isPremiseUnproven({ red_team_verdict: null })).toBe(false);
    expect(isPremiseUnproven({})).toBe(false);
    expect(isPremiseUnproven({ red_team_verdict: "killed", red_team_findings: [] }))
      .toBe(false);
    expect(isPremiseUnproven({ red_team_verdict: "killed", red_team_findings: null }))
      .toBe(true);
    expect(isPremiseUnproven({
      red_team_verdict: "killed",
      red_team_findings: [{
        claim: "The incumbent ships the workflow.",
        kind: "verified_incumbent_overlap",
      }],
    })).toBe(true);
  });

  it("names both ideas in the split note and keeps the leader in play", () => {
    const note = recommendationSplitNote("FaxCorrectionCache", "CountPad Vet");
    expect(note).toContain("FaxCorrectionCache scores highest");
    expect(note).toContain("could not confirm its premise");
    expect(note).toContain("the recommendation goes to CountPad Vet");
    expect(note).toContain("keeps its rank and you can still shortlist it");
  });

  it("uses typed counterevidence in the recommendation split note", () => {
    const note = recommendationSplitNote("Leader", "Recommended", {
      red_team_findings: [{
        claim: "The incumbent already ships it.",
        kind: "verified_incumbent_overlap",
      }],
    });
    expect(note).toContain("the adversarial review found verified incumbent overlap");
    expect(note).toContain("The incumbent already ships it.");
    expect(note).not.toContain("could not confirm its premise");
  });
});

/**
 * THE PROPERTY, in place of a prose pin.
 *
 * `incumbent_parity: "none found"` records that OUR QUERIES returned nothing. Those queries are
 * built out of each idea's own vocabulary (`crews/unified_solution_crew.py`), so the wording of
 * the pitch decides the verdict — a live run shipped "none found" for a #1 recommendation while
 * a same-pain sibling carried "partial by Synup", and ~90% of the 591 "none"-stamped ideas on
 * disk sit in a run that already names an incumbent elsewhere. Anything rendered from that stamp
 * must therefore say whose search it was, must not stand as a finding of absence, and must carry
 * the reason a miss is possible.
 */
const ABSENCE_STATED_AS_FACT = [
  /\bno (?:competing|competitor|competition|incumbent|rival|equivalent|direct|one|body)\b/i,
  /\bnone found\b/i,
  /\bnothing (?:ships|exists|is (?:shipping|out there))\b/i,
  /\b(?:open|empty|unserved|untapped|uncontested) (?:lane|market|space|field|category)\b/i,
  /\bfirst[- ]mover\b/i,
  /\bwhite ?space\b/i,
];

function expectRetrievalScoped(phrase: string): void {
  expect(phrase.trim()).not.toBe("");
  // Attributed to the retrieval that produced it, not to the market.
  expect(phrase).toMatch(/\bour\b/i);
  expect(phrase).toMatch(/\bsearch(?:es)?\b/i);
  // Does not OPEN as a bare finding of absence ("No competing product found", "None found").
  expect(phrase).not.toMatch(/^\s*(?:no|none|nothing)\b/i);
  // States the limit that makes a miss possible, so the reader can weigh the result.
  expect(phrase).toMatch(/\bmiss(?:ed)?\b/i);
  for (const claim of ABSENCE_STATED_AS_FACT) {
    expect(phrase).not.toMatch(claim);
  }
}

describe("NONE_SURFACED_PHRASE", () => {
  // Two components render the constant directly rather than through the helper
  // (SolutionDetailContent's "Direct incumbent check" row and AlternativesSection's
  // "Incumbent check (web-verified)" card), so the property is asserted on the constant too.
  it("claims a retrieval result and not an empty market", () => {
    expectRetrievalScoped(NONE_SURFACED_PHRASE);
  });
});

describe("incumbentParityPhrase", () => {
  // These strings are duplicated in backend/src/utils/selectionVocabulary.ts on purpose:
  // the analyst and the UI describe the same stored finding, and must not drift.
  it.each([
    ["shipped by VenueArc: provides event settlement", "Already shipped by VenueArc"],
    ["partial by Fieldproxy: covers dispatch only", "Partly covered by Fieldproxy"],
    ["substitute (Forrager): buyers use spreadsheets", "Buyers already get this outcome from Forrager"],
    ["bundled_free (Notion): included in the base plan", "Already included free with Notion"],
  ])("phrases the class prefix of %s", (raw, head) => {
    const out = incumbentParityPhrase(raw);
    expect(out.startsWith(head)).toBe(true);
    // The evidence half survives — phrasing the prefix must not drop the finding.
    expect(out).toContain(raw.slice(raw.indexOf(":") + 2));
  });

  it("never leaves a bare class token at the head of the phrase", () => {
    for (const raw of [
      "shipped by VenueArc: x", "partial by X: y",
      "substitute (Z): w", "bundled_free (Q): v", "none found",
    ]) {
      expect(incumbentParityPhrase(raw)).not.toMatch(/^(shipped|partial|substitute|bundled_free)\b/i);
    }
  });

  it("names no product when the vendor slot holds red-team or evidence", () => {
    // Such a finding names an alternative CLASS. Calling it a competitor would lend it a
    // vendor's authority it never had.
    for (const slot of ["red-team", "evidence"]) {
      const out = incumbentParityPhrase(`bundled_free (${slot}): a free tool covers it`);
      expect(out).toContain("an alternative class, no product named");
      expect(out).not.toContain(slot);
    }
  });

  it("renders a 'none' stamp as a search result, never as a proven empty market", () => {
    // BEHAVIOURAL, not a literal pin. This assertion used to read
    // `.toBe("No competing product found")` — prose inside an expectation, so the suite
    // fought the copy instead of guarding it, and the claim it pinned was the defect: the
    // parity probe builds its queries from each idea's OWN vocabulary, so a "none" stamp is
    // the outcome of a search and not a fact about the market. What is asserted here is the
    // property. The wording may improve again without touching this test.
    for (const raw of ["none found", "None found", "none", "NONE FOUND: nothing surfaced"]) {
      expectRetrievalScoped(incumbentParityPhrase(raw));
    }
  });

  it("passes free prose through untouched and renders nothing for an absent value", () => {
    const prose = "Two vendors cover adjacent workflows but neither ships this mechanism.";
    expect(incumbentParityPhrase(prose)).toBe(prose);
    expect(incumbentParityPhrase(null)).toBe("");
    expect(incumbentParityPhrase("")).toBe("");
  });
});

describe("incumbentParityPhrase vendor-echo joins", () => {
	it("joins a subject-echo evidence as its own sentence, never a colon stitch", () => {
		expect(
			incumbentParityPhrase("shipped by Rentec Direct: Rentec Direct ships Ratio utility billing"),
		).toBe("Already shipped by Rentec Direct. Rentec Direct ships Ratio utility billing");
	});

	it("drops a duplicated label echo and keeps the colon join", () => {
		expect(incumbentParityPhrase("shipped by PepLab: PepLab: peptide database")).toBe(
			"Already shipped by PepLab: peptide database",
		);
	});

	it("keeps the colon join when a DIFFERENT vendor opens the evidence", () => {
		expect(incumbentParityPhrase("shipped by MoeGo: Gingr ships this too")).toBe(
			"Already shipped by MoeGo: Gingr ships this too",
		);
	});
});
