import { describe, expect, it } from "vitest";
import type { SolutionPreview } from "$lib/types/job";
import {
  displayCompositeScore,
  solutionPrimaryStrengthKey,
  solutionStrengthBadge,
  validatedBuildComplexity,
  validatedNoveltyLevel,
  validatedStrengthKeys,
} from "$lib/utils/solution-utils";

function candidate(overrides: Partial<SolutionPreview> = {}): SolutionPreview {
  return {
    solution_name: "Legacy candidate",
    description: "A candidate from an older report.",
    value_proposition: "Useful when its evidence exists.",
    ...overrides,
  };
}

describe("displayCompositeScore", () => {
  it("preserves a valid zero adjusted score", () => {
    expect(displayCompositeScore(candidate({ adjusted_composite_score: 0 }))).toBe(0);
  });

  it("uses valid component evidence when the adjusted score is unavailable", () => {
    expect(displayCompositeScore(candidate({ market_fit_score: 0.6 }))).not.toBeNull();
  });

  it("returns null when no valid adjusted or component score exists", () => {
    expect(displayCompositeScore(candidate())).toBeNull();
    expect(displayCompositeScore(candidate({
      adjusted_composite_score: Number.NaN,
      market_fit_score: 2,
    }))).toBeNull();
  });
});

describe("score-backed strength badges", () => {
  const stalePfpg = candidate({
    market_fit_score: 0.55,
    technical_feasibility_score: 0.9,
    solo_dev_feasibility: 0.85,
    novelty_score: 0.45,
    tags: {
      build_complexity: "medium",
      strengths: ["market-fit", "solo-friendly", "quick-build"],
      primary_strength: "market-fit",
    },
  });

  it("does not show a persisted strength contradicted by the displayed score", () => {
    expect(validatedStrengthKeys(stalePfpg)).not.toContain("market-fit");
    expect(solutionStrengthBadge(stalePfpg)?.label).not.toContain("Demand fit");
  });

  it("recomputes the primary strength with the pipeline's max-margin rule", () => {
    expect(validatedStrengthKeys(stalePfpg)).toEqual(["quick-build", "solo-friendly"]);
    expect(solutionPrimaryStrengthKey(stalePfpg)).toBe("solo-friendly");
    expect(solutionStrengthBadge(stalePfpg)?.label).toBe("Solo-manageable");
  });
});

describe("score-backed watch-outs", () => {
  it("does not show stale build or distinctiveness tags contradicted by current scores", () => {
    const staleTags = candidate({
      technical_feasibility_score: 0.9,
      solo_dev_feasibility: 0.85,
      obviousness_score: 0.2,
      novelty_score: 0.75,
      tags: {
        build_complexity: "high",
        novelty_level: "conventional",
      },
    });

    expect(validatedBuildComplexity(staleTags)).toBe("low");
    expect(validatedNoveltyLevel(staleTags)).toBe("novel");
  });

  it("uses the persisted buckets only when their source scores are unavailable", () => {
    const legacyTags = candidate({
      tags: {
        build_complexity: "high",
        novelty_level: "conventional",
      },
    });

    expect(validatedBuildComplexity(legacyTags)).toBe("high");
    expect(validatedNoveltyLevel(legacyTags)).toBe("conventional");
  });
});
