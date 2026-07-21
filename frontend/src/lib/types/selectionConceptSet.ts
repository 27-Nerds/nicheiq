import type {
  ExperimentEvidenceSignal,
  ExperimentMethod,
} from './selectionExperiment';

export type SelectionConceptPurpose = 'diverge' | 'resolve_tradeoff' | 'reshape';
export type SelectionConceptOperation = 'narrow' | 'reposition' | 'combine' | 'adjacent';
export type SelectionConceptAxis = 'buyer' | 'job' | 'mechanism' | 'channel' | 'scope' | 'business_model';
export type SelectionConceptRiskType = 'demand' | 'distribution' | 'competition' | 'feasibility' | 'founder_fit';

export interface SelectionConceptParentRequest {
  ideaId: string;
  ideaRevision: number;
}

export interface SelectionConceptSetRequest {
  purpose: SelectionConceptPurpose;
  parents: SelectionConceptParentRequest[];
  targetTradeoff?: string;
}

export interface SelectionConceptParent extends SelectionConceptParentRequest {
  solutionName: string;
  candidateSnapshotSha256: string;
  pain: string | null;
  audience: string | null;
}

export interface SelectionConceptAssumption {
  assumptionId: string;
  type: SelectionConceptRiskType;
  statement: string;
  whyDecisionChanging: string;
  consequenceIfFalse: string;
}

export interface SelectionConceptOption {
  optionId: string;
  operation: SelectionConceptOperation;
  title: string;
  brief: string;
  changeSummary: string;
  rationale: string;
  parentContributions: Array<SelectionConceptParent & { contribution: string }>;
  changedAxes: Array<{
    axis: SelectionConceptAxis;
    from: string;
    to: string;
    reason: string;
  }>;
  retainedEvidence: string[];
  evidenceToRecheck: string[];
  assumptions: SelectionConceptAssumption[];
  disqualifiers: string[];
  suggestedTest: {
    assumptionId: string;
    hypothesis: string;
    method: ExperimentMethod;
    evidenceSignal: ExperimentEvidenceSignal;
    audience: string;
    artifact: string;
    primaryMetric: string;
    passThreshold: string;
    failThreshold: string;
    measurementWindow: string;
  };
}

export interface SelectionConceptSetArtifact {
  inputFingerprint: string;
  purpose: SelectionConceptPurpose;
  targetTradeoff: string | null;
  parents: SelectionConceptParent[];
  context: {
    reportSha256: string;
    founderFitFingerprint: string | null;
    challengeFingerprints: string[];
    conclusionFingerprints: string[];
  };
  options: SelectionConceptOption[];
  model: string;
  promptId: string;
  createdAt: string;
}

export interface SelectionConceptSet {
  id: string;
  artifact: SelectionConceptSetArtifact;
  stale: boolean;
  createdAt: string;
}

export interface PreparedSelectionConceptOption {
  sourceMessageId: string;
  patch: import('$lib/api').IdeaSynthesisPatch;
  cached: boolean;
}
