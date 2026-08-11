import { describe, expect, it } from "vitest";
import { getAdjustedStageCounts, getVisibleStageProgress } from "./stages";

describe("visible research-stage projection", () => {
  it("projects production 15- and 16-stage jobs onto the same 14 public steps", () => {
    expect(getAdjustedStageCounts({
      stagesCompleted: 1,
      totalStages: 16,
      currentStage: 2,
      status: "RUNNING",
    })).toEqual({ completed: 1, current: 2, total: 14 });
    expect(getAdjustedStageCounts({
      stagesCompleted: 1,
      totalStages: 15,
      currentStage: 2,
      status: "RUNNING",
    }).total).toBe(14);
  });

  it("folds the parallel audience callback into the combined third step", () => {
    expect(getVisibleStageProgress({
      stagesCompleted: 2,
      totalStages: 16,
      currentStage: 4,
      currentStageName: "Audience Mapping",
      status: "RUNNING",
    })).toMatchObject({
      completed: 2,
      current: 3,
      total: 14,
      currentName: "Pain Point & Audience Analysis",
      currentCallbackIsComplete: false,
    });
    expect(getVisibleStageProgress({
      stagesCompleted: 4,
      totalStages: 16,
      currentStage: 4,
      currentStageName: "Audience Mapping",
      status: "RUNNING",
    })).toMatchObject({
      completed: 3,
      total: 14,
      currentName: null,
      currentCallbackIsComplete: true,
    });
  });

  it("does not trust a stage name without a coherent stage number", () => {
    expect(getVisibleStageProgress({
      stagesCompleted: 3,
      totalStages: 16,
      currentStageName: "Pain Point Analysis",
      status: "RUNNING",
    })).toMatchObject({
      currentName: null,
      completed: 3,
      total: 14,
    });
  });

  it("uses ledger ordinals after the fractional competitive-analysis stage", () => {
    expect(getVisibleStageProgress({
      stagesCompleted: 6,
      totalStages: 16,
      currentStage: 6,
      currentStageName: "Solution Generation",
      status: "RUNNING",
    })).toMatchObject({
      currentName: "Solution Generation",
      currentCallbackIsComplete: false,
    });
    expect(getVisibleStageProgress({
      stagesCompleted: 12,
      totalStages: 16,
      currentStage: 12,
      currentStageName: "Marketing Strategy",
      status: "RUNNING",
    })).toMatchObject({
      currentName: "Marketing Strategy",
      currentCallbackIsComplete: false,
    });
    expect(getVisibleStageProgress({
      stagesCompleted: 7,
      totalStages: 16,
      currentStage: 6,
      currentStageName: "Solution Generation",
      status: "RUNNING",
    })).toMatchObject({
      currentName: null,
      currentCallbackIsComplete: true,
    });
  });

  it("keeps an active stage active when the worker omits its display name", () => {
    expect(getVisibleStageProgress({
      stagesCompleted: 1,
      totalStages: 16,
      currentStage: 2,
      currentStageName: "",
      status: "RUNNING",
    })).toMatchObject({
      completed: 1,
      current: 2,
      currentName: "Research in progress",
      currentCallbackIsComplete: false,
    });
  });
});
