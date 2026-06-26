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

export const HELP_TOPICS: HelpTopic[] = [
  {
    slug: "discovery",
    title: "How the research works",
    subtitle: "The steps behind every report, and what the Discovery phase does",
  },
  {
    slug: "search",
    title: "How the search finds discussions",
    subtitle: "Turning your niche into many small searches, and keeping them broad and honest",
  },
  {
    slug: "pain-points",
    title: "How pain points are gathered",
    subtitle: "From public discussion to specific, evidence-backed problems",
  },
  {
    slug: "idea-generation",
    title: "How ideas are generated",
    subtitle: "From the strongest problems to a varied, vetted shortlist",
  },
  {
    slug: "methodology",
    title: "How scoring works",
    subtitle: "What the severity, commercial-intent, opportunity and idea scores mean, and how far to trust them",
  },
  {
    slug: "how-its-built",
    title: "How it's built and tuned",
    subtitle: "The agents, tools, model choices, and safeguards behind the research",
  },
];

export function getHelpTopic(slug: string): HelpTopic | undefined {
  return HELP_TOPICS.find((t) => t.slug === slug);
}
