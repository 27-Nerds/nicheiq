import type { SelectionChallengeLens } from './selectionChallenge';

export type SelectionOwnerEvidenceKind =
  | 'NOTE'
  | 'CUSTOMER_QUOTE'
  | 'ANALYTICS_OBSERVATION'
  | 'LINK';

export type SelectionOwnerEvidencePosition = 'SUPPORTS' | 'CONTRADICTS' | 'CONTEXT';

export interface SelectionOwnerEvidence {
  id: string;
  jobId: string;
  ideaId: string;
  ideaRevision: number;
  lens: SelectionChallengeLens;
  kind: SelectionOwnerEvidenceKind;
  position: SelectionOwnerEvidencePosition;
  title: string;
  content: string;
  sourceUrl: string | null;
  observedAt: string | null;
  createdAt: string;
  retractedAt: string | null;
  retractionReason: string | null;
}

export interface SelectionOwnerEvidenceInput {
  ideaId: string;
  ideaRevision: number;
  lens: SelectionChallengeLens;
  kind: SelectionOwnerEvidenceKind;
  position: SelectionOwnerEvidencePosition;
  title: string;
  content: string;
  sourceUrl: string | null;
  observedAt: string | null;
}

export interface SelectionOwnerEvidenceListResponse {
  evidence: SelectionOwnerEvidence[];
  editable: boolean;
}

export interface SelectionOwnerEvidenceMutationResponse {
  evidence: SelectionOwnerEvidence;
  cached: boolean;
}
