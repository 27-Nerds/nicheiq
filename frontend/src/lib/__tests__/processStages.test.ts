import { describe, it, expect } from 'vitest';

/**
 * These tests verify the stage processing logic from +page.svelte.
 * The functions are replicated here as pure functions since they
 * are defined inline in the Svelte component.
 */

interface StageProgress {
  stageNumber: number;
  stageName: string;
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'SKIPPED' | 'FAILED';
  durationSeconds: number | null;
}

const PARALLEL_STAGE_GROUPS: Record<number, { hide: number[]; combinedName: string }> = {
  3: { hide: [4], combinedName: 'Pain Point & Audience Analysis' },
};

function processStagesForDisplay(stages: StageProgress[], jobStatus: string): StageProgress[] {
  const hiddenStages = new Set<number>();

  for (const group of Object.values(PARALLEL_STAGE_GROUPS)) {
    group.hide.forEach(s => hiddenStages.add(s));
  }

  return stages
    .filter(stage => !hiddenStages.has(stage.stageNumber))
    .map(stage => {
      const group = PARALLEL_STAGE_GROUPS[stage.stageNumber];
      let processed = group ? { ...stage, stageName: group.combinedName } : stage;
      if ((jobStatus === 'FAILED' || jobStatus === 'CANCELLED') && processed.status === 'RUNNING') {
        processed = { ...processed, status: 'FAILED' };
      }
      return processed;
    });
}

// Helper to create a stage
function makeStage(
  stageNumber: number,
  status: StageProgress['status'],
  stageName = `Stage ${stageNumber}`
): StageProgress {
  return { stageNumber, stageName, status, durationSeconds: null };
}

// ============================================
// Test D: processStagesForDisplay safety net
// ============================================
describe('processStagesForDisplay', () => {
  it('maps RUNNING → FAILED when job is FAILED', () => {
    const stages = [
      makeStage(1, 'COMPLETED'),
      makeStage(2, 'COMPLETED'),
      makeStage(3, 'RUNNING'),
      makeStage(4, 'PENDING'),
    ];

    const result = processStagesForDisplay(stages, 'FAILED');

    expect(result[2].status).toBe('FAILED');
  });

  it('maps RUNNING → FAILED when job is CANCELLED', () => {
    const stages = [
      makeStage(1, 'COMPLETED'),
      makeStage(2, 'RUNNING'),
    ];

    const result = processStagesForDisplay(stages, 'CANCELLED');

    expect(result[1].status).toBe('FAILED');
  });

  it('does NOT map RUNNING → FAILED when job is RUNNING', () => {
    const stages = [
      makeStage(1, 'COMPLETED'),
      makeStage(2, 'RUNNING'),
    ];

    const result = processStagesForDisplay(stages, 'RUNNING');

    expect(result[1].status).toBe('RUNNING');
  });

  it('preserves COMPLETED and PENDING stages when job is FAILED', () => {
    const stages = [
      makeStage(1, 'COMPLETED'),
      makeStage(2, 'RUNNING'),
      makeStage(3, 'PENDING'),
    ];

    const result = processStagesForDisplay(stages, 'FAILED');

    expect(result[0].status).toBe('COMPLETED');
    expect(result[1].status).toBe('FAILED'); // was RUNNING
    expect(result[2].status).toBe('PENDING');
  });

  it('hides parallel stage 4 and renames stage 3', () => {
    const stages = [
      makeStage(2, 'COMPLETED'),
      makeStage(3, 'RUNNING', 'Pain Point Analysis'),
      makeStage(4, 'RUNNING', 'Audience Analysis'),
      makeStage(5, 'PENDING'),
    ];

    const result = processStagesForDisplay(stages, 'RUNNING');

    // Stage 4 should be hidden
    expect(result.find(s => s.stageNumber === 4)).toBeUndefined();
    // Stage 3 should be renamed
    expect(result.find(s => s.stageNumber === 3)?.stageName).toBe('Pain Point & Audience Analysis');
  });

  it('maps multiple RUNNING stages to FAILED on job failure', () => {
    const stages = [
      makeStage(2, 'COMPLETED'),
      makeStage(3, 'RUNNING'),
      // 4 is hidden, but if present it should also be mapped
      makeStage(5, 'RUNNING'),
    ];

    const result = processStagesForDisplay(stages, 'FAILED');

    expect(result.find(s => s.stageNumber === 3)?.status).toBe('FAILED');
    expect(result.find(s => s.stageNumber === 5)?.status).toBe('FAILED');
  });
});

// ============================================
// Test E: resumeJob stage mapping
// ============================================
describe('resumeJob stage mapping', () => {
  // Replicate the mapping logic from resumeJob in +page.svelte
  function mapStagesForResume(stages: StageProgress[]): StageProgress[] {
    return stages.map(stage =>
      (stage.status === 'FAILED' || stage.status === 'RUNNING')
        ? { ...stage, status: 'PENDING' as const }
        : stage
    );
  }

  it('FAILED stages become PENDING', () => {
    const stages = [
      makeStage(1, 'COMPLETED'),
      makeStage(2, 'FAILED'),
    ];

    const result = mapStagesForResume(stages);

    expect(result[1].status).toBe('PENDING');
  });

  it('RUNNING stages become PENDING', () => {
    const stages = [
      makeStage(1, 'COMPLETED'),
      makeStage(2, 'RUNNING'),
    ];

    const result = mapStagesForResume(stages);

    expect(result[1].status).toBe('PENDING');
  });

  it('COMPLETED stages stay COMPLETED', () => {
    const stages = [
      makeStage(1, 'COMPLETED'),
      makeStage(2, 'COMPLETED'),
      makeStage(3, 'FAILED'),
    ];

    const result = mapStagesForResume(stages);

    expect(result[0].status).toBe('COMPLETED');
    expect(result[1].status).toBe('COMPLETED');
    expect(result[2].status).toBe('PENDING');
  });

  it('PENDING stages stay PENDING', () => {
    const stages = [
      makeStage(1, 'COMPLETED'),
      makeStage(2, 'FAILED'),
      makeStage(3, 'PENDING'),
    ];

    const result = mapStagesForResume(stages);

    expect(result[2].status).toBe('PENDING');
  });
});
