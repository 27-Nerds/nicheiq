import type {
  SelectionDecisionIdeaRef,
  SelectionDecisionNextAction,
  SelectionDecisionState,
} from "$lib/types/selectionDecisionState";
import { STEP_LOCK_HINTS, TOOL_NAMES } from "$lib/selection/labels";

export type SelectionJourneyTaskKey =
  | "constraints"
  | "compare"
  | "risks"
  | "tests"
  | "alternatives";

export type SelectionJourneyTarget =
  | "shortlist"
  | SelectionJourneyTaskKey
  | "deep_research";

export type SelectionJourneyTaskStatus =
  | "not_ready"
  | "available"
  | "recommended"
  | "in_progress"
  | "complete"
  | "needs_refresh"
  | "optional";

/**
 * Semantic class for a task's status, so consumers can style it without
 * re-deriving intent from the status string. Crucially, `needs_refresh` maps to
 * "warning" — NOT the "success" class `complete` uses — so a stale step never
 * reads as done.
 */
export type SelectionJourneyStatusKind =
  | "locked"
  | "neutral"
  | "recommended"
  | "active"
  | "success"
  | "warning";

export interface SelectionJourneyTask {
  key: SelectionJourneyTaskKey;
  title: string;
  description: string;
  status: SelectionJourneyTaskStatus;
  statusLabel: string;
  statusKind: SelectionJourneyStatusKind;
}

export interface SelectionJourneyRecommendation {
  target: SelectionJourneyTarget;
  title: string;
  description: string;
  actionLabel: string;
  ideas: SelectionDecisionIdeaRef[];
}

export interface SelectionJourney {
  shortlist: {
    version: number;
    maxItems: 3;
    items: SelectionDecisionIdeaRef[];
    staleItems: SelectionDecisionIdeaRef[];
  };
  tasks: SelectionJourneyTask[];
  recommendation: SelectionJourneyRecommendation;
  deepResearch: SelectionDecisionState["deepResearch"];
}

const STATUS_LABELS: Record<SelectionJourneyTaskStatus, string> = {
  /** Generic fallback. Per-step rows override this with STEP_LOCK_HINTS, which
   *  name the action that unlocks the step instead of only stating the lock. */
  not_ready: "Choose ideas first",
  available: "Not reviewed",
  recommended: "Recommended",
  in_progress: "In progress",
  complete: "Reviewed",
  // Distinct from `complete`: a stale step is a to-do, not a done step.
  needs_refresh: "Re-check needed",
  optional: "Optional",
};

/** Semantic class per status. `needs_refresh` is "warning", never "success",
 *  so consumers cannot render a stale step with the completed treatment. */
const STATUS_KINDS: Record<SelectionJourneyTaskStatus, SelectionJourneyStatusKind> = {
  not_ready: "locked",
  available: "neutral",
  recommended: "recommended",
  in_progress: "active",
  complete: "success",
  needs_refresh: "warning",
  optional: "neutral",
};

function task(
  key: SelectionJourneyTaskKey,
  title: string,
  description: string,
  status: SelectionJourneyTaskStatus,
  lockHint?: string,
  statusLabel?: string,
): SelectionJourneyTask {
  return {
    key,
    title,
    description,
    status,
    statusLabel: statusLabel ?? (status === "not_ready" && lockHint ? lockHint : STATUS_LABELS[status]),
    statusKind: STATUS_KINDS[status],
  };
}

function targetForAction(action: SelectionDecisionNextAction): SelectionJourneyTarget {
  switch (action.kind) {
    case "select_candidate":
      return "shortlist";
    case "add_decision_context":
      return "constraints";
    case "analyze_founder_fit":
      return "compare";
    case "stress_test_evidence":
    case "capture_assumption":
      return "risks";
    // Test work is never a standalone top-level target: `tests` redirects to
    // `risks`, and the test planner opens contextually from the evidence page.
    // Surfacing "tests" as its own next-step would point the recommendation at a
    // destination the sidebar does not render, so it collapses onto "risks".
    case "draft_test":
    case "review_test_brief":
    case "launch_test":
    case "monitor_test":
    case "record_conclusion":
      return "risks";
    case "start_deep_research":
      return "deep_research";
  }
}

