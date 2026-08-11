/**
 * Shared Job-related types used across the application.
 * Single source of truth — do not duplicate these interfaces elsewhere.
 */

export type JobStatus =
  | 'PENDING'
  | 'QUEUED'
  | 'RUNNING'
  | 'AWAITING_SELECTION'
  | 'AWAITING_GATE'
  | 'REGENERATING'
  | 'RUNNING_PHASE2'
  | 'COMPLETED'
  | 'FAILED'
  | 'CANCELLED';

// ============================================
// Guided mode (Phase B — plans/eager-meandering-feather.md): G1 (post-Stage-1) / G2
// (post-Stage-4) stage gates. Mirrors the Python artifact builders
// (`_build_stage_artifact(1)` / `_build_g2_gate_artifact` in research_flow.py) and the
// Zod whitelists in backend/src/types/job.ts (GateG1PatchSchema / GateG2PatchSchema).
// ============================================

/** `_build_stage_artifact(1)` — G1 gate card data (niche-context fields only). */
export interface GateG1Artifact {
  type: 'niche_validation';
  niche_description: string | null;
  market_segments: string[];
  industry_boundaries: string | null;
  /** G1-editable audience fields + derived search plan (refreshed on apply_stay). */
  user_target_audience?: string | null;
  audience_scope?: string | null;
  anchor_entities?: string[];
  disambiguation_exclusions?: string[];
}

/** One entry of `_build_g2_gate_artifact()`'s `pains` list. */
export interface GateG2PainEntry {
  title: string;
  severity: number | null;
  opportunity: string | null;
}

/** One entry of `_build_g2_gate_artifact()`'s `segments` list. */
export interface GateG2SegmentEntry {
  segment_name: string;
  size_estimate: string | null;
  payability_class: string | null;
  payability_score: number | null;
}

/** `_build_g2_gate_artifact()` — G2 gate card data (full pain titles + segments). */
export interface GateG2Artifact {
  type: 'audience_mapping_gate';
  pains: GateG2PainEntry[];
  segments: GateG2SegmentEntry[];
  primary_target?: string | null;
  /** Set to 'pain_scope_only' when audience_mapping failed (DR N4 degraded path). */
  degraded?: string;
}

export type GateArtifact = GateG1Artifact | GateG2Artifact | Record<string, unknown>;

/** Mirrors backend `GateG1PatchSchema` (backend/src/types/job.ts) — field SHAPE only,
 *  cross-checked against the job's gateArtifact server-side. */
export interface GateG1PatchFields {
  niche_description?: string;
  market_segments?: string[];
  industry_boundaries?: string;
  user_target_audience?: string;
}

/** Mirrors backend `GateG2PatchSchema`. */
export interface GateG2PatchFields {
  user_target_audience?: string;
  primary_target_segment?: string;
  excluded_segments?: string[];
  segment_emphasis?: Record<string, 'high' | 'low'>;
  pain_scope?: {
    excluded_titles: string[];
    pinned_titles: string[];
  };
}

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
  /** How often the buyer USES the product (not how it bills): continuous | periodic | episodic | one-shot. */
  usage_cadence?: string | null;
  /** Code-derived: episodic/one-shot usage sold as a subscription (buyers churn between events). */
  pricing_shape_mismatch?: boolean;
  pricing_shape_note?: string | null;
  build_complexity?: string | null;
  novelty_level?: string | null;
  strengths?: StrengthKey[];
  /** The single most-exceptional strength (max margin above cutoff), or null — the card badge. */
  primary_strength?: StrengthKey | null;
  /** LLM's one-sentence justification of the non-obvious tag calls ("Why these tags"). */
  rationale?: string | null;
}

export type DecisionProfilePreset = 'balanced' | 'fast_revenue' | 'solo_bootstrap' | 'audience_first';
export type WeeklyTime = 'under_10' | '10_20' | '20_40' | 'full_time';
export type ValidationBudget = 'under_1k' | '1k_5k' | '5k_20k' | '20k_plus';
export type TeamShape = 'solo' | 'small_team' | 'funded_team';
export type BuildModel = 'self' | 'contractor';
export type RevenueHorizon = '30_days' | '90_days' | '6_months' | 'patient';
export type DistributionAdvantage = 'seo' | 'community' | 'existing_audience' | 'outbound' | 'paid' | 'partnerships';

