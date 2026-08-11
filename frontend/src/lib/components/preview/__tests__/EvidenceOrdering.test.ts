import { afterEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render } from "@testing-library/svelte";
import type {
  DiscoveryData,
  SocialPost,
  SpeakerAttribution,
  SpeakerRole,
} from "$lib/types/discovery";
import CommunitySourcesSection, { orderCommunitiesByPostCount } from "../CommunitySourcesSection.svelte";
import { orderQuotesByRelevance } from "../PainPointSummaryCard.svelte";
import DiscoveryEvidence, {
  orderSocialPostsByRelevance,
  rankDiscoveryConversations,
} from "../../discovery/DiscoveryEvidence.svelte";
import { bookkeepingDiscoveryFixture } from "./fixtures/bookkeepingDiscovery.fixture";
import { veterinaryDiscoveryFixture } from "./fixtures/veterinaryDiscovery.fixture";

function post(title: string, subreddit: string, score: number): SocialPost {
  return {
    title,
    subreddit,
    score,
    num_comments: 0,
    url: `https://example.com/${subreddit}/${score}`,
    created_utc: "2026-01-01T00:00:00Z",
  };
}

function attribution(
  contribution_id: string,
  role: SpeakerRole,
  confidence = 0.9,
): SpeakerAttribution {
  return {
    role,
    confidence,
    rationale: `Fixture role: ${role}`,
    target_segment: "Independent practice owners",
    contribution_id,
    author: `${contribution_id}-author`,
    is_submitter: false,
    method: "llm",
  };
}

