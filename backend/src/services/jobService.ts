import { prisma } from './db.js';
import { JobStatus, StageStatus, AssetType, Prisma, BillingModel, DispatchState, DispatchKind, CreditTransactionType, type Job } from '@prisma/client';
import { PIPELINE_STAGES, TOTAL_STAGES } from '../types/job.js';
import {
  determineFailedStage,
  refundChargeInTx,
  refundForStage,
  refundForStageInTx,
  refundForRegenerationStage,
  isGuidedSegment,
  type StageName,
} from './creditService.js';
import {
  buildRegenerationEnvelope,
  buildRegenerationReceiptContent,
  buildSeedEnvelope,
  buildSeedReceiptContent,
} from '../utils/ledgerEvents.js';
import {
  COMMERCIAL_COPY_CONTRACT_VERSION,
  hashRegisteredAsset,
  needsCommercialCopyFence,
} from './assetPublicationFence.js';

/**
 * Create a new research job
 */
export async function createJob(
  niche: string,
  allowedProjectTypes?: string[],
  userId?: string,
  jobMode?: string
) {
  // Create job with initial progress entries for all stages
  const job = await prisma.job.create({
    data: {
      niche,
      userId, // Associate with user if provided
      allowedProjectTypes: allowedProjectTypes as Prisma.InputJsonValue,
      jobMode,
      status: JobStatus.PENDING,
      totalStages: TOTAL_STAGES,
      progress: {
        create: PIPELINE_STAGES.map(stage => ({
          stageNumber: stage.number,
          stageName: stage.name,
          status: StageStatus.PENDING,
        })),
      },
    },
    include: {
      progress: {
        orderBy: { stageNumber: 'asc' },
      },
      assets: true,
    },
  });

  return job;
}

/**
 * Get a job by ID with all related data
 */
export async function getJob(id: string) {
  return prisma.job.findUnique({
    where: { id },
    include: {
      progress: {
        orderBy: { stageNumber: 'asc' },
      },
      assets: true,
      creditTransactions: {
        where: { type: CreditTransactionType.REFUND },
        select: {
          id: true,
          amount: true,
        },
      },
      dispatches: {
        orderBy: { createdAt: 'desc' },
        take: 1,
        select: {
          id: true,
          kind: true,
          state: true,
          refundedAmount: true,
          refundTransaction: {
            select: { amount: true },
          },
        },
      },
    },
  });
}

/**
 * Update job status
 */
export async function updateJobStatus(
  id: string,
  status: JobStatus,
  errorMessage?: string
) {
  const updateData: Prisma.JobUpdateInput = { status };

  if (status === JobStatus.RUNNING) {
    updateData.startedAt = new Date();
  } else if (status === JobStatus.COMPLETED) {
    updateData.completedAt = new Date();
    updateData.progressPercent = 100;
  } else if (status === JobStatus.FAILED && errorMessage) {
    updateData.errorMessage = errorMessage;
  }

  return prisma.job.update({
    where: { id },
    data: updateData,
    include: {
      progress: {
        orderBy: { stageNumber: 'asc' },
      },
      assets: true,
    },
  });
}

/**
 * Update stage progress
 */
export async function updateStageProgress(
  jobId: string,
  stageNumber: number,
  status: StageStatus,
  errorMessage?: string,
  details?: Record<string, unknown>,
  dispatchId?: string,
) {
  const applyUpdate = async (db: Prisma.TransactionClient | typeof prisma) => {
    const now = new Date();

    // Get current stage status to avoid overwriting historical data on resume
    const currentStage = await db.jobProgress.findUnique({
      where: { jobId_stageNumber: { jobId, stageNumber } },
      select: { status: true, startedAt: true, completedAt: true, durationSeconds: true },
    });

    // Skip update if stage is already completed (preserve historical timestamps during resume)
    // BUT still persist details/artifact if provided (handles resume/reload artifact population)
    if (currentStage?.status === StageStatus.COMPLETED && (status === StageStatus.COMPLETED || status === StageStatus.SKIPPED)) {
      if (details) {
        await db.jobProgress.update({
          where: { jobId_stageNumber: { jobId, stageNumber } },
          data: { details: details as Prisma.InputJsonValue },
        });
      }
      const existingProgress = await db.jobProgress.findUnique({
        where: { jobId_stageNumber: { jobId, stageNumber } },
      });
      return existingProgress;
    }

    // Upsert: creates the row if it doesn't exist yet (forward compat for new stages)
    const stageName = PIPELINE_STAGES.find(s => s.number === stageNumber)?.name ?? `Stage ${stageNumber}`;
    const progress = await db.jobProgress.upsert({
      where: {
        jobId_stageNumber: {
          jobId,
          stageNumber,
        },
      },
      create: {
        jobId,
        stageNumber,
        stageName,
        status,
        startedAt: status === StageStatus.RUNNING ? now : undefined,
        completedAt: (status === StageStatus.COMPLETED || status === StageStatus.SKIPPED || status === StageStatus.FAILED) ? now : undefined,
        errorMessage,
        ...(details ? { details: details as Prisma.InputJsonValue } : {}),
      },
      update: {
        status,
        startedAt: status === StageStatus.RUNNING && !currentStage?.startedAt ? now : undefined,
        completedAt: (status === StageStatus.COMPLETED || status === StageStatus.SKIPPED || status === StageStatus.FAILED) && !currentStage?.completedAt ? now : undefined,
        errorMessage,
        ...(details ? { details: details as Prisma.InputJsonValue } : {}),
      },
    });

    // Only calculate duration if not already set
    if (progress.startedAt && progress.completedAt && !currentStage?.durationSeconds) {
      await db.jobProgress.update({
        where: { id: progress.id },
        data: {
          durationSeconds: (progress.completedAt.getTime() - progress.startedAt.getTime()) / 1000,
        },
      });
    }

    // Update job's current stage and progress percent
    const [completedStages, jobRecord] = await Promise.all([
      db.jobProgress.count({
        where: {
          jobId,
          status: { in: [StageStatus.COMPLETED, StageStatus.SKIPPED] },
        },
      }),
      db.job.findUnique({
        where: { id: jobId },
        select: { totalStages: true },
      }),
    ]);

    const dynamicTotal = Math.max(jobRecord?.totalStages ?? TOTAL_STAGES, TOTAL_STAGES);

    await db.job.update({
      where: { id: jobId },
      data: {
        currentStage: stageNumber,
        currentStageName: stageName,
        stagesCompleted: completedStages,
        progressPercent: (completedStages / dynamicTotal) * 100,
      },
    });

    return progress;
  };

  if (!dispatchId) return applyUpdate(prisma);

  return prisma.$transaction(async (tx) => {
    // This is both the ownership check and the row lock. A terminal callback uses the same Job
    // row first, so it either waits for this authorized projection to commit or wins first and
    // makes the predicate miss. A read-before-write guard cannot provide that guarantee.
    const fenced = await tx.job.updateMany({
      where: { id: jobId, activeDispatchId: dispatchId },
      data: { updatedAt: new Date() },
    });
    if (fenced.count !== 1) return null;
    return applyUpdate(tx);
  });
}

