// Shared stage-count display adjustment. Stage 4 (Audience Mapping) runs in
// parallel with stage 3 and is hidden from users, so displayed counts subtract
// it once it has been passed. Shared by every surface that shows progress — the
// dashboard's in-progress rows, the job page aside, ResearchProgressScreen and
// SegmentedLedger — so they always show the same "N / M" for the same job.

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
  current: number;
  total: number;
} {
  const hiddenCount = HIDDEN_STAGES.length;
  const total = (input.totalStages || TOTAL_STAGES) - hiddenCount;
  const passedHidden =
    (input.currentStage ?? 0) > 4 ||
    (input.status ?? "").toUpperCase() === "COMPLETED";
  const completed = input.stagesCompleted - (passedHidden ? hiddenCount : 0);
  const adjustedCompleted = Math.max(0, completed);
  // stagesCompleted is a count of finished ledger rows. While a worker is active,
  // the user is therefore on the next visible stage, not the last finished one.
  const active = ["RUNNING", "RUNNING_PHASE2"].includes(
    (input.status ?? "").toUpperCase(),
  );
  const current = active
    ? Math.min(total, adjustedCompleted + 1)
    : adjustedCompleted;
  return { completed: adjustedCompleted, current, total };
}
