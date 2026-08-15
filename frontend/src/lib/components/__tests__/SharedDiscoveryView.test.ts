import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, waitFor } from "@testing-library/svelte";
import SharedDiscoveryView from "../SharedDiscoveryView.svelte";
import type { DiscoveryShareData } from "$lib/api";
import type { IdeaValidation } from "$lib/types/report";
// Asserted through the shared constant, never a copy of the sentence.
import { EVIDENCE_WITHHELD_DETAIL, EVIDENCE_WITHHELD_TITLE } from "$lib/selection/labels";
/**
 * CAPTURED, not written. Each entry records the source `file` and JSON `path` it was
 * copied byte-exact from. Vendored because the artifact it came from lives under the
 * gitignored `output/` tree: importing it directly made this whole file fail to load on
 * any checkout without that run, which vitest reports as a failed FILE contributing
 * "no tests" — six assertions vanishing from the totals without a red test.
 * `noEscapingTestImports.test.ts` is the guard that keeps that from recurring.
 */
import capturedCommunities from "./fixtures/discoveryCommunities.captured.json";
import { gradedBlock, notEvaluatedBlock } from "./fixtures/ideaValidationBlocks";

const capturedValue = <T,>(path: string): T => {
  const hit = capturedCommunities.find((entry) => entry.path === path);
  if (!hit) throw new Error(`No captured fixture entry for ${path}`);
  return hit.value as T;
};

const checkpoint = {
  subreddit_names: capturedValue<string[]>(".subreddit_names"),
  subreddit_post_counts: capturedValue<Record<string, number>>(".subreddit_post_counts"),
};

const topic =
  "Employees trying to figure out which AI skills to learn and where to expand their professional knowledge to stay employable, overwhelmed by scattered courses and conflicting advice about what their role will actually require";

const data: DiscoveryShareData = {
  shareType: "discovery",
  niche: topic,
  solutions: [],
  discoveryData: null,
  previewReport: null,
  voteSummary: { totalVotes: 0, solutionVotes: {} },
};

