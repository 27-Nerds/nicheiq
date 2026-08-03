import { cleanup, render } from "@testing-library/svelte";
import { afterEach, describe, expect, it } from "vitest";
import SelectionDecisionRecord from "../SelectionDecisionRecord.svelte";

afterEach(cleanup);

describe("SelectionDecisionRecord", () => {
  it("renders the saved scope, vote tally, rationale, and read-only route", () => {
    const view = render(SelectionDecisionRecord, {
      props: {
        jobId: "job-1",
        completed: true,
        selectedNames: ["Signal Desk"],
        selectionRationale: "Strongest buyer evidence and the clearest repeat workflow.",
        solutions: [{
          idea_id: "idea-signal",
          idea_revision: 3,
          solution_name: "Signal Desk",
          description: "Find buying signals",
          value_proposition: "Find recurring buying signals",
        }],
        solutionVotes: { "Signal Desk": 2 },
        solutionVotesById: { "idea-signal": 2 },
        voteRationales: [{
          solutionId: "idea-signal",
          solutionName: "Signal Desk",
          comment: "This matches the workflow best.",
        }],
      },
    });

    expect(view.getByRole("heading", { name: "How the research scope was chosen" })).toBeInTheDocument();
    expect(view.getByText("2 collaborator votes saved with selection")).toBeInTheDocument();
    expect(view.getByText("Strongest buyer evidence and the clearest repeat workflow.")).toBeInTheDocument();
    expect(view.getByText("This matches the workflow best.")).toBeInTheDocument();
    expect(view.queryByRole("button", { name: "Ask analyst to synthesize" })).not.toBeInTheDocument();
    expect(view.getByRole("link", { name: /Review decision record/ })).toHaveAttribute(
      "href",
      "/jobs/job-1/selection/compare",
    );
  });
});
