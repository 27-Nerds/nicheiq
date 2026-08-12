import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render } from "@testing-library/svelte";
import AlternativesSection from "../AlternativesSection.svelte";
import type { AlternativeSolution } from "$lib/types/report";
import captured from "./fixtures/alternativeSolutions.captured.json";

afterEach(cleanup);

function solution(overrides: Partial<AlternativeSolution>): AlternativeSolution {
  return {
    solution_name: "Test Solution",
    summary: "A test summary.",
    ...overrides,
  };
}

/**
 * RAW pipeline strings, captured from the run artifacts under `output/` — never
 * hand-written, and never pre-sanitised before they are handed to the component. Each entry
 * records the file and JSON path it came from. This section prints them on the PAID Deep
 * Research report, and it printed them through `humanizeInternalJargon`, which owns renamed
 * metrics and money units and has no idea vocabulary at all.
 */
const RAW = captured as { why: string; file: string; path: string; value: string }[];
function rawValue(fragment: string): string {
  const entry = RAW.find(
    (candidate) => candidate.value.toLowerCase().includes(fragment.toLowerCase()),
  );
  if (!entry) throw new Error(`no captured artifact carries "${fragment}"`);
  return entry.value;
}

const PIPELINE_VOCABULARY =
  /\bcorpus\b|cold[- ]start|web-verified|\bwedge\b|mechanism parity|\bdata_feas\b|\bbuild_feas\b/i;

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

  it("uses the primary affirmative claim and counterevidence coda for mixed gap-first kills", () => {
    const view = render(AlternativesSection, {
      props: {
        data: [
          solution({
            red_team_verdict: "killed",
            red_team_findings: [
              { claim: "No free tool was found.", kind: "evidence_gap" },
              {
                claim: "SuiteCo bundles the same workflow in its free plan.",
                kind: "verified_free_or_bundled_alternative",
              },
            ],
          }),
        ],
      },
    });

    expect(view.getByText("Adversarial review: Verified free or bundled alternative"))
      .toBeInTheDocument();
    const details = view.container.querySelectorAll(".text-text-secondary");
    expect([...details].some((node) => node.textContent === "SuiteCo bundles the same workflow in its free plan."))
      .toBe(true);
    expect(view.getByText(/This is verified counterevidence, not missing evidence/))
      .toBeInTheDocument();
    expect(view.queryByText(/verdict on the premise, not on the idea/)).not.toBeInTheDocument();
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

describe("AlternativesSection renders no pipeline vocabulary", () => {
  it("sanitises every captured critic_concern the corpus carries, in one mount", () => {
    const view = render(AlternativesSection, {
      props: {
        data: [
          solution({ solution_name: "Candidate A", critic_concern: rawValue("wedge") }),
          solution({
            solution_name: "Candidate B",
            critic_concern: rawValue("mechanism parity"),
          }),
          solution({ solution_name: "Candidate C", critic_concern: rawValue("data_feas") }),
        ],
      },
    });

    const text = view.container.textContent ?? "";
    expect(text).not.toMatch(PIPELINE_VOCABULARY);
    expect(view.getByText(/defensible entry point in a high-pain area/)).toBeInTheDocument();
    expect(view.getByText(/but feature overlap shows VetSnap/)).toBeInTheDocument();
    expect(view.getByText(/limited build feasibility signals the core PIMS/)).toBeInTheDocument();
    expect(view.getByText(/but good data feasibility and unverified data access/)).toBeInTheDocument();
  });

  it("sanitises data_acquisition_notes in the data badge's tooltip", () => {
    const view = render(AlternativesSection, {
      props: {
        data: [
          solution({
            data_access_model: "public",
            data_acquisition_notes: rawValue("cold-start corpus"),
          }),
        ],
      },
    });

    const badge = view.getByTitle(/User-submitted fix reports/);
    expect(badge.getAttribute("title")).toBe(
      "User-submitted fix reports via web form; requires up-front dataset but no technical "
        + "barriers.",
    );
    expect(badge.getAttribute("title")).not.toMatch(PIPELINE_VOCABULARY);
  });

  it("renders identically whether the host pre-sanitised or not", async () => {
    const { buyerFacingSolutionPreview } = await import(
      "$lib/selection/buyerFacingResearchProse"
    );
    const raw = solution({ critic_concern: rawValue("mechanism parity") });
    const first = render(AlternativesSection, { props: { data: [raw] } });
    const rawText = first.container.textContent;
    cleanup();

    const pre = render(AlternativesSection, {
      props: {
        data: [buyerFacingSolutionPreview(raw as never) as unknown as AlternativeSolution],
      },
    });
    expect(pre.container.textContent).toBe(rawText);
  });
});
