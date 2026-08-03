import { afterEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render } from "@testing-library/svelte";
import SelectedSolutionsSummary from "../SelectedSolutionsSummary.svelte";
import type { SolutionPreview } from "$lib/types/job";

afterEach(cleanup);

function candidate(revision: number): SolutionPreview {
  return {
    idea_id: "idea-1",
    idea_revision: revision,
    solution_name: "Same display name",
    description: `Revision ${revision} description`,
    value_proposition: `Revision ${revision} value`,
    market_fit_score: 0.6,
    technical_feasibility_score: 0.7,
  };
}

describe("SelectedSolutionsSummary exact identity", () => {
  it("resolves saved id+revision rather than the first duplicate name", async () => {
    const view = render(SelectedSolutionsSummary, {
      props: {
        selectedNames: ["Same display name"],
        selectedItems: [{ ideaId: "idea-1", ideaRevision: 2 }],
        solutionIdeas: [candidate(1), candidate(2)],
        status: "COMPLETED",
        jobId: "job-1",
        showIdentity: true,
      },
    });

    expect(view.getByLabelText("Exact Deep Research selection")).toHaveTextContent(
      "Idea idea-1 · rev 2",
    );
    await fireEvent.click(view.getByRole("button", { name: "Your Selections (1)" }));
    await fireEvent.click(view.getByRole("button", { name: /Same display name/ }));

    expect(view.getByText("Revision 2 description")).toBeInTheDocument();
    expect(view.getByRole("link", { name: "Download Markdown" })).toHaveAttribute(
      "href",
      "/api/jobs/job-1/solutions/idea-1/export/md?revision=2",
    );
    expect(view.queryByRole("button", { name: /Remove|Shortlist/ })).not.toBeInTheDocument();
    expect(view.getByText("Deep Research checked this idea")).toBeInTheDocument();
  });

  it("does not guess when a legacy name matches multiple revisions", () => {
    const view = render(SelectedSolutionsSummary, {
      props: {
        selectedNames: ["Same display name"],
        solutionIdeas: [candidate(1), candidate(2)],
        status: "RUNNING_PHASE2",
      },
    });

    expect(view.getByText(/1 selected candidate is no longer available at the saved revision/)).toBeInTheDocument();
    expect(view.queryByRole("button", { name: /Same display name/ })).not.toBeInTheDocument();
  });

  it("marks the exact recommended revision when finalists share a name", () => {
    const view = render(SelectedSolutionsSummary, {
      props: {
        selectedNames: ["Same display name", "Same display name"],
        selectedItems: [
          { ideaId: "idea-1", ideaRevision: 1 },
          { ideaId: "idea-1", ideaRevision: 2 },
        ],
        solutionIdeas: [candidate(1), candidate(2)],
        primaryWinner: "Same display name",
        primaryWinnerRef: { ideaId: "idea-1", ideaRevision: 2 },
        status: "RUNNING_PHASE2",
      },
    });

    expect(view.getAllByText("Top Recommended")).toHaveLength(1);
  });
});
