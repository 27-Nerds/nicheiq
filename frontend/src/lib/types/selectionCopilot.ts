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
  /** Who prepared this prefill. Every entry path passes a prefill, so the
   *  forge must distinguish an analyst-prepared brief (skip the saved-set
   *  restore, show the brief aside) from a plain owner open (restore saved
   *  sets, no aside). When absent, a prefill with an empty rationale and no
   *  caveats is treated as an owner open. */
  source?: "analyst" | "owner";
}
