import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render } from "@testing-library/svelte";
import SolutionDetail from "../SolutionDetail.svelte";
import type { SolutionPreview } from "$lib/types/job";
import type { OverlapGroup } from "$lib/types/report";
import capturedArtifacts from "$lib/selection/__tests__/fixtures/runArtifacts.captured.json";

afterEach(() => cleanup());

function solution(overrides: Partial<SolutionPreview> = {}): SolutionPreview {
  return {
    idea_id: "idea-1",
    idea_revision: 2,
    solution_name: "Signal Desk",
    description: "A guided tapering companion.",
    value_proposition: "Keep the weight off after GLP-1.",
    ...overrides,
  };
}

function renderDetail(props: {
  solution: SolutionPreview;
  solutions?: SolutionPreview[];
  jobId?: string;
  lifecycle?: "selection" | "reference" | "running" | "completed";
  isSelected?: boolean;
  disabled?: boolean;
  disabledReason?: string;
  maxReached?: boolean;
  selectedCount?: number;
  maxSelections?: number;
  overlapGroups?: OverlapGroup[];
  onSelect?: (solution: SolutionPreview) => void;
  onNavigate?: (index: number) => void;
  onClose?: () => void;
  evidenceLinks?: { href: string; label: string }[];
}) {
  return render(SolutionDetail, {
    props: {
      open: true,
      solutions: props.solutions ?? [props.solution],
      currentIndex: 0,
      onNavigate: vi.fn(),
      onClose: vi.fn(),
      ...props,
    },
  });
}

describe("SolutionDetail export links", () => {
  it("links to the exact stored revision's md and json exports when jobId is present", () => {
    const { getByRole } = renderDetail({ solution: solution(), jobId: "job-1" });

    const md = getByRole("link", { name: "Download Markdown" });
    expect(md).toHaveAttribute(
      "href",
      "/api/jobs/job-1/solutions/idea-1/export/md?revision=2",
    );
    const json = getByRole("link", { name: "Download JSON" });
    expect(json).toHaveAttribute(
      "href",
      "/api/jobs/job-1/solutions/idea-1/export/json?revision=2",
    );
  });

  it("defaults the export revision to 1 for legacy candidates without a stored revision", () => {
    const { getByRole } = renderDetail({
      solution: solution({ idea_revision: undefined }),
      jobId: "job-1",
    });

    expect(getByRole("link", { name: "Download Markdown" })).toHaveAttribute(
      "href",
      "/api/jobs/job-1/solutions/idea-1/export/md?revision=1",
    );
  });

  it("hides export links without a job or an idea identity", () => {
    const noJob = renderDetail({ solution: solution() });
    expect(noJob.queryByRole("link", { name: "Download Markdown" })).not.toBeInTheDocument();

    cleanup();

    const noIdentity = renderDetail({ solution: solution({ idea_id: undefined }), jobId: "job-1" });
    expect(noIdentity.queryByRole("link", { name: "Download Markdown" })).not.toBeInTheDocument();
  });
});