function recommendationForAction(
  action: SelectionDecisionNextAction,
  decisionTools = false,
): SelectionJourneyRecommendation {
  const firstIdea = action.ideas[0]?.title?.trim();

  switch (action.kind) {
    case "select_candidate":
      return {
        target: "shortlist",
        title: "Review the strongest candidate",
        description: "Open the idea, check the evidence, and add it to your shortlist if it holds up.",
        actionLabel: firstIdea ? `Review ${firstIdea}` : "Review candidates",
        ideas: action.ideas.map((idea) => ({ ...idea })),
      };
    case "add_decision_context":
      return {
        target: "constraints",
        title: "Add your build limits",
        description: "Save your time, budget, team, and advantages so fit is judged for your situation.",
        actionLabel: "Add build limits",
        ideas: action.ideas.map((idea) => ({ ...idea })),
      };
    case "analyze_founder_fit":
      return {
        target: "compare",
        title: action.variant === "refresh" ? "Update the comparison" : "Compare your ideas",
        description: action.variant === "refresh"
          ? "The shortlist or your goals changed since this comparison. Update it before relying on the result."
          : "See the important market trade-offs and how each idea fits your time, budget, and launch goal.",
        actionLabel: action.variant === "refresh" ? "Update comparison" : "Compare trade-offs",
        ideas: action.ideas.map((idea) => ({ ...idea })),
      };
    case "stress_test_evidence":
      return {
        target: "risks",
        title: action.variant === "rerun" ? "Update an evidence check" : "Check the evidence",
        description: action.variant === "rerun"
          ? "The idea or its saved evidence changed since this review. Update it before relying on the result."
          : "Review one question that could change what you research. This rechecks saved sources and does not search for new evidence.",
        actionLabel: action.variant === "rerun" ? "Update evidence check" : "Check the evidence",
        ideas: action.ideas.map((idea) => ({ ...idea })),
      };
    case "capture_assumption":
      return {
        target: "risks",
        title: "Save a question to resolve",
        description: "Turn an unanswered question into something you can revisit or test.",
        actionLabel: "Save a question to resolve",
        ideas: action.ideas.map((idea) => ({ ...idea })),
      };
    case "draft_test":
      return {
        target: "risks",
        title: "Plan the next useful test",
        description: "Draft a small real-world test for the open assumption before results can influence the choice.",
        actionLabel: "Draft test",
        ideas: action.ideas.map((idea) => ({ ...idea })),
      };
    case "review_test_brief":
      return {
        target: "risks",
        title: "Review the test draft",
        description: "Check the signal, outcome rules, cost, and next actions before you launch anything.",
        actionLabel: "Review test draft",
        ideas: action.ideas.map((idea) => ({ ...idea })),
      };
    case "launch_test":
      return {
        target: "risks",
        title: "Launch the prepared test",
        description: "The plan is locked and ready. Review it once more before collecting evidence.",
        actionLabel: "Review and launch",
        ideas: action.ideas.map((idea) => ({ ...idea })),
      };
    case "monitor_test":
      return {
        target: "risks",
        title: "Review the active test",
        description: "Check the evidence collected so far without changing the precommitted outcome rules.",
        actionLabel: "Review active test",
        ideas: action.ideas.map((idea) => ({ ...idea })),
      };
    case "record_conclusion":
      return {
        target: "risks",
        title: "Record the test outcome",
        description: "The test window is complete. Record what happened and what it changes about the choice.",
        actionLabel: "Record outcome",
        ideas: action.ideas.map((idea) => ({ ...idea })),
      };
    case "start_deep_research":
      return {
        target: "deep_research",
        title: "Review and start",
        description: `Deep Research will cover ${action.ideas.length} selected ${action.ideas.length === 1 ? "idea" : "ideas"}.${decisionTools ? " Comparing and checking risks are optional." : " Comparing is optional."}`,
        actionLabel: "Review and start",
        ideas: action.ideas.map((idea) => ({ ...idea })),
      };
  }
}

function withRecommendation(
  tasks: SelectionJourneyTask[],
  recommendation: SelectionJourneyRecommendation,
): SelectionJourneyTask[] {
  return tasks.map((item) =>
    item.key === recommendation.target && (item.status === "available" || item.status === "optional")
      ? { ...item, status: "recommended", statusLabel: STATUS_LABELS.recommended, statusKind: STATUS_KINDS.recommended }
      : item,
  );
}

/**
 * Projects the persisted selection decision state into a novice-facing task
 * journey. It never infers identity from titles: every idea reference is copied
 * with its backend-authored id and revision intact.
 */
