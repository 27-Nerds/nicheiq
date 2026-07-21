import type {
  FinalDecisionDisposition,
  FrozenFinalDecisionPreMortem,
  FrozenFinalDecisionTestBrief,
  RecommendationRelation,
} from "./finalDecision";

export type DecisionHandoffAction = "BUILD" | "VALIDATE_MORE" | "PARK" | "STOP";

export interface DecisionHandoffTarget {
  ideaId: string;
  ideaRevision: number;
  title: string | null;
  problem: string | null;
  audience: string | null;
  valueProposition: string | null;
  proposedScope: string[];
  technicalApproach: string | null;
  estimatedBuildTime: string | null;
}

interface DecisionHandoffArtifactBase {
  jobId: string;
  finalDecisionId: string;
  action: DecisionHandoffAction;
  target: DecisionHandoffTarget | null;
  decision: {
    disposition: FinalDecisionDisposition;
    recommendationRelation: RecommendationRelation;
    rationale: string;
    acceptedRisks: string;
    changeCriterion: string;
    overrideReason: string | null;
    decidedAt: string;
  };
  evidence: {
    sourceFingerprint: string;
    reportSha256: string;
    recommendationSnapshot: Record<string, unknown>;
    selectedIdeaSnapshot: Record<string, unknown> | null;
    alternativesSnapshot: Record<string, unknown>;
    evidenceSnapshot: Record<string, unknown>;
  };
  executionPolicy: {
    providerDispatchAllowed: boolean;
    allowedOperation: "CREATE_IMPLEMENTATION_ISSUE" | "CREATE_VALIDATION_ISSUE" | null;
    resumeRequiresNewOwnerDecision: boolean;
    terminal: boolean;
  };
}

export interface DecisionHandoffArtifact extends DecisionHandoffArtifactBase {
  testBrief: FrozenFinalDecisionTestBrief | null;
  preMortem: FrozenFinalDecisionPreMortem | null;
}

export interface SelectionDecisionHandoff {
  id: string;
  finalDecisionId: string;
  action: DecisionHandoffAction;
  ideaId: string | null;
  ideaRevision: number | null;
  inputFingerprint: string;
  artifact: DecisionHandoffArtifact;
  createdAt: string;
}

export interface DecisionHandoffLoadResponse {
  handoff: SelectionDecisionHandoff | null;
}
