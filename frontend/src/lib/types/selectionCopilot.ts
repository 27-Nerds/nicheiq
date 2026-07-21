import type { SelectionChallengeLens } from "$lib/types/selectionChallenge";
import type {
  SelectionOwnerEvidenceKind,
  SelectionOwnerEvidencePosition,
} from "$lib/types/selectionOwnerEvidence";

export interface SelectionCopilotOrigin {
  challengeId: string;
  questionId: string;
}

export type SelectionCopilotGroundingField =
  | "statement"
  | "impactIfFalse"
  | "falsificationQuestion";

export interface SelectionCopilotGroundingSource {
  ref: string;
  kind: "candidate" | "assumption" | "owner_evidence" | "challenge_question";
  label: string;
  recordId?: string;
  challengeId?: string;
  questionId?: string;
}

export type SelectionCopilotGrounding = Partial<
  Record<SelectionCopilotGroundingField, SelectionCopilotGroundingSource[]>
>;

export interface SelectionAssumptionPrefill {
  requestId: string;
  ideaId: string;
  ideaRevision: number;
  lens: SelectionChallengeLens;
  record?: { id: string; version?: number };
  origin?: SelectionCopilotOrigin;
  grounding: SelectionCopilotGrounding;
  rationale: string;
  caveats: string[];
  values: Partial<{
    statement: string;
    impactIfFalse: string;
    falsificationQuestion: string;
  }>;
}

export interface SelectionOwnerEvidencePrefill {
  requestId: string;
  ideaId: string;
  ideaRevision: number;
  lens: SelectionChallengeLens;
  origin?: SelectionCopilotOrigin;
  values: Partial<{
    kind: SelectionOwnerEvidenceKind;
    position: SelectionOwnerEvidencePosition;
    title: string;
    content: string;
    sourceUrl: string | null;
    observedAt: string | null;
  }>;
}

export interface SelectionConceptForgePrefill {
  requestId: string;
  purpose: "diverge" | "resolve_tradeoff" | "reshape";
  targetTradeoff: string;
  rationale: string;
  caveats: string[];
}
