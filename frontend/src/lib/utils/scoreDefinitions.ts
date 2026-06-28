/**
 * Canonical plain-English definitions of each displayed idea score, for hover tooltips.
 *
 * Copy is grounded in the ACTUAL backend lifecycle (generator self-score → independent realism
 * critic re-scores & replaces it → deterministic downgrade-only caps), verified against
 * src/nicheiq/crews/unified_solution_crew.py and src/nicheiq/utils/seo_helpers.py. Keep these
 * accurate when editing: market-fit really is hard-capped at 40% on an unverified data route, and
 * solo-dev is re-scored by the same critic (weighing ongoing ops burden) then held at or below the
 * build-feasibility estimate.
 */
export const SCORE_DEFINITIONS = {
  market_fit:
    "Market Fit — how well the idea fits real, validated demand, weighted by how severe the pains it addresses are. An independent critic re-scores it conservatively, and it's capped at 40% when the data the idea needs can't be obtained through a verified route.",
  technical_feasibility:
    "Feasibility — whether the idea can be built at all with today's tech and obtainable data (capability, not effort). Held at or below an independent build-feasibility estimate.",
  competitive_advantage:
    "Competitive Edge — how defensible the idea is versus existing tools. Higher means a more original, harder-to-copy angle.",
  solo_dev:
    "Solo-Dev — how realistic it is for one person to build AND keep running. The main driver is ongoing burden (support, uptime, moderation, marketing), not just build time. An independent critic re-scores it conservatively, and it can't exceed the build-feasibility estimate — you can't solo-run what you can't build.",
  seo:
    "SEO — how easily the idea can scale organic traffic through indexable content. Based on page count and indexability only (not how the data is sourced); capped for login-gated or thin-content models.",
  originality:
    "Originality — how non-obvious the idea is: the share of builders who would NOT also land on it. Higher means more original. (Shown as 1 − obviousness.)",
  composite:
    "Overall score — a blend of market fit, feasibility, originality and SEO, reduced when the idea is hard to build. Used for ranking.",

  // Catalog idea-hero axes — re-labelled idea scores on the public idea page.
  demand:
    "Demand — how well the idea fits real, validated demand (its Market Fit score), weighted by pain severity.",
  opportunity:
    "Opportunity — how easily the idea can scale organic traffic through indexable content (its SEO scalability).",
} as const;

export type ScoreDefKey = keyof typeof SCORE_DEFINITIONS;
