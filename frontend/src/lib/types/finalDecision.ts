import type {
  ExperimentAssumptionType,
  ExperimentEvidenceSignal,
  ExperimentMethod,
  ExperimentRunStatus,
  SelectionExperimentOriginSnapshot,
} from "./selectionExperiment";
import type {
  SelectionChallengeConsensus,
  SelectionChallengeLens,
  SelectionChallengePosition,
} from "./selectionChallenge";

export type FinalDecisionDisposition = 'PROCEED' | 'TEST_FIRST' | 'PARK' | 'STOP';
export type RecommendationRelation = 'FOLLOWED' | 'OVERRIDDEN' | 'DEFERRED' | 'REJECTED';

export interface FinalDecisionFinalist {
  ideaId: string;
  ideaRevision: number;
  solutionName: string;
  reportEvidence: Record<string, unknown> | null;
}

export interface FinalDecisionRecommendation extends FinalDecisionFinalist {
  identityResolution: 'exact' | 'legacy_unique_name';
  selectionRationale: string | null;
  verdict: {
    verdict?: string;
    rationale?: string;
    risk_level?: string;
    primary_concern?: string | null;
  } | null;
  generatedAt: string | null;
}

export interface FinalDecisionConclusion {
  id: string;
  experimentId: string;
  ideaId: string;
  ideaRevision: number;
  outcome: 'PASS' | 'FAIL' | 'AMBIGUOUS' | 'INVALID';
  nextAction: string;
  ownerRationale: string;
  createdAt: string;
  snapshot: Record<string, unknown>;
}

export interface FinalDecisionLockedTestBrief {
  version: 1;
  experimentId: string;
  jobId: string;
  lockedAt: string;
  idea: {
    ideaId: string;
    ideaRevision: number;
    snapshot: Record<string, unknown>;
  };
  origin: SelectionExperimentOriginSnapshot | null;
  assumption: {
    type: ExperimentAssumptionType;
    statement: string;
    whyCritical: string;
    currentEvidence: string;
  };
  testDesign: {
    method: ExperimentMethod;
    evidenceSignal: ExperimentEvidenceSignal;
    stimulus: string;
    audience: string;
    channel: string;
    primaryMetric: string;
    passThreshold: string;
    failThreshold: string;
    measurementWindow: string;
    sampleTarget: number | null;
    costEstimate: string;
  };
  decisionRules: {
    pass: string;
    fail: string;
    ambiguous: string;
    invalid: string;
  };
  briefFingerprint: string;
  runStatus: ExperimentRunStatus | null;
  conclusionId: null;
}

export interface FinalDecisionRiskPrompt {
  challengeId: string;
  challengeInputFingerprint: string;
  challengeArtifactFingerprint: string;
  ideaId: string;
  ideaRevision: number;
  lens: SelectionChallengeLens;
  questionId: string;
  consensus: SelectionChallengeConsensus;
  skeptic: { position: SelectionChallengePosition; summary: string };
  auditor: { position: SelectionChallengePosition; summary: string };
}

export interface FinalDecisionPreMortemEntryInput {
  failureMode: string;
  earlyWarningSignal: string;
  mitigation: string;
  origin?: {
    challengeId: string;
    questionId: string;
  };
}

export interface FrozenFinalDecisionPreMortem {
  version: 1;
  target: {
    ideaId: string;
    ideaRevision: number;
  };
  entries: Array<{
    failureMode: string;
    earlyWarningSignal: string;
    mitigation: string;
    origin: null | {
      kind: "SELECTION_CHALLENGE_QUESTION";
      challengeId: string;
      challengeInputFingerprint: string;
      challengeArtifactFingerprint: string;
      questionId: string;
      lens: SelectionChallengeLens;
      consensus: SelectionChallengeConsensus;
      skeptic: { position: SelectionChallengePosition; summary: string };
      auditor: { position: SelectionChallengePosition; summary: string };
    };
  }>;
}

export type FrozenFinalDecisionTestBrief = Omit<FinalDecisionLockedTestBrief, "runStatus" | "conclusionId"> & {
  runStatusAtDecision: ExperimentRunStatus | null;
};

export interface SelectionFinalDecision {
  id: string;
  jobId: string;
  disposition: FinalDecisionDisposition;
  selectedIdeaId: string | null;
  selectedIdeaRevision: number | null;
  testExperimentId: string | null;
  testExperimentSnapshot: FrozenFinalDecisionTestBrief | null;
  preMortemSnapshot: FrozenFinalDecisionPreMortem | null;
  recommendationRelation: RecommendationRelation;
  rationale: string;
  acceptedRisks: string;
  changeCriterion: string;
  overrideReason: string | null;
  requestFingerprint: string;
  sourceFingerprint: string;
  recommendationSnapshot: Record<string, unknown>;
  selectedIdeaSnapshot: Record<string, unknown> | null;
  createdAt: string;
}

export interface FinalDecisionLoadResponse {
  decision: SelectionFinalDecision | null;
  sourceFingerprint: string;
  recommendation: FinalDecisionRecommendation;
  finalists: FinalDecisionFinalist[];
  conclusions: FinalDecisionConclusion[];
  lockedTestBriefs: FinalDecisionLockedTestBrief[];
  riskPrompts: FinalDecisionRiskPrompt[];
}

interface FinalDecisionBaseInput {
  rationale: string;
  acceptedRisks: string;
  changeCriterion: string;
  sourceFingerprint: string;
}

export type FinalDecisionInput =
  | (FinalDecisionBaseInput & {
      disposition: 'PROCEED';
      ideaId: string;
      ideaRevision: number;
      preMortem: FinalDecisionPreMortemEntryInput[];
      overrideReason?: string;
    })
  | (FinalDecisionBaseInput & {
      disposition: 'TEST_FIRST';
      ideaId: string;
      ideaRevision: number;
      testExperimentId: string;
      preMortem: FinalDecisionPreMortemEntryInput[];
      overrideReason?: string;
    })
  | (FinalDecisionBaseInput & { disposition: 'PARK' | 'STOP' });
