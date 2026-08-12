/**
 * Help-section topic registry. The `/help` index and per-topic routes read from
 * here so adding a doc is: drop a `content/help/<slug>.md`, add an entry below,
 * add a thin `(public)/help/<slug>/+page.svelte` wrapper.
 */
export interface HelpTopic {
  slug: string;
  title: string;
  subtitle: string;
}

export interface HelpSection {
  title: string;
  subtitle: string;
  topics: HelpTopic[];
}

export const HELP_SECTIONS: HelpSection[] = [
  {
    title: "Start research",
    subtitle: "Pick the right starting point and know what happens before you spend credits.",
    topics: [
      {
        slug: "starting-research",
        title: "Choose how to start",
        subtitle: "Explore a niche, solve for a group, or check a product you already have in mind",
      },
      {
        slug: "choosing-a-niche",
        title: "Choose a useful niche",
        subtitle: "Write an Explore-a-niche brief that produces specific, evidence-backed results",
      },
      {
        slug: "credits-and-refunds",
        title: "Credits, charges, and refunds",
        subtitle: "When credits are charged, when they return, and what a retry costs",
      },
    ],
  },
  {
    title: "Use your results",
    subtitle: "Understand the shortlist, choose what to research, and share the right view.",
    topics: [
      {
        slug: "reading-and-sharing-reports",
        title: "Read and share a report",
        subtitle: "Ranks, recommendations, locked sections, voting links, and read-only copies",
      },
      {
        slug: "idea-check",
        title: "Understand an idea check",
        subtitle: "What a check of your own idea can and can't tell you, and what to test next",
      },
      {
        slug: "deep-research",
        title: "Pressure-test selected ideas",
        subtitle: "What happens after you confirm one to three exact candidates for Deep Research",
      },
      {
        slug: "idea-generation",
        title: "Understand the ranked ideas",
        subtitle: "Where candidates come from, what their labels mean, and how the shortlist is organised",
      },
    ],
  },
  {
    title: "Understand the method",
    subtitle: "Go deeper on sources, scoring, safeguards, and the limits of the research.",
    topics: [
      {
        slug: "discovery",
        title: "How Discovery works",
        subtitle: "How public discussion becomes a ranked set of candidate ideas",
      },
      {
        slug: "search",
        title: "How discussions are found",
        subtitle: "Turning your brief into focused searches without forcing a preferred answer",
      },
      {
        slug: "pain-points",
        title: "How pain points are gathered",
        subtitle: "From public discussion to specific, source-linked problems",
      },
      {
        slug: "methodology",
        title: "How scoring works",
        subtitle: "What the scores mean, what can cap them, and how far to trust them",
      },
      {
        slug: "how-its-built",
        title: "How the system is built and checked",
        subtitle: "The staged pipeline, evidence boundaries, model roles, and safeguards",
      },
    ],
  },
];

export const HELP_TOPICS: HelpTopic[] = HELP_SECTIONS.flatMap((section) => section.topics);

export function getHelpTopic(slug: string): HelpTopic | undefined {
  return HELP_TOPICS.find((t) => t.slug === slug);
}
