/**
 * Display labels for closed-vocabulary idea tag values (see docs/IDEA_TAGS.md).
 * Values are mutually exclusive across facets, so one flat map is unambiguous.
 */
const TAG_LABELS: Record<string, string> = {
  // project_type
  aggregator: "Aggregator",
  saas: "SaaS",
  "comparison-tool": "Comparison tool",
  directory: "Directory",
  marketplace: "Marketplace",
  other: "Other",
  // target_market
  b2b: "B2B",
  b2c: "B2C",
  prosumer: "Prosumer",
  b2b2c: "B2B2C",
  // monetization
  subscription: "Subscription",
  "one-time": "One-time",
  commission: "Commission",
  "usage-based": "Usage-based",
  advertising: "Advertising",
  affiliate: "Affiliate",
  licensing: "Licensing",
  // data_access (suffix "data" so the chip is self-explanatory)
  public: "Public data",
  freemium: "Freemium data",
  paywalled: "Paywalled data",
  unofficial: "Unofficial data",
  restricted: "Hard-to-get data",
  blocked: "Blocked data",
  unverified: "Unverified data",
  // build_complexity (plain effort phrasing — "high complexity" reads ambiguously)
  low: "Solo-manageable",
  medium: "Some solo constraints",
  high: "Hard to run solo",
  // novelty_level (self-describing — "moderate novelty" is vague)
  conventional: "Familiar approach",
  moderate: "Some differentiation",
  novel: "Distinct approach",
  // growth_channels
  "programmatic-seo": "Programmatic SEO",
  content: "Content",
  community: "Community",
  "paid-ads": "Paid ads",
  "network-effects": "Network effects",
  integrations: "Integrations",
  // risk_flags
  regulatory: "Regulatory",
  "tos-risk": "Terms risk",
  "grey-market": "Gray-area market",
  "trust-dependent": "Trust-dependent",
  // usage_cadence
  continuous: "Daily-use tool",
  periodic: "Periodic use",
  episodic: "Episodic use",
  "one-shot": "One-shot use",
};

/** Humanize a tag value to a display label (sentence case), falling back to title-casing. */
export function humanizeTag(value?: string | null): string {
  if (!value) return "";
  return (
    TAG_LABELS[value] ??
    value
      .split("-")
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(" ")
  );
}

/**
 * One-line explanation of what a tag means / why it was added — shown on hover.
 * Derived facets explain their basis ("why"); LLM/reused facets are definitional ("what").
 * See docs/IDEA_TAGS.md.
 */
const TAG_DESCRIPTIONS: Record<string, string> = {
  // project_type
  aggregator: "Pulls data from many sources into one place.",
  saas: "Subscription software tool.",
  "comparison-tool": "Compares options side by side.",
  directory: "A browsable listing or index.",
  marketplace: "Connects buyers and sellers.",
  other: "Doesn't fit the standard project types.",
  // target_market
  b2b: "Sold to businesses or teams.",
  b2c: "Sold to individual consumers.",
  prosumer: "For power-users and serious hobbyists.",
  b2b2c: "Reaches consumers through a business.",
  // monetization
  subscription: "Primary revenue is a recurring subscription.",
  "one-time": "Primary revenue is a one-time purchase.",
  commission: "Takes a cut of each transaction.",
  "usage-based": "Charges per usage / metered.",
  advertising: "Ad-supported.",
  affiliate: "Earns affiliate referral commissions.",
  licensing: "Licenses the product or data.",
  // data_access
  public: "Built on openly available public data.",
  freemium: "Free data tier plus paid features.",
  paywalled: "Requires paid data access.",
  unofficial: "Relies on an unofficial API or scraping route that needs a terms review.",
  restricted: "Data is hard to obtain in bulk (per-lookup or login-gated).",
  blocked: "No reliable route to the required data.",
  unverified: "Couldn't confirm or refute a public source for this data — verify it's obtainable before building.",
  // build_complexity (derived from solo-dev feasibility — the same number shown as the "Solo" score)
  low: "The expected build and ongoing operating load look manageable for one person.",
  medium: "One person could make progress, but parts of the build or ongoing operation may need help.",
  high: "The build or ongoing operating load is likely to exceed what one person can sustain.",
  // novelty_level (derived from novelty / obviousness)
  conventional: "Uses a familiar mechanism that may be easy for alternatives to match.",
  moderate: "Adds meaningful differences to a familiar approach.",
  novel: "Uses a clearly different mechanism or product angle.",
  // growth_channels
  "programmatic-seo": "Grows via many auto-generated SEO pages.",
  content: "Grows via content marketing.",
  community: "Grows via community and user contributions.",
  "paid-ads": "Grows via paid advertising.",
  "network-effects": "Gets more valuable as more people join.",
  integrations: "Grows by integrating into other platforms.",
  // risk_flags
  regulatory: "Health, finance, or privacy compliance exposure.",
  "tos-risk": "Data acquisition may violate a platform's terms of service.",
  "grey-market": "Operates in a legally ambiguous market.",
  "trust-dependent": "Success hinges on trust that's hard to build or easy to game.",
  // usage_cadence (how often the buyer USES it — not how it bills)
  continuous: "Used as part of a daily or weekly workflow.",
  periodic: "Used on a recurring calendar cadence (monthly reports, quarterly filings).",
  episodic: "Used when an irregular event triggers it (validating an idea, raising prices) — subscriptions churn between events.",
  "one-shot": "Delivers its value once — fits one-time pricing better than a subscription.",
  // strengths (derived from scores, standardized cutoffs)
  "market-fit": "The product closely matches an important, evidence-backed problem for buyers likely to pay.",
  "seo-power": "The product can create useful, public pages that give it a strong organic-discovery path.",
  innovator: "The core mechanism is meaningfully different from obvious approaches and existing alternatives.",
  "quick-build": "The core product appears technically possible with available tools and obtainable data. This does not promise a short build.",
  "solo-friendly": "The expected build and ongoing operating load look manageable for one person.",
};

/** One-line hover explanation for a tag value (empty string if unknown). */
export function tagDescription(value?: string | null): string {
  return value ? (TAG_DESCRIPTIONS[value] ?? "") : "";
}

/** The closed data_access vocabulary (see docs/IDEA_TAGS.md). */
const DATA_ACCESS_VALUES = new Set([
  "public",
  "freemium",
  "paywalled",
  "unofficial",
  "restricted",
  "blocked",
  "unverified",
]);

/**
 * Boundary aliases for off-vocabulary data_access_model values.
 * The pipeline now folds these in before storing, but ideas generated earlier
 * still carry them — mirrored here so they render without a data migration.
 * Do NOT treat these as vocabulary: they are inbound-only synonyms.
 */
const DATA_ACCESS_ALIASES: Record<string, string> = {
  none: "public",
  "not-data-dependent": "public",
  official: "public",
  licensed: "paywalled",
};

/**
 * Fold a raw data_access_model value into the canonical vocabulary.
 * Returns null for anything still outside it, so callers can omit the field
 * instead of printing a raw token.
 */
export function normalizeDataAccess(value?: string | null): string | null {
  if (!value) return null;
  const raw = value.trim().toLowerCase();
  const canonical = DATA_ACCESS_ALIASES[raw] ?? raw;
  return DATA_ACCESS_VALUES.has(canonical) ? canonical : null;
}
