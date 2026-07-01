/**
 * Shared Job-related types used across the application.
 * Single source of truth — do not duplicate these interfaces elsewhere.
 */

export type JobStatus =
  | 'PENDING'
  | 'QUEUED'
  | 'RUNNING'
  | 'AWAITING_SELECTION'
  | 'REGENERATING'
  | 'RUNNING_PHASE2'
  | 'COMPLETED'
  | 'FAILED'
  | 'CANCELLED';

export type ErrorSeverity = 'info' | 'warning' | 'error';

// Interactive job flow — solution selection types

export interface SolutionValidationData {
  keyword_demand_score?: number | null;
  demand_signal?: string | null;
  total_volume?: number | null;
  validated_count?: number | null;
  avg_keyword_difficulty?: number | null;
  rankability_factor?: number | null;
  top_keywords?: { keyword: string; volume: number; difficulty?: number }[] | null;
  top_geographic_keywords?: { keyword: string; volume: number }[] | null;
  pricing_validation?: Record<string, unknown> | null;
}

/** Canonical strength keys (mirror StrengthTag in solution_idea.py + superpower.ts). */
export type StrengthKey =
  | "market-fit"
  | "seo-power"
  | "innovator"
  | "quick-build"
  | "solo-friendly";

/** Closed-vocabulary filter facets for an idea. Mirrors IdeaTags in solution_idea.py.
 *  See docs/IDEA_TAGS.md. Values are display-only chips this round (filtering is later). */
export interface IdeaTags {
  project_type?: string | null;
  data_access?: string | null;
  target_market?: string | null;
  monetization?: string | null;
  monetization_secondary?: string | null;
  growth_channels?: string[];
  risk_flags?: string[];
  build_complexity?: string | null;
  novelty_level?: string | null;
  strengths?: StrengthKey[];
  /** The single most-exceptional strength (max margin above cutoff), or null — the card badge. */
  primary_strength?: StrengthKey | null;
  /** LLM's one-sentence justification of the non-obvious tag calls ("Why these tags"). */
  rationale?: string | null;
}

export interface SolutionPreview {
  solution_name: string;
  headline?: string | null;
  short_description?: string | null;
  description: string;
  value_proposition: string;
  pain_points_addressed?: string[];
  core_features?: string[];
  target_personas?: string[];
  project_type?: string | null;
  differentiation_factors?: string[] | null;
  market_fit_score?: number | null;
  technical_feasibility_score?: number | null;
  seo_scalability_score?: number | null;
  novelty_score?: number | null;
  obviousness_score?: number | null; // 0-1, lower = more original; shown as "Originality" (1 - this)
  programmatic_seo_opportunity?: string | null;
  estimated_cac_organic?: string | null;
  estimated_cac_paid?: string | null;
  organic_discovery_queries?: string[] | null;
  validation?: SolutionValidationData | null;
  adjusted_composite_score?: number | null;
  solo_dev_feasibility?: number | null;
  pricing_strategy?: string | null;
  estimated_development_time?: string | null;
  dev_time_rationale?: string | null;
  why_it_works?: string | null;
  why_it_works_short?: string | null;
  innovation_angle?: string | null;
  conventional_approach?: string | null;
  // Angle-aware evaluation (set when angle eval is on; absent/null otherwise)
  winning_angle?: string | null; // distribution_seo | novel_differentiation | vertical_workflow
  angle_rationale?: string | null; // user-facing comment about the angle
  novelty_rationale?: string | null; // user-facing: why this novelty score fits the project_type
  differentiation_locus?: string | null; // WHERE the edge lives (or honest "thin me-too")
  // Feasibility rationale — already emitted in the preview dict (BaseSolutionIdea.model_dump),
  // declared here so the per-score "why" tooltips can read them type-safely.
  technical_approach?: string | null;
  data_acquisition_notes?: string | null;
  data_access_model?: string | null;
  data_feasibility_score?: number | null;
  build_feasibility_score?: number | null;
  // Grounded generation provenance — the (pain × segment) cell that produced this idea.
  source_pain?: string | null;
  source_segment?: string | null;
  // Audience framing (output lens only): true when this idea serves the user's stated
  // audience (set post-generation). Drives the primary/adjacent grid split.
  audience_fit?: boolean | null;
  // Closed-vocabulary filter facets (chips + future filtering). See docs/IDEA_TAGS.md.
  tags?: IdeaTags | null;
}