/**
 * Add an asset to a job
 */
export async function addJobAsset(
  jobId: string,
  assetType: AssetType,
  filePath: string,
  fileSizeBytes?: number,
  commercialCopyContractVersion?: string,
) {
  const asset = await prisma.jobAsset.upsert({
    where: {
      jobId_assetType: {
        jobId,
        assetType,
      },
    },
    create: {
      jobId,
      assetType,
      filePath,
      fileSizeBytes,
    },
    update: {
      filePath,
      fileSizeBytes,
    },
  });

  if (commercialCopyContractVersion) {
    const stamped = await stampJobAssetCommercialCopy(
      jobId, assetType, filePath, commercialCopyContractVersion,
    );
    if (stamped) return stamped;
  }
  return asset;
}

export async function stampJobAssetCommercialCopy(
  jobId: string,
  assetType: AssetType,
  filePath: string,
  commercialCopyContractVersion?: string,
) {
  if (
    !needsCommercialCopyFence(assetType)
    || commercialCopyContractVersion !== COMMERCIAL_COPY_CONTRACT_VERSION
  ) return null;

  try {
    const fingerprint = await hashRegisteredAsset(filePath);
    return await prisma.jobAsset.updateMany({
      where: { jobId, assetType, filePath },
      data: {
        commercialCopyStatus: 'GENERATED_CONTRACT',
        commercialCopySha256: fingerprint.sha256,
        commercialCopyCheckedAt: new Date(),
      },
    });
  } catch (error) {
    console.error(`[JobService] Could not stamp commercial-copy fence for ${jobId}/${assetType}:`, error);
    return null;
  }
}

/**
 * Get asset by type for a job
 */
export async function getJobAsset(jobId: string, assetType: AssetType) {
  return prisma.jobAsset.findUnique({
    where: {
      jobId_assetType: {
        jobId,
        assetType,
      },
    },
  });
}

/**
 * Complete a job with assets
 *
 * This function is IDEMPOTENT - safe to call multiple times for the same job.
 * If the job is already COMPLETED, it returns the existing job without changes.
 */
export async function completeJob(
  jobId: string,
  reportPath: string,
  landingPath?: string
) {
  // Check if job is already COMPLETED (idempotency)
  const existingJob = await prisma.job.findUnique({
    where: { id: jobId },
    select: { status: true },
  });

  if (!existingJob) {
    console.log(`[JobService] Job ${jobId} not found`);
    return null;
  }

  if (existingJob.status === JobStatus.COMPLETED) {
    console.log(`[JobService] Job ${jobId} is already COMPLETED, skipping duplicate completeJob() call`);
    return prisma.job.findUnique({
      where: { id: jobId },
      include: { progress: { orderBy: { stageNumber: 'asc' } }, assets: true },
    });
  }

  // Accept RUNNING_PHASE2 as valid pre-completion state (interactive flow)
  const validPreCompletionStatuses: JobStatus[] = [JobStatus.RUNNING, JobStatus.RUNNING_PHASE2];
  if (!validPreCompletionStatuses.includes(existingJob.status)) {
    console.log(`[JobService] Job ${jobId} is in ${existingJob.status}, not a valid pre-completion state`);
    return null;
  }

  // Add report asset
  await addJobAsset(jobId, AssetType.REPORT_JSON, reportPath);

  // Add landing page asset if provided
  if (landingPath) {
    await addJobAsset(jobId, AssetType.LANDING_PAGE, landingPath);
  }

  // Update job status
  return updateJobStatus(jobId, JobStatus.COMPLETED);
}

