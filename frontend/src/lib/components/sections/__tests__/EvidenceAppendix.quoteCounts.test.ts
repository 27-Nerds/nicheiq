import { cleanup, fireEvent, render } from "@testing-library/svelte";
import { afterEach, describe, expect, it } from "vitest";
import type { EvidenceAppendix as EvidenceAppendixData, RedditThread } from "$lib/types/report";
import EvidenceAppendix from "../EvidenceAppendix.svelte";

afterEach(cleanup);

function thread(post_id: string, title: string): RedditThread {
  return {
    post_id,
    title,
    subreddit: "sweatystartup",
    platform: "reddit",
    score: 10,
    num_comments: 2,
    url: `https://example.com/${post_id}`,
    key_insight: "A retained source record.",
  };
}

function data(quoteCounts: number[]): EvidenceAppendixData {
  return {
    top_reddit_threads: [thread("t-1", "A retained thread")],
    pain_point_quote_sources: quoteCounts.map((count, groupIndex) => ({
      pain_point_title: `Pain group ${groupIndex + 1}`,
      quotes_with_sources: Array.from({ length: count }, (_, i) => ({
        quote: `Quote ${groupIndex + 1}.${i + 1}`,
        post_id: "t-1",
        source_label: "sweatystartup",
        score: "10",
      })),
    })),
  };
}

describe("EvidenceAppendix quote counts", () => {
  it("uses the singular noun for a single quote", () => {
    const view = render(EvidenceAppendix, { props: { data: data([1]) } });

    expect(view.getByText("quote")).toBeInTheDocument();
    expect(view.queryByText("quotes")).not.toBeInTheDocument();
  });

  it("uses the plural noun for several quotes", () => {
    const view = render(EvidenceAppendix, { props: { data: data([2]) } });

    expect(view.getByText("quotes")).toBeInTheDocument();
    expect(view.queryByText("quote")).not.toBeInTheDocument();
  });

  it("reads zero quotes as an absence of evidence, not a count", () => {
    const view = render(EvidenceAppendix, { props: { data: data([]) } });

    expect(view.getByText("No quotes")).toBeInTheDocument();
    expect(view.queryByText("quotes")).not.toBeInTheDocument();
    expect(view.queryByText("quote")).not.toBeInTheDocument();
  });

  it("pluralizes the per-pain-group badge", async () => {
    const view = render(EvidenceAppendix, { props: { data: data([1, 3]) } });

    await fireEvent.click(view.getByRole("button", { name: /Pain Point Evidence/ }));

    expect(view.getByText("1 quote")).toBeInTheDocument();
    expect(view.getByText("3 quotes")).toBeInTheDocument();
  });
});
