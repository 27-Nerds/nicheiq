import type { SelectionDecisionProfile } from './job';
import type { SelectionExperimentDraft } from './selectionExperiment';

export type FounderFitDimension =
  | 'time'
  | 'budget'
  | 'team'
  | 'revenue_horizon'
  | 'distribution'
  | 'strengths'
  | 'hard_constraints';

export type FounderFitStatus = 'aligned' | 'conflict' | 'unknown' | 'irrelevant';
export type FounderFitVerdict = 'fits' | 'needs_reshape' | 'blocked' | 'insufficient_evidence';

export type FounderFitProfileField =
  | 'preset'
  | 'weeklyTime'
  | 'budget'
  | 'team'
  | 'buildModel'
  | 'revenueHorizon'
  | 'distributionAdvantages'
  | 'strengths'
  | 'hardConstraints';

export type FounderFitIdeaField =
  | 'description'
  | 'value_proposition'
  | 'source_pain'
  | 'source_segment'
  | 'target_personas'
  | 'core_features'
  | 'project_type'
  | 'estimated_development_time'
  | 'dev_time_rationale'
  | 'technical_feasibility_score'
  | 'solo_dev_feasibility'
  | 'seo_scalability_score'
  | 'programmatic_seo_opportunity'
  | 'pricing_strategy'
  | 'critic_concern'
  | 'data_acquisition_notes'
  | 'tags.build_complexity'
  | 'tags.data_access'
  | 'tags.growth_channels';

export interface FounderFitDimensionResult {
  dimension: FounderFitDimension;
  status: FounderFitStatus;
  summary: string;
  /**
   * Old stored artifacts may contain an unknown token. Rendering must pass
   * through founderFitFieldLabel(), which deliberately hides unknown internals.
   */
  profileFields: Array<FounderFitProfileField | string>;
  ideaFields: Array<FounderFitIdeaField | string>;
}

export interface FounderFitResult {
  ideaId: string;
  ideaRevision: number;
  ideaTitle: string;
  verdict: FounderFitVerdict;
  summary: string;
  strongestAdvantage: string;
  blockingConflict: string | null;
  decisionChangingUnknown: string;
  sensitivity: string;
  dimensions: FounderFitDimensionResult[];
  suggestedExperiment: SelectionExperimentDraft;
}

export interface FounderFitArtifact {
  version: 1;
  inputFingerprint: string;
  profileSnapshot: SelectionDecisionProfile;
  ideaSnapshots: Array<Record<string, unknown>>;
  model: string;
  createdAt: string;
  results: FounderFitResult[];
}

export interface FounderFitReference {
  ideaId: string;
  ideaRevision: number;
}

export interface FounderFitLoadResponse {
  analysis: FounderFitArtifact | null;
  stale: boolean;
}

export interface FounderFitRunResponse {
  analysis: FounderFitArtifact;
  cached: boolean;
}
