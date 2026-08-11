// Shared public-stage projection. Stage 4 (Audience Mapping) runs in parallel
// with stage 3, and the optional landing-page build is outside research progress.
// Shared by every surface that shows progress — the
// dashboard's in-progress rows, the job page aside, ResearchProgressScreen and
// SegmentedLedger — so they always show the same "N / M" for the same job.

// Mirrors backend TOTAL_STAGES (backend/src/types/job.ts). Fallback only —
// the backend always sends totalStages on real jobs.
export const TOTAL_STAGES = 16;
export const VISIBLE_TOTAL_STAGES = 14;
const PARALLEL_AUDIENCE_STAGE = 4;

export interface StageCountInput {
  stagesCompleted: number;
  totalStages?: number | null;
  currentStage?: number | null;
  status?: string | null;
}

export interface VisibleStageInput extends StageCountInput {
  currentStageName?: string | null;
}

export function getAdjustedStageCounts(input: StageCountInput): {
  completed: number;
  current: number;
  total: number;
} {
  const internalTotal = input.totalStages && input.totalStages > 0
    ? input.totalStages
    : TOTAL_STAGES;
  // Real research jobs carry 15 stages without the optional landing-page build,
  // or 16 with it. Audience Mapping is parallel with Pain Point Analysis and the
  // landing-page build is not part of research progress, so both shapes project
  // to the same 14-step public contract.
  const total = internalTotal >= 15
    ? VISIBLE_TOTAL_STAGES
    : Math.max(0, internalTotal - (internalTotal >= PARALLEL_AUDIENCE_STAGE ? 1 : 0));
  const stage = typeof input.currentStage === "number" && Number.isFinite(input.currentStage)
    ? input.currentStage
    : null;
  const active = ["RUNNING", "RUNNING_PHASE2"].includes(
    (input.status ?? "").toUpperCase(),
  );
  let completed = Number.isFinite(input.stagesCompleted)
    ? Math.max(0, input.stagesCompleted)
    : 0;
  if (completed >= PARALLEL_AUDIENCE_STAGE) completed -= 1;
  // Stage 3 is not publicly complete until its parallel audience work is also
  // complete. A stage-3 completion callback may arrive while stage 4 is active.
  if (
    active
    && stage !== null
    && stage >= 3
    && stage <= PARALLEL_AUDIENCE_STAGE
    && input.stagesCompleted === 3
  ) {
    completed = 2;
  }
  const adjustedCompleted = Math.min(total, completed);
  // stagesCompleted is a count of finished ledger rows. While a worker is active,
  // the user is therefore on the next visible stage, not the last finished one.
  const current = active
    ? Math.min(total, adjustedCompleted + 1)
    : adjustedCompleted;
  return { completed: adjustedCompleted, current, total };
}

export function getVisibleStageProgress(input: VisibleStageInput): {
  completed: number;
  current: number;
  total: number;
  currentName: string | null;
  currentCallbackIsComplete: boolean;
} {
  const counts = getAdjustedStageCounts(input);
  const active = ["RUNNING", "RUNNING_PHASE2"].includes(
    (input.status ?? "").toUpperCase(),
  );
  const stage = typeof input.currentStage === "number"
    && Number.isFinite(input.currentStage)
    && input.currentStage > 0
    ? input.currentStage
    : null;
  // `stagesCompleted` counts ledger rows, while stage identifiers include the
  // fractional Competitive Analysis stage at 5.5. From stage 6 onward the row
  // ordinal is therefore one greater than the numeric stage identifier.
  const stageOrdinal = stage === null
    ? null
    : stage > 5 ? Math.floor(stage) + 1 : stage;
  const currentCallbackIsComplete = Boolean(
    active && stageOrdinal !== null && input.stagesCompleted >= stageOrdinal,
  );
  const coherentActive = active && stage !== null && !currentCallbackIsComplete;
  const rawName = input.currentStageName?.trim() || null;
  const currentName = coherentActive
    ? stage === PARALLEL_AUDIENCE_STAGE
      ? "Pain Point & Audience Analysis"
      : rawName ?? "Research in progress"
    : null;
  return { ...counts, currentName, currentCallbackIsComplete };
}
