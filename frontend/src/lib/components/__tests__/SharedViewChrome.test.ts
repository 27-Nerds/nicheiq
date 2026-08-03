import { cleanup, render } from "@testing-library/svelte";
import { afterEach, describe, expect, it } from "vitest";

import SharedViewBanner from "$lib/components/share/SharedViewBanner.svelte";
import SharedViewEndCTA from "$lib/components/share/SharedViewEndCTA.svelte";

afterEach(cleanup);

describe("shared-view chrome", () => {
  it("identifies a shared report as a read-only copy without hiding the state in prose", () => {
    const view = render(SharedViewBanner, {
      props: { variant: "report", shareToken: "shared-token" },
    });

    expect(
      view.getByRole("complementary", { name: "Shared report: Read-only copy" }),
    ).toBeInTheDocument();
    expect(view.getByText("Read-only copy")).toBeInTheDocument();
    expect(view.getByRole("link", { name: /Research your own niche/ })).toHaveAttribute(
      "href",
      "/register?ref=shared-report&t=shared-token",
    );
  });

  it("labels discovery collaboration honestly instead of calling it view only", () => {
    const view = render(SharedViewBanner, {
      props: { variant: "discovery", shareToken: "discovery-token" },
    });

    expect(
      view.getByRole("complementary", { name: "Shared discovery: Voting enabled" }),
    ).toBeInTheDocument();
    expect(view.queryByText(/view only/i)).not.toBeInTheDocument();
  });

  it("keeps the end callout in the heading outline and avoids an unconditional refund claim", () => {
    const view = render(SharedViewEndCTA, { props: { variant: "report" } });

    const heading = view.getByRole("heading", {
      level: 2,
      name: "You saw one niche analyzed. Now do the same for yours.",
    });
    expect(heading).toHaveAttribute("id", "shared-report-end-title");
    expect(heading.closest("section")).toHaveAttribute(
      "aria-labelledby",
      "shared-report-end-title",
    );
    expect(view.getByText("Create an account to start a private Discovery run.")).toBeInTheDocument();
    expect(view.queryByText(/auto-refund/i)).not.toBeInTheDocument();
  });
});
