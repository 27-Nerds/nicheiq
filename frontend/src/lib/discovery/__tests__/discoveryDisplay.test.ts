import { describe, expect, it } from "vitest";
import {
  createDiscoveryDisplayModel,
  discoveryDiscussionCount,
  rankDiscoveryPainPoints,
} from "../discoveryDisplay";

describe("discoveryDisplay", () => {
  it("uses the analyzed cross-platform discussion total before URL fallbacks", () => {
    expect(discoveryDiscussionCount({
      research_metadata: {
        reddit_posts_analyzed: 4,
        twitter_threads_analyzed: 3,
        generic_posts_analyzed: 2,
        filtering_stats: { total_urls_relevant: 99 },
      },
    } as never, {
      methodology: { urls_relevant: 88 },
    } as never)).toBe(9);
  });

  it("keeps equal-severity pain points in report order", () => {
    const points = [
      { title: "First", severity_score: 0.7 },
      { title: "Second", severity_score: 0.9 },
      { title: "Third", severity_score: 0.7 },
    ] as never[];

    expect(rankDiscoveryPainPoints(points).map((point) => point.title)).toEqual([
      "Second",
      "First",
      "Third",
    ]);
  });

  it("quarantines out-of-range legacy pain scores instead of rendering invalid percentages", () => {
    const [point] = rankDiscoveryPainPoints([{
      title: "Malformed scores",
      severity_score: 99,
      commercial_intent: -1,
    }]);

    expect(point.severity_score).toBe(0);
    expect(point.commercial_intent).toBe(0);
  });

  it("derives one owner/share display model and only exposes rendered sections", () => {
    const model = createDiscoveryDisplayModel({
      research_metadata: { reddit_posts_analyzed: 3, generic_posts_analyzed: 2 },
      detailed_pain_points: [{ title: "Pain", severity_score: 0.8 }],
      audience_mapping: {
        audience_segments: [{ segment_name: "Operators" }],
        community_hubs: ["Hacker News"],
      },
      pain_point_analytics: { total_pain_points: 1 },
    } as never, {
      subreddit_names: ["r/saas", "Hacker News"],
      discussion_trend: [{ month: "2026-01", count: 5 }],
      methodology: { total_engagement: 12 },
    } as never);

    expect(model.discussionCount).toBe(5);
    expect(model.communityNames).toEqual(["r/saas", "Hacker News"]);
    expect(model.availableSectionIds).toEqual([
      "overview",
      "market-snapshot",
      "pain-points",
      "audience",
      "community",
    ]);
  });
});
