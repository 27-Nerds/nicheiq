export interface ShortlistProposalHandoff {
  requestId: string;
  expectedVersion: number;
  refs: Array<{ ideaId: string; ideaRevision: number }>;
  returnHref?: string;
  reason: "compare_scope" | "branch_result" | "analyst_proposal";
}
