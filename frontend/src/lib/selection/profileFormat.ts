import type { SelectionDecisionProfile } from "$lib/types/job";

/**
 * Human-readable build-constraints line: `20-40 hrs/week · $1k-$5k · small team
 * · contractor or agency builds it · revenue in 30 days`. The raw profile values are enum tokens (`20_40`,
 * `1k_5k`) — never show those; a `.replace("_"," ")` gives "20 40", which reads
 * as broken. This is the single formatter every surface (workspace header,
 * compare fit view, evidence dialog) shares so the phrasing never drifts.
 */
const TIME: Record<string, string> = {
  under_10: "under 10 hrs/week",
  "10_20": "10-20 hrs/week",
  "20_40": "20-40 hrs/week",
  full_time: "full time",
};
const BUDGET: Record<string, string> = {
  under_1k: "under $1k",
  "1k_5k": "$1k-$5k",
  "5k_20k": "$5k-$20k",
  "20k_plus": "$20k+",
};
const TEAM: Record<string, string> = {
  solo: "solo",
  small_team: "small in-house team",
  funded_team: "funded in-house team",
};
const BUILD_MODEL: Record<string, string> = {
  self: "I build the software",
  contractor: "contractor or agency builds it",
};
const HORIZON: Record<string, string> = {
  "30_days": "revenue in 30 days",
  "90_days": "revenue in 90 days",
  "6_months": "revenue in 6 months",
  patient: "patient horizon",
};

function label(map: Record<string, string>, value: string): string {
  return map[value] ?? value.replaceAll("_", " ");
}

export function formatBuildConstraints(profile: SelectionDecisionProfile): string {
  return [
    label(TIME, profile.weeklyTime),
    label(BUDGET, profile.budget),
    label(TEAM, profile.team),
    profile.buildModel
      ? label(BUILD_MODEL, profile.buildModel)
      : "build model not specified",
    label(HORIZON, profile.revenueHorizon),
  ].join(" · ");
}