/**
 * Fail a job with error message
 * Automatically refunds the research credit to the user
 *
 * This function is IDEMPOTENT - safe to call multiple times for the same job.
 * If the job is already FAILED, it returns the existing job without making changes.
 *
 * @param jobId - The job UUID
 * @param errorMessage - Error message or recommendation
 * @param errorStage - Stage number where failure/stop occurred
 * @param stopReason - Optional quality gate stop reason (e.g., 'INSUFFICIENT_DATA')
 * @param stopReasonDetails - Optional quality metrics and recommendation
 * @param errorCode - Classified error code for user-friendly messaging
 * @param errorDetails - Translated error details with user message and guidance
 */
/**
 * Statuses a user may cancel from. Kept here (not in the route) because BOTH cancel verbs now go
 * through this service — they used to be two different state machines: POST timestamped, dequeued
 * and failed RUNNING progress rows; DELETE did none of that. Same user intent, two behaviours, and
 * once money is attached to cancellation that divergence becomes a pricing bug.
 */
export const CANCELLABLE_STATUSES: JobStatus[] = [
  JobStatus.PENDING, JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.AWAITING_GATE,
];

export type CancelOutcome =
  | { cancelled: true; creditRefunded: number }
  | { cancelled: false; reason: 'not_found' | 'not_cancellable'; status?: JobStatus };

/**
 * Cancel a job. The ONE cancellation path.
 *
 * The terminal transition is a CAS, so cancel and failJob cannot both win it. Previously each read
 * the status and then wrote unconditionally: the last writer set the status, but BOTH issued a
 * refund, so a job could be settled twice.
 */
