/**
 * Maps the real backend payloads (`/solutions` + `/preview-report`) into the
 * view model the redesigned job page renders. All scaling, band derivation,
 * chip building and pain matching lives here so the component stays dumb.
 *
 * Real-data truths this encodes (see job 65b05ea7 "Peptides Supplements"):
 *  - All *_score fields are 0-1 → scaled to 0-100 for display.
 *  - `idea_tier` is 'single' | 'bundle' (a shape, not a quality band); the
 *    quality band is derived from `adjusted_composite_score`.
 *  - Human title is `headline`; `name`/`solution_name` is a slug.
 *  - Model chips come from the structured `tags` object, not `pricing_strategy`.
 *  - There is NO per-idea Go/No-Go verdict pre-deep-research, so the "signal"
 *    card is derived honestly from real fields (edge / weakest signal + risk
 *    flags / wallet reality) instead of inventing strength/risk/unknown.
 */

export type Band = "Strong" | "Moderate" | "Weak";

export interface Signals {
  originality: number;
  marketFit: number;
  seo: number;
  feasibility: number;
  novelty: number;
}

export interface PainEvidence {
  title: string;
  severity: number; // 0-100
  commercialIntent: number; // 0-100
  opportunity: string | null;
  mentions: number;
  platform: string;
  quotes: string[];
  coveredBy: string[]; // idea headlines addressing this pain
  isOpportunity: boolean; // uncovered AND high-severity — whitespace worth expanding into
}

export interface IdeaVM {
  id: string;
  title: string;
  name: string;
  score: number; // 0-100
  band: Band;
  tier: "single" | "bundle" | null;
  timeToBuild: string | null;
  soloFriendly: number | null; // 0-100
  model: string[];
  monetization: string | null;
  payability: string | null; // humanized wallet class
  features: string[];
  signals: Signals;
  why: { short: string | null; long: string | null };
  edge: string | null;
  angle: { label: string; rationale: string | null } | null;
  riskFlags: string[];
  sourcePain: string | null;
  painsAddressed: string[];
  weakest: { label: string; value: number };
  pains: PainEvidence[];
  // richer idea detail (parity with live SolutionDetailContent)
  deck: string | null; // short_description
  pricing: string | null;
  conventional: string | null;
  innovation: string | null;
  seoOpportunity: string | null;
  indexablePages: number | null;
  cacOrganic: string | null;
  cacPaid: string | null;
  queries: string[];
  personas: string[];
  diffFactors: string[];
  // full-detail fields (idea "everything" view)
  valueProposition: string | null;
  description: string | null;
  devTimeRationale: string | null;
  technicalApproach: string | null;
  dataAcquisition: string | null;
  dataAccessModel: string | null;
  dataSources: string[];
  noveltyRationale: string | null;
  calibrationNotes: string | null;
  incumbentParity: string | null;
  adjacentParity: string | null;
  rank: number; // 1-based, by score
  pricingShapeMismatch: boolean;
  pricingShapeNote: string | null;
  buildComplexity: string | null;
  journeyTag: string | null;
  mechanismTag: string | null;
  growthChannels: string[];
}

export interface AudienceSegmentVM {
  name: string;
  size: string | null;
  priceSensitivity: string | null;
  expertise: string | null;
  motivations: string[];
  payability: string | null; // humanized wallet class
  payabilityRationale: string | null;
}

export interface ContextVM {
  niche: string; // short input name
  nicheDescription: string | null;
  primarySegment: string | null;
  audienceSegments: AudienceSegmentVM[];
  communityHubs: string[];
  topPains: PainEvidence[];
  painCount: number;
  uncoveredPains: string[]; // high-severity pains no idea addresses
  dataQuality: {
    painTier: string | null;
    contentTier: string | null;
    confidence: number | null; // 0-100
    totalSources: number | null;
    caveats: string[];
  } | null;
  ideaCount: number;
  verdict: {
    headline: string | null;
    difficulty: string | null;
    addressability: number | null; // 0-100
    narrative: string | null;
    keyChallenges: string[];
    buyerNote: string | null;
  } | null;
}

export interface JobVM {
  context: ContextVM;
  ideas: IdeaVM[];
  nicheAvg: Signals;
}

const pct = (v: unknown): number =>
  typeof v === "number" ? Math.round(Math.max(0, Math.min(1, v)) * 100) : 0;

function band(score: number): Band {
  if (score >= 60) return "Strong";
  if (score >= 45) return "Moderate";
  return "Weak";
}

const TITLE_CASE = (s: string) =>
  s
    .split(/[-_\s]+/)
    .map((w) => (w.length <= 3 ? w.toUpperCase() : w[0].toUpperCase() + w.slice(1)))
    .join(" ");

