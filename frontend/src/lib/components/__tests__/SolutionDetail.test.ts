import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render } from "@testing-library/svelte";
import SolutionDetail from "../SolutionDetail.svelte";
import type { SolutionPreview } from "$lib/types/job";
import type { OverlapGroup } from "$lib/types/report";

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

    const md = getByRole("link", { name: /\.md/i });
    expect(md).toHaveAttribute(
      "href",
      "/api/jobs/job-1/solutions/idea-1/export/md?revision=2",
    );
    const json = getByRole("link", { name: /\.json/i });
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

    expect(getByRole("link", { name: /\.md/i })).toHaveAttribute(
      "href",
      "/api/jobs/job-1/solutions/idea-1/export/md?revision=1",
    );
  });

  it("hides export links without a job or an idea identity", () => {
    const noJob = renderDetail({ solution: solution() });
    expect(noJob.queryByRole("link", { name: /\.md/i })).not.toBeInTheDocument();

    cleanup();

    const noIdentity = renderDetail({ solution: solution({ idea_id: undefined }), jobId: "job-1" });
    expect(noIdentity.queryByRole("link", { name: /\.md/i })).not.toBeInTheDocument();
  });
});

describe("SolutionDetail interaction model", () => {
  it("uses roving tab focus and supports Arrow, Home, and End keys", async () => {
    const view = renderDetail({ solution: solution() });
    const overview = view.getByRole("tab", { name: "Overview" });
    const detail = view.getByRole("tab", { name: "Full detail" });

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
    await fireEvent.click(view.getByRole("tab", { name: "Full detail" }));
    expect(view.getByRole("tab", { name: "Full detail" })).toHaveAttribute(
      "aria-selected",
      "true",
    );

    // Page to the next candidate — the user comparing Full details stays on that tab.
    await view.rerender({
      open: true,
      solution: ideas[1],
      solutions: ideas,
      currentIndex: 1,
      onNavigate: vi.fn(),
      onClose: vi.fn(),
    });

    expect(view.getByRole("tab", { name: "Full detail" })).toHaveAttribute(
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

    await fireEvent.click(view.getByRole("button", { name: "Shortlist" }));
    expect(onSelect).toHaveBeenCalledWith(candidate);
  });
});

describe("SolutionDetail lifecycle and provenance", () => {
  it("labels a legacy candidate without score inputs as not scored", () => {
    const view = renderDetail({ solution: solution() });

    expect(view.getByRole("button", { name: "Overall score details" })).toHaveTextContent(
      "Not scored",
    );
  });

  it("never renders shortlist controls in completed reference mode and uses completed tense", () => {
    const view = renderDetail({
      solution: solution(),
      lifecycle: "completed",
      onSelect: vi.fn(),
    });

    expect(view.queryByRole("button", { name: /Shortlist|Remove|Limit reached/ })).not.toBeInTheDocument();
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

  it("links the disabled Limit reached button to the visible hint via aria-describedby", () => {
    const view = renderDetail({
      solution: solution(),
      lifecycle: "selection",
      isSelected: false,
      maxReached: true,
      selectedCount: 3,
      maxSelections: 3,
      onSelect: vi.fn(),
    });

    const button = view.getByRole("button", { name: "Limit reached" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-describedby", "shortlist-limit-note");
    const note = document.getElementById("shortlist-limit-note");
    expect(note).toHaveTextContent("Remove one to add this candidate.");
  });
});