export async function cancelJob(jobId: string): Promise<CancelOutcome> {
  const existing = await prisma.job.findUnique({
    where: { id: jobId },
    select: { status: true, activeDispatchId: true },
  });
  if (!existing) return { cancelled: false, reason: 'not_found' };

  // A SEED_IDEA dispatch is a paid operation ON TOP of an already-settled AWAITING_SELECTION
  // job — the whole-job cancellation below (CANCELLED + refund 'discovery'/segment) would
  // destroy an already-completed, already-paid-for pool over the user cancelling a small paid
  // follow-up request. Settle THAT dispatch, refund its numbered seed_idea_N charge, and
  // restore AWAITING_SELECTION with the pool intact instead (plan: eager-meandering-feather.md
  // Phase 5, "op-scoped cancel + heartbeat"). Checked BEFORE the whole-job CANCELLABLE_STATUSES
  // gate below, because QUEUED/RUNNING (the seed op's own statuses) are already cancellable
  // there too — this branch has to intercept first, not fall through to it.
  if (existing.activeDispatchId) {
    const dispatch = await prisma.jobDispatch.findUnique({
      where: { id: existing.activeDispatchId },
      select: {
        id: true,
        kind: true,
        state: true,
        seedOrdinal: true,
        sourceMessageId: true,
        chargeId: true,
      },
    });
    if (dispatch?.kind === DispatchKind.SEED_IDEA) {
      // Once a worker owns the attempt, freeing the parent selection state would let a
      // second paid pool mutation start while the first worker can still commit or
      // compensate the same checkpoint. User cancellation is therefore exact and safe
      // only before AUTHORIZED -> CLAIMED.
      if (dispatch.state !== DispatchState.AUTHORIZED) {
        return {
          cancelled: false,
          reason: 'not_cancellable',
          status: existing.status,
        };
      }
      return cancelSeedIdeaDispatch(
        jobId,
        dispatch,
        existing.status,
        'CANCELLED_BY_USER',
        undefined,
        true,
      );
    }
  }

  if (!CANCELLABLE_STATUSES.includes(existing.status)) {
    return { cancelled: false, reason: 'not_cancellable', status: existing.status };
  }

  const settled = await prisma.$transaction(async (tx) => {
    // Job-first CAS preserves the start/cancel lock order. The exact refunds below share this
    // transaction: if the ledger is unavailable, cancellation rolls back and remains retryable.
    const claimed = await tx.job.updateMany({
      where: {
        id: jobId,
        status: { in: CANCELLABLE_STATUSES },
        activeDispatchId: existing.activeDispatchId,
      },
      data: {
        status: JobStatus.CANCELLED,
        errorMessage: 'Cancelled by user',
        completedAt: new Date(),
        activeDispatchId: null,
      },
    });
    if (claimed.count === 0) return null;

    await tx.jobProgress.updateMany({
      where: { jobId, status: StageStatus.RUNNING },
      data: { status: StageStatus.FAILED, errorMessage: 'Cancelled by user' },
    });

    const billing = await tx.job.findUnique({
      where: { id: jobId },
      select: { billingModel: true, selectedSolutions: true },
    });
    const open = await tx.jobDispatch.findMany({
      where: { jobId, state: { in: [DispatchState.AUTHORIZED, DispatchState.CLAIMED] } },
      select: { id: true, state: true, segment: true, chargeId: true, kind: true, gateStage: true },
    });

    let creditRefunded = 0;
    const markRefunded = async (
      dispatchId: string,
      refund: NonNullable<Awaited<ReturnType<typeof refundChargeInTx>>>,
    ) => {
      const refundedAmount = Math.max(refund.amount, 0);
      creditRefunded += refundedAmount;
      await tx.jobDispatch.updateMany({
        where: {
          id: dispatchId,
          state: { in: [DispatchState.AUTHORIZED, DispatchState.CLAIMED] },
        },
        data: {
          state: refundedAmount > 0 ? DispatchState.REFUNDED : DispatchState.FAILED,
          refundTransactionId: refund.id,
          refundedAt: refundedAmount > 0 ? new Date() : undefined,
          refundedAmount: refund.amount,
          settledAt: new Date(),
          failureKind: 'CANCELLED_BY_USER',
        },
      });
    };

    if (billing?.billingModel === BillingModel.GUIDED_SEGMENTS_V1) {
      // Guided work is refundable only before claim. Resolve modern attempts by chargeId; the
      // stage lookup remains solely for rolling-deploy dispatches that predate charge linkage.
      for (const dispatch of open) {
        if (dispatch.state !== DispatchState.AUTHORIZED) continue;

        let refund = dispatch.chargeId
          ? await refundChargeInTx(tx, dispatch.chargeId)
          : null;
        if (!dispatch.chargeId) {
          let stage: StageName | null = null;
          if (dispatch.segment) {
            if (isGuidedSegment(dispatch.segment)) {
              stage = dispatch.segment;
            } else {
              console.warn(
                `[JobService] Dispatch ${dispatch.id} has unrecognised segment ` +
                `'${dispatch.segment}' — skipping refund`,
              );
            }
          } else if (dispatch.kind === DispatchKind.CONTINUE && dispatch.gateStage == null) {
            stage = ((billing.selectedSolutions as string[] | null)?.length ?? 0) > 0
              ? 'deep_research'
              : 'guided_s1';
          }
          if (stage) refund = await refundForStageInTx(tx, jobId, stage);
        }
        if (refund) await markRefunded(dispatch.id, refund);
      }
    } else {
      // Prepaid cancellation returns the attempt in full, even after claim. Prefer the active
      // dispatch's immutable charge; only identityless rolling-deploy jobs use stage resolution.
      const active =
        open.find(dispatch => dispatch.id === existing.activeDispatchId)
        ?? open.find(dispatch => dispatch.chargeId != null);
      const refund = active?.chargeId
        ? await refundChargeInTx(tx, active.chargeId)
        : await refundForStageInTx(tx, jobId, 'discovery');
      if (refund) {
        if (active) {
          await markRefunded(active.id, refund);
        } else {
          creditRefunded += Math.max(refund.amount, 0);
        }
      }
    }

    await tx.jobDispatch.updateMany({
      where: { jobId, state: { in: [DispatchState.AUTHORIZED, DispatchState.CLAIMED] } },
      data: {
        state: DispatchState.FAILED,
        failureKind: 'CANCELLED_BY_USER',
        settledAt: new Date(),
      },
    });

    return { creditRefunded };
  });

  if (!settled) {
    const current = await prisma.job.findUnique({ where: { id: jobId }, select: { status: true } });
    return { cancelled: false, reason: 'not_cancellable', status: current?.status };
  }

  if (existing.status === JobStatus.QUEUED) {
    const { removeJobFromQueue } = await import('./queueService.js');
    await removeJobFromQueue(jobId).catch((err) =>
      console.error(`[JobService] Failed to remove cancelled job ${jobId} from the queue:`, err)
    );
  }
  return { cancelled: true, creditRefunded: settled.creditRefunded };
}

/**
 * Op-scoped cancellation for a SEED_IDEA dispatch (plan: eager-meandering-feather.md Phase 5,
 * "op-scoped cancel + heartbeat"). Unlike `cancelJob` above, a seed request is an operation ON
 * TOP of an already-paid-for, already-completed AWAITING_SELECTION job — settling it must
 * refund THAT dispatch's numbered seed_idea_N charge and restore AWAITING_SELECTION with the
 * pool intact, never mark the parent research job CANCELLED/FAILED.
 *
 * Shared by two callers: `cancelJob` (user hits Cancel while a seed is in flight) and
 * `heartbeatService`'s stale-job recovery (the worker crashed mid-seed). `failureKind` and the
 * caller-supplied `currentStatus` (read before this function's own CAS) distinguish the two in
 * logs/dispatch history without duplicating the transaction.
 */
