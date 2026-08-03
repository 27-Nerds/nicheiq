import { cleanup, fireEvent, render } from "@testing-library/svelte";
import { afterEach, describe, expect, it } from "vitest";
import type { EvidenceAppendix as EvidenceAppendixData, RedditThread } from "$lib/types/report";
import EvidenceAppendix from "../EvidenceAppendix.svelte";

afterEach(cleanup);

function thread(overrides: Partial<RedditThread> & Pick<RedditThread, "post_id" | "title">): RedditThread {
  return {
    subreddit: "test",
    score: 1,
    num_comments: 1,
    url: `https://example.com/${overrides.post_id}`,
    key_insight: "A retained source record.",
    ...overrides,
  };
}

describe("EvidenceAppendix provenance", () => {
  it("opens selected-problem sources first and keeps the engagement corpus contextual", async () => {
    const selectedPain = "Cannot balance truck stock against return-trip risk";
    const unrelatedThreadTitle = "A highly engaged but unrelated sysadmin thread";
    const data: EvidenceAppendixData = {
      top_reddit_threads: [
        thread({
          post_id: "global-1",
          title: unrelatedThreadTitle,
          subreddit: "r/sysadmin",
          platform: "reddit",
          score: 1000,
        }),
        thread({
          post_id: "selected-1",
          title: "Appliance repair truck-stock discussion",
          subreddit: "sweatystartup",
          platform: "reddit",
          score: 250,
        }),
        thread({
          post_id: "hn-1",
          title: "A broader Hacker News discussion",
          subreddit: "Hacker News",
          platform: "hackernews",
          score: 100,
        }),
      ],
      pain_point_quote_sources: [
        {
          pain_point_title: selectedPain,
          quotes_with_sources: [
            {
              quote: "I either carry too much stock or make an unpaid return trip.",
              post_id: "selected-1",
              source_label: "sweatystartup",
              score: "250",
            },
          ],
        },
        {
          pain_point_title: "A different niche problem",
          quotes_with_sources: [
            {
              quote: "Evidence for another problem.",
              post_id: "other-1",
              source_label: "r/appliancerepair",
              score: "12",
            },
          ],
        },
      ],
    };

    const view = render(EvidenceAppendix, {
      props: { data, selectedPainTitle: selectedPain },
    });

    expect(view.getByRole("button", { name: /Selected-Problem Evidence/ })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
    expect(view.getByText(selectedPain)).toBeInTheDocument();
    expect(
      view.getByText("I either carry too much stock or make an unpaid return trip."),
    ).toBeInTheDocument();
    expect(view.getByText("Appliance repair truck-stock discussion")).toBeInTheDocument();
    expect(view.getAllByText("r/sweatystartup").length).toBeGreaterThan(0);
    expect(view.queryByText(unrelatedThreadTitle)).not.toBeInTheDocument();

    const corpusButton = view.getByRole("button", { name: /Engagement-Ranked Niche Corpus/ });
    expect(corpusButton).toHaveAttribute("aria-expanded", "false");
    await fireEvent.click(corpusButton);

    expect(view.getByText(unrelatedThreadTitle)).toBeInTheDocument();
    expect(view.getByText("A broader Hacker News discussion")).toBeInTheDocument();
    expect(view.getAllByText("r/sysadmin").length).toBeGreaterThan(0);
    expect(view.queryByText("r/r/sysadmin")).not.toBeInTheDocument();
    expect(view.getAllByText("Hacker News").length).toBeGreaterThan(0);
    expect(view.queryByText("r/Hacker News")).not.toBeInTheDocument();
    expect(
      view.getByText(/High engagement does not mean a thread supports the selected problem/i),
    ).toBeInTheDocument();

    await fireEvent.click(view.getByRole("button", { name: /Other Niche Pain Evidence/ }));
    expect(view.getByText("A different niche problem")).toBeInTheDocument();
  });
});