export function buildSelectionJourney(
  state: SelectionDecisionState,
  /**
   * Whether the owner has the optional decision tools grant. When false only the
   * always-available "Compare trade-offs" task is emitted, which empties the optional
   * checks list on the hub AND the tool rows in PhaseNav — both read `tasks`.
   * `shortlist` and `deepResearch` are unaffected, so the shortlist rail keeps working.
   * Defaults to FALSE: a caller that forgets to pass it gets the required path, not a
   * silently ungated journey.
   */
  decisionTools = false,
): SelectionJourney {
  const shortlistCount = state.shortlist.items.length;
  const hasShortlist = shortlistCount > 0;
  const canCompare = shortlistCount >= 2;
  const rawRecommendation = recommendationForAction(state.nextAction, decisionTools);
  // Defence in depth: the server already collapses the ladder without the grant, but a
  // cached or in-flight state could still carry a gated next action. Never surface a
  // recommendation pointing at a tool this owner cannot open.
  const recommendation: SelectionJourneyRecommendation =
    decisionTools
    || rawRecommendation.target === "shortlist"
    || rawRecommendation.target === "deep_research"
      ? rawRecommendation
      : recommendationForAction(
        {
          kind: "start_deep_research",
          target: "deep_research",
          reason: "",
          required: false,
          ideas: state.shortlist.items.map((idea) => ({ ...idea })),
          lens: null,
          records: [],
        } as SelectionDecisionNextAction,
        false,
      );
  const currentShortlistRefs = new Set(
    state.shortlist.items.map((idea) => `${idea.ideaId}:${idea.ideaRevision}`),
  );
  const currentChallenges = state.challenges.filter((challenge) =>
    currentShortlistRefs.has(`${challenge.idea.ideaId}:${challenge.idea.ideaRevision}`),
  );

  const constraintsStatus: SelectionJourneyTaskStatus = state.staleCounts.profile > 0
    ? "needs_refresh"
    : state.profile
      ? "complete"
      : hasShortlist
        ? "available"
        : "optional";

  const compareStatus: SelectionJourneyTaskStatus = !canCompare
    ? "not_ready"
    : state.staleCounts.founderFit > 0
      ? "needs_refresh"
      : state.founderFit
        ? "complete"
        : "available";

  const risksStatus: SelectionJourneyTaskStatus = !hasShortlist
    ? "not_ready"
    : currentChallenges.length > 0
      ? state.staleCounts.challenges > 0
        ? "needs_refresh"
        : "complete"
      : "available";

  const allTestsConcluded = state.experiments.length > 0
    && state.experiments.every((experiment) => experiment.conclusionId !== null);
  const testsStatus: SelectionJourneyTaskStatus = !hasShortlist
    ? "not_ready"
    : state.staleCounts.experiments > 0 || state.staleCounts.conclusions > 0
      ? "needs_refresh"
      : allTestsConcluded
        ? "complete"
        : state.experiments.length > 0
          ? "in_progress"
          : state.assumptions.length > 0
            ? "available"
            : "optional";

  const compareOnlyTask = task(
    "compare",
    TOOL_NAMES.compare,
    canCompare
      ? "See how the shortlisted ideas differ on the research evidence."
      : "Shortlist at least two ideas to compare them side by side.",
    compareStatus,
    STEP_LOCK_HINTS.compare,
    compareStatus === "complete" ? "Reviewed" : undefined,
  );

  const tasks = !decisionTools ? [compareOnlyTask] : withRecommendation([
    task(
      "constraints",
      "Your build limits",
      state.profile
        ? "Time, budget, team, and advantages are saved."
        : "Add your situation so fit can be judged for you.",
      constraintsStatus,
      undefined,
      constraintsStatus === "complete" ? "Saved" : constraintsStatus === "available" ? "Not added" : undefined,
    ),
    task(
      "compare",
      TOOL_NAMES.compare,
      canCompare
        ? "See the market differences and how each idea fits your constraints."
        : "Shortlist at least two ideas to compare them side by side.",
      compareStatus,
      STEP_LOCK_HINTS.compare,
      compareStatus === "complete" ? "Reviewed" : undefined,
    ),
    task(
      "risks",
      TOOL_NAMES.challenge,
      "Review a question that could change which ideas you research. Optional.",
      risksStatus,
      STEP_LOCK_HINTS.challenge,
      risksStatus === "complete"
        ? `${currentChallenges.length} ${currentChallenges.length === 1 ? "risk" : "risks"} reviewed`
        : risksStatus === "available"
          ? "Optional"
          : undefined,
    ),
    task(
      "tests",
      TOOL_NAMES.test,
      state.assumptions.length > 0
        ? "Turn an open assumption into a small test with outcome rules."
        : "Tests are strongest when they start from a tracked assumption.",
      testsStatus,
      STEP_LOCK_HINTS.test,
    ),
    task(
      "alternatives",
      TOOL_NAMES.branch,
      "Branch a new direction from selected ideas, or generate a fresh batch of ideas.",
      // Always available: besides branching from shortlisted parents, this can
      // generate a fresh batch, which needs no shortlist. So it never locks, and
      // with no authoritative branch artifact it never reads complete/refresh.
      "optional",
      STEP_LOCK_HINTS.branch,
    ),
  ], recommendation);

  return {
    shortlist: {
      version: state.shortlist.version,
      maxItems: 3,
      items: state.shortlist.items.map((idea) => ({ ...idea })),
      staleItems: (state.shortlist.staleItems ?? []).map((idea) => ({
        ideaId: idea.ideaId,
        ideaRevision: idea.ideaRevision,
        title: idea.titleSnapshot ?? "Unavailable candidate",
      })),
    },
    tasks,
    recommendation,
    deepResearch: {
      eligible: state.deepResearch.eligible,
      optionalWorkRequired: false,
      blockers: [...state.deepResearch.blockers],
    },
  };
}
