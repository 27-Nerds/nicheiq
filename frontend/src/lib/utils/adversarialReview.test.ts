import { describe, expect, it } from "vitest";
import {
  adversarialReviewFinding,
  adversarialReviewSummary,
  directIncumbentParity,
  incumbentParityPhrase,
  isPremiseUnproven,
  noDirectIncumbentFound,
  recommendationSplitNote,
} from "./adversarialReview";

describe("adversarial review classification", () => {
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
  });

  it("names both ideas in the split note and keeps the leader in play", () => {
    const note = recommendationSplitNote("FaxCorrectionCache", "CountPad Vet");
    expect(note).toContain("FaxCorrectionCache scores highest");
    expect(note).toContain("could not confirm its premise");
    expect(note).toContain("the recommendation goes to CountPad Vet");
    expect(note).toContain("keeps its rank and you can still shortlist it");
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

  it("reads 'none found' as a sentence, and passes free prose through untouched", () => {
    expect(incumbentParityPhrase("none found")).toBe("No competing product found");
    const prose = "Two vendors cover adjacent workflows but neither ships this mechanism.";
    expect(incumbentParityPhrase(prose)).toBe(prose);
    expect(incumbentParityPhrase(null)).toBe("");
  });
});
