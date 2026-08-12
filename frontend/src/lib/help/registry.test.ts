import { describe, expect, it } from "vitest";

import choosingANiche from "$lib/content/help/choosing-a-niche.md?raw";
import creditsAndRefunds from "$lib/content/help/credits-and-refunds.md?raw";
import ideaCheck from "$lib/content/help/idea-check.md?raw";
import ideaGeneration from "$lib/content/help/idea-generation.md?raw";
import readingAndSharing from "$lib/content/help/reading-and-sharing-reports.md?raw";
import startingResearch from "$lib/content/help/starting-research.md?raw";
import { HELP_SECTIONS, HELP_TOPICS } from "./registry";

describe("Help center coverage", () => {
  it("groups every topic once in a task-based section", () => {
    const groupedSlugs = HELP_SECTIONS.flatMap((section) => section.topics.map((topic) => topic.slug));

    expect(new Set(groupedSlugs).size).toBe(groupedSlugs.length);
    expect(groupedSlugs).toEqual(HELP_TOPICS.map((topic) => topic.slug));
    expect(HELP_SECTIONS.map((section) => section.title)).toEqual([
      "Start research",
      "Use your results",
      "Understand the method",
    ]);
  });

  it("covers the current starting modes and setup vocabulary", () => {
    expect(startingResearch).toContain("Explore a niche");
    expect(startingResearch).toContain("Solve for a group");
    expect(startingResearch).toContain("Check my idea");
    expect(startingResearch).toContain("Idea Catalog");
    expect(startingResearch).toContain("Product shape filter");
    expect(startingResearch).toContain("Idea focus");
    expect(choosingANiche).toContain("When you choose **Explore a niche**");
  });

  it("explains the current idea and report identity rules", () => {
    expect(ideaCheck).toContain("pinned at the top for comparison");
    expect(ideaCheck).toContain("score rank");
    expect(ideaCheck).toContain("adversarial review");
    expect(ideaGeneration).toContain("Delivered as");
    expect(ideaGeneration).toContain("Product shape");
  });

  it("documents sharing, locked sections, charges, and refunds", () => {
    expect(readingAndSharing).toContain("Voting enabled");
    expect(readingAndSharing).toContain("Read-only copy");
    expect(readingAndSharing).toContain("Key Influencers");
    expect(readingAndSharing).toContain("Source Posts");
    expect(creditsAndRefunds).toContain("current price");
    expect(creditsAndRefunds).toContain("refund");
    expect(creditsAndRefunds).toContain("charged again");
  });
});
