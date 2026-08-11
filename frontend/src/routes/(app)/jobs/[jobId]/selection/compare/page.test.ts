import { cleanup, fireEvent, render, within } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import ComparePage from "./+page.svelte";
import capturedEvidenceNotes from "../__tests__/fixtures/evidenceNote.captured.json";

const workspaceMocks = vi.hoisted(() => ({
  openConstraints: vi.fn(),
  openTestPlanner: vi.fn(),
  openVariants: vi.fn(),
}));

vi.mock("$app/navigation", () => ({
  goto: vi.fn(),
  invalidateAll: vi.fn(),
}));
vi.mock("$lib/api", () => ({
  runFounderFit: vi.fn(),
}));
vi.mock("$lib/selection/workspaceTools", () => ({
  getWorkspaceTools: () => workspaceMocks,
}));

function idea(overrides: Record<string, unknown>) {
  return {
    idea_id: "idea-a",
    idea_revision: 1,
    solution_name: "Candidate A",
    description: "A candidate.",
    value_proposition: "vp",
    ...overrides,
  };
}

function data(ideas: ReturnType<typeof idea>[], overrides: Record<string, unknown> = {}) {
  return {
    job: { id: "job-1", status: "AWAITING_SELECTION" },
    // Fit-for-you is a decision tool; these suites describe a granted owner.
    decisionTools: overrides.decisionTools ?? true,
    workspace: {
      ideas,
      refs: ideas.map((entry) => ({ ideaId: entry.idea_id, ideaRevision: entry.idea_revision ?? 1 })),
      canonicalQuery: "?idea=idea-a%3A1&idea=idea-b%3A1",
      compareView: "market",
      ...(overrides.workspace as Record<string, unknown> ?? {}),
    },
    decisionState: overrides.decisionState ?? null,
    founderFit: overrides.founderFit ?? null,
    metricExplanations: {
      metrics: [
        {
          key: "originality",
          label: "Distinctiveness",
          summary: "How meaningfully the idea differs from obvious approaches.",
          method: "1 minus obviousness when present; legacy records show novelty.",
          caveat: "Use it to compare angles, not predict success.",
        },
      ],
    },
  } as never;
}