const ENUM_LABELS: Record<string, string> = {
  saas: "SaaS",
  b2c: "B2C",
  b2b: "B2B",
  "comparison-tool": "Comparison tool",
  aggregator: "Aggregator",
  marketplace: "Marketplace",
  subscription: "Subscription",
  commission: "Commission",
  freemium: "Freemium",
  "one-time": "One-time",
};
const label = (v?: string | null): string => (v ? (ENUM_LABELS[v] ?? TITLE_CASE(v)) : "");

const ANGLE_LABELS: Record<string, string> = {
  distribution_seo: "Distribution / SEO",
  novel_differentiation: "Novel differentiation",
  vertical_workflow: "Vertical workflow",
};

const PAYABILITY_LABELS: Record<string, string> = {
  "personal-wallet": "Personal wallet",
  "prosumer-wallet": "Prosumer wallet",
  "business-wallet": "Business wallet",
  mixed: "Mixed wallet",
};

/** slug/enum → readable chip label; upper-cases known acronyms. */
const ACRONYMS = /\b(seo|api|coa|fda|glp|ndc|wada|cac|faers)\b/gi;
function humanTag(v: string): string {
  const t = v.replace(/[-_]+/g, " ").trim();
  return (t.charAt(0).toUpperCase() + t.slice(1)).replace(ACRONYMS, (m) => m.toUpperCase());
}
/** mechanism_tag is usually a slug but occasionally free prose — keep only slug-like. */
function slugTag(v: string | null | undefined): string | null {
  if (!v || v.includes(".") || v.length > 45 || v.trim().split(/\s+/).length > 4) return null;
  return humanTag(v);
}

function buildModel(tags: Record<string, unknown> | null, projectType: string | null): string[] {
  const t = tags ?? {};
  const out: string[] = [];
  const pt = (t.project_type as string) ?? projectType;
  if (pt) out.push(label(pt));
  if (t.target_market) out.push(label(t.target_market as string));
  if (t.monetization) out.push(label(t.monetization as string));
  return out;
}

const SIG_LABELS: [keyof Signals, string][] = [
  ["marketFit", "Market fit"],
  ["seo", "SEO"],
  ["feasibility", "Feasibility"],
  ["originality", "Originality"],
  ["novelty", "Novelty"],
];

function weakest(s: Signals): { label: string; value: number } {
  let best = SIG_LABELS[0];
  let bestV = s[best[0]];
  for (const pair of SIG_LABELS) {
    if (s[pair[0]] < bestV) {
      bestV = s[pair[0]];
      best = pair;
    }
  }
  return { label: best[1], value: bestV };
}

/* token-overlap match of an idea's addressed pains to the report's detailed pains */
const stop = new Set([
  "the", "and", "for", "with", "from", "due", "lack", "of", "to", "a", "on", "in",
  "no", "not", "by", "or", "an", "is", "are", "can", "cannot", "users", "peptide", "peptides",
]);
const toks = (s: string) =>
  new Set(
    (s || "")
      .toLowerCase()
      .replace(/[^a-z0-9\s]/g, " ")
      .split(/\s+/)
      .filter((w) => w.length > 2 && !stop.has(w)),
  );

function matchPains(
  idea: Record<string, unknown>,
  detailed: Record<string, unknown>[],
): PainEvidence[] {
  const needles = [
    idea.source_pain as string,
    ...((idea.pain_points_addressed as string[]) ?? []),
  ].filter(Boolean);
  if (!needles.length || !detailed.length) return [];

  const scored = detailed
    .map((p) => {
      const pt = toks(p.title as string);
      let best = 0;
      for (const n of needles) {
        const nt = toks(n);
        let hits = 0;
        for (const w of nt) if (pt.has(w)) hits++;
        const j = nt.size ? hits / nt.size : 0;
        best = Math.max(best, j);
      }
      return { p, score: best };
    })
    .filter((x) => x.score >= 0.2)
    .sort((a, b) => b.score - a.score)
    .slice(0, 2);

  return scored.map(({ p }) => ({
    title: p.title as string,
    severity: pct(p.severity_score),
    commercialIntent: pct(p.commercial_intent),
    opportunity: (p.opportunity_level as string) ?? null,
    mentions: (p.mention_count as number) ?? 0,
    platform: ((p.source_platforms as string[]) ?? [])[0] ?? "Reddit",
    quotes: ((p.representative_quotes as string[]) ?? []).slice(0, 2),
    coveredBy: [],
    isOpportunity: false,
  }));
}

/**
 * Job-level pain-coverage map: every pain ranked by severity, annotated with
 * which ideas address it (join on each idea's already-matched pains).
 */