export async function cancelSeedIdeaDispatch(
  jobId: string,
  dispatch: {
    id: string;
    seedOrdinal: number | null;
    sourceMessageId?: string | null;
    chargeId?: string | null;
  },
  currentStatus: JobStatus,
  failureKind: string,
  recoveryFence?: HeartbeatRecoveryFence,
  authorizedOnly = false,
): Promise<CancelOutcome> {
  const reverted = await prisma.$transaction(async (tx) => {
    const result = await tx.job.updateMany({
      where: {
        id: jobId,
        status: authorizedOnly
          ? JobStatus.QUEUED
          : recoveryFence?.status ?? { in: [JobStatus.QUEUED, JobStatus.RUNNING] },
        activeDispatchId: dispatch.id,
        ...(recoveryFence ? { lastHeartbeat: recoveryFence.lastHeartbeat } : {}),
      },
      data: { status: JobStatus.AWAITING_SELECTION, activeDispatchId: null },
    });
    if (result.count === 0) return { count: 0, creditRefunded: 0 };

    const dispatchSettled = await tx.jobDispatch.updateMany({
      where: {
        id: dispatch.id,
        ...(authorizedOnly ? { state: DispatchState.AUTHORIZED } : {}),
      },
      data: { state: DispatchState.FAILED, failureKind, settledAt: new Date() },
    });
    if (authorizedOnly && dispatchSettled.count !== 1) {
      throw new Error('SEED_CANCEL_RACE');
    }

    // Modern seed dispatches own the exact charge that bought this attempt. Refund it in the
    // same transaction as restoring the parent Job so a process crash cannot leave the user
    // back at selection while their credits remain captured.
    const refund = dispatch.chargeId
      ? await refundChargeInTx(tx, dispatch.chargeId)
      : dispatch.seedOrdinal != null
        ? await refundForStageInTx(tx, jobId, `seed_idea_${dispatch.seedOrdinal}`)
        : null;
    const refundedAmount = Math.max(refund?.amount ?? 0, 0);
    if (refund && refundedAmount > 0) {
      await tx.jobDispatch.updateMany({
        where: { id: dispatch.id, state: DispatchState.FAILED },
        data: {
          state: DispatchState.REFUNDED,
          refundTransactionId: refund.id,
          refundedAt: new Date(),
          refundedAmount: refund.amount,
        },
      });
    }

    // Durable terminal receipt — without this the durable
    // 'seed_submitted' receipt (written by POST /:jobId/seed-idea) stays 'pending' forever,
    // which pins the frontend's hasPendingSeed lock open permanently (mirrors /seed-failed's
    // own receipt write in workers.ts). Guard: if this dispatch predates sourceMessageId
    // (shouldn't happen, but be safe), skip the receipt — never throw over a missing id.
    if (dispatch.sourceMessageId) {
      const outcome = refundedAmount > 0 ? 'refunded' : 'cancelled';
      await tx.chatMessage.create({
        data: {
          jobId,
          gateStage: 5,
          role: 'receipt',
          content: buildSeedReceiptContent('seed_settled', outcome),
          patchJson: buildSeedEnvelope(
            'seed_settled', dispatch.sourceMessageId, outcome, undefined,
            dispatch.id,
          ) as unknown as object,
        },
      });
    } else {
      console.warn(`[JobService] Seed dispatch ${dispatch.id} has no sourceMessageId — skipping seed_settled receipt`);
    }

    return {
      count: result.count,
      creditRefunded: refundedAmount,
    };
  });

  if (reverted.count === 0) {
    // Somebody else already settled this dispatch (a completion landed first, or a concurrent
    // cancel/recovery won the CAS) — nothing to do, and definitely nothing to refund on top of it.
    const current = await prisma.job.findUnique({ where: { id: jobId }, select: { status: true } });
    return { cancelled: false, reason: 'not_cancellable', status: current?.status };
  }

  if (currentStatus === JobStatus.QUEUED) {
    const { removeJobFromQueue } = await import('./queueService.js');
    await removeJobFromQueue(jobId).catch((err) =>
      console.error(`[JobService] Failed to remove cancelled seed op ${jobId} from the queue:`, err)
    );
  }

  return { cancelled: true, creditRefunded: reverted.creditRefunded };
}

function regenerationOrdinal(segment: string | null | undefined): number | null {
  const match = /^regenerate_ideas_(\d+)$/.exec(segment ?? '');
  if (!match) return null;
  const value = Number(match[1]);
  return Number.isInteger(value) && value > 0 ? value : null;
}

/**
 * Operation-scoped failure recovery for an additional idea batch.
 *
 * A batch runs on top of an already-valid AWAITING_SELECTION job. A worker crash or
 * failed callback must therefore restore that state and preserve the candidate pool,
 * never fail the parent research job. The dispatch's numbered segment identifies the
 * exact regeneration charge to refund.
 */
