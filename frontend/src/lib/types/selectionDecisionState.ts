import type { SelectionDecisionProfile } from "$lib/types/job";
import type { SelectionChallengeLens } from "$lib/types/selectionChallenge";

export interface SelectionDecisionIdeaRef {
  ideaId: string;
  ideaRevision: number;
  title: string;
}

export type SelectionDecisionRecordKind =
  | "challenge"
  | "owner_evidence"
  | "assumption"
  | "experiment"
  | "conclusion";

export interface SelectionDecisionRecordRef {
  kind: SelectionDecisionRecordKind;
  id: string;
  version?: number;
}

export type SelectionDecisionNextActionKind =
  | "select_candidate"
  | "add_decision_context"
  | "analyze_founder_fit"
  | "stress_test_evidence"
  | "capture_assumption"
  | "draft_test"
  | "review_test_brief"
  | "launch_test"
  | "monitor_test"
  | "record_conclusion"
  | "start_deep_research";

export interface SelectionDecisionNextAction {
  kind: SelectionDecisionNextActionKind;
  target:
    | "shortlist"
    | "profile"
    | "founder_fit"
    | "challenges"
    | "assumptions"
    | "experiments"
    | "deep_research";
  reason: string;
  required: boolean;
  /**
   * Distinguishes a suggested re-do of an already-completed step from a
   * first-time step: 'rerun' = a completed challenge went stale after the
   * underlying evidence changed; 'refresh' = founder fit was computed but the
   * shortlist changed underneath it. Absent for first-time steps.
   */
  variant?: "rerun" | "refresh";
  ideas: SelectionDecisionIdeaRef[];
  lens: SelectionChallengeLens | null;
  records: SelectionDecisionRecordRef[];
}

export interface SelectionDecisionState {
  schemaVersion: 1;
  jobId: string;
  status: string;
  shortlist: { version: number; items: SelectionDecisionIdeaRef[] };
  profile: SelectionDecisionProfile | null;
  founderFit: {
    inputFingerprint: string;
    results: Array<{
      idea: SelectionDecisionIdeaRef;
      verdict: "fits" | "needs_reshape" | "blocked" | "insufficient_evidence";
    }>;
  } | null;
  challenges: Array<{
    id: string;
    idea: SelectionDecisionIdeaRef;
    lens: SelectionChallengeLens;
    overall: "withstands" | "weakened" | "contradicted" | "disputed" | "insufficient_evidence";
    gapQuestionIds: string[];
  }>;
  ownerEvidence: Array<{
    id: string;
    idea: SelectionDecisionIdeaRef;
    lens: SelectionChallengeLens;
    kind: string;
    position: string;
    title: string;
  }>;
  assumptions: Array<{
    id: string;
    idea: SelectionDecisionIdeaRef;
    lens: SelectionChallengeLens;
    statement: string;
    impact: string;
    ownerState: string;
    version: number;
    originChallengeId: string | null;
    originQuestionId: string | null;
    experimentIds: string[];
  }>;
  experiments: Array<{
    id: string;
    idea: SelectionDecisionIdeaRef;
    assumptionId: string | null;
    status: string;
    runStatus: string | null;
    conclusionId: string | null;
  }>;
  conclusions: Array<{
    id: string;
    experimentId: string;
    idea: SelectionDecisionIdeaRef;
    outcome: string;
  }>;
  staleCounts: {
    shortlist: number;
    profile: number;
    founderFit: number;
    challenges: number;
    ownerEvidence: number;
    assumptions: number;
    experiments: number;
    conclusions: number;
    total: number;
  };
  deepResearch: {
    eligible: boolean;
    optionalWorkRequired: false;
    blockers: Array<"JOB_NOT_AWAITING_SELECTION" | "NO_CURRENT_SHORTLIST">;
  };
  nextAction: SelectionDecisionNextAction;
}
