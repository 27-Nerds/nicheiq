import type {
  FounderFitIdeaField,
  FounderFitProfileField,
} from "$lib/types/founderFit";

const PROFILE_FIELD_LABELS: Record<FounderFitProfileField, string> = {
  preset: "founder profile",
  weeklyTime: "available time",
  budget: "testing budget",
  team: "team",
  revenueHorizon: "revenue timing",
  distributionAdvantages: "distribution advantages",
  strengths: "founder strengths",
  hardConstraints: "non-negotiables",
};

const IDEA_FIELD_LABELS: Record<FounderFitIdeaField, string> = {
  description: "what it is",
  value_proposition: "value proposition",
  source_pain: "pain it addresses",
  source_segment: "audience segment",
  target_personas: "target personas",
  core_features: "core features",
  project_type: "project type",
  estimated_development_time: "build estimate",
  dev_time_rationale: "build estimate rationale",
  technical_feasibility_score: "technical feasibility",
  solo_dev_feasibility: "solo-developer feasibility",
  seo_scalability_score: "SEO opportunity",
  programmatic_seo_opportunity: "programmatic SEO opportunity",
  pricing_strategy: "pricing strategy",
  critic_concern: "known concern",
  data_acquisition_notes: "data sourcing notes",
  "tags.build_complexity": "build complexity",
  "tags.data_access": "data access",
  "tags.growth_channels": "growth channels",
};

export function founderFitFieldLabel(
  kind: "profile" | "idea",
  field: string,
): string {
  const normalized = field.replace(/^(profile|idea)\./, "");
  const label = kind === "profile"
    ? PROFILE_FIELD_LABELS[normalized as FounderFitProfileField]
    : IDEA_FIELD_LABELS[normalized as FounderFitIdeaField];
  if (label) return label;

  // Artifacts are durable and an older model may have emitted a field that is
  // no longer public. Never turn internal dotted/snake/camel tokens into UI.
  return kind === "profile" ? "saved founder constraints" : "candidate evidence";
}

export function founderFitReasoningSources(
  profileFields: string[],
  ideaFields: string[],
): string {
  const labels = [
    ...profileFields.map((field) => founderFitFieldLabel("profile", field)),
    ...ideaFields.map((field) => founderFitFieldLabel("idea", field)),
  ];
  return [...new Set(labels)].join(" · ")
    || "saved founder constraints and candidate evidence";
}