export async function cancelRegenerationDispatch(
  jobId: string,
  dispatch: { id: string; segment: string | null; chargeId?: string | null },
  currentStatus: JobStatus,
  failureKind: string,
  recoveryFence?: HeartbeatRecoveryFence,
): Promise<CancelOutcome> {
  const ordinal = regenerationOrdinal(dispatch.segment);
  const reverted = await prisma.$transaction(async (tx) => {
    const result = await tx.job.updateMany({
      where: {
        id: jobId,
        status: recoveryFence?.status ?? { in: [JobStatus.QUEUED, JobStatus.REGENERATING] },
        activeDispatchId: dispatch.id,
        ...(recoveryFence ? { lastHeartbeat: recoveryFence.lastHeartbeat } : {}),
      },
      data: { status: JobStatus.AWAITING_SELECTION, activeDispatchId: null },
    });
    if (result.count === 0) return { count: 0, creditRefunded: 0 };

    await tx.jobDispatch.updateMany({
      where: { id: dispatch.id, kind: DispatchKind.REGENERATE },
      data: { state: DispatchState.FAILED, failureKind, settledAt: new Date() },
    });
    const refund = dispatch.chargeId
      ? await refundChargeInTx(tx, dispatch.chargeId)
      : null;
    const refundedAmount = Math.max(refund?.amount ?? 0, 0);
    if (refund && refundedAmount > 0) {
      await tx.jobDispatch.update({
        where: { id: dispatch.id },
        data: {
          state: DispatchState.REFUNDED,
          refundTransactionId: refund.id,
          refundedAt: new Date(),
          refundedAmount: refund.amount,
        },
      });
    }
    // The settled receipt is the ONLY thing that clears the client's pending-batch state,
    // and that state gates every pool mutation. It must therefore be written even when the
    // segment carries no ordinal (dispatches opened before batches were numbered) — the
    // exact ordinal is needed for the REFUND below, not for settling the operation.
    const counted = await tx.job.findUnique({
      where: { id: jobId },
      select: { regenerationCount: true },
    });
    await tx.chatMessage.upsert({
      where: { operationId: `regeneration:${dispatch.id}:settled` },
      create: {
        jobId,
        gateStage: 5,
        role: 'receipt',
        content: buildRegenerationReceiptContent(
          'regeneration_settled',
          refundedAmount > 0 ? 'refunded' : 'failed',
        ),
        operationId: `regeneration:${dispatch.id}:settled`,
        patchJson: buildRegenerationEnvelope({
          event: 'regeneration_settled',
          operationId: dispatch.id,
          ordinal: ordinal ?? counted?.regenerationCount ?? 0,
          outcome: refundedAmount > 0 ? 'refunded' : 'failed',
          refunded: refundedAmount > 0,
        }) as unknown as object,
      },
      update: {},
    });
    return { count: result.count, creditRefunded: refundedAmount };
  });

  if (reverted.count === 0) {
    const current = await prisma.job.findUnique({
      where: { id: jobId },
      select: { status: true },
    });
    return { cancelled: false, reason: 'not_cancellable', status: current?.status };
  }

  if (currentStatus === JobStatus.QUEUED) {
    const { removeJobFromQueue } = await import('./queueService.js');
    await removeJobFromQueue(jobId).catch((error) =>
      console.error(`[JobService] Failed to remove failed idea batch ${jobId} from the queue:`, error)
    );
  }

  let creditRefunded = reverted.creditRefunded;
  if (!dispatch.chargeId && ordinal != null) {
    try {
      const refund = await refundForRegenerationStage(jobId, ordinal);
      if (refund) {
        creditRefunded = Math.max(refund.amount, 0);
        if (creditRefunded > 0) {
          await prisma.$transaction(async (tx) => {
            await tx.jobDispatch.updateMany({
              where: { id: dispatch.id },
              data: { state: DispatchState.REFUNDED },
            });
            await tx.chatMessage.update({
              where: { operationId: `regeneration:${dispatch.id}:settled` },
              data: {
                content: buildRegenerationReceiptContent('regeneration_settled', 'refunded'),
                patchJson: buildRegenerationEnvelope({
                  event: 'regeneration_settled',
                  operationId: dispatch.id,
                  ordinal,
                  outcome: 'refunded',
                  refunded: true,
                }) as unknown as object,
              },
            });
          });
        }
      }
    } catch (error) {
      console.error(`[JobService] Failed to refund idea batch ${dispatch.id}:`, error);
    }
  } else if (!dispatch.chargeId) {
    console.error(
      `[JobService] Regeneration dispatch ${dispatch.id} has no numbered segment; ` +
      'cannot identify its exact charge for refund',
    );
  }

  return { cancelled: true, creditRefunded };
}

export type FailJobResult =
  | { applied: true; job: Job | null }
  | { applied: false; job: Job | null };

export type HeartbeatRecoveryFence = {
  status: JobStatus;
  lastHeartbeat: Date | null;
};

