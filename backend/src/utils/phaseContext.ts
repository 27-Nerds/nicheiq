import { DISCOVERY_PHASE_MAX_STAGE } from '../types/job.js';

export interface PhaseContext {
  phaseLabel: string;
  guidance: string;
}

/**
 * Build phase-specific context for error emails based on which stage failed.
 */
export function getPhaseContext(
  errorStage: number | null | undefined,
  selectedSolutions?: string[] | null
): PhaseContext {
  if (errorStage == null) {
    return {
      phaseLabel: 'During research',
      guidance: 'You can try submitting your research request again.',
    };
  }

  if (errorStage <= DISCOVERY_PHASE_MAX_STAGE) {
    return {
      phaseLabel: 'During Discovery Phase (market analysis)',
      guidance: 'You can retry the research — discovery results are checkpointed and the job will resume where it left off.',
    };
  }

  // Deep Research Phase
  const solutionSuffix = selectedSolutions?.length
    ? ` for "${selectedSolutions.join('", "')}"`
    : '';
  return {
    phaseLabel: `During Deep Research Phase${solutionSuffix}`,
    guidance: 'Your discovery results and solution selection are saved. You can resume the job and deep research will continue from its checkpoint.',
  };
}
