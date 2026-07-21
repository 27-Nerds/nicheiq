import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, waitFor } from "@testing-library/svelte";
import SharedDiscoveryView from "../SharedDiscoveryView.svelte";
import type { DiscoveryShareData } from "$lib/api";

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
    expect(getByText("Discovery is complete. Review the strongest opportunities before moving to Deep Research.")).toBeInTheDocument();
    expect(queryByText(/Ask the analyst/i)).not.toBeInTheDocument();
    expect(queryByText(/Send to GitHub/i)).not.toBeInTheDocument();

    const root = container.querySelector(".shared-discovery-root");
    const surface = container.querySelector('[data-annotation-surface="research:page"]');
    expect(root).toContainElement(surface as HTMLElement);
    expect(surface?.parentElement).toBe(root);
    expect(surface?.querySelector(".shared-discovery-content")).toBeInTheDocument();
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
    const voteButtons = getAllByRole("button", { name: "Vote for this solution" });
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
      const changedVote = getAllByRole("button", { name: "Change vote" });
      const remainingVote = getAllByRole("button", { name: "Vote for this solution" });
      expect(changedVote).toHaveLength(1);
      expect(changedVote[0]).toHaveTextContent("1");
      expect(remainingVote).toHaveLength(1);
      expect(remainingVote[0]).toHaveTextContent("0");
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
