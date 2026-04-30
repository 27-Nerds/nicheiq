import type { ProgrammaticIdeaPage } from '$lib/types/catalog-landing';

/**
 * Programmatic-SEO landing pages — hand-curated topic clusters that target
 * high-volume search intent ("b2b saas ideas", "ai startup ideas",
 * "bootstrap ideas") that doesn't strictly map to a single category.
 *
 * Resolution order in `(public)/ideas/[niche]/+page.server.ts`:
 *   1. Try real CatalogCategory lookup via `/api/public/catalog/landing/:slug`.
 *   2. On 404, look up this array.
 *   3. Otherwise 404.
 *
 * Slug-collision validation (with real `CatalogCategory.slug` top-level rows)
 * lives at deploy time in `backend/scripts/validatePseoSlugs.ts`, not at
 * frontend module load (frontend has no Prisma access).
 *
 * featuredIdeaSlugs are best-effort. The loader fetches each via
 * `/api/public/catalog/idea-by-slug/:slug` and silently filters nulls, so a
 * stale entry doesn't break the page. Update this list as the catalog grows.
 */
export const programmaticIdeaPages: ProgrammaticIdeaPage[] = [
  {
    slug: 'b2b-saas',
    title: 'B2B SaaS Ideas',
    seoTitle: 'B2B SaaS Ideas, Validated from Real Founder Pain | NicheIQ',
    seoDescription:
      'Hand-picked B2B SaaS startup ideas backed by real Reddit and Hacker News discussions. Updated weekly with founder pain points and pricing intel.',
    longDescription:
      "B2B SaaS is the dominant playing field for indie founders today: high willingness to pay, monthly-recurring economics, and well-documented pain points across hundreds of vertical workflows. The trade-off is a ruthlessly competitive landscape — every obvious idea has a dozen incumbents, and growth is slow without a clear distribution wedge.\n\nThe ideas in this collection lean toward verticals where automation, integration, or compliance keeps the moat defensible: tools that pull data out of clunky source systems, agents that reduce a manual ops loop from hours to minutes, or thin layers on top of expensive enterprise software that small teams can actually afford. Each one is sourced from public discussions where founders or operators describe the pain in their own words — not a competitor scrape, not a brainstorming session.\n\nWe weigh each idea on market fit (Is the pain real and frequent?), technical feasibility for a small team (Can two engineers ship V1 in a quarter?), novelty (Is the wedge defensible against the obvious incumbent?), and SEO scalability (Can the niche be reached via organic content rather than $200 CAC?). Filter for the combinations that match your strengths — the shortcut to a viable B2B SaaS isn't picking the best idea on paper, it's picking the one whose distribution channel you can actually run.",
    faqJson: [
      {
        q: 'How are these B2B SaaS ideas selected?',
        a: 'Each idea originates from a documented pain point on Reddit, Hacker News, or a similar founder-adjacent community. We score willingness to pay, severity, and mention frequency, then run an LLM-assisted analysis to draft a solution shape. Only ideas with non-trivial validation make it into the catalog.',
      },
      {
        q: "What does 'B2B SaaS' mean here?",
        a: 'A subscription software product sold to businesses (not consumers). Pricing typically starts at $20–$200/month per seat. The ideas in this collection assume self-serve onboarding rather than enterprise sales motion.',
      },
      {
        q: 'How often is this list updated?',
        a: 'New ideas are surfaced as soon as our research pipeline classifies a published report into the B2B SaaS bucket. In practice that means weekly additions during active research cycles.',
      },
      {
        q: 'Can I commission research on a specific B2B niche?',
        a: 'Yes — start a research job from the dashboard. NicheIQ generates pain-point analysis, validated solution concepts, competitive landscape, and SEO strategy for any niche you specify.',
      },
    ],
    featuredIdeaSlugs: [],
    tags: ['B2B', 'SaaS', 'Recurring Revenue', 'Vertical'],
  },
  {
    slug: 'ai-startup',
    title: 'AI Startup Ideas',
    seoTitle: 'AI Startup Ideas Backed by Real Demand Signals | NicheIQ',
    seoDescription:
      'Curated AI startup ideas from real-world pain points. Each concept includes market fit scoring, technical feasibility, and SEO angle.',
    longDescription:
      "AI startup ideas are everywhere — most of them are GPT wrappers chasing whatever benchmark went viral last week. The interesting ones live in a different place: workflows where humans do tedious classification work, where domain-specific accuracy matters more than model novelty, and where the value comes from integration depth rather than model API calls.\n\nThe ideas in this collection start with the pain, not the model. A bookkeeper spending three hours reconciling line items across PDFs. A recruiter copy-pasting candidate notes from a CRM into a different CRM. A compliance officer manually flagging policy drift across hundreds of documents. The AI is just the engine — the moat is the workflow integration, the proprietary data flywheel, and the willingness to do the unsexy enterprise integration work that pure API startups won't.\n\nWe score each idea on the dimensions that actually matter for AI products: technical feasibility (Can a fine-tuned smaller model do this without burning API costs?), defensibility (What's the data moat in 12 months when the underlying model is commoditised?), and novelty (Has Microsoft Copilot already shipped this?). Use the filters to find the niches where AI is a competitive weapon, not a checkbox feature.",
    faqJson: [
      {
        q: 'Are these LLM-wrapper ideas?',
        a: 'No. We deliberately filter out ideas where the entire product is a thin wrapper over a public model API with no data moat or workflow depth. Every idea in the catalog has a defensible angle beyond model access.',
      },
      {
        q: 'How is technical feasibility scored?',
        a: 'On a 0-1 scale considering: required model capability vs. current frontier; integration complexity; team size needed for V1; and ongoing inference cost at modest scale (1k MAU).',
      },
      {
        q: 'Do these require fine-tuning or training?',
        a: "Most don't. The strongest ideas use prompt engineering, retrieval augmentation, or function calling on existing models. We flag the few that genuinely require fine-tuning so you can plan accordingly.",
      },
      {
        q: 'How do I evaluate the data moat?',
        a: 'Look for ideas where users contribute data through normal use, where domain-specific labelling is hard to acquire, or where integration with proprietary enterprise data sources locks in the moat. NicheIQ flags these in the differentiation factors per idea.',
      },
    ],
    featuredIdeaSlugs: [],
    tags: ['AI', 'LLM', 'Workflow', 'Automation'],
  },
  {
    slug: 'bootstrapped',
    title: 'Bootstrapped Startup Ideas',
    seoTitle: 'Bootstrapped Startup Ideas: Solo-Dev Friendly | NicheIQ',
    seoDescription:
      'Startup ideas you can build solo and bootstrap to profitability. Filtered for solo-dev feasibility and short time-to-revenue.',
    longDescription:
      "Bootstrapping is a different game than venture-funded startups. The constraint isn't ambition — it's runway. Every idea you pick needs to clear a higher bar on three dimensions: time-to-revenue (months not years), solo-buildable (one engineer, no co-founder), and organic distribution (you can't outspend an incumbent on paid ads).\n\nThe ideas in this collection optimise for those constraints. Tools that solve a specific, narrow pain in a niche where the buyer self-identifies and converts at high rates. Productised services that look like SaaS to the buyer but don't require a complex backend. Vertical micro-SaaS where the market is small enough that VC-backed competitors won't bother — but big enough to support a $20k–$50k MRR solo business.\n\nWe filter aggressively on solo-dev feasibility (a 0-1 score that asks: could one engineer ship V1 in 8 weeks?) and SEO scalability (can the entire customer acquisition pipeline run on organic content without paid ads?). The trade-off is ambition: these aren't billion-dollar TAM businesses. They're $1M ARR businesses for an indie founder who wants to control their own runway. Pick the niche where you have personal context — bootstrapped success rates are 5× higher when the founder is a domain expert in the buyer's world.",
    faqJson: [
      {
        q: "What does 'bootstrapped' mean in this context?",
        a: 'Self-funded — no venture capital. The ideas in this collection assume the founder is funding development from savings or revenue, with a target of profitable operation within 6-12 months.',
      },
      {
        q: 'How is solo-dev feasibility scored?',
        a: 'On a 0-1 scale. We ask: could one engineer ship a V1 in 8 weeks of full-time work, with no co-founder and no contractors? Ideas with scores below 0.6 are flagged as needing a team or significant infrastructure.',
      },
      {
        q: 'What about no-code or low-code ideas?',
        a: "We include them, but flag them clearly. No-code ideas have lower defensibility (the moat is operations and distribution, not technology) but faster time-to-revenue. They're a fit if you have audience or distribution but limited eng time.",
      },
      {
        q: 'How big can a bootstrapped business get?',
        a: "Realistically, $500k-$5M ARR for a solo founder; $1M-$20M ARR for a small bootstrapped team. The ideas here aren't venture-scale — they're indie-scale. If your goal is a 9-figure exit, this isn't the right collection.",
      },
    ],
    featuredIdeaSlugs: [],
    tags: ['Bootstrapped', 'Solo Dev', 'Indie', 'Micro-SaaS'],
  },
];

/**
 * Lookup helper used by the [niche] loader's pSEO fallback.
 */
export function findProgrammaticIdeaPage(slug: string): ProgrammaticIdeaPage | undefined {
  return programmaticIdeaPages.find((p) => p.slug === slug);
}
