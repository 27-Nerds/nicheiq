import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render } from "@testing-library/svelte";
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
  });

  it("uses the shared long-topic treatment and visitor context", () => {
    const { getByRole, getByText } = render(SharedDiscoveryView, { props: { data, shareToken: "share-token" } });

    const heading = getByRole("heading", { level: 1, name: topic });
    expect(heading).toHaveClass("page-header-title--research-topic", "page-header-title--long");
    expect(heading).toHaveAttribute("title", topic);
    expect(getByText("Review the opportunities uncovered during Discovery.")).toBeInTheDocument();
  });
});