export interface ReportSummary {
  opportunity_score: number | null;
  market_fit_score: number | null;
  technical_feasibility_score: number | null;
  verdict: string | null;
  risk_level: string | null;
  primary_concern: string | null;
  solution_name: string | null;
  solution_tagline: string | null;
  core_value_prop: string | null;
  project_type: string | null;
  confidence_score: number | null;
  total_keywords: number | null;
  total_search_volume: number | null;
  competitor_count: number | null;
  pain_points_found: number | null;
}

export interface ErrorDetails {
  code: string;
  severity: ErrorSeverity;
  userMessage: string;
  actionableGuidance: string;
  retryDelayMinutes?: number;
  rawMessage?: string;
}

export interface StageProgress {
  stageNumber: number;
  stageName: string;
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'SKIPPED' | 'FAILED';
  startedAt?: string | null;
  completedAt?: string | null;
  durationSeconds: number | null;
  artifact?: Record<string, any> | null;
}

export interface JobAsset {
  type: 'REPORT_JSON' | 'LANDING_PAGE' | string;
  url: string;
}

export interface StopReasonDetails {
  qualityTier?: string;
  confidenceScore?: number;
  metrics?: {
    painPointCount?: number;
    quoteDensity?: number;
    uniqueSourceCount?: number;
  };
  recommendation?: string;
}

// -- Billable stage types (single source of truth) --

export type BillableStageName = 'discovery' | 'deep_research' | 'landing_page' | 'regenerate_ideas';

export interface StageCosts {
  discovery: number;
  deep_research: number;
  landing_page: number;
  regenerate_ideas: number;
}

export const DEFAULT_STAGE_COSTS: StageCosts = {
  discovery: 5,
  deep_research: 15,
  landing_page: 5,
  regenerate_ideas: 2,
};

export function computeFullResearchCost(costs: StageCosts): number {
  return costs.discovery + costs.deep_research;
}

export interface Job {
  id: string;
  email?: string;
  niche: string;
  status: JobStatus | string;
  currentStage: number;
  currentStageName: string | null;
  stagesCompleted: number;
  totalStages: number;
  progressPercent: number;
  errorMessage: string | null;
  createdAt: string;
  startedAt: string | null;
  completedAt: string | null;
  progress?: StageProgress[];
  assets?: JobAsset[];
  // Optional fields returned by some endpoints
  hasReport?: boolean;
  hasLandingPage?: boolean;
  creditRefunded?: boolean;
  queuePosition?: number | null;
  aheadCount?: number;
  totalQueued?: number;
  stopReason?: string | null;
  stopReasonDetails?: StopReasonDetails | null;
  // User-friendly error information
  errorCode?: string | null;
  errorDetails?: ErrorDetails | null;
  // Project type filter selected at creation
  allowedProjectTypes?: string[] | null;
  // Landing page lifecycle
  generateLandingPage?: boolean;
  landingPageStatus?: string | null;
  // Interactive job flow
  jobMode?: 'interactive' | 'auto' | null;
  // Entry mode — how the job was created. 'pain_research' (single/remix, skips
  // discovery stages 1-4) and 'deep_idea' (skips 1-5) drive shortened-flow UI.
  entryMode?: 'idea' | 'audience' | 'discovery' | 'pain_research' | 'pain_remix' | 'deep_idea' | null;
  selectedSolution?: string | null;
  selectedSolutions?: string[] | null;
  selectionRationale?: string | null;
  awaitingSelectionAt?: string | null;
  ideasShownAt?: string | null;
  solutionIdeas?: SolutionPreview[] | null;
  solutionIdeasCount?: number | null;
  canRegenerate?: boolean;
}
