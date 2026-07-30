import { cleanup, render } from "@testing-library/svelte";
import { createRawSnippet } from "svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import AnalysisAppendix from "../AnalysisAppendix.svelte";
import RuledOutDetail from "../RuledOutDetail.svelte";
import RuledOutList from "../RuledOutList.svelte";
import type { RuledOutFinding } from "$lib/types/report";

const finding: RuledOutFinding = {
  pain_title: "Teams lose the signal after a GLP-1 exit",
  idea_name: "GLP-1 Off-Ramp + Peptide Maintenance Hub",
  reason: "The buyer signal was too weak.",
  market_fit: 0.31,
  market_fit_band: "low",
  prior_tier: "explore",
  source: "demoted_winner",
  evidence: "Most users expected free guidance.",
  source_frame: "owner_synthesis",
  evaluation_id: "evaluation-1",
};

afterEach(cleanup);

describe("ruled-out discovery surfaces", () => {
  it("describes pipeline screening without calling it the user's shortlist", () => {
    const view = render(RuledOutList, {
      props: {
        findings: [finding],
        highlightedIndex: null,
        onOpen: vi.fn(),
      },
    });

    expect(view.getByText(
      "These concepts were examined, then screened out before the ranked ideas were presented. Open an idea to review the evidence and assumptions behind that decision.",
    )).toBeInTheDocument();
    expect(view.queryByText(/excluded from the shortlist/i)).toBeNull();
  });

  it("names the appendix after the ranked pipeline output", () => {
    const children = createRawSnippet(() => ({
      render: () => "<p>Appendix body</p>",
    }));
    const view = render(AnalysisAppendix, {
      props: { meta: "1 idea ruled out", children },
    });

    expect(view.getByText("How the ranked ideas were formed")).toBeInTheDocument();
    expect(view.queryByText("How the shortlist was formed")).toBeNull();
  });

  it("keeps requested-evaluation provenance visible in detail", () => {
    const view = render(RuledOutDetail, {
      props: { finding, onClose: vi.fn() },
    });

    expect(view.getByText("Evaluated on request")).toBeInTheDocument();
    expect(view.getByText(finding.idea_name as string)).toBeInTheDocument();
  });
});
