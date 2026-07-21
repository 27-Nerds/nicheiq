import { describe, expect, it } from "vitest";
import { buildSelectionJourney } from "../decisionJourney";
import type { SelectionDecisionProfile } from "$lib/types/job";
import type {
  SelectionDecisionIdeaRef,
  SelectionDecisionNextActionKind,
  SelectionDecisionState,
} from "$lib/types/selectionDecisionState";

const IDEA_A: SelectionDecisionIdeaRef = {
  ideaId: "idea-a",
  ideaRevision: 2,
  title: "Signal desk",
};
const IDEA_B: SelectionDecisionIdeaRef = {
  ideaId: "idea-b",
  ideaRevision: 4,
  title: "Evidence map",
};

const PROFILE = {
  preset: "balanced",
  weeklyTime: "10_20",
  budget: "under_1k",
  team: "solo",
  revenueHorizon: "90_days",
  distributionAdvantages: [],
  strengths: "",
  hardConstraints: "",
} as SelectionDecisionProfile;

function state(
  kind: SelectionDecisionNextActionKind,
  ideas: SelectionDecisionIdeaRef[] = [],
): SelectionDecisionState {
  return {
    schemaVersion: 1,
    jobId: "job-1",
    status: "AWAITING_SELECTION",
    shortlist: { version: 3, items: ideas },
    profile: null,
    founderFit: null,
    challenges: [],
    ownerEvidence: [],
    assumptions: [],
    experiments: [],
    conclusions: [],
    staleCounts: {
      shortlist: 0,
      profile: 0,
      founderFit: 0,
      challenges: 0,
      ownerEvidence: 0,
      assumptions: 0,
      experiments: 0,
      conclusions: 0,
      total: 0,
    },
    deepResearch: {
      eligible: ideas.length > 0,
      optionalWorkRequired: false,
      blockers: ideas.length > 0 ? [] : ["NO_CURRENT_SHORTLIST"],
    },
    nextAction: {
      kind,
      target: kind === "select_candidate"
        ? "shortlist"
        : kind === "start_deep_research"
          ? "deep_research"
          : kind === "add_decision_context"
            ? "profile"
            : kind === "analyze_founder_fit"
              ? "founder_fit"
              : kind === "draft_test"
                ? "experiments"
                : "challenges",
      reason: "Server reason",
      required: kind === "select_candidate",
      ideas,
      lens: null,
      records: [],
    },
  };
}

describe("buildSelectionJourney", () => {
  it("guides an empty shortlist toward candidate review without inventing readiness", () => {
    const journey = buildSelectionJourney(state("select_candidate"));

    expect(journey.shortlist.items).toEqual([]);
    expect(journey.recommendation).toMatchObject({
      target: "shortlist",
      title: "Review the strongest candidate",
      actionLabel: "Review candidates",
    });
    expect(journey.tasks.find((task) => task.key === "compare")?.status).toBe("not_ready");
    expect(journey.tasks.find((task) => task.key === "risks")?.status).toBe("not_ready");
    expect(journey.deepResearch.eligible).toBe(false);
  });

  it("preserves exact ids and revisions even when shortlist titles collide", () => {
    const sameTitle = { ...IDEA_B, title: IDEA_A.title };
    const journey = buildSelectionJourney(state("add_decision_context", [IDEA_A, sameTitle]));

    expect(journey.shortlist.items).toEqual([IDEA_A, sameTitle]);
    expect(journey.shortlist.items.map((idea) => `${idea.ideaId}:${idea.ideaRevision}`)).toEqual([
      "idea-a:2",
      "idea-b:4",
    ]);
    expect(journey.recommendation.ideas).toEqual([IDEA_A, sameTitle]);
    expect(journey.tasks.find((task) => task.key === "constraints")?.status).toBe("recommended");
  });

  it("projects current decision artifacts into plain task states", () => {
    const current = state("draft_test", [IDEA_A, IDEA_B]);
    current.profile = PROFILE;
    current.founderFit = {
      inputFingerprint: "fit-fingerprint",
      results: [
        { idea: IDEA_A, verdict: "fits" },
        { idea: IDEA_B, verdict: "needs_reshape" },
      ],
    };
    current.challenges = [{
      id: "challenge-1",
      idea: IDEA_A,
      lens: "demand",
      overall: "weakened",
      gapQuestionIds: ["gap-1"],
    }];
    current.assumptions = [{
      id: "assumption-1",
      idea: IDEA_A,
      lens: "demand",
      statement: "Buyers show urgent workaround behavior.",
      impact: "Drop this candidate if false.",
      ownerState: "open",
      version: 1,
      originChallengeId: "challenge-1",
      originQuestionId: "gap-1",
      experimentIds: [],
    }];

    const journey = buildSelectionJourney(current);
    const statuses = Object.fromEntries(journey.tasks.map((task) => [task.key, task.status]));

    expect(statuses).toMatchObject({
      constraints: "complete",
      compare: "complete",
      risks: "complete",
      tests: "recommended",
      alternatives: "optional",
    });
    expect(journey.recommendation).toMatchObject({
      target: "tests",
      title: "Plan the next useful test",
    });
  });

  it("uses needs-refresh language when persisted artifacts are stale", () => {
    const stale = state("stress_test_evidence", [IDEA_A, IDEA_B]);
    stale.nextAction.variant = "rerun";
    stale.staleCounts.founderFit = 1;
    stale.staleCounts.challenges = 2;

    const journey = buildSelectionJourney(stale);

    expect(journey.tasks.find((task) => task.key === "compare")).toMatchObject({
      status: "needs_refresh",
      statusLabel: "Needs refresh",
    });
    expect(journey.tasks.find((task) => task.key === "risks")).toMatchObject({
      status: "needs_refresh",
      statusLabel: "Needs refresh",
    });
    expect(journey.recommendation.title).toBe("Refresh the evidence review");
  });

  it("shows test work in progress until every experiment has a conclusion", () => {
    const active = state("monitor_test", [IDEA_A]);
    active.experiments = [{
      id: "experiment-1",
      idea: IDEA_A,
      assumptionId: null,
      status: "locked",
      runStatus: "active",
      conclusionId: null,
    }];

    expect(buildSelectionJourney(active).tasks.find((task) => task.key === "tests")?.status)
      .toBe("in_progress");

    active.nextAction = {
      ...active.nextAction,
      kind: "start_deep_research",
      target: "deep_research",
    };
    active.experiments[0].conclusionId = "conclusion-1";
    expect(buildSelectionJourney(active).tasks.find((task) => task.key === "tests")?.status)
      .toBe("complete");
  });

  it("names the unlocking action on locked steps instead of a bare lock label", () => {
    const empty = state("select_candidate");
    const tasks = buildSelectionJourney(empty).tasks;

    const compare = tasks.find((task) => task.key === "compare");
    const risks = tasks.find((task) => task.key === "risks");
    const tests = tasks.find((task) => task.key === "tests");

    expect(compare?.status).toBe("not_ready");
    expect(compare?.statusLabel).toBe("Shortlist two ideas to compare them");
    expect(risks?.statusLabel).toBe("Shortlist an idea to check its evidence");
    expect(tests?.statusLabel).toBe("Shortlist an idea to plan a test");
  });

  it("uses one canonical name per tool across the rail", () => {
    const tasks = buildSelectionJourney(state("select_candidate")).tasks;
    expect(tasks.map((task) => task.title)).toEqual([
      "Your build constraints",
      "Compare finalists",
      "Check the evidence",
      "Plan a test",
      "Explore variants",
    ]);
  });
});