export interface SelectionDecisionProfile {
  preset: DecisionProfilePreset;
  weeklyTime: WeeklyTime;
  budget: ValidationBudget;
  team: TeamShape;
  /** Added after the original profile contract. Missing means genuinely unspecified. */
  buildModel?: BuildModel;
  revenueHorizon: RevenueHorizon;
  distributionAdvantages: DistributionAdvantage[];
  strengths: string;
  hardConstraints: string;
}

export interface SolutionPreview {
  idea_id?: string;
  idea_revision?: number;
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
  obviousness_score?: number | null; // 0-1, lower = less obvious/more distinct; UI displays 1 - this
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
  novelty_rationale?: string | null; // stable field name; user-facing explanation of distinctiveness for this project type
  differentiation_locus?: string | null; // WHERE the edge lives (or honest "thin me-too")
  // Feasibility rationale — already emitted in the preview dict (BaseSolutionIdea.model_dump),
  // declared here so the per-score "why" tooltips can read them type-safely.
  technical_approach?: string | null;
  data_acquisition_notes?: string | null;
  data_access_model?: string | null;
  data_sources?: string[] | null;
  data_feasibility_score?: number | null;
  build_feasibility_score?: number | null;
  // Structural-dedup reference tags (hyphenated phrases): how users reach value / core mechanism.
  journey_tag?: string | null;
  mechanism_tag?: string | null;
  // Competitive parity — set only by the web-verified parity probe (top ideas only); null otherwise.
  incumbent_parity?: string | null;
  adjacent_market_parity?: string | null;
  // Adversarial review. A killed idea stays visible, selectable and ranked, and its scores
  // are NOT capped for it (that coupling was removed 2026-08-02) — the verdict says the
  // premise is unproven, while the scores describe the idea if the premise holds. The UI
  // renders `killed` as "Premise unproven" (see utils/adversarialReview.ts).
  red_team_verdict?: string | null; // survives | weakened | killed
  red_team_caveats?: string[] | null;
  // Buyer-segment payability (0-1) stamped from the segment map; drives the market_fit
  // payability cap in _validate_idea_caps rule (d).
  source_segment_payability?: number | null;
  source_segment_payability_class?: string | null;
  // Multi-Frame Idea Generation Portfolio: which generation frame minted this idea's cell.
  // CODE-FILLED, never LLM-set. Includes owner_synthesis and additional_batch for
  // user-triggered candidate-pool operations.
  source_frame?: string | null;
  /** Durable identity and exact proposal retained for a Concept Forge evaluation. */
  evaluation_id?: string | null;
  evaluation_source_message_id?: string | null;
  proposed_title?: string | null;
  synthesis_evaluation?: Record<string, unknown> | null;
  /** Durable provenance for an append-only additional batch. */
  generation_operation_id?: string | null;
  generation_batch_ordinal?: number | null;
  /** Submitted idea with no validated pain match in this run's evidence. */
  unanchored_hypothesis?: boolean | null;
  // Distilled bear case — the calibration critic's market_fit reason, distilled
  // (via extract_criterion_reason) to one user-facing note. NOT the raw
  // calibration_notes. Emitted in the same preview payload as the parity fields.
  critic_concern?: string | null;
  // Refinement tournament judge's binding constraint + directive on the winning
  // revision — the second bear case. Null when the v4 refinement loop didn't run.
  refine_binding_constraint?: string | null;
  // Grounded generation provenance — the (pain × segment) cell that produced this idea.
  source_pain?: string | null;
  source_segment?: string | null;
  // Audience framing (output lens only): true when this idea serves the user's stated
  // audience (set post-generation). Drives the primary/adjacent grid split.
  audience_fit?: boolean | null;
  // Closed-vocabulary filter facets (chips + future filtering). See docs/IDEA_TAGS.md.
  tags?: IdeaTags | null;
  // Portfolio-funnel provenance tier: 'single' (cell winner) | 'salvaged' (critic-rescued
  // loser) | 'bundle' (synthesis-stage multi-pain product) | 'merged' (synthesized from
  // overlapping variants). Absent on legacy reports = 'single'.
  idea_tier?: string | null;
  // Portfolio-funnel lifecycle status: 'active' | 'demoted' | 'restored' | 'absorbed'.
  candidate_status?: string | null;
  // Names of the variant ideas synthesized into this one (only set when idea_tier === 'merged').
  merged_from?: string[] | null;
  synthesis_operation?: 'narrow' | 'reposition' | 'combine' | 'adjacent' | null;
  synthesized_from?: {
    idea_id: string;
    idea_revision: number;
    solution_name: string;
    contribution: string;
  }[] | null;
  synthesis_evidence?: {
    sourceAnchors?: { ideaId: string; pain?: string; audience?: string }[];
    requiresValidation?: string[];
  } | null;
  synthesis_source_message_id?: string | null;
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

export type BillableStageName = 'discovery' | 'deep_research' | 'landing_page' | 'regenerate_ideas' | 'seed_idea';

export interface StageCosts {
  discovery: number;
  deep_research: number;
  landing_page: number;
  regenerate_ideas: number;
  /** Selection-chat "generate an idea from your own idea" (flat, like regenerate_ideas — NOT
   *  part of `guided`, which is discovery-segment-only pricing). Optional so older deployments
   *  don't break callers. */
  seed_idea?: number;
  /** Guided-mode (Phase B) per-checkpoint segment prices, returned alongside the flat
   *  costs above once the endpoint is redeployed — optional so older deployments don't
   *  break callers. s1 = discovery, s2_4 = audience + pain analysis, s5 = idea generation. */
  guided?: {
    s1: number;
    s2_4: number;
    s5: number;
    total: number;
  };
}

export const DEFAULT_STAGE_COSTS: StageCosts = {
  discovery: 5,
  deep_research: 15,
  landing_page: 5,
  regenerate_ideas: 2,
  seed_idea: 2,
};

export function computeFullResearchCost(costs: StageCosts): number {
  return costs.discovery + costs.deep_research;
}

export interface SelectionDraftItem {
  ideaId: string;
  ideaRevision: number;
}

export interface SelectionDraft {
  version: number;
  items: SelectionDraftItem[];
}

export interface SelectedSolutionRef extends SelectionDraftItem {
  snapshotSha256: string;
}

export interface Job {
  id: string;
  email?: string;
  niche: string;
  /** Display-safe short label (word-boundary truncated backend-side). Render this in
   *  list rows/headers/titles; `niche` stays verbatim for re-run/prefill round-trips. */
  nicheDisplay?: string;
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
  /** Exact positive amount restored by the latest dispatch; zero means no spendable refund. */
  creditRefundedAmount?: number;
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
  // 'validate_idea' ("Check my idea") runs the full pipeline with the user's own
  // idea seeded in and renders the idea-report layout at AWAITING_SELECTION.
  entryMode?: 'idea' | 'audience' | 'discovery' | 'pain_research' | 'pain_remix' | 'deep_idea' | 'validate_idea' | null;
  selectedSolution?: string | null;
  selectedSolutions?: string[] | null;
  selectedSolutionIds?: string[] | null;
  /** Immutable ordered Phase-2 scope; authoritative after Deep Research is purchased. */
  selectedSolutionRefs?: SelectedSolutionRef[] | null;
  deepResearchRecommendedIdeaId?: string | null;
  deepResearchRecommendedIdeaRevision?: number | null;
  selectionRationale?: string | null;
  selectionDecisionProfile?: SelectionDecisionProfile | null;
  selectionDraft?: SelectionDraft | null;
  awaitingSelectionAt?: string | null;
  ideasShownAt?: string | null;
  solutionIdeas?: SolutionPreview[] | null;
  solutionIdeasCount?: number | null;
  canRegenerate?: boolean;
  ideaBatchCompletedCount?: number;
  maxIdeaBatches?: number;
  // Guided mode (Phase B) — chatMode opts a job into the G1/G2 stage gates;
  // gateStage/gateArtifact/gateReachedAt are only set while status=AWAITING_GATE
  // (null otherwise, including at AWAITING_SELECTION).
  chatMode?: boolean;
  gateStage?: 1 | 4 | null;
  gateArtifact?: GateArtifact | null;
  gateReachedAt?: string | null;
  /** apply_stay count for the CURRENT gate — capped at 5 (gate-action route). */
  gateApplyCount?: number | null;
  /** Exact durable operation currently owning the job; null when no dispatch is active. */
  activeDispatchKind?: 'CONTINUE' | 'APPLY_STAY' | 'REGENERATE' | 'SEED_IDEA' | 'DEEP_RESEARCH' | null;
  /** Operation identity/state used for exact cancellation; never infer it from job status. */
  activeOperation?: {
    id: string;
    kind: 'CONTINUE' | 'APPLY_STAY' | 'REGENERATE' | 'SEED_IDEA' | 'DEEP_RESEARCH';
    state: 'AUTHORIZED' | 'CLAIMED' | 'RECOVERING';
  } | null;
}