function buildPainCoverage(
  detailed: Record<string, unknown>[],
  ideas: IdeaVM[],
): PainEvidence[] {
  return [...detailed]
    .sort(
      (a, b) =>
        ((b.severity_score as number) ?? 0) - ((a.severity_score as number) ?? 0) ||
        ((b.mention_count as number) ?? 0) - ((a.mention_count as number) ?? 0),
    )
    .map((p) => {
      const title = p.title as string;
      const severity = pct(p.severity_score);
      const coveredBy = ideas
        .filter((i) => i.pains.some((mp) => mp.title === title))
        .map((i) => i.title);
      return {
        title,
        severity,
        commercialIntent: pct(p.commercial_intent),
        opportunity: (p.opportunity_level as string) ?? null,
        mentions: (p.mention_count as number) ?? 0,
        platform: ((p.source_platforms as string[]) ?? [])[0] ?? "Reddit",
        quotes: ((p.representative_quotes as string[]) ?? []).slice(0, 1),
        coveredBy,
        isOpportunity: coveredBy.length === 0 && severity >= 55,
      };
    });
}

export function normalizeJob(
  solutionsPayload: { solutionIdeas?: Record<string, unknown>[] } | null,
  preview: Record<string, unknown> | null,
): JobVM {
  const raw = solutionsPayload?.solutionIdeas ?? [];
  const detailed = (preview?.detailed_pain_points as Record<string, unknown>[]) ?? [];

  const ideas: IdeaVM[] = raw
    .map((i) => {
      const score = pct(i.adjusted_composite_score);
      const signals: Signals = {
        originality:
          typeof i.obviousness_score === "number" ? 100 - pct(i.obviousness_score) : pct(i.novelty_score),
        marketFit: pct(i.market_fit_score),
        seo: pct(i.seo_scalability_score),
        feasibility: pct(i.technical_feasibility_score),
        novelty: pct(i.novelty_score),
      };
      const tags = (i.tags as Record<string, unknown>) ?? null;
      const angleKey = i.winning_angle as string | null;
      return {
        id: (i.solution_name as string) || (i.name as string) || crypto.randomUUID(),
        title: (i.headline as string) || (i.solution_name as string) || "Untitled idea",
        name: (i.solution_name as string) || (i.name as string) || "",
        score,
        band: band(score),
        tier: (i.idea_tier as "single" | "bundle") ?? null,
        timeToBuild: (i.estimated_development_time as string) ?? null,
        soloFriendly:
          typeof i.solo_dev_feasibility === "number" ? pct(i.solo_dev_feasibility) : null,
        model: buildModel(tags, (i.project_type as string) ?? null),
        monetization: tags?.monetization ? label(tags.monetization as string) : null,
        payability: i.source_segment_payability_class
          ? (PAYABILITY_LABELS[i.source_segment_payability_class as string] ??
            TITLE_CASE(i.source_segment_payability_class as string))
          : null,
        features: ((i.core_features as string[]) ?? []).slice(0, 6),
        signals,
        why: {
          short: (i.why_it_works_short as string) ?? null,
          long: (i.why_it_works as string) ?? null,
        },
        edge: (i.differentiation_locus as string) ?? null,
        angle: angleKey
          ? {
              label: ANGLE_LABELS[angleKey] ?? TITLE_CASE(angleKey),
              rationale: (i.angle_rationale as string) ?? null,
            }
          : null,
        riskFlags: ((tags?.risk_flags as string[]) ?? []).map(TITLE_CASE),
        sourcePain: (i.source_pain as string) ?? null,
        painsAddressed: ((i.pain_points_addressed as string[]) ?? []).slice(0, 4),
        weakest: weakest(signals),
        pains: matchPains(i, detailed),
        deck: (i.short_description as string) ?? (i.value_proposition as string) ?? null,
        pricing: (i.pricing_strategy as string) ?? null,
        conventional: (i.conventional_approach as string) ?? null,
        innovation: (i.innovation_angle as string) ?? null,
        seoOpportunity: (i.programmatic_seo_opportunity as string) ?? null,
        indexablePages:
          typeof i.estimated_indexable_pages === "number" ? i.estimated_indexable_pages : null,
        cacOrganic: (i.estimated_cac_organic as string) ?? null,
        cacPaid: (i.estimated_cac_paid as string) ?? null,
        queries: ((i.organic_discovery_queries as string[]) ?? []).slice(0, 12),
        personas: ((i.target_personas as string[]) ?? []).slice(0, 6),
        diffFactors: ((i.differentiation_factors as string[]) ?? []).slice(0, 6),
        valueProposition: (i.value_proposition as string) ?? null,
        description: (i.description as string) ?? null,
        devTimeRationale: (i.dev_time_rationale as string) ?? null,
        technicalApproach: (i.technical_approach as string) ?? null,
        dataAcquisition: (i.data_acquisition_notes as string) ?? null,
        dataAccessModel: (i.data_access_model as string) ?? null,
        dataSources: ((i.data_sources as string[]) ?? []).slice(0, 6),
        noveltyRationale: (i.novelty_rationale as string) ?? null,
        calibrationNotes: (i.calibration_notes as string) ?? null,
        incumbentParity: (i.incumbent_parity as string) ?? null,
        adjacentParity: (i.adjacent_market_parity as string) ?? null,
        rank: 0, // stamped after sort
        pricingShapeMismatch: (tags?.pricing_shape_mismatch as boolean) ?? false,
        pricingShapeNote: (tags?.pricing_shape_note as string) ?? null,
        buildComplexity: tags?.build_complexity
          ? humanTag(tags.build_complexity as string)
          : null,
        journeyTag: i.journey_tag ? humanTag(i.journey_tag as string) : null,
        mechanismTag: slugTag(i.mechanism_tag as string),
        growthChannels: ((tags?.growth_channels as string[]) ?? []).map(humanTag),
      };
    })
    .sort((a, b) => b.score - a.score);
  ideas.forEach((it, i) => (it.rank = i + 1));

  // niche average = mean across ideas (no stored baseline exists)
  const nicheAvg: Signals = { originality: 0, marketFit: 0, seo: 0, feasibility: 0, novelty: 0 };
  if (ideas.length) {
    for (const k of Object.keys(nicheAvg) as (keyof Signals)[]) {
      nicheAvg[k] = Math.round(ideas.reduce((s, i) => s + i.signals[k], 0) / ideas.length);
    }
  }

  const am = (preview?.audience_mapping as Record<string, unknown>) ?? {};
  const nc = (preview?.niche_context as Record<string, unknown>) ?? {};
  const ndv = (preview?.niche_difficulty_verdict as Record<string, unknown>) ?? null;
  const dqs = (preview?.data_quality_summary as Record<string, unknown>) ?? null;

  const coverage = buildPainCoverage(detailed, ideas);
  // slug → human headline, so caveats don't print raw idea slugs
  const slugToTitle = (s: string): string =>
    ideas.reduce((acc, i) => (i.name ? acc.split(i.name).join(i.title) : acc), s);
  const dataQuality = dqs
    ? {
        painTier: (dqs.pain_point_quality_tier as string) ?? null,
        contentTier: (dqs.social_content_quality_tier as string) ?? null,
        confidence:
          typeof dqs.pain_point_confidence_score === "number"
            ? pct(dqs.pain_point_confidence_score)
            : null,
        totalSources:
          ((dqs.social_content_metrics as Record<string, unknown>)?.total_sources as number) ??
          null,
        // drop caveats that just restate the uncovered-pain flags already in the coverage grid;
        // keep the net-new ones (e.g. "N ideas overlap as one product"), de-slugged.
        caveats: ((dqs.quality_caveats as string[]) ?? [])
          .filter((c) => !/not addressed by any generated|no idea\b/i.test(c))
          .map(slugToTitle)
          .slice(0, 4),
      }
    : null;

  const context: ContextVM = {
    niche: (nc.niche_input as string) || "Research niche",
    nicheDescription: (nc.niche_description as string) ?? (preview?.niche as string) ?? null,
    primarySegment: (am.primary_target_segment as string) ?? null,
    audienceSegments: ((am.audience_segments as Record<string, unknown>[]) ?? [])
      .slice(0, 3)
      .map((s) => ({
        name: (s.segment_name as string) ?? "Segment",
        size: (s.size_estimate as string) ?? null,
        priceSensitivity: (s.budget_sensitivity as string) ?? null,
        expertise: (s.expertise_level as string) ?? null,
        motivations: ((s.motivation_drivers as string[]) ?? []).slice(0, 3),
        payability: s.payability_class
          ? (PAYABILITY_LABELS[s.payability_class as string] ??
            TITLE_CASE(s.payability_class as string))
          : null,
        payabilityRationale: (s.payability_rationale as string) ?? null,
      })),
    communityHubs: ((am.community_hubs as string[]) ?? []).slice(0, 8),
    topPains: coverage,
    painCount: detailed.length,
    uncoveredPains: coverage.filter((p) => p.severity >= 55 && p.coveredBy.length === 0).map((p) => p.title),
    dataQuality,
    ideaCount: ideas.length,
    verdict: ndv
      ? {
          headline: (ndv.headline as string) ?? null,
          difficulty: (ndv.difficulty_level as string) ?? null,
          addressability:
            typeof ndv.software_addressability === "number"
              ? pct(ndv.software_addressability)
              : null,
          narrative: (ndv.narrative_summary as string) ?? null,
          keyChallenges: ((ndv.key_challenges as string[]) ?? []).slice(0, 3),
          buyerNote: (ndv.buyer_class_note as string) ?? null,
        }
      : null,
  };

  return { context, ideas, nicheAvg };
}
