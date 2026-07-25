import type { SolutionPreview } from "$lib/types/job";

const UNIT_SCORE_FIELDS = [
  "market_fit_score",
  "technical_feasibility_score",
  "seo_scalability_score",
  "novelty_score",
  "obviousness_score",
  "adjusted_composite_score",
  "solo_dev_feasibility",
  "data_feasibility_score",
  "build_feasibility_score",
  "source_segment_payability",
] as const satisfies readonly (keyof SolutionPreview)[];

const STRING_LIST_FIELDS = [
  "pain_points_addressed",
  "core_features",
  "target_personas",
  "differentiation_factors",
  "organic_discovery_queries",
  "data_sources",
  "merged_from",
] as const satisfies readonly (keyof SolutionPreview)[];

export interface NormalizedSolutionPreviews {
  solutions: SolutionPreview[];
  invalidCount: number;
}

export function finiteUnitScore(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 1
    ? value
    : null;
}

export function nonNegativeInteger(value: unknown): number | null {
  return typeof value === "number" && Number.isInteger(value) && value >= 0
    ? value
    : null;
}

export function safeStringList(value: unknown): string[] {
  const values = Array.isArray(value) ? value : typeof value === "string" ? [value] : [];
  return values
    .filter((item): item is string => typeof item === "string")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function normalizeSolutionPreviews(input: unknown): NormalizedSolutionPreviews {
  if (!Array.isArray(input)) return { solutions: [], invalidCount: input == null ? 0 : 1 };

  let invalidCount = 0;
  const solutions: SolutionPreview[] = [];

  for (const candidate of input) {
    if (!candidate || typeof candidate !== "object" || Array.isArray(candidate)) {
      invalidCount += 1;
      continue;
    }

    const record = candidate as Record<string, unknown>;
    const solutionName = typeof record.solution_name === "string"
      ? record.solution_name.trim()
      : "";
    if (!solutionName) {
      invalidCount += 1;
      continue;
    }

    const normalized = {
      ...record,
      solution_name: solutionName,
      description: typeof record.description === "string" ? record.description : "",
      value_proposition: typeof record.value_proposition === "string" ? record.value_proposition : "",
    } as unknown as SolutionPreview;

    for (const field of UNIT_SCORE_FIELDS) {
      (normalized as unknown as Record<string, unknown>)[field] = finiteUnitScore(record[field]);
    }
    for (const field of STRING_LIST_FIELDS) {
      (normalized as unknown as Record<string, unknown>)[field] = safeStringList(record[field]);
    }

    solutions.push(normalized);
  }

  return { solutions, invalidCount };
}
