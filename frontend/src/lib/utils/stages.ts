// Shared stage-count display adjustment. Stage 4 (Audience Mapping) runs in
// parallel with stage 3 and is hidden from users, so displayed counts subtract
// it once it has been passed. Used by JobCard and ResearchProgressScreen so the
// dashboard card and the job page always show the same "N / M".

// Mirrors backend TOTAL_STAGES (backend/src/types/job.ts). Fallback only —
// the backend always sends totalStages on real jobs.
export const TOTAL_STAGES = 16;

const HIDDEN_STAGES = [4];

export interface StageCountInput {
  stagesCompleted: number;
  totalStages?: number | null;
  currentStage?: number | null;
  status?: string | null;
}

export function getAdjustedStageCounts(input: StageCountInput): {
  completed: number;
  total: number;
} {
  const hiddenCount = HIDDEN_STAGES.length;
  const total = (input.totalStages || TOTAL_STAGES) - hiddenCount;
  const passedHidden =
    (input.currentStage ?? 0) > 4 ||
    (input.status ?? "").toUpperCase() === "COMPLETED";
  const completed = input.stagesCompleted - (passedHidden ? hiddenCount : 0);
  return { completed: Math.max(0, completed), total };
}