describe("SolutionDetail interaction model", () => {
  it("uses roving tab focus and supports Arrow, Home, and End keys", async () => {
    const view = renderDetail({ solution: solution() });
    const overview = view.getByRole("tab", { name: "Decision summary" });
    const detail = view.getByRole("tab", { name: "All details" });

    expect(overview).toHaveAttribute("tabindex", "0");
    expect(detail).toHaveAttribute("tabindex", "-1");

    overview.focus();
    await fireEvent.keyDown(overview, { key: "ArrowRight" });
    expect(detail).toHaveFocus();
    expect(detail).toHaveAttribute("aria-selected", "true");

    await fireEvent.keyDown(detail, { key: "Home" });
    expect(overview).toHaveFocus();
    expect(overview).toHaveAttribute("aria-selected", "true");

    await fireEvent.keyDown(overview, { key: "End" });
    expect(detail).toHaveFocus();
  });

  it("pages candidates from the reading surface but not from interactive controls", async () => {
    const onNavigate = vi.fn();
    const ideas = [
      solution(),
      solution({ idea_id: "idea-2", solution_name: "Second idea" }),
    ];
    const view = renderDetail({
      solution: ideas[0],
      solutions: ideas,
      onNavigate,
    });

    await fireEvent.keyDown(view.getByRole("tabpanel"), { key: "ArrowRight" });
    expect(onNavigate).toHaveBeenCalledWith(1);

    onNavigate.mockClear();
    await fireEvent.keyDown(view.getByRole("button", { name: "Next idea" }), {
      key: "ArrowRight",
    });
    expect(onNavigate).not.toHaveBeenCalled();
  });

  it("announces candidate changes and keeps the active tab across paging", async () => {
    const ideas = [
      solution(),
      solution({ idea_id: "idea-2", solution_name: "Second idea" }),
    ];
    const view = renderDetail({ solution: ideas[0], solutions: ideas });
    await fireEvent.click(view.getByRole("tab", { name: "All details" }));
    expect(view.getByRole("tab", { name: "All details" })).toHaveAttribute(
      "aria-selected",
      "true",
    );

    // Page to the next candidate — the user comparing All details stays on that tab.
    await view.rerender({
      open: true,
      solution: ideas[1],
      solutions: ideas,
      currentIndex: 1,
      onNavigate: vi.fn(),
      onClose: vi.fn(),
    });

    expect(view.getByRole("tab", { name: "All details" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(view.getByText(/Viewing candidate 2 of 2: Second idea, revision 2/)).toBeInTheDocument();
  });

  it("passes the exact candidate object to selection callbacks", async () => {
    const candidate = solution();
    const onSelect = vi.fn();
    const view = renderDetail({
      solution: candidate,
      lifecycle: "selection",
      selectedCount: 0,
      maxSelections: 3,
      onSelect,
    });

    await fireEvent.click(view.getByRole("button", { name: "Add to shortlist" }));
    expect(onSelect).toHaveBeenCalledWith(candidate);
  });
});

describe("SolutionDetail lifecycle and provenance", () => {
  it("labels a legacy candidate without score inputs as not scored", () => {
    const view = renderDetail({ solution: solution() });

    expect(view.getByRole("button", { name: "Discovery score details" })).toHaveTextContent(
      "Not scored",
    );
  });

  it("never renders shortlist controls in completed reference mode and uses completed tense", () => {
    const view = renderDetail({
      solution: solution(),
      lifecycle: "completed",
      onSelect: vi.fn(),
    });

    expect(
      view.queryByRole("button", {
        name: /Add to shortlist|Remove from shortlist|Shortlist full/,
      }),
    ).not.toBeInTheDocument();
    expect(view.getByText("Deep Research checked this idea")).toBeInTheDocument();
  });

  it("shows a bundle kicker with normalized per-signal list items and full pain text", () => {
    const longPain = "A".repeat(180);
    const view = renderDetail({
      solution: solution({
        idea_tier: "bundle",
        source_pain: longPain,
        pain_points_addressed: [
          "1. Adverse Reactions and Safety Concerns from Nail Products (Severity 8.0/10, Mentions 10): reduces risk by flagging harmful ingredients",
          "2. Second complementary pain (Severity 6.0/10, Mentions 3): bundles neatly",
        ],
      }),
    });

    expect(view.getByText(/Bundle · 2 Discovery pain signals/)).toBeInTheDocument();
    const items = view.getAllByRole("listitem").map((li) => li.textContent?.trim());
    expect(items).toContain("Adverse Reactions and Safety Concerns from Nail Products");
    expect(items).toContain("Second complementary pain");
    // No raw ranked-list metadata leaks into the bundle list.
    expect(view.queryByText(/Severity 8\.0\/10/)).not.toBeInTheDocument();
    // The Pain-signal fact still shows the untruncated source pain.
    expect(view.getByText(longPain)).toBeInTheDocument();
    expect(view.getByText(longPain).closest("dd")).not.toHaveClass("is-clamped");
  });

  it("normalizes the legacy pain_points_addressed fallback in the Pain signal fact", () => {
    const view = renderDetail({
      solution: solution({
        source_pain: undefined,
        pain_points_addressed: [
          "1. Adverse Reactions and Safety Concerns from Nail Products (Severity 8.0/10, Mentions 10): reduces risk by flagging harmful ingredients",
        ],
      }),
    });

    expect(
      view.getByText("Adverse Reactions and Safety Concerns from Nail Products"),
    ).toBeInTheDocument();
    expect(view.queryByText(/Severity 8\.0\/10/)).not.toBeInTheDocument();
  });

  it("presents a killed red-team result as an adversarial finding, not an incumbent", async () => {
    const view = renderDetail({
      solution: solution({
        winning_angle: "novel_differentiation",
        angle_rationale: "A distinct service model.",
        incumbent_parity:
          "shipped by evidence: the public-company data source does not cover the target buyer",
        red_team_verdict: "killed",
        red_team_caveats: ["Private-company trial balances are not available in SEC filings."],
      }),
    });

    expect(view.getByText("Adversarial review: Premise unproven")).toBeInTheDocument();
    // Body finding + the facet chip's tooltip summary both quote the caveat.
    expect(view.getAllByText(/Private-company trial balances/).length).toBeGreaterThan(0);
    expect(view.getByText("Premise unproven")).toBeInTheDocument();
    expect(view.queryByText("Web-verified incumbent:")).not.toBeInTheDocument();

    await fireEvent.click(view.getByRole("tab", { name: "All details" }));

    expect(view.getByRole("heading", { name: "Adversarial review: Premise unproven" })).toBeInTheDocument();
    expect(view.queryByText("Direct incumbents")).not.toBeInTheDocument();
  });

  it("explains that a premise-unproven idea's other scores assume the premise holds", async () => {
    const view = renderDetail({
      solution: solution({
        market_fit_score: 0.78,
        technical_feasibility_score: 0.71,
        red_team_verdict: "killed",
        red_team_caveats: ["No reachable buyer owns the fax queue."],
      }),
    });

    // Overview: the finding is a verdict on the premise, not a rating of the idea.
    expect(
      view.getByText(/This is a verdict on the premise, not on the idea/),
    ).toBeInTheDocument();
    expect(view.getByText(/keeps its rank and stays selectable/)).toBeInTheDocument();

    await fireEvent.click(view.getByRole("tab", { name: "All details" }));

    // Full detail: the score list says outright what the numbers are conditional on.
    expect(view.getByText(/These scores assume the premise holds/)).toBeInTheDocument();
  });

  it("leaves the scoring card unqualified when the review raised nothing", async () => {
    const view = renderDetail({
      solution: solution({ market_fit_score: 0.78, technical_feasibility_score: 0.71 }),
    });

    expect(view.queryByText(/Premise unproven/)).not.toBeInTheDocument();
    await fireEvent.click(view.getByRole("tab", { name: "All details" }));
    expect(view.queryByText(/These scores assume the premise holds/)).not.toBeInTheDocument();
  });

  it("keeps the tournament bear case out of the overview and shows it in full detail", async () => {
    const view = renderDetail({
      solution: solution({
        market_fit_score: 0.62,
        critic_concern: "Buyer urgency has not been demonstrated behaviorally.",
        refine_binding_constraint: "novelty: differentiate the tapering mechanism, not the copy",
      }),
    });

    expect(view.queryByText("Tournament bear case")).not.toBeInTheDocument();
    expect(
      view.queryByText(/differentiate the tapering mechanism/),
    ).not.toBeInTheDocument();

    await fireEvent.click(view.getByRole("tab", { name: "All details" }));

    expect(view.getByText("Tournament bear case")).toBeInTheDocument();
    expect(
      view.getByText("novelty: differentiate the tapering mechanism, not the copy"),
    ).toBeInTheDocument();
    // sits alongside, not in place of, the calibration critic's note
    expect(view.getByText("Independent critic's take")).toBeInTheDocument();
  });

  it("lets a clamped score reason be read in full", async () => {
    // The rationale is clamped to 240 chars so the popover stays scannable; every
    // reason on the scoring card ended in "…" with no way to reach the rest.
    const long = `Venue finance leads reconcile door splits by hand every night, ${"and the sheet they trust is a spreadsheet nobody owns ".repeat(6)}which is the whole opening.`;
    const view = renderDetail({
      solution: solution({ market_fit_score: 0.62, why_it_works: long }),
    });

    await fireEvent.click(view.getByRole("tab", { name: "All details" }));

    const more = view.getByRole("button", { name: "Show full reasoning" });
    expect(view.queryByText(long)).not.toBeInTheDocument();
    await fireEvent.click(more);
    expect(view.getByText(long)).toBeInTheDocument();
    expect(view.getByRole("button", { name: "Show less" })).toBeInTheDocument();
  });

  it("links only to evidence sections supplied by the job-page caller", () => {
    const view = renderDetail({
      solution: solution(),
      evidenceLinks: [
        { href: "/jobs/job-1#pain-points", label: "Pain evidence" },
        { href: "/jobs/job-1#audience", label: "Audience evidence" },
      ],
    });

    expect(view.getByRole("link", { name: "Pain evidence" })).toHaveAttribute(
      "href",
      "/jobs/job-1#pain-points",
    );
    expect(view.getByRole("link", { name: "Audience evidence" })).toHaveAttribute(
      "href",
      "/jobs/job-1#audience",
    );
  });

  it("resolves overlap peers to display titles with shared_product and pages to in-pool peers", async () => {
    const onNavigate = vi.fn();
    const peer = solution({
      idea_id: "idea-2",
      solution_name: "PatchImpactRadar",
      headline: "Patch impact radar for ops teams",
    });
    const view = renderDetail({
      solution: solution(),
      solutions: [solution(), peer],
      onNavigate,
      overlapGroups: [
        {
          idea_names: ["Signal Desk", "PatchImpactRadar", "NotInPool"],
          shared_product: "patch impact analyzer",
        },
      ],
    });

    expect(
      view.getByText(/Overlaps with 2 other candidates on "patch impact analyzer":/),
    ).toBeInTheDocument();

    // In-pool peer shows its display title (not the internal name) and pages the overlay.
    const peerButton = view.getByRole("button", { name: "Patch impact radar for ops teams" });
    await fireEvent.click(peerButton);
    expect(onNavigate).toHaveBeenCalledWith(1);

    // Out-of-pool name stays plain text — no button.
    expect(view.getByText(/NotInPool/)).toBeInTheDocument();
    expect(view.queryByRole("button", { name: "NotInPool" })).not.toBeInTheDocument();
  });

  it("labels the working-name subtitle and suppresses it when it equals the headline", () => {
    const labeled = renderDetail({
      solution: solution({ headline: "Keep taper patients on track" }),
    });
    const subtitle = labeled.getByText("Signal Desk").closest("p");
    expect(subtitle).toHaveTextContent(/Working name/i);

    cleanup();

    const duplicate = renderDetail({
      solution: solution({ headline: "Signal Desk" }),
    });
    expect(duplicate.queryByText(/Working name/i)).not.toBeInTheDocument();
  });

  it("links the disabled Shortlist full button to the visible hint via aria-describedby", () => {
    const view = renderDetail({
      solution: solution(),
      lifecycle: "selection",
      isSelected: false,
      maxReached: true,
      selectedCount: 3,
      maxSelections: 3,
      onSelect: vi.fn(),
    });

    const button = view.getByRole("button", { name: "Shortlist full" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-describedby", "shortlist-limit-note");
    const note = document.getElementById("shortlist-limit-note");
    expect(note).toHaveTextContent("Shortlist is full. Remove another candidate first.");
  });

  it("explains why shortlist changes are temporarily disabled", () => {
    const view = renderDetail({
      solution: solution(),
      lifecycle: "selection",
      disabled: true,
      disabledReason: "Another idea update is running. You can change the shortlist when it finishes.",
      onSelect: vi.fn(),
    });

    const button = view.getByRole("button", { name: "Add to shortlist" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-describedby", "shortlist-disabled-note");
    expect(document.getElementById("shortlist-disabled-note")).toHaveTextContent(
      "Another idea update is running. You can change the shortlist when it finishes.",
    );
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// Pipeline vocabulary
// ─────────────────────────────────────────────────────────────────────────────

/**
 * THE LEAK WAS NEVER IN THE FUNCTION, IT WAS IN WHO CALLED IT. Rounds 4-7 each proved
 * `buyerFacingIdeaProse` correct with a unit test and each shipped the vocabulary anyway,
 * because the fix lived at ONE of four call sites. `/selection/review` mounts this overlay
 * with `data.workspace.ideas` straight off `resolveSelectionWorkspace`, and
 * SelectedSolutionsSummary mounts it with `job.solutionIdeas` — both RAW.
 *
 * So this test renders the component the way those two pages do: raw pipeline values,
 * CAPTURED from artifacts under `output/` and stored with the path they were copied from,
 * never retyped. A unit test on the function cannot fail when the call site is missing;
 * this one can, and it is the only kind that could have caught the last four rounds.
 */
function capturedRaw(path: string): string {
  const hit = capturedArtifacts.find((entry) => entry.path === path);
  if (!hit) throw new Error(`fixture lost its capture: ${path}`);
  return hit.value;
}

describe("SolutionDetail renders buyer-facing prose from a RAW pipeline payload", () => {
  const raw = () => solution({
    solution_name: "AuditFlowPM",
    winning_angle: "distribution_seo",
    market_fit_score: 0.42,
    solo_dev_feasibility: 0.4,
    data_access_model: "restricted",
    angle_rationale: capturedRaw(".solution_ideas[2].angle_rationale"),
    data_acquisition_notes: capturedRaw(".idea_ruled_out[0].idea.data_acquisition_notes"),
    critic_concern: capturedRaw(".alternative_solutions[4].critic_concern"),
    refine_binding_constraint: capturedRaw(".solution_ideas[0].refine_binding_constraint"),
  });

  it("prints no pipeline vocabulary on the decision-summary tab", () => {
    renderDetail({ solution: raw(), lifecycle: "reference" });
    const text = document.body.textContent ?? "";

    expect(text).toContain("The read");
    expect(text).toMatch(/search opportunity/);
    expect(text).not.toMatch(/SEO surface/i);
    expect(text).not.toMatch(/data representation/i);
    // The angle rationale is the one field printed on this tab; the other three live on
    // the All-details tab and are asserted there.
    expect(text).not.toMatch(/\bcorpus\b/i);
  });

  it("prints no pipeline vocabulary on the all-details tab", async () => {
    const view = renderDetail({ solution: raw(), lifecycle: "reference" });
    await fireEvent.click(view.getByRole("tab", { name: /All details/i }));
    const text = document.body.textContent ?? "";

    // data_acquisition_notes
    expect(text).not.toMatch(/cold[-\s]start/i);
    expect(text).not.toMatch(/\bcorpus\b/i);
    expect(text).toContain("up-front dataset required");
    expect(text).toContain("with no bulk download route confirmed and per-record access");
    // critic_concern
    expect(text).not.toMatch(/mechanism parity/i);
    expect(text).not.toMatch(/build_feas/i);
    expect(text).toContain("feature overlap");
    expect(text).toContain("limited build feasibility");
    // refine_binding_constraint
    expect(text).not.toMatch(/\bwedge\b/i);
    expect(text).toContain("Sharpen the entry point");
    // Every dash in the three captured fields is gone, and the two clause dashes in the
    // constraint became sentences with their first word cased — asserted as whole strings
    // so a rule that only half-fires cannot pass.
    expect(text).toContain(
      "First-party user submissions; up-front dataset required, with no bulk download route "
      + "confirmed and per-record access that is unverified.",
    );
    expect(text).toContain(
      "The comparison engine is solid but generic. Every affiliate site does feature grids. "
      + "Sharpen the entry point: make the scoring system expose hidden cost of switching as "
      + "the primary axis. For each tool, compute a \"lock-in risk\" score from "
      + "(a) data exportability. Can you get your analytics/scheduled posts OUT?",
    );
  });

  it("feeds the SANITISED note to the solo-dev score rationale", async () => {
    const view = renderDetail({ solution: raw(), lifecycle: "reference" });
    await fireEvent.click(view.getByRole("button", { name: /Solo/ }));
    const text = document.body.textContent ?? "";
    expect(text).toContain("up-front dataset required");
    expect(text).not.toMatch(/cold[-\s]start/i);
  });
});
