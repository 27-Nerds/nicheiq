import { Job, JobProgress, JobAsset, DispatchKind, DispatchState } from '@prisma/client';
import { ensureIdeaIdentities } from './ideaIdentity.js';
import { currentSelectionDraft } from './selectionDraft.js';
import { MAX_IDEA_BATCHES } from '../types/job.js';

type JobWithRelations = Job & {
  progress: JobProgress[];
  assets: JobAsset[];
  creditTransactions?: { id: string; amount: number }[];
  dispatches?: {
    id: string;
    kind: DispatchKind;
    state: DispatchState;
    refundedAmount: number | null;
    refundTransaction: { amount: number } | null;
  }[];
};

// Word-boundary truncation for display labels. `niche` itself must stay verbatim in
// API payloads (re-run/prefill URLs round-trip it); list rows, headers, titles and
// aria-labels render this instead — validate_idea pitches run to 2000 chars.
const NICHE_DISPLAY_MAX = 96;
export function toNicheDisplay(niche: string): string {
  if (niche.length <= NICHE_DISPLAY_MAX) return niche;
  const cut = niche.slice(0, NICHE_DISPLAY_MAX);
  const lastSpace = cut.lastIndexOf(' ');
  return (lastSpace > 60 ? cut.slice(0, lastSpace) : cut).trimEnd() + '…';
}

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
  const latestDispatch = job.dispatches?.[0] ?? null;
  const activeDispatch =
    job.activeDispatchId
    && latestDispatch?.id === job.activeDispatchId
    && (
      latestDispatch.state === DispatchState.AUTHORIZED
      || latestDispatch.state === DispatchState.CLAIMED
      || latestDispatch.state === DispatchState.RECOVERING
    )
      ? latestDispatch
      : null;
  const base = {
    id: job.id,
    niche: job.niche,
    // Display-safe short label. `niche` itself stays verbatim — re-run/prefill URLs
    // round-trip it, so truncation must NEVER happen on the source field. validate_idea
    // pitches run to 2000 chars; every list/header surface renders this instead.
    nicheDisplay: toNicheDisplay(job.niche),
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
    // Entry mode — drives shortened-flow rendering (pain_research / deep_idea).
    entryMode: job.entryMode || null,
    selectedSolution: job.selectedSolution || null,
    selectedSolutions: job.selectedSolutions?.length ? job.selectedSolutions : null,
    selectedSolutionIds: job.selectedSolutionIds?.length ? job.selectedSolutionIds : null,
    selectedSolutionRefs: Array.isArray(job.selectedSolutionRefs) ? job.selectedSolutionRefs : null,
    deepResearchRecommendedIdeaId: job.deepResearchRecommendedIdeaId || null,
    deepResearchRecommendedIdeaRevision: job.deepResearchRecommendedIdeaRevision ?? null,
    awaitingSelectionAt: job.awaitingSelectionAt?.toISOString() || null,
    ideasShownAt: job.ideasShownAt?.toISOString() || null,
    // Lean count so list payloads can show "N candidates ready" without the full array
    solutionIdeasCount: Array.isArray(job.solutionIdeas) ? job.solutionIdeas.length : null,
    // Guided mode (Phase B — plans/eager-meandering-feather.md): chatMode opts a job into
    // the G1/G2 stage gates; gateStage/gateArtifact/gateReachedAt are only set while
    // status=AWAITING_GATE (null otherwise, including at AWAITING_SELECTION).
    chatMode: job.chatMode ?? false,
    gateStage: job.gateStage ?? null,
    gateArtifact: job.gateArtifact ?? null,
    gateReachedAt: job.gateReachedAt?.toISOString() || null,
    // apply_stay counter for the CURRENT gate (gate-action route caps at 5) — the
    // GateWorkbench "change limit reached" affordance reads this.
    gateApplyCount: job.gateApplyCount ?? 0,
    // The exact durable operation currently owning this job. The selection UI uses this
    // instead of inferring SEED_IDEA vs DEEP_RESEARCH from a separately-loaded chat ledger.
    activeDispatchKind: activeDispatch?.kind ?? null,
    activeOperation: activeDispatch
      ? {
          id: activeDispatch.id,
          kind: activeDispatch.kind,
          state: activeDispatch.state,
        }
      : null,
  };

  // Optional fields based on endpoint needs
  const result: Record<string, any> = { ...base };
  if (job.creditTransactions !== undefined) {
    // A prior refunded seed/batch must not make a later, unrelated terminal failure claim
    // that credits were restored. Modern jobs report against their latest exact dispatch;
    // the broad transaction scan is only a compatibility fallback for legacy jobs.
    const exactRefundAmount = latestDispatch
      ? Math.max(latestDispatch.refundedAmount ?? latestDispatch.refundTransaction?.amount ?? 0, 0)
      : null;
    result.creditRefunded = exactRefundAmount !== null
      ? exactRefundAmount > 0
      : job.creditTransactions.some(transaction => transaction.amount > 0);
    // Resume re-charges the unmatched refund amount, not today's configured stage price.
    // Expose that exact amount only when a modern dispatch owns it; legacy transaction-only
    // jobs keep the boolean fallback because their latest unmatched refund is ambiguous here.
    if (exactRefundAmount !== null) {
      result.creditRefundedAmount = exactRefundAmount;
    }
  }

  if (options.includeCreatedAt) {
    result.createdAt = job.createdAt.toISOString();
  }

  if (options.includeAssetFlags) {
    result.hasReport = job.assets.some(a => a.assetType === 'REPORT_JSON');
    result.hasLandingPage = job.assets.some(a => a.assetType === 'LANDING_PAGE');
  }

  if (options.queueStats) {
    result.queuePosition = options.queueStats.position ?? null;
    result.aheadCount = options.queueStats.aheadCount ?? 0;
    result.totalQueued = options.queueStats.totalQueued ?? 0;
  }

  if (options.includeSolutionIdeas) {
    const solutionIdeas = job.solutionIdeas
      ? ensureIdeaIdentities(job.id, job.solutionIdeas)
      : [];
    result.solutionIdeas = job.solutionIdeas ? solutionIdeas : null;
    result.canRegenerate = (job.ideaBatchCompletedCount ?? 0) < MAX_IDEA_BATCHES;
    // Successful additional batches consume the cap. Expose both values even at the
    // limit so clients can explain a disabled action instead of making it disappear.
    result.ideaBatchCompletedCount = job.ideaBatchCompletedCount ?? 0;
    result.maxIdeaBatches = MAX_IDEA_BATCHES;
    result.selectionRationale = job.selectionRationale || null;
    result.selectionDecisionProfile = job.selectionDecisionProfile || null;
    result.selectionDraft = currentSelectionDraft(
      job.selectionDraft,
      job.selectionDraftVersion,
      solutionIdeas,
    );
  }

  if (options.includeProgress) {
    result.progress = job.progress.map(p => {
      const stage: Record<string, any> = {
        stageNumber: p.stageNumber,
        stageName: p.stageName,
        status: p.status,
        durationSeconds: p.durationSeconds,
        artifact: p.details ?? null,
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
