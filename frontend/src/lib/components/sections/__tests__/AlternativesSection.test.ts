import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render } from "@testing-library/svelte";
import AlternativesSection from "../AlternativesSection.svelte";
import type { AlternativeSolution } from "$lib/types/report";

afterEach(cleanup);

function solution(overrides: Partial<AlternativeSolution>): AlternativeSolution {
  return {
    solution_name: "Test Solution",
    summary: "A test summary.",
    ...overrides,
  };
}

describe("AlternativesSection adversarial review rendering", () => {
  it("renders a killed verdict with the error (red) treatment", () => {
    const view = render(AlternativesSection, {
      props: {
        data: [
          solution({
            red_team_verdict: "killed",
            red_team_caveats: ["The buyer has no budget line."],
          }),
        ],
      },
    });

    const label = view.getByText("Adversarial review: Premise unproven");
    expect(label).toHaveClass("text-error");
    expect(label.parentElement).toHaveClass("border-error/30", "bg-error/5");
    expect(view.getByText("The buyer has no budget line.")).toBeInTheDocument();
    expect(
      view.getByText(/a verdict on the premise, not on the idea/),
    ).toBeInTheDocument();
  });

  it("renders a weakened verdict with the warning (amber) treatment", () => {
    const view = render(AlternativesSection, {
      props: {
        data: [
          solution({
            red_team_verdict: "weakened",
            red_team_caveats: ["The edge may be thin."],
          }),
        ],
      },
    });

    const label = view.getByText("Adversarial review: Weakened");
    expect(label).toHaveClass("text-warning");
    expect(label.parentElement).toHaveClass("border-warning/30", "bg-warning/5");
    expect(
      view.getByText(
        "This candidate remains available — review these concerns before committing to it.",
      ),
    ).toBeInTheDocument();
  });

  it("suppresses a bare weakened verdict with no caveats", () => {
    const view = render(AlternativesSection, {
      props: {
        data: [
          solution({
            red_team_verdict: "weakened",
            red_team_caveats: [],
          }),
        ],
      },
    });

    expect(view.queryByText(/Adversarial review/)).not.toBeInTheDocument();
  });
});
