/**
 * Blog post registry. The `/blog` index and per-post routes read from here so
 * adding a post is: drop a `content/blog/<slug>.md` (with `![](src)` image refs),
 * add an entry below, and the index + `/blog/[slug]` route pick it up
 * automatically.
 *
 * Mirrors the help-registry pattern (`src/lib/help/registry.ts`).
 */
export interface BlogPost {
  slug: string;
  title: string;
  /** Short standfirst / dek — used for SEO description and index card blurb. */
  description: string;
  /** ISO date (YYYY-MM-DD) — drives sorting, sitemap lastmod, Article datePublished. */
  date: string;
  /** Human label rendered in the byline, e.g. "July 2026". */
  dateLabel: string;
  author: string;
  /** Estimated reading time in minutes (drives the byline meta). */
  readingMins: number;
  /** Cover image served from /static/blog. Titleless illustration — used for
   *  the in-page hero and the index card (the HTML already renders the title). */
  coverImage: string;
  /** Titled social card (OG/Twitter). Separate from `coverImage` so the in-page
   *  hero isn't redundant with the <h1>; the titled version only appears in
   *  unfurled link previews where there's no surrounding HTML. */
  ogImage: string;
  /** Topical tags rendered as pills on the index card + article header. */
  tags: string[];
}

export const BLOG_POSTS: BlogPost[] = [
  {
    slug: "evolution-of-idea-generation",
    title: "How our idea-generation pipeline learned to stop lying to itself",
    description:
      "From self-graded 0.88s to honest No-Gos: the structural changes, failed hypotheses, and one cottage-food run that exposed everything about how we generate SaaS ideas.",
    date: "2026-07-03",
    dateLabel: "July 2026",
    author: "NicheIQ Research Team",
    readingMins: 20,
    coverImage: "/blog/cover.svg",
    ogImage: "/blog/cover-og.svg",
    tags: ["idea generation", "evaluation", "benchmarks", "engineering"],
  },
];

/** Sorted newest-first (index renders in this order). */
export const BLOG_POSTS_SORTED: BlogPost[] = [...BLOG_POSTS].sort((a, b) =>
  b.date.localeCompare(a.date),
);

export function getBlogPost(slug: string): BlogPost | undefined {
  return BLOG_POSTS.find((p) => p.slug === slug);
}
