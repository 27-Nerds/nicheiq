import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, waitFor } from "@testing-library/svelte";
import SharedDiscoveryView from "../SharedDiscoveryView.svelte";
import type { DiscoveryShareData } from "$lib/api";
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

  it("badges the recommended idea when the guidance still names this pool", async () => {
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
      .toHaveTextContent("Recommended");
    expect(table.querySelector('[data-solution-name="Beta Idea"]'))
      .not.toHaveTextContent("Recommended");
    expect(view.queryByText(EVIDENCE_WITHHELD_TITLE)).toBeNull();
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
