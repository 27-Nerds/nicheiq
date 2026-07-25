/**
 * Canonical plain-English definitions of each displayed idea score, for hover tooltips.
 *
 * These definitions explain what each measure helps the user decide. Calculation details remain
 * available in the methodology/analyst data, rather than crowding hover help with internal fields
 * and decimal thresholds.
 */
export const SCORE_DEFINITIONS = {
  market_fit:
    "Market fit — how strongly this exact product addresses an important, evidence-backed problem for buyers likely to pay. It is lower when required data is uncertain, existing tools already cover the need, or the proposed value is not well supported.",
  technical_feasibility:
    "Feasibility — whether a working version is technically possible with available tools and obtainable data. It does not estimate how long the product will take or how manageable it is for one person.",
  competitive_advantage:
    "Competitive edge — whether the product has a meaningful advantage that alternatives would struggle to match.",
  solo_dev:
    "Solo manageability — how realistic it is for one person to build and keep the product running, including support, uptime, moderation, maintenance, and marketing.",
  seo:
    "Organic discovery — how readily the product can attract search traffic through useful, public, indexable content. It is lower when useful pages are limited, gated, or already dominated by an incumbent.",
  originality:
    "Distinctiveness — how meaningfully the idea differs from obvious approaches and existing alternatives. A higher rating means the product has a clearer, less interchangeable angle.",
  composite:
    "Research score — a relative ranking of the ideas in this Discovery run, combining demand fit, buildability, differentiation, and organic-discovery potential. It helps compare ideas; it is not a prediction of success.",

  // Catalog idea-hero axes — re-labelled idea scores on the public idea page.
  demand:
    "Demand — how strongly this product addresses an important, evidence-backed problem for buyers likely to pay.",
  opportunity:
    "Organic discovery — how readily the product can attract search traffic through useful, public, indexable content.",
} as const;

export type ScoreDefKey = keyof typeof SCORE_DEFINITIONS;
