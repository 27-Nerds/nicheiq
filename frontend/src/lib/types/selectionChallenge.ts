export type SelectionChallengeLens = "demand" | "competition" | "distribution" | "dependencies";
export type SelectionChallengePosition = "supports" | "contradicts" | "mixed" | "insufficient";
export type SelectionChallengeEvidenceClass = "observed" | "proxy" | "inference";
export type SelectionChallengeConsensus = "supported" | "contradicted" | "mixed" | "disputed" | "insufficient";
export type SelectionChallengeOverall =
  | "withstands"
  | "weakened"
  | "contradicted"
  | "disputed"
  | "insufficient_evidence";

export interface SelectionChallengeAgentAssessment {
  questionId: string;
  position: SelectionChallengePosition;
  summary: string;
  subjectKeys: string[];
  evidenceKeys: string[];
  evidenceClass: SelectionChallengeEvidenceClass;
  /** Server-stamped when the assessor omitted this question and it was backfilled as insufficient. */
  backfilled?: boolean;
}

export interface SelectionChallengeSource {
  key: string;
  kind: "customer_quote" | "competitor_fact" | "market_caveat" | "audience_fact" | "dependency_note" | "owner_evidence" | "experiment_result";
  title: string;
  excerpt: string;
  url: string | null;
  capturedAt: string | null;
  provenance: {
    assetType: "DISCOVERY_DATA" | "PREVIEW_REPORT";
    jsonPointer: string;
  } | {
    assetType: "OWNER_EVIDENCE";
    evidenceItemId: string;
    position: "SUPPORTS" | "CONTRADICTS" | "CONTEXT";
    ownerKind: "NOTE" | "CUSTOMER_QUOTE" | "ANALYTICS_OBSERVATION" | "LINK";
  } | {
    assetType: "EXPERIMENT_RESULT";
    experimentId: string;
    conclusionId: string;
    originChallengeId: string;
    evidenceClass: "observed" | "proxy";
    sourceType: "FIRST_PARTY" | "MANUAL";
    adapterKey: string;
    precommitment: {
      primaryMetric: string;
      passThreshold: string;
      failThreshold: string;
      measurementWindow: string;
      sampleTarget: number | null;
    };
    observation: {
      observedThrough: string | null;
      observationSummary: string | null;
      observedMetric: string | null;
      metrics: Array<{
        key: string;
        label: string;
        valueType: string;
        value: number;
        numerator?: number;
        denominator?: number;
        isPrimary: boolean;
      }>;
      sample: {
        observed: number | null;
        target: number | null;
        unit: string | null;
      };
      limitations: string[];
    };
  };
}

export interface SelectionChallengeSubject {
  key: string;
  field: string;
  value: unknown;
}

export interface SelectionChallengeQuestion {
  questionId: string;
  consensus: SelectionChallengeConsensus;
  skeptic: SelectionChallengeAgentAssessment;
  auditor: SelectionChallengeAgentAssessment;
}

export interface SelectionChallenge {
  id: string;
  version: 1;
  inputFingerprint: string;
  ideaId: string;
  ideaRevision: number;
  ideaTitle: string;
  lens: SelectionChallengeLens;
  overall: SelectionChallengeOverall;
  ideaSnapshot: Record<string, unknown>;
  subjectSnapshot: SelectionChallengeSubject[];
  evidenceSnapshot: SelectionChallengeSource[];
  questions: SelectionChallengeQuestion[];
  skepticModel: string;
  auditorModel: string;
  promptVersion: 1 | 2;
  createdAt: string;
}

export interface SelectionChallengeStaleReference {
  ideaId: string;
  ideaRevision: number;
  lens: SelectionChallengeLens;
}

export interface SelectionChallengeListResponse {
  challenges: SelectionChallenge[];
  stale: SelectionChallengeStaleReference[];
}

export interface SelectionChallengeRunResponse {
  challenge: SelectionChallenge;
  cached: boolean;
}
