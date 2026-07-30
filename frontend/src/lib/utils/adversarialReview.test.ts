import { describe, expect, it } from "vitest";
import {
  adversarialReviewFinding,
  directIncumbentParity,
  noDirectIncumbentFound,
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
      label: "Adversarial review: Killed",
      details: [
        "The buyer has no public filing.",
        "the proposed source misses the buyer",
      ],
    });
  });

  it("preserves actual incumbent and no-incumbent findings", () => {
    expect(directIncumbentParity({
      incumbent_parity: "shipped by Karbon: workflow automation",
    })).toBe("shipped by Karbon: workflow automation");
    expect(noDirectIncumbentFound({ incumbent_parity: "none found" })).toBe(true);
  });

  it("does not add a new warning for a weakened review without the evidence marker", () => {
    expect(adversarialReviewFinding({
      incumbent_parity: "partial by Karbon: workflow automation",
      red_team_verdict: "weakened",
      red_team_caveats: ["The edge may be thin."],
    })).toBeNull();
  });
});