describe("SharedDiscoveryView research topic header", () => {
  afterEach(() => {
    cleanup();
    localStorage.clear();
    vi.unstubAllGlobals();
  });

  it("uses the shared long-topic treatment and visitor context", () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));
    const { container, getByRole, getByText, queryByText } = render(SharedDiscoveryView, { props: { data, shareToken: "share-token" } });

    const heading = getByRole("heading", { level: 1, name: topic });
    expect(heading).toHaveClass("page-header-title--research-topic", "page-header-title--long");
    expect(heading).toHaveAttribute("title", topic);
    expect(getByText("Discovery is complete. Review the ranked opportunities and vote for the direction you would back.")).toBeInTheDocument();
    expect(getByText("Voting enabled")).toBeInTheDocument();
    expect(queryByText("Read-only copy")).not.toBeInTheDocument();
    expect(queryByText(/Ask the analyst/i)).not.toBeInTheDocument();
    expect(queryByText(/Send to GitHub/i)).not.toBeInTheDocument();

    const root = container.querySelector(".shared-discovery-root");
    const surface = container.querySelector('[data-annotation-surface="research:page"]');
    expect(root).toContainElement(surface as HTMLElement);
    expect(surface?.parentElement).toBe(root);
    expect(surface?.querySelector(".shared-discovery-content")).toBeInTheDocument();
  });

  it("renders the complete idea check as a read-only shared report", () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));
    /**
     * GENERATED, then narrated (2026-08-15). Every list on this block used to be typed here
     * — three parts, one anchored pain, one competitor, one kill risk — beside two fields
     * correctly taken from the builder. The graded block the pipeline really emits carries
     * twelve competitors and a populated `score_bands`/`breadth`, so the hand-written
     * version was a shape it cannot produce: the same defect the two derived fields below
     * were added to fix, still live on five more.
     *
     * Only the NARRATIVE this test is about is overridden: the outcome, the name, and the
     * adversarial-review verdict whose rendering the assertions below check.
     */
    const ideaValidation: IdeaValidation = gradedBlock({
      outcome: "premise_unproven",
      idea_name: "Context-aware support reply extension",
      headline: "The problem is real, but the product premise is unproven.",
      user_idea_text: "A browser extension that drafts context-aware support replies.",
      user_idea_brief: "A browser extension that drafts context-aware support replies.",
      derived_market: "Shopify merchant support tools",
      derived_buyer: "Independent Shopify merchants",
      red_team_verdict: "killed",
      red_team_findings: [{
        claim: "The incumbent already ships the same workflow.",
        kind: "verified_incumbent_overlap",
      }],
      seed_idea_id: "idea-seed",
      seed_idea_revision: 1,
      seed_purchasable: true,
      seed_display_composite_score: 55,
    } as Partial<IdeaValidation>);
    const validateShare: DiscoveryShareData = {
      ...data,
      nicheDisplay: "Context-aware support reply extension",
      solutions: [{
        solution_name: "Context-aware support reply extension",
        description: "Draft support replies with order context.",
        value_proposition: "Answer repetitive tickets without switching tabs.",
        idea_id: "idea-seed",
        idea_revision: 1,
        source_frame: "user_seed",
        generation_operation_id: "validate",
        adjusted_composite_score: 0.55,
      }],
      previewReport: { idea_validation: ideaValidation } as unknown as NonNullable<DiscoveryShareData["previewReport"]>,
    };

    const view = render(SharedDiscoveryView, {
      props: { data: validateShare, shareToken: "share-token" },
    });

    expect(view.getByRole("heading", { level: 1, name: "Context-aware support reply extension" })).toBeInTheDocument();
    expect(view.getByRole("heading", { name: "How we read your idea" })).toBeInTheDocument();
    expect(view.getByRole("heading", { name: "Evidence for your idea" })).toBeInTheDocument();
    // The competitor card's heading is keyed on the `space_occupied` part's state, so it is
    // read from the generated block rather than typed: the hand-written fixture this
    // replaced said `review_concerns`, and the block the pipeline really emits for this run
    // says `none_found`, which renders the OTHER heading. Asserting the literal here is how
    // a spec ends up pinning a card the real shape never shows.
    const spaceState = ideaValidation.parts?.find((p) => p.key === "space_occupied")?.state;
    expect(view.getByRole("heading", {
      name: spaceState === "none_found"
        ? "Who ships in this category"
        : "Competitors and adjacent tools",
    })).toBeInTheDocument();
    expect(view.getByRole("heading", { name: "What would kill it" })).toBeInTheDocument();
    expect(view.getByText(/The adversarial review found verified incumbent overlap/))
      .toBeInTheDocument();
    expect(view.queryByText(/could not find evidence for this idea's premise/)).toBeNull();
    expect(view.getByRole("heading", { name: "Your idea, ranked with the alternatives" })).toBeInTheDocument();
    expect(view.queryByText(/Edit and rerun/)).not.toBeInTheDocument();
    expect(view.queryByText("Continue with your idea")).not.toBeInTheDocument();

    cleanup();
    const malformedValidation = { ...ideaValidation };
    Object.assign(malformedValidation as unknown as Record<string, unknown>, {
      incumbent_parity: 12,
      red_team_caveats: [null, 7, {}, ""],
      red_team_findings: [
        { kind: "verified_incumbent_overlap", claim: 99 },
        { kind: "invented_kind", claim: "Not a contract finding." },
      ],
    });
    const malformedView = render(SharedDiscoveryView, {
      props: {
        data: {
          ...validateShare,
          previewReport: {
            idea_validation: malformedValidation,
          } as unknown as NonNullable<DiscoveryShareData["previewReport"]>,
        },
        shareToken: "share-token",
      },
    });

    expect(malformedView.getByText(/decision-critical evidence incomplete/))
      .toBeInTheDocument();
    expect(malformedView.queryByText(/could not find evidence for this idea's premise/))
      .not.toBeInTheDocument();
    expect(malformedView.queryByText(/material concern/i)).not.toBeInTheDocument();
    expect(malformedView.queryByText(/decision-critical objection/i)).not.toBeInTheDocument();
    expect(malformedView.queryByText(/verified incumbent overlap/i)).not.toBeInTheDocument();
    expect(malformedView.queryByText(/Not a contract finding/)).not.toBeInTheDocument();
  });

  it("wires checkpoint post counts into the rendered community order", () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));
    const checkpointData: DiscoveryShareData = {
      ...data,
      discoveryData: {
        subreddit_names: checkpoint.subreddit_names,
        subreddit_post_counts: checkpoint.subreddit_post_counts,
      },
    };

    const { container } = render(SharedDiscoveryView, {
      props: { data: checkpointData, shareToken: "share-token" },
    });
    const renderedCommunities = Array.from(
      container.querySelectorAll('[aria-label="Captured communities"] .source-pill'),
    ).slice(0, 8).map((node) => node.textContent?.trim());

    expect(renderedCommunities).toEqual([
      "r/InventoryManagement",
      "r/VetTech",
      "r/Veterinary",
      "r/pharmacy",
      "r/Pets",
      "r/veterinaryprofession",
      "r/ADHD",
      "r/PharmacyTechnician",
    ]);
  });

  it("submits and highlights duplicate-named ideas by stable ID", async () => {
    localStorage.setItem("nicheiq_viewer_token", "00000000-0000-4000-8000-000000000001");
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "POST") {
        return new Response(JSON.stringify({
          totalVotes: 1,
          solutionVotes: { Duplicate: 1 },
          solutionVotesById: { idea_second: 1 },
        }), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      return new Response(JSON.stringify({
        totalVotes: 0,
        solutionVotes: {},
        solutionVotesById: {},
        viewerVote: null,
      }), { status: 200, headers: { "Content-Type": "application/json" } });
    });
    vi.stubGlobal("fetch", fetchMock);

    const duplicateData: DiscoveryShareData = {
      ...data,
      solutions: [
        {
          solution_name: "Duplicate",
          description: "First duplicate candidate",
          value_proposition: "First candidate value",
          idea_id: "idea_first",
          idea_revision: 1,
        },
        {
          solution_name: "Duplicate",
          description: "Second duplicate candidate",
          value_proposition: "Second candidate value",
          idea_id: "idea_second",
          idea_revision: 1,
        },
      ],
    };
    const { getAllByRole } = render(SharedDiscoveryView, {
      props: { data: duplicateData, shareToken: "share-token" },
    });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });
    const voteButtons = getAllByRole("button", { name: /Vote for ranked idea/ });
    expect(voteButtons[0]).toHaveAccessibleName("Vote for ranked idea 1: Duplicate. 0 votes");
    expect(voteButtons[0]).toHaveAttribute("aria-pressed", "false");
    expect(voteButtons[1]).toHaveAccessibleName("Vote for ranked idea 2: Duplicate. 0 votes");
    await fireEvent.click(voteButtons[1]);

    await waitFor(() => {
      const postCall = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
      expect(postCall).toBeDefined();
      expect(JSON.parse(String(postCall?.[1]?.body))).toMatchObject({
        solutionId: "idea_second",
        solutionName: "Duplicate",
      });
    });
    await waitFor(() => {
      const changedVote = getAllByRole("button", { name: /Your vote:/ });
      const remainingVote = getAllByRole("button", { name: /Vote for ranked idea/ });
      expect(changedVote).toHaveLength(1);
      expect(changedVote[0]).toHaveAccessibleName("Your vote: ranked idea 2: Duplicate. 1 vote");
      expect(changedVote[0]).toHaveAttribute("aria-pressed", "true");
      expect(remainingVote).toHaveLength(1);
      expect(remainingVote[0]).toHaveAccessibleName("Vote for ranked idea 1: Duplicate. 0 votes");
    });
  });

  it("restores the viewer's private rationale and saves a trimmed edit", async () => {
    localStorage.setItem("nicheiq_viewer_token", "00000000-0000-4000-8000-000000000001");
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "POST") {
        return new Response(JSON.stringify({
          totalVotes: 1,
          solutionVotes: { "Chosen idea": 1 },
          solutionVotesById: { idea_chosen: 1 },
        }), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      return new Response(JSON.stringify({
        totalVotes: 1,
        solutionVotes: { "Chosen idea": 1 },
        solutionVotesById: { idea_chosen: 1 },
        viewerVote: {
          solutionId: "idea_chosen",
          solutionName: "Chosen idea",
          comment: "This fits my workflow.",
        },
      }), { status: 200, headers: { "Content-Type": "application/json" } });
    });
    vi.stubGlobal("fetch", fetchMock);

    const rationaleData: DiscoveryShareData = {
      ...data,
      solutions: [{
        solution_name: "Chosen idea",
        description: "A candidate with a clear workflow",
        value_proposition: "Saves review time",
        idea_id: "idea_chosen",
        idea_revision: 1,
      }],
    };
    const view = render(SharedDiscoveryView, {
      props: { data: rationaleData, shareToken: "share-token" },
    });

    expect(await view.findByText("Your rationale is saved for the report owner.")).toBeInTheDocument();
    await fireEvent.click(view.getByRole("button", { name: "Edit rationale" }));
    const textarea = view.getByRole("textbox", { name: "Why you prefer this idea" });
    expect(textarea).toHaveValue("This fits my workflow.");
    await fireEvent.input(textarea, { target: { value: "  Useful for weekly reviews.  " } });
    await fireEvent.click(view.getByRole("button", { name: "Save rationale" }));

    await waitFor(() => {
      const postCall = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
      expect(postCall).toBeDefined();
      expect(JSON.parse(String(postCall?.[1]?.body))).toMatchObject({
        solutionId: "idea_chosen",
        solutionName: "Chosen idea",
        comment: "Useful for weekly reviews.",
      });
    });
  });
});

