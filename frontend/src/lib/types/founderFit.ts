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

export interface FounderFitDimensionResult {
  dimension: FounderFitDimension;
  status: FounderFitStatus;
  summary: string;
  profileFields: string[];
  ideaFields: string[];
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