export async function failJob(
  jobId: string,
  errorMessage: string,
  errorStage?: number,
  stopReason?: string,
  stopReasonDetails?: Record<string, any>,
  errorCode?: string,
  errorDetails?: Record<string, any>,
  dispatchId?: string,
  recoveryFence?: HeartbeatRecoveryFence,
): Promise<FailJobResult> {
  // Check if job is already FAILED (idempotency)
  const existingJob = await prisma.job.findUnique({
    where: { id: jobId },
    select: { status: true, regenerationCount: true, activeDispatchId: true },
  });

  if (!existingJob) {
    console.log(`[JobService] Job ${jobId} not found`);
    return { applied: false, job: null };
  }

  if (existingJob.status === JobStatus.FAILED) {
    console.log(`[JobService] Job ${jobId} is already FAILED, skipping duplicate failJob() call`);
    return {
      applied: false,
      job: await prisma.job.findUnique({ where: { id: jobId } }),
    };
  }

  // Accept interactive flow statuses as valid pre-fail states. AWAITING_GATE included:
  // notify_job_failed is queue_consumer's LAST RESORT when even notify_gate_failed's
  // compensating revert fails (worker crash mid gate-continuation exhausting retries) — a
  // job stuck AWAITING_GATE must still be failable, not stranded forever.
  const validPreFailStatuses: JobStatus[] = [
    JobStatus.PENDING, JobStatus.QUEUED, JobStatus.RUNNING,
    JobStatus.AWAITING_SELECTION, JobStatus.AWAITING_GATE,
    JobStatus.REGENERATING, JobStatus.RUNNING_PHASE2,
  ];
  if (!validPreFailStatuses.includes(existingJob.status)) {
    console.log(`[JobService] Job ${jobId} is in ${existingJob.status}, cannot fail from this state`);
    return {
      applied: false,
      job: await prisma.job.findUnique({ where: { id: jobId } }),
    };
  }

  const failureData = {
    status: JobStatus.FAILED,
    errorMessage,
    errorStage,
    stopReason: stopReason ?? null,
    stopReasonDetails: stopReasonDetails ?? Prisma.JsonNull,
    errorCode: errorCode ?? null,
    errorDetails: errorDetails ?? Prisma.JsonNull,
    activeDispatchId: null,
  };

  if (dispatchId) {
    const dispatch = await prisma.jobDispatch.findUnique({
      where: { id: dispatchId },
      select: { id: true, jobId: true, chargeId: true },
    });
    if (!dispatch || dispatch.jobId !== jobId) {
      console.warn(
        `[JobService] Ignoring failure for job ${jobId}: dispatch ${dispatchId} does not belong to it`,
      );
      return {
        applied: false,
        job: await prisma.job.findUnique({ where: { id: jobId } }),
      };
    }

    const settled = await prisma.$transaction(async (tx) => {
      // The dispatch id is part of the terminal CAS. A delayed failure from attempt A must not
      // terminate attempt B merely because both attempts used RUNNING_PHASE2.
      const claimed = await tx.job.updateMany({
        where: {
          id: jobId,
          status: recoveryFence?.status ?? { in: validPreFailStatuses },
          activeDispatchId: dispatchId,
          ...(recoveryFence ? { lastHeartbeat: recoveryFence.lastHeartbeat } : {}),
        },
        data: failureData,
      });
      if (claimed.count === 0) return null;

      const terminal = await tx.jobDispatch.updateMany({
        where: {
          id: dispatchId,
          jobId,
          state: { in: [DispatchState.AUTHORIZED, DispatchState.CLAIMED] },
        },
        data: {
          state: DispatchState.FAILED,
          failureKind: 'SYSTEM_FAULT',
          settledAt: new Date(),
        },
      });
      if (terminal.count !== 1) {
        // Roll the Job CAS back too. A FAILED job with an unsettled attempt is not a valid
        // terminal state, and retrying the callback is safer than losing its exact refund target.
        throw new Error('DISPATCH_FAILURE_SETTLEMENT_RACE');
      }

      let refund = null;
      if (dispatch.chargeId) {
        refund = await refundChargeInTx(tx, dispatch.chargeId);
        if (refund && refund.amount > 0) {
          await tx.jobDispatch.update({
            where: { id: dispatchId },
            data: {
              state: DispatchState.REFUNDED,
              refundTransactionId: refund.id,
              refundedAt: new Date(),
              refundedAmount: refund.amount,
            },
          });
        }
      }

      return {
        job: await tx.job.findUnique({ where: { id: jobId } }),
        refund,
      };
    });

    if (!settled) {
      const current = await prisma.job.findUnique({ where: { id: jobId } });
      console.log(
        `[JobService] Ignoring stale failure for job ${jobId} dispatch ${dispatchId} ` +
        `(active: ${current?.activeDispatchId ?? 'none'}, status: ${current?.status ?? 'missing'})`,
      );
      return { applied: false, job: current };
    }
    if (settled.refund && settled.refund.amount > 0) {
      console.log(
        `[JobService] Refunded ${Math.abs(settled.refund.amount)} credits for failed job ${jobId} ` +
        `dispatch ${dispatchId}`,
      );
    }
    return { applied: true, job: settled.job };
  }

  // A callback with no dispatch identity is only valid for a genuinely legacy job that also has
  // no active dispatch. Treating omission as "skip the guard" would let an old worker terminate
  // and refund a newer, dispatch-scoped attempt.
  if (existingJob.activeDispatchId) {
    console.warn(
      `[JobService] Ignoring identityless failure for job ${jobId}; ` +
      `active dispatch is ${existingJob.activeDispatchId}`,
    );
    return {
      applied: false,
      job: await prisma.job.findUnique({ where: { id: jobId } }),
    };
  }

  // Terminal write as a CAS, not a bare update().
  //
  // The status was read above, and an unconditional update() by id would blindly overwrite
  // whatever happened in between — most importantly a CANCEL. Cancel and fail were racing for the
  // terminal status: whichever wrote LAST won the status, but BOTH refunded, so the same job could
  // be settled twice and the same user action could have two prices. Now exactly one of them can
  // win the transition, and only the winner pays out.
  const claimed = await prisma.job.updateMany({
    where: {
      id: jobId,
      status: recoveryFence?.status ?? { in: validPreFailStatuses },
      activeDispatchId: null,
      ...(recoveryFence ? { lastHeartbeat: recoveryFence.lastHeartbeat } : {}),
    },
    data: failureData,
  });

  if (claimed.count === 0) {
    // Somebody else reached a terminal state first (a cancel, almost always). They own the
    // settlement; we must not refund on top of it.
    const current = await prisma.job.findUnique({ where: { id: jobId } });
    console.log(
      `[JobService] Job ${jobId} was settled concurrently (now ${current?.status}) — not failing, not refunding`
    );
    return { applied: false, job: current };
  }

  const job = await prisma.job.findUnique({ where: { id: jobId } });

  // A segmented job never paid for a stage called 'discovery', so the mapping below would look for
  // a charge that does not exist and refund NOTHING — silently turning "we broke it, here's your
  // money back" into "we broke it, you keep nothing". Refund the segment that was actually in
  // flight, named by its dispatch.
  if (job?.billingModel === BillingModel.GUIDED_SEGMENTS_V1) {
    try {
      // NOT filtered to `segment: { not: null }` — that filter is exactly what made this branch
      // find nothing for the two dispatches opened with no segment at all (job creation's
      // guided_s1 charge, and the post-select-solution deep_research charge; see jobs.ts), silently
      // skipping the refund entirely. Take the most recent open dispatch regardless, and fall back
      // to naming the implicit stage below when it carries no segment of its own.
      const inFlight = await prisma.jobDispatch.findFirst({
        where: {
          jobId,
          state: { in: [DispatchState.AUTHORIZED, DispatchState.CLAIMED] },
        },
        orderBy: { createdAt: 'desc' },
      });
      if (inFlight) {
        let stage: StageName | null = null;
        if (inFlight.segment && inFlight.chargeId) {
          if (!isGuidedSegment(inFlight.segment)) {
            console.warn(`[JobService] Dispatch ${inFlight.id} has unrecognised segment '${inFlight.segment}' — skipping refund`);
          } else {
            stage = inFlight.segment;
          }
        } else if (inFlight.kind === DispatchKind.CONTINUE && inFlight.gateStage == null) {
          // Same two "no identity" dispatches as cancelJob's guided branch above — mirror its
          // fallback (empty selection = the creation charge, non-empty = the phase-2 charge).
          stage = ((job.selectedSolutions as string[] | null)?.length ?? 0) > 0 ? 'deep_research' : 'guided_s1';
        }

        if (stage) {
          const refund = await refundForStage(jobId, stage);
          const refundedAmount = Math.max(refund?.amount ?? 0, 0);
          if (refundedAmount > 0) {
            console.log(
              `[JobService] Refunded ${refundedAmount} credits for failed guided job ${jobId} ` +
              `(stage ${stage})`
            );
          }
          await prisma.jobDispatch.updateMany({
            where: { id: inFlight.id },
            data: {
              state: refundedAmount > 0 ? DispatchState.REFUNDED : DispatchState.FAILED,
              settledAt: new Date(),
            },
          });
        }
      }
    } catch (refundError) {
      console.error(`[JobService] Failed to refund segment for failed job ${jobId}:`, refundError);
    }
    return { applied: true, job };
  }

  // Stage inference is a legacy-only fallback. Modern attempts settle the exact dispatch charge
  // above; reaching this branch proves both the callback and Job lack a dispatch identity.
  try {
    const failedStage = determineFailedStage(errorStage, existingJob.status);
    if (failedStage) {
      const refund = await refundForStage(jobId, failedStage);
      if (refund && refund.amount > 0) {
        console.log(`[JobService] Auto-refunded ${refund.amount} credits for failed job ${jobId} stage ${failedStage}`);
      }
    } else if (existingJob.status === JobStatus.REGENERATING) {
      // Numbered regeneration stage — use count from initial SELECT
      if (existingJob.regenerationCount) {
        const refund = await refundForRegenerationStage(jobId, existingJob.regenerationCount);
        if (refund && refund.amount > 0) {
          console.log(`[JobService] Auto-refunded ${refund.amount} credits for crashed regen job ${jobId}`);
        }
      }
    }
  } catch (refundError) {
    // Log but don't fail the failJob operation
    console.error(`[JobService] Failed to auto-refund credit for job ${jobId}:`, refundError);
  }

  return { applied: true, job };
}

/**
 * List jobs with pagination
 */
export async function listJobs(options?: {
  userId?: string;
  status?: JobStatus;
  limit?: number;
  offset?: number;
}) {
  const { userId, status, limit = 20, offset = 0 } = options || {};

  const where: Prisma.JobWhereInput = {};
  if (userId) where.userId = userId;
  if (status) where.status = status;

  const [jobs, total] = await Promise.all([
    prisma.job.findMany({
      where,
      include: {
        progress: {
          orderBy: { stageNumber: 'asc' },
        },
        assets: true,
      },
      orderBy: { createdAt: 'desc' },
      take: limit,
      skip: offset,
    }),
    prisma.job.count({ where }),
  ]);

  return { jobs, total, limit, offset };
}
