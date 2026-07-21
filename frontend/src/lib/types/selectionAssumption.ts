import type { SelectionChallengeLens } from "$lib/types/selectionChallenge";

export type SelectionAssumptionImpact = "MEDIUM" | "HIGH" | "DECISIVE";
export type SelectionAssumptionOwnerState = "OPEN" | "ACCEPTED_RISK" | "RETIRED";
export type SelectionAssumptionDirection = "UNKNOWN" | "SUPPORTING" | "MIXED" | "CONTRADICTING";
export type SelectionAssumptionEvidenceClass = "NONE" | "INFERENCE" | "PROXY" | "OBSERVED";

export interface SelectionAssumption {
  id: string;
  jobId: string;
  ideaId: string;
  ideaRevision: number;
  lens: SelectionChallengeLens;
  statement: string;
  impactIfFalse: string;
  falsificationQuestion: string;
  impact: SelectionAssumptionImpact;
  ownerState: SelectionAssumptionOwnerState;
  version: number;
  originChallengeId: string | null;
  originQuestionId: string | null;
  createdByUserId: string;
  createdAt: string;
  updatedAt: string;
  stale: boolean;
  direction: SelectionAssumptionDirection;
  evidenceClass: SelectionAssumptionEvidenceClass;
  experiments: Array<{
    id: string;
    status: "DRAFT" | "LOCKED";
    outcome: "PASS" | "FAIL" | "AMBIGUOUS" | "INVALID" | null;
  }>;
}

export interface SelectionAssumptionCreateInput {
  ideaId: string;
  ideaRevision: number;
  lens: SelectionChallengeLens;
  statement: string;
  impactIfFalse: string;
  falsificationQuestion: string;
  impact: SelectionAssumptionImpact;
  originChallengeId?: string | null;
  originQuestionId?: string | null;
}

export interface SelectionAssumptionPatchInput {
  expectedVersion: number;
  ideaId: string;
  ideaRevision: number;
  statement?: string;
  impactIfFalse?: string;
  falsificationQuestion?: string;
  impact?: SelectionAssumptionImpact;
  ownerState?: SelectionAssumptionOwnerState;
}

export interface SelectionAssumptionListResponse {
  assumptions: SelectionAssumption[];
}

export interface SelectionAssumptionCreateResponse {
  assumption: SelectionAssumption;
  cached: boolean;
}

export interface SelectionAssumptionMutationResponse {
  assumption: SelectionAssumption;
}