/**
 * Finding D2, secondary defect. The public share serves the LIVE pool, so the analyst
 * "Recommended" badge on a visitor's ballot must be bound to the pool the guidance was
 * written for. The backend withholds the pool-scoped fields outright when they diverge
 * (discoveryShares.portfolioSummary.test.ts); this covers what the visitor then sees.
 */
describe("SharedDiscoveryView portfolio guidance", () => {
  afterEach(() => {
    cleanup();
    localStorage.clear();
    vi.unstubAllGlobals();
  });

  /** The fingerprint the pipeline writes for exactly these two ideas. Pinned in
   *  backend/src/routes/__tests__/discoveryShares.portfolioSummary.test.ts. */
  const POOL_FINGERPRINT = '{"version":1,"ideas":[["idea-alpha",1],["idea-beta",1]]}';

  const sharedSolutions = [
    {
      solution_name: "Alpha Idea",
      idea_id: "idea-alpha",
      idea_revision: 1,
      description: "Reconciles service records against the parts actually shipped",
      value_proposition: "Cuts the reconciliation pass from a day to an hour",
      market_fit_score: 0.72,
      technical_feasibility_score: 0.68,
      adjusted_composite_score: 0.71,
    },
    {
      solution_name: "Beta Idea",
      idea_id: "idea-beta",
      idea_revision: 1,
      description: "Tracks warranty claims through their approval chain",
      value_proposition: "Shows where a claim stalled without opening the portal",
      market_fit_score: 0.61,
      technical_feasibility_score: 0.64,
      adjusted_composite_score: 0.62,
    },
  ] as unknown as DiscoveryShareData["solutions"];

  it("does not turn stored portfolio prose into a recommendation badge", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));
    const view = render(SharedDiscoveryView, {
      props: {
        data: {
          ...data,
          solutions: sharedSolutions,
          previewReport: {
            idea_portfolio_summary:
              "Alpha Idea most deserves deeper validation because its buyer is named directly in the evidence.",
            idea_portfolio_summary_fingerprint: POOL_FINGERPRINT,
          },
          evidenceFramingWithheld: false,
        },
        shareToken: "share-token",
      },
    });

    const table = await view.findByRole("table", { name: "Ranked ideas" });
    await waitFor(() =>
      expect(table.querySelectorAll("[data-solution-name]")).toHaveLength(2));
    expect(table.querySelector('[data-solution-name="Alpha Idea"]'))
      .not.toHaveTextContent("Recommended");
    expect(table.querySelector('[data-solution-name="Beta Idea"]'))
      .not.toHaveTextContent("Recommended");
    expect(view.queryByText(EVIDENCE_WITHHELD_TITLE)).toBeNull();
  });

  it("renders delivery format in the visitor's shared candidate detail", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));
    const view = render(SharedDiscoveryView, {
      props: {
        data: {
          ...data,
          solutions: sharedSolutions.map((solution, index) => (
            index === 0
              ? { ...solution, delivery_format: "browser-extension", project_type: "saas" }
              : solution
          )),
        },
        shareToken: "share-token",
      },
    });

    await fireEvent.click(
      await view.findByRole("button", { name: /Review details for Alpha Idea/ }),
    );

    expect(await view.findByText("Delivered as")).toBeInTheDocument();
    expect(view.getByText("Browser extension")).toBeInTheDocument();
    expect(view.queryByText("Product shape")).not.toBeInTheDocument();
  });

  it("says the framing was withheld and badges nothing once the backend strips it", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));
    const view = render(SharedDiscoveryView, {
      props: {
        data: {
          ...data,
          solutions: sharedSolutions,
          // What the endpoint actually returns for a diverged pool: pool-scoped fields
          // gone, niche-scoped framing intact.
          previewReport: {
            market_reality: { incumbents: [{ name: "Sheet template pack" }] },
          },
          evidenceFramingWithheld: true,
        },
        shareToken: "share-token",
      },
    });

    const banner = await view.findByText(EVIDENCE_WITHHELD_TITLE);
    expect(banner.parentElement).toHaveTextContent(
      EVIDENCE_WITHHELD_DETAIL,
    );
    const table = await view.findByRole("table", { name: "Ranked ideas" });
    expect(table).not.toHaveTextContent("Recommended");
  });
});

