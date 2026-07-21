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

export interface SelectionJourneyTask {
  key: SelectionJourneyTaskKey;
  title: string;
  description: string;
  status: SelectionJourneyTaskStatus;
  statusLabel: string;
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
  };
  tasks: SelectionJourneyTask[];
  recommendation: SelectionJourneyRecommendation;
  deepResearch: SelectionDecisionState["deepResearch"];
}

const STATUS_LABELS: Record<SelectionJourneyTaskStatus, string> = {
  /** Generic fallback. Per-step rows override this with STEP_LOCK_HINTS, which
   *  name the action that unlocks the step instead of only stating the lock. */
  not_ready: "Choose ideas first",
  available: "Ready",
  recommended: "Recommended",
  in_progress: "In progress",
  complete: "Complete",
  needs_refresh: "Needs refresh",
  optional: "Optional",
};

function task(
  key: SelectionJourneyTaskKey,
  title: string,
  description: string,
  status: SelectionJourneyTaskStatus,
  lockHint?: string,
): SelectionJourneyTask {
  return {
    key,
    title,
    description,
    status,
    statusLabel: status === "not_ready" && lockHint ? lockHint : STATUS_LABELS[status],
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
    case "draft_test":
    case "review_test_brief":
    case "launch_test":
    case "monitor_test":
    case "record_conclusion":
      return "tests";
    case "start_deep_research":
      return "deep_research";
  }
}

function recommendationForAction(
  action: SelectionDecisionNextAction,
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
        title: "Add your build constraints",
        description: "Save your time, budget, team, and advantages so fit is judged for your situation.",
        actionLabel: "Add constraints",
        ideas: action.ideas.map((idea) => ({ ...idea })),
      };
    case "analyze_founder_fit":
      return {
        target: "compare",
        title: action.variant === "refresh" ? "Refresh the fit comparison" : "Compare fit for you",
        description: action.variant === "refresh"
          ? "Your shortlist changed. Refresh the comparison before relying on its fit conclusions."
          : "See how each finalist fits your saved time, budget, team, and advantages.",
        actionLabel: action.variant === "refresh" ? "Refresh comparison" : "Compare finalists",
        ideas: action.ideas.map((idea) => ({ ...idea })),
      };
    case "stress_test_evidence":
      return {
        target: "risks",
        title: action.variant === "rerun" ? "Refresh the evidence review" : "Check the biggest uncertainty",
        description: action.variant === "rerun"
          ? "The underlying evidence changed. Refresh the review before using its open questions."
          : "Stress-test the evidence and surface the question most likely to change your choice.",
        actionLabel: action.variant === "rerun" ? "Refresh evidence review" : "Review the evidence",
        ideas: action.ideas.map((idea) => ({ ...idea })),
      };
    case "capture_assumption":
      return {
        target: "risks",
        title: "Track the key assumption",
        description: "Turn the open evidence gap into a specific question you can revisit or test.",
        actionLabel: "Track key assumption",
        ideas: action.ideas.map((idea) => ({ ...idea })),
      };
    case "draft_test":
      return {
        target: "tests",
        title: "Plan the next useful test",
        description: "Draft a small real-world test for the open assumption before results can influence the choice.",
        actionLabel: "Draft test",
        ideas: action.ideas.map((idea) => ({ ...idea })),
      };
    case "review_test_brief":
      return {
        target: "tests",
        title: "Review the test draft",
        description: "Check the signal, outcome rules, cost, and next actions before you launch anything.",
        actionLabel: "Review test draft",
        ideas: action.ideas.map((idea) => ({ ...idea })),
      };
    case "launch_test":
      return {
        target: "tests",
        title: "Launch the prepared test",
        description: "The plan is locked and ready. Review it once more before collecting evidence.",
        actionLabel: "Review and launch",
        ideas: action.ideas.map((idea) => ({ ...idea })),
      };
    case "monitor_test":
      return {
        target: "tests",
        title: "Review the active test",
        description: "Check the evidence collected so far without changing the precommitted outcome rules.",
        actionLabel: "Review active test",
        ideas: action.ideas.map((idea) => ({ ...idea })),
      };
    case "record_conclusion":
      return {
        target: "tests",
        title: "Record the test outcome",
        description: "The test window is complete. Record what happened and what it changes about the choice.",
        actionLabel: "Record outcome",
        ideas: action.ideas.map((idea) => ({ ...idea })),
      };
    case "start_deep_research":
      return {
        target: "deep_research",
        title: "Ready for Deep Research",
        description: "Your shortlist is saved. Optional decision work remains available if you want it.",
        actionLabel: "Start Deep Research",
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
      ? { ...item, status: "recommended", statusLabel: STATUS_LABELS.recommended }
      : item,
  );
}

/**
 * Projects the persisted selection decision state into a novice-facing task
 * journey. It never infers identity from titles: every idea reference is copied
 * with its backend-authored id and revision intact.
 */
export function buildSelectionJourney(state: SelectionDecisionState): SelectionJourney {
  const shortlistCount = state.shortlist.items.length;
  const hasShortlist = shortlistCount > 0;
  const canCompare = shortlistCount >= 2;
  const recommendation = recommendationForAction(state.nextAction);

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
    : state.staleCounts.challenges > 0
      ? "needs_refresh"
      : state.challenges.length > 0
        ? "complete"
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

  const tasks = withRecommendation([
    task(
      "constraints",
      "Your build constraints",
      state.profile
        ? "Time, budget, team, and advantages are saved."
        : "Add your situation so fit can be judged for you.",
      constraintsStatus,
    ),
    task(
      "compare",
      TOOL_NAMES.compare,
      canCompare
        ? "See the market differences and how each idea fits your constraints."
        : "Shortlist at least two ideas to compare them side by side.",
      compareStatus,
      STEP_LOCK_HINTS.compare,
    ),
    task(
      "risks",
      TOOL_NAMES.challenge,
      "Review the evidence, open questions, and assumptions that could change your choice.",
      risksStatus,
      STEP_LOCK_HINTS.challenge,
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
      TOOL_NAMES.shape,
      "Create variants from selected ideas or generate a small additional batch.",
      // Always available: besides branching from shortlisted parents, this can
      // generate a fresh batch, which needs no shortlist. So it never locks, and
      // with no authoritative variant artifact it never reads complete/refresh.
      "optional",
      STEP_LOCK_HINTS.shape,
    ),
  ], recommendation);

  return {
    shortlist: {
      version: state.shortlist.version,
      maxItems: 3,
      items: state.shortlist.items.map((idea) => ({ ...idea })),
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
