import { Job, JobProgress, JobAsset } from '@prisma/client';

type JobWithRelations = Job & {
  progress: JobProgress[];
  assets: JobAsset[];
  creditTransactions?: { id: string; amount: number }[];
};

interface FormatOptions {
  includeCreatedAt?: boolean;           // Dashboard, Job detail
  includeAssetFlags?: boolean;          // Dashboard only (hasReport, hasLandingPage)
  includeProgress?: boolean;            // Job detail, SSE
  includeProgressTimestamps?: boolean;  // Job detail only (startedAt/completedAt per stage)
  includeAssets?: boolean;              // Job detail, SSE
  includeSolutionIdeas?: boolean;       // Interactive flow: include solution ideas
  queueStats?: { position: number | null; totalQueued: number; aheadCount: number } | null;
}

export function formatJobResponse(job: JobWithRelations, options: FormatOptions = {}) {
  const base = {
    id: job.id,
    niche: job.niche,
    status: job.status,
    currentStage: job.currentStage,
    currentStageName: job.currentStageName,
    stagesCompleted: job.stagesCompleted,
    totalStages: job.totalStages,
    progressPercent: job.progressPercent,
    errorMessage: job.errorMessage,
    startedAt: job.startedAt?.toISOString() || null,
    completedAt: job.completedAt?.toISOString() || null,
    // Quality gate stop metadata (for intentional stops, not errors)
    stopReason: job.stopReason || null,
    stopReasonDetails: job.stopReasonDetails || null,
    // User-friendly error information
    errorCode: job.errorCode || null,
    errorDetails: job.errorDetails || null,
    // Landing page lifecycle
    generateLandingPage: job.generateLandingPage ?? false,
    landingPageStatus: job.landingPageStatus || null,
    // Interactive job flow
    jobMode: job.jobMode || null,
    selectedSolution: job.selectedSolution || null,
    selectedSolutions: job.selectedSolutions?.length ? job.selectedSolutions : null,
    awaitingSelectionAt: job.awaitingSelectionAt?.toISOString() || null,
    ideasShownAt: job.ideasShownAt?.toISOString() || null,
  };

  // Optional fields based on endpoint needs
  const result: Record<string, any> = { ...base };

  if (options.includeCreatedAt) {
    result.createdAt = job.createdAt.toISOString();
  }

  if (options.includeAssetFlags) {
    result.hasReport = job.assets.some(a => a.assetType === 'REPORT_JSON');
    result.hasLandingPage = job.assets.some(a => a.assetType === 'LANDING_PAGE');
    result.creditRefunded = (job.creditTransactions?.length ?? 0) > 0;
  }

  if (options.queueStats) {
    result.queuePosition = options.queueStats.position ?? null;
    result.aheadCount = options.queueStats.aheadCount ?? 0;
    result.totalQueued = options.queueStats.totalQueued ?? 0;
  }

  if (options.includeSolutionIdeas) {
    result.solutionIdeas = job.solutionIdeas || null;
    result.canRegenerate = job.ideasRegeneratedAt === null;
    result.selectionRationale = job.selectionRationale || null;
  }

  if (options.includeProgress) {
    result.progress = job.progress.map(p => {
      const stage: Record<string, any> = {
        stageNumber: p.stageNumber,
        stageName: p.stageName,
        status: p.status,
        durationSeconds: p.durationSeconds,
      };
      if (options.includeProgressTimestamps) {
        stage.startedAt = p.startedAt?.toISOString() || null;
        stage.completedAt = p.completedAt?.toISOString() || null;
      }
      return stage;
    });
  }

  if (options.includeAssets) {
    result.assets = job.assets.map(a => ({
      type: a.assetType,
      url: `/api/jobs/${job.id}/${a.assetType.toLowerCase().replace('_', '')}`,
    }));
  }

  return result;
}
