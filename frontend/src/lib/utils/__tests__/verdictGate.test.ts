import { describe, expect, it } from "vitest";
import {
  narrativeVerdictQualifier,
  planVerdictGate,
  verdictBlocker,
} from "../verdictGate";

const RED_TEAM =
  "FDA already provides searchable refusal data by country/area and product, with "
  + "weekly-updated final-action datasets";
const SCORE_ARTIFACT = "Limited market fit signals soft product-market alignment";

describe("verdictBlocker", () => {
  it("leads with the red-team refutation over the score artifact", () => {
    expect(
      verdictBlocker({
        verdict: "No-Go",
        risk_level: "High",
        primary_concern: SCORE_ARTIFACT,
        red_team_context: RED_TEAM,
      }),
    ).toBe(RED_TEAM);
  });

  it("falls back to the primary concern when no red-team finding was recorded", () => {
    expect(
      verdictBlocker({
        verdict: "No-Go",
        risk_level: "High",
        primary_concern: SCORE_ARTIFACT,
        red_team_context: null,
      }),
    ).toBe(SCORE_ARTIFACT);
  });

  it("strips markdown so the blocker reads as prose wherever it is stated", () => {
    expect(
      verdictBlocker({
        verdict: "No-Go",
        risk_level: "High",
        primary_concern: null,
        red_team_context: "**FDA** already publishes this data",
      }),
    ).toBe("FDA already publishes this data");
  });

  // The stored value is written for the accordion row, so it carries that row's label and
  // a generic coda. Both restate the sentence that introduces the blocker.
  it("drops the accordion label and coda the stored context is wrapped in", () => {
    expect(
      verdictBlocker({
        verdict: "No-Go",
        risk_level: "High",
        primary_concern: SCORE_ARTIFACT,
        red_team_context:
          "Red-team review: an adversarial evidence probe could not find evidence for this "
          + `idea's premise — ${RED_TEAM}. `
          + "Treat the caveat as a validation task, not a footnote.",
      }),
    ).toBe(
      "an adversarial evidence probe could not find evidence for this idea's premise — "
      + `${RED_TEAM}.`,
    );
  });

  it("returns null when the verdict recorded nothing", () => {
    expect(verdictBlocker(undefined)).toBeNull();
    expect(
      verdictBlocker({
        verdict: "Go",
        risk_level: "Low",
        primary_concern: "   ",
      }),
    ).toBeNull();
  });
});

describe("planVerdictGate", () => {
  it("reframes the plan as a validation program under No-Go and gates the spend", () => {
    const gate = planVerdictGate({
      verdict: "No-Go",
      risk_level: "High",
      primary_concern: SCORE_ARTIFACT,
      red_team_context: RED_TEAM,
    });

    expect(gate).not.toBeNull();
    expect(gate!.tone).toBe("negative");
    expect(gate!.heading).toBe("What this idea would have to prove first");
    expect(gate!.title).toContain("No-Go");
    expect(gate!.spendNote).toContain("Before committing budget");
    // The specific refutation, not the score artifact, is what gates the budget.
    expect(gate!.spendNote).toContain("FDA already provides searchable refusal data");
    expect(gate!.spendNote).not.toContain(SCORE_ARTIFACT);
  });

  it("applies a lighter caution under Conditional", () => {
    const gate = planVerdictGate({
      verdict: "Conditional",
      risk_level: "Medium",
      primary_concern: "Validate demand before committing",
    });

    expect(gate!.tone).toBe("caution");
    expect(gate!.title).toContain("Conditional");
    expect(gate!.spendNote).toBe(
      "Before committing budget, resolve this: Validate demand before committing.",
    );
  });

  it("changes nothing under Go", () => {
    expect(
      planVerdictGate({
        verdict: "Go",
        risk_level: "Low",
        primary_concern: "A residual risk.",
      }),
    ).toBeNull();
    expect(planVerdictGate(null)).toBeNull();
  });

  it("still gates the spend when the verdict recorded no blocker text", () => {
    const gate = planVerdictGate({
      verdict: "No-Go",
      risk_level: "High",
      primary_concern: null,
    });

    expect(gate!.spendNote).toContain("Before committing budget");
  });
});

describe("narrativeVerdictQualifier", () => {
  it("names the frame the generated summary was written in under No-Go", () => {
    expect(
      narrativeVerdictQualifier({ verdict: "No-Go", risk_level: "High", primary_concern: null }),
    ).toContain("No-Go");
  });

  it("is quieter under Conditional and silent under Go", () => {
    expect(
      narrativeVerdictQualifier({
        verdict: "Conditional",
        risk_level: "Medium",
        primary_concern: null,
      }),
    ).toContain("Conditional");
    expect(
      narrativeVerdictQualifier({ verdict: "Go", risk_level: "Low", primary_concern: null }),
    ).toBeNull();
  });
});