/**
 * A share of a run that REFUSED to grade the submitted idea. `idea_validation` is present
 * on that outcome too, so `isIdeaCheckShare` (block presence) answered a different question
 * from "was an idea checked" — and every visitor-facing line keyed on it asserted a verdict,
 * a ranked submission and a completed check that do not exist.
 */
describe("SharedDiscoveryView · shared run that could not grade the idea", () => {
  afterEach(() => {
    cleanup();
    localStorage.clear();
    vi.unstubAllGlobals();
  });

  const notEvaluatedShare = (): DiscoveryShareData => ({
    ...data,
    nicheDisplay: "Shopify merchant support tools",
    solutions: [{
      solution_name: "Order-context reply drafts",
      description: "Draft support replies with order context.",
      value_proposition: "Answer repetitive tickets without switching tabs.",
      idea_id: "idea-alt",
      idea_revision: 1,
      adjusted_composite_score: 0.61,
    }],
    // GENERATED, not hand-written. The version here carried `experiment_ladder` with one
    // rung and one desk limit — the pipeline emits four rungs and three limits on a refusal
    // (both fields are stamped before the refusal branch), so the read-only share's real
    // last card was a four-rung testing plan for an idea that was never graded, and no
    // assertion in this file could see it. Regenerate via
    // tests/unit/report/test_not_evaluated_fixture_contract.py.
    previewReport: {
      idea_validation: notEvaluatedBlock({
        user_idea_text: "A browser extension that drafts context-aware support replies.",
        user_idea_brief: "A browser extension that drafts context-aware support replies.",
        // Derived, not typed: the narrative varies the pool COUNT, and the rest of the
        // record keeps the shape the builder emits.
        alternatives: { ...notEvaluatedBlock().alternatives, count: 1, top: [] },
      }),
    } as unknown as NonNullable<DiscoveryShareData["previewReport"]>,
  });

  it("never tells a visitor the submitted idea was checked, ranked or verdicted", () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));
    const view = render(SharedDiscoveryView, {
      props: { data: notEvaluatedShare(), shareToken: "share-token" },
    });

    expect(view.queryByText(/Review the submitted idea's verdict/)).not.toBeInTheDocument();
    expect(
      view.queryByRole("heading", { name: "Your idea, ranked with the alternatives" }),
    ).not.toBeInTheDocument();
    expect(view.container.textContent ?? "").not.toContain("You saw one idea checked.");

    expect(view.getByRole("heading", { name: "The approaches this run generated" }))
      .toBeInTheDocument();
    expect(view.getByText(/could not check the submitted idea/)).toBeInTheDocument();
    expect(view.getByText(/this run could not grade it, so no version of it was built/))
      .toBeInTheDocument();
    expect(view.container.textContent ?? "").toContain("That check couldn't finish.");
  });
});