describe("evidence showcase ordering", () => {
  afterEach(cleanup);

  it("uses complete checkpoint corpora without trimming or reshaping them", () => {
    const corpusShape = (data: DiscoveryData) => ({
      painGroups: Object.keys(data.quotes).length,
      quotes: Object.values(data.quotes).flat().length,
      quotedPosts: new Set(Object.values(data.quotes).flat().map((quote) => quote.post_id)).size,
      sampledPosts: data.social_posts_sample.length,
    });

    expect(corpusShape(veterinaryDiscoveryFixture)).toEqual({
      painGroups: 13,
      quotes: 35,
      quotedPosts: 17,
      sampledPosts: 10,
    });
    expect(corpusShape(bookkeepingDiscoveryFixture)).toEqual({
      painGroups: 26,
      quotes: 67,
      quotedPosts: 40,
      sampledPosts: 10,
    });
  });

  it("orders communities by the same post counts used for share distribution", () => {
    const names = ["r/ADHD", "r/InventoryManagement", "r/VetTech", "r/Veterinary"];
    const counts = { InventoryManagement: 24, VetTech: 10, Veterinary: 9, ADHD: 3 };

    expect(orderCommunitiesByPostCount(names, counts)).toEqual([
      "r/InventoryManagement",
      "r/VetTech",
      "r/Veterinary",
      "r/ADHD",
    ]);
  });

  it("preserves count-map order for equal shares and appends communities without counts", () => {
    const names = ["r/Uncounted", "r/ADHD", "r/veterinaryprofession"];
    const counts = { veterinaryprofession: 3, ADHD: 3 };

    expect(orderCommunitiesByPostCount(names, counts)).toEqual([
      "r/veterinaryprofession",
      "r/ADHD",
      "r/Uncounted",
    ]);
  });

  it("keeps today's community order when counts cannot be matched", () => {
    const names = ["r/First", "r/Second"];

    expect(orderCommunitiesByPostCount(names)).toBe(names);
    expect(orderCommunitiesByPostCount(names, { Elsewhere: 4 })).toBe(names);
  });

  it("does not promote a community-only match above pain-relevant posts", () => {
    const posts = [
      post("A viral general discussion", "LifeProTips", 3000),
      post("Medication inventory count failures", "operations", 120),
      post("Pay is just cruel", "VetTech", 20),
      post("Medication inventory software", "vendors", 40),
    ];

    expect(orderSocialPostsByRelevance(
      posts,
      ["veterinary medication inventory"],
      ["r/VetTech"],
    )).toEqual([posts[1], posts[3], posts[0], posts[2]]);
  });

  it("renders a neutral, nonempty feed for legacy checkpoints without attribution", () => {
    const { container } = render(DiscoveryEvidence, {
      props: { data: veterinaryDiscoveryFixture },
    });

    const renderedTitles = Array.from(container.querySelectorAll(".source-title"))
      .map((node) => node.textContent?.trim());
    expect(renderedTitles).toHaveLength(5);
    expect(renderedTitles.every(Boolean)).toBe(true);
    expect(container).toHaveTextContent("Captured conversations");
    expect(container).toHaveTextContent("Pain relevance first");
    expect(container).not.toHaveTextContent("Confirmed buyer conversations");
    expect(container).toHaveTextContent("engagement");
  });

  it("keeps the complete real bookkeeping corpus available in legacy mode", () => {
    const ranked = rankDiscoveryConversations(bookkeepingDiscoveryFixture);
    expect(ranked.length).toBeGreaterThanOrEqual(40);
    expect(ranked.slice(0, 5).every(({ text }) => text.length > 0)).toBe(true);
  });

  it("labels every durable role and prefers buyer-side evidence without filtering", async () => {
    const painTitle = "Reconcile medication inventory after dispensing";
    const quote = (post_id: string, text: string, role: SpeakerRole, confidence = 0.9) => ({
      text,
      post_id,
      source_url: `https://example.com/comments/${post_id}`,
      upvotes: 10,
      subreddit: "SameCommunity",
      speaker_attribution: attribution(post_id, role, confidence),
    });
    const data: DiscoveryData = {
      ...veterinaryDiscoveryFixture,
      speaker_attribution_version: 1,
      speaker_attribution_target: "Independent practice owners",
      quotes: {
        [painTitle]: [
          quote("adjacent-worker", "A worker account.", "adjacent_worker"),
          quote("supplier", "A supplier account.", "adjacent_worker"),
          quote("customer", "A customer grievance.", "customer"),
          quote("unknown", "An ambiguous account.", "unknown"),
          quote("durable-buyer", "A buyer account from the durable classifier.", "buyer", 0.6),
          quote("buyer-one", "A confirmed buyer account.", "buyer", 0.95),
          quote("buyer-two", "Another confirmed buyer account.", "buyer", 0.88),
        ],
      },
      social_posts_sample: [],
      subreddit_post_counts: { SameCommunity: 7 },
    };

    const ranked = rankDiscoveryConversations(data).map(({ sourceKey }) => sourceKey);
    expect(ranked).toEqual([
      "durable-buyer",
      "buyer-one",
      "buyer-two",
      "adjacent-worker",
      "supplier",
      "customer",
      "unknown",
    ]);

    const view = render(DiscoveryEvidence, { props: { data } });
    const { container } = view;
    expect(container.querySelectorAll(".source-row")).toHaveLength(5);
    expect(container).toHaveTextContent("Captured conversations");
    expect(container).toHaveTextContent("3 of 5 shown buyer-side");
    expect(container).toHaveTextContent("Role: buyer");
    expect(container).toHaveTextContent("Role: adjacent worker");
    await fireEvent.click(view.getByRole("button", { name: "Show all 7 conversations →" }));
    expect(container.querySelectorAll(".source-row")).toHaveLength(7);
    expect(container).toHaveTextContent("3 of 7 shown buyer-side");
    expect(container).toHaveTextContent("A customer grievance");
    expect(container).toHaveTextContent("Role: customer");
    expect(container).toHaveTextContent("Role: unknown");
    expect(container).toHaveTextContent("not presented as the primary buyer's voice");
  });

  it("shows a coherent labelled zero-buyer state without hiding captured evidence", () => {
    const data: DiscoveryData = {
      ...veterinaryDiscoveryFixture,
      speaker_attribution_version: 1,
      speaker_attribution_target: "Independent practice owners",
      quotes: {
        "A pain": [{
          text: "A customer account",
          post_id: "customer",
          source_url: "https://example.com/customer",
          upvotes: 20,
          subreddit: "SameCommunity",
          speaker_attribution: attribution("customer", "customer"),
        }],
      },
      social_posts_sample: [],
    };

    const { container } = render(DiscoveryEvidence, { props: { data } });
    expect(container.querySelectorAll(".source-row")).toHaveLength(1);
    expect(container).toHaveTextContent("0 of 1 shown buyer-side");
    expect(container).toHaveTextContent("None of the shown conversations is buyer-side");
    expect(container).toHaveTextContent("A customer account");
    expect(container).toHaveTextContent("Role: customer");
  });

  it("reveals every captured community from the more control", async () => {
    const names = Array.from({ length: 12 }, (_, index) => `r/Community${index + 1}`);
    const view = render(CommunitySourcesSection, { props: { subredditNames: names } });

    expect(view.container.querySelectorAll('[aria-label="Captured communities"] .source-pill')).toHaveLength(8);
    const more = view.getByRole("button", { name: "Show 4 more communities" });
    await fireEvent.click(more);

    expect(view.container.querySelectorAll('[aria-label="Captured communities"] .source-pill')).toHaveLength(12);
    expect(view.getByRole("button", { name: "Show fewer communities" })).toHaveAttribute("aria-expanded", "true");
  });

  it("uses engagement only after relevance", () => {
    const posts = [
      post("Medication inventory workflow", "one", 10),
      post("Medication inventory workflow", "two", 50),
    ];

    expect(orderSocialPostsByRelevance(posts, ["medication inventory"]))
      .toEqual([posts[1], posts[0]]);
  });

  it("keeps today's conversation order when relevance cannot be computed", () => {
    const posts = [post("First", "one", 1), post("Second", "two", 2)];

    expect(orderSocialPostsByRelevance(posts, [])).toBe(posts);
    expect(orderSocialPostsByRelevance(posts, ["unmatched vocabulary"])).toBe(posts);
  });

  it("keeps a text-less post but never scores it as relevant", () => {
    const relevant = post("Medication inventory workflow", "operators", 1);
    const textless = {
      ...post("placeholder", "operators", 9999),
      title: undefined,
      body: null,
    } as unknown as SocialPost;

    const ranked = orderSocialPostsByRelevance(
      [textless, relevant],
      ["medication inventory"],
    );
    expect(ranked).toEqual([relevant, textless]);

    const fallback = orderSocialPostsByRelevance([textless], ["medication inventory"]);
    expect(fallback).toEqual([textless]);

    const conversations = rankDiscoveryConversations({
      ...veterinaryDiscoveryFixture,
      quotes: {},
      social_posts_sample: [textless],
    });
    expect(conversations).toHaveLength(1);
    expect(conversations[0].text).toBe("Conversation text unavailable");
  });

  it("orders representative quotes by overlap with the pain vocabulary", () => {
    const quotes = [
      "Support took a long time to reply.",
      "We reconcile controlled medication inventory after every surgery.",
      "Medication counts are often wrong.",
      "The interface is confusing.",
    ];

    expect(orderQuotesByRelevance(
      quotes,
      ["Reconcile controlled medications and physical inventory counts"],
    )).toEqual([quotes[1], quotes[2], quotes[0], quotes[3]]);
  });

  it("keeps today's quote order when there is no usable vocabulary or overlap", () => {
    const quotes = ["First quote", "Second quote"];

    expect(orderQuotesByRelevance(quotes, [])).toBe(quotes);
    expect(orderQuotesByRelevance(quotes, ["inventory medication"])).toBe(quotes);
  });
});
