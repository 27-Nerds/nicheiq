import { describe, expect, it } from "vitest";
import {
  finiteUnitScore,
  nonNegativeInteger,
  normalizeSolutionPreviews,
  safeStringList,
} from "$lib/utils/displayGuards";

describe("display guards", () => {
  it("accepts only finite scores inside the unit interval", () => {
    expect(finiteUnitScore(0)).toBe(0);
    expect(finiteUnitScore(0.65)).toBe(0.65);
    expect(finiteUnitScore(1)).toBe(1);
    expect(finiteUnitScore(-0.1)).toBeNull();
    expect(finiteUnitScore(1.1)).toBeNull();
    expect(finiteUnitScore(Number.NaN)).toBeNull();
    expect(finiteUnitScore(Number.POSITIVE_INFINITY)).toBeNull();
    expect(finiteUnitScore("0.65")).toBeNull();
  });

  it("accepts only non-negative integer amounts", () => {
    expect(nonNegativeInteger(0)).toBe(0);
    expect(nonNegativeInteger(100)).toBe(100);
    expect(nonNegativeInteger(-1)).toBeNull();
    expect(nonNegativeInteger(1.5)).toBeNull();
    expect(nonNegativeInteger(Number.NaN)).toBeNull();
  });

  it("normalizes legacy scalar lists without splitting strings into characters", () => {
    expect(safeStringList("one source")).toEqual(["one source"]);
    expect(safeStringList([" one ", 2, "", "two"])).toEqual(["one", "two"]);
    expect(safeStringList(null)).toEqual([]);
  });

  it("quarantines candidates without a stable display title", () => {
    const result = normalizeSolutionPreviews([
      null,
      { description: "Missing title" },
      {
        solution_name: " Valid idea ",
        description: "Description",
        value_proposition: "Value",
      },
    ]);

    expect(result.invalidCount).toBe(2);
    expect(result.solutions).toHaveLength(1);
    expect(result.solutions[0].solution_name).toBe("Valid idea");
  });

  it("normalizes risky score and list fields", () => {
    const result = normalizeSolutionPreviews([
      {
        solution_name: "Legacy idea",
        description: null,
        value_proposition: null,
        market_fit_score: 2,
        technical_feasibility_score: Number.NaN,
        adjusted_composite_score: 0.7,
        merged_from: "Earlier idea",
        core_features: "One feature",
      },
    ]);

    expect(result.invalidCount).toBe(0);
    expect(result.solutions[0]).toMatchObject({
      description: "",
      value_proposition: "",
      market_fit_score: null,
      technical_feasibility_score: null,
      adjusted_composite_score: 0.7,
      merged_from: ["Earlier idea"],
      core_features: ["One feature"],
    });
  });
});