function founderFitArtifact(
  ideas: ReturnType<typeof idea>[],
  conflicts: Array<string | null>,
) {
  return {
    version: 1,
    inputFingerprint: "fit-fingerprint",
    profileSnapshot: {},
    ideaSnapshots: ideas,
    model: "test-model",
    createdAt: "2026-08-09T12:00:00.000Z",
    results: ideas.map((entry, index) => ({
      ideaId: entry.idea_id,
      ideaRevision: entry.idea_revision ?? 1,
      ideaTitle: entry.solution_name,
      verdict: "fits",
      summary: "Fits the saved build limits.",
      strongestAdvantage: "Existing buyer reach.",
      blockingConflict: conflicts[index] ?? null,
      decisionChangingUnknown: "Whether buyers convert.",
      sensitivity: "A longer sales cycle could change the call.",
      dimensions: [],
      suggestedExperiment: {
        assumption: "Buyers will convert.",
        whyCritical: "Conversion decides the next step.",
      },
    })),
  };
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("compare page distinctiveness row", () => {
  it("uses the same user-facing label for legacy novelty data", () => {
    const view = render(ComparePage, {
      props: {
        data: data([
          idea({ idea_id: "idea-a", solution_name: "Candidate A", novelty_score: 0.66 }),
          idea({ idea_id: "idea-b", solution_name: "Candidate B", novelty_score: 0.5 }),
        ]),
      },
    });

    expect(view.getByText("Distinctiveness")).toBeInTheDocument();
    expect(view.getByText(/How meaningfully the idea differs/)).toBeInTheDocument();
    expect(view.getByText(/Use it to compare angles/)).toBeInTheDocument();
    expect(view.queryByText(/1 minus obviousness/)).toBeNull();
  });

  it("uses the same user-facing label for current obviousness data", () => {
    const view = render(ComparePage, {
      props: {
        data: data([
          idea({ idea_id: "idea-a", solution_name: "Candidate A", obviousness_score: 0.2 }),
          idea({ idea_id: "idea-b", solution_name: "Candidate B", novelty_score: 0.5 }),
        ]),
      },
    });

    expect(view.getByText("Distinctiveness")).toBeInTheDocument();
    expect(view.queryByText("Originality")).toBeNull();
    expect(view.queryByText("Novelty")).toBeNull();
  });
});

describe("compare page evidence note", () => {
  it("prioritizes a killed adversarial finding over a softer critic concern", () => {
    const view = render(ComparePage, {
      props: {
        data: data([
          idea({
            idea_id: "idea-a",
            solution_name: "Candidate A",
            critic_concern: "The moat may be thin.",
            incumbent_parity: "shipped by evidence: the data source misses the buyer",
            red_team_verdict: "killed",
            red_team_caveats: ["Private-company records are unavailable."],
          }),
          idea({ idea_id: "idea-b", solution_name: "Candidate B" }),
        ]),
      },
    });

    expect(view.getByText(/Adversarial review: Premise unproven/)).toHaveTextContent(
      "Private-company records are unavailable.",
    );
    expect(view.queryByText("The moat may be thin.")).toBeNull();
  });

  // The finding only reached the evidence-note row far below the fold, so a candidate the
  // review could not confirm read as a peer of the survivors in its own column head.
  it("marks a premise-unproven candidate in its column head and leaves survivors unmarked", () => {
    const view = render(ComparePage, {
      props: {
        data: data([
          idea({
            idea_id: "idea-a",
            solution_name: "Candidate A",
            red_team_verdict: "killed",
            red_team_caveats: ["FDA already publishes this data."],
          }),
          idea({
            idea_id: "idea-b",
            solution_name: "Candidate B",
            red_team_verdict: "survives",
          }),
        ]),
      },
    });

    const headings = view.container.querySelectorAll(".candidate-heading");
    expect(headings).toHaveLength(2);
    // The shipped user-facing name, never the raw `killed` enum.
    expect(within(headings[0] as HTMLElement).getByText("Premise unproven")).toBeInTheDocument();
    expect(within(headings[1] as HTMLElement).queryByText("Premise unproven")).toBeNull();
    expect(view.container.textContent).not.toMatch(/\bkilled\b/i);
  });

  it("does not label positive calibration prose as a known concern", () => {
    const positiveCalibration = "Addresses high-severity delay pain with a focused mechanism and avoids broad competition.";
    const view = render(ComparePage, {
      props: {
        data: data([
          idea({
            idea_id: "idea-a",
            solution_name: "PartLimboBoard",
            critic_concern: positiveCalibration,
          }),
          idea({ idea_id: "idea-b", solution_name: "Candidate B" }),
        ]),
      },
    });

    expect(view.getByText("Evidence note")).toBeInTheDocument();
    expect(view.getByText(positiveCalibration)).toBeInTheDocument();
    expect(view.queryByText("Known concern")).toBeNull();
  });

  it("rewrites internal critic tokens in exemplar evidence notes", () => {
    const view = render(ComparePage, {
      props: {
        data: data([
          idea({
            idea_id: "idea-a",
            solution_name: "Candidate A",
            critic_concern: "The mechanism parity check found overlap; build_feas limited and data_feas good leave data_access unverified.",
          }),
          idea({ idea_id: "idea-b", solution_name: "Candidate B" }),
        ]),
      },
    });

    expect(view.getByText(/The feature overlap check found overlap/)).toHaveTextContent(
      "limited build feasibility and good data feasibility leave data access unverified",
    );
    expect(view.container.textContent).not.toMatch(
      /mechanism parity|build_feas|data_feas|data_access/i,
    );
  });
});

describe("compare page metric help markers", () => {
  it("renders help markers as plain spans inside the Tooltip trigger — no nested button tab stop", () => {
    const view = render(ComparePage, {
      props: {
        data: data([
          idea({ idea_id: "idea-a", solution_name: "Candidate A", novelty_score: 0.66 }),
          idea({ idea_id: "idea-b", solution_name: "Candidate B", novelty_score: 0.5 }),
        ]),
      },
    });

    expect(view.container.querySelectorAll("button.metric-help")).toHaveLength(0);
    expect(view.container.querySelectorAll("span.metric-help").length).toBeGreaterThan(0);
  });
});

describe("compare page branch escape hatch", () => {
  it("offers a quiet branch action under the grid that opens the variants tool", async () => {
    const view = render(ComparePage, {
      props: {
        data: data([
          idea({ idea_id: "idea-a", solution_name: "Candidate A" }),
          idea({ idea_id: "idea-b", solution_name: "Candidate B" }),
        ]),
      },
    });

    await fireEvent.click(view.getByRole("button", { name: "None of these fit? Branch a new direction →" }));
    expect(workspaceMocks.openVariants).toHaveBeenCalledTimes(1);
  });

  it("returns an incomplete comparison to the first ranked idea row", () => {
    const view = render(ComparePage, {
      props: { data: data([idea({ idea_id: "idea-a", solution_name: "Candidate A" })]) },
    });

    expect(view.getByRole("link", { name: "Back to ranked ideas" }))
      .toHaveAttribute("href", "/jobs/job-1#idea-select-0");
  });

  it("keeps the saved comparison readable without offering mutations after selection ends", () => {
    const completedData = data([
      idea({ idea_id: "idea-a", solution_name: "Candidate A", novelty_score: 0.66 }),
      idea({ idea_id: "idea-b", solution_name: "Candidate B", novelty_score: 0.5 }),
    ]) as any;
    completedData.job.status = "COMPLETED";

    const view = render(ComparePage, { props: { data: completedData } });

    expect(view.getByRole("status")).toHaveTextContent("View only. Idea selection has ended");
    expect(view.getByRole("heading", { name: "Candidate A" })).toBeInTheDocument();
    expect(view.getByRole("heading", { name: "Candidate B" })).toBeInTheDocument();
    expect(view.queryByRole("button", { name: /Branch a new direction/ })).not.toBeInTheDocument();
  });

  it("describes a one-idea post-selection record without telling the user to add another", () => {
    const completedData = data([
      idea({ idea_id: "idea-a", solution_name: "Candidate A" }),
    ]) as any;
    completedData.job.status = "COMPLETED";

    const view = render(ComparePage, { props: { data: completedData } });

    expect(view.getByRole("heading", { name: "One idea in the saved comparison" })).toBeInTheDocument();
    expect(view.getByText("A side-by-side comparison was not saved for this run.")).toBeInTheDocument();
    expect(view.getByRole("link", { name: "Back to ranked ideas" }))
      .toHaveAttribute("href", "/jobs/job-1#idea-select-0");
    expect(view.queryByText(/Add a second idea/)).not.toBeInTheDocument();
  });
});

describe("compare page analyze-fit accessibility", () => {
  it("points the fit button at its visible error node when exact scope references are missing", () => {
    const ideas = [
      idea({ idea_id: "idea-a", solution_name: "Candidate A" }),
      idea({ idea_id: "idea-b", solution_name: "Candidate B" }),
    ];
    const view = render(ComparePage, {
      props: {
        data: data(ideas, {
          workspace: {
            ideas,
            refs: [],
            canonicalQuery: "?idea=idea-a%3A1&idea=idea-b%3A1",
            compareView: "founder",
          },
          decisionState: {
            profile: { weeklyTime: "10_20", budget: "1k_5k", team: "solo", revenueHorizon: "90_days" },
          },
        }),
      },
    });

    const button = view.getByRole("button", { name: "Analyze fit" });
    expect(button).toHaveAttribute("aria-describedby", "fit-analysis-error");
    expect(document.getElementById("fit-analysis-error")?.textContent)
      .toContain("Reload the shortlist before analyzing fit.");
  });
});

describe("compare page founder-fit rows and disclosures", () => {
  const ideas = [
    idea({ idea_id: "idea-a", solution_name: "Candidate A" }),
    idea({ idea_id: "idea-b", solution_name: "Candidate B" }),
  ];

  function founderData(conflicts: Array<string | null>) {
    return data(ideas, {
      workspace: { compareView: "founder" },
      founderFit: { analysis: founderFitArtifact(ideas, conflicts), stale: false },
    });
  }

  it("omits Blocking conflict when every scoped idea has a null conflict", () => {
    const view = render(ComparePage, { props: { data: founderData([null, null]) } });

    expect(view.queryByText("Blocking conflict")).not.toBeInTheDocument();
    expect(view.queryByText("No blocking conflict recorded.")).not.toBeInTheDocument();
  });

  it("renders Blocking conflict when at least one scoped idea has a real conflict", () => {
    const view = render(ComparePage, {
      props: { data: founderData(["The weekly workload exceeds the saved limit.", null]) },
    });

    expect(view.getByText("Blocking conflict")).toBeInTheDocument();
    expect(view.getByText("The weekly workload exceeds the saved limit.")).toBeInTheDocument();
  });

  it("wires each fit-reasoning summary to its controlled body", async () => {
    const view = render(ComparePage, { props: { data: founderData([null, null]) } });
    const summary = view.container.querySelector<HTMLElement>(".fit-detail summary");

    expect(summary).not.toBeNull();
    expect(summary).toHaveAttribute("aria-expanded", "false");
    const bodyId = summary?.getAttribute("aria-controls");
    expect(bodyId).toBe("fit-reasoning-body-idea-a-1");
    expect(view.container.querySelector(`#${bodyId}`)).toHaveClass("fit-detail__body");

    const details = summary!.closest("details")!;
    details.open = true;
    await fireEvent(details, new Event("toggle"));
    expect(summary).toHaveAttribute("aria-expanded", "true");
  });
});

describe("compare page without the decision tools grant", () => {
  const ideas = [
    idea({ idea_id: "idea-a", solution_name: "Candidate A" }),
    idea({ idea_id: "idea-b", solution_name: "Candidate B" }),
  ];

  it("hides the view switcher and never renders the fit half", () => {
    const view = render(ComparePage, {
      props: { data: data(ideas, { decisionTools: false }) },
    });

    expect(view.queryByRole("button", { name: "Fit for you" })).toBeNull();
    expect(view.queryByRole("button", { name: "Analyze fit" })).toBeNull();
    expect(view.queryByText("Add your build limits")).toBeNull();
    // The research-evidence comparison itself is never gated.
    expect(view.getAllByText("Candidate A").length).toBeGreaterThan(0);
  });

  it("forces the market view even on a ?view=founder deep link", () => {
    const view = render(ComparePage, {
      props: {
        data: data(ideas, {
          decisionTools: false,
          workspace: { compareView: "founder" },
        }),
      },
    });

    expect(view.queryByRole("button", { name: "Analyze fit" })).toBeNull();
    expect(view.getAllByText("Candidate A").length).toBeGreaterThan(0);
  });
});

/**
 * `evidenceNote()` used to end in a blind replace of every spaced em/en dash by ". " — the
 * SAME line `buyerFacingIdeaProse` was extracted to delete after it produced 990 degraded
 * instances on the idea cards. It shipped here for another round with its own thin jargon
 * list and no cold-start or corpus rule at all.
 *
 * The strings below are RAW captures from the run artifacts under `output/`, never
 * hand-written; the fixture records the file and JSON path of each. Measured over the 730
 * distinct values this row reads, the chain left 81 residual jargon instances and invented 99
 * lower-cased sentence starts; the shared authority leaves 0 of each.
 */
describe("compare page evidence note uses the shared buyer-facing authority", () => {
  const RAW = capturedEvidenceNotes as { why: string; file: string; path: string; value: string }[];
  const JARGON = /\bcorpus\b|cold[- ]start|\bwedge\b|\bdata_feas\b|\bbuild_feas\b/i;

  it("keeps both dash tails as sentences and rewrites the cold-start vocabulary", () => {
    const view = render(ComparePage, {
      props: {
        data: data([
          idea({ idea_id: "idea-a", solution_name: "Candidate A", critic_concern: RAW[0].value }),
          idea({ idea_id: "idea-b", solution_name: "Candidate B", critic_concern: RAW[1].value }),
        ]),
      },
    });

    expect(view.getByText(/^User-submitted Janoshik COA PDFs/)).toHaveTextContent(
      "User-submitted Janoshik COA PDFs; requires verification mechanism to prevent fake "
        + "submissions, checking against known Janoshik report formats (watermarks, QR codes, "
        + "layout). Up-front data problem: needs ~30 initial submissions to generate "
        + "meaningful vendor scores. Solved by partnering with existing community testing "
        + "pools and offering free premium access as upload incentive.",
    );
    expect(view.getByText(/^User-submitted COA PDFs via upload/)).toHaveTextContent(
      /cross-references\. Up-front data is the primary risk$/,
    );
  });

  it("leaves no pipeline vocabulary and no lower-cased sentence start in the table", () => {
    const view = render(ComparePage, {
      props: {
        data: data([
          idea({ idea_id: "idea-a", solution_name: "Candidate A", critic_concern: RAW[0].value }),
          idea({ idea_id: "idea-b", solution_name: "Candidate B", critic_concern: RAW[1].value }),
        ]),
      },
    });

    for (const raw of RAW) {
      const cell = view.getByText(new RegExp(`^${raw.value.slice(0, 24).replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`));
      expect(cell.textContent).not.toMatch(JARGON);
      // The chain's signature defect: a full stop followed by a lower-case word.
      expect(cell.textContent).not.toMatch(/[.!?]\s+[a-z]/);
      expect(cell.textContent).not.toMatch(/[—–]/);
    }
  });
});
