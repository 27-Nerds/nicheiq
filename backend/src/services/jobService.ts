import { prisma } from './db.js';
import { JobStatus, StageStatus, AssetType, Prisma, BillingModel, DispatchState, DispatchKind } from '@prisma/client';
import { PIPELINE_STAGES, TOTAL_STAGES } from '../types/job.js';
import { determineFailedStage, refundForStage, refundForRegenerationStage, refundForSeedIdeaStage, isGuidedSegment, type StageName } from './creditService.js';
import { buildSeedEnvelope, buildSeedReceiptContent } from '../utils/ledgerEvents.js';

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
  details?: Record<string, unknown>
) {
  const now = new Date();

  // Get current stage status to avoid overwriting historical data on resume
  const currentStage = await prisma.jobProgress.findUnique({
    where: { jobId_stageNumber: { jobId, stageNumber } },
    select: { status: true, startedAt: true, completedAt: true, durationSeconds: true },
  });

  // Skip update if stage is already completed (preserve historical timestamps during resume)
  // BUT still persist details/artifact if provided (handles resume/reload artifact population)
  if (currentStage?.status === StageStatus.COMPLETED && (status === StageStatus.COMPLETED || status === StageStatus.SKIPPED)) {
    if (details) {
      await prisma.jobProgress.update({
        where: { jobId_stageNumber: { jobId, stageNumber } },
        data: { details: details as Prisma.InputJsonValue },
      });
    }
    const existingProgress = await prisma.jobProgress.findUnique({
      where: { jobId_stageNumber: { jobId, stageNumber } },
    });
    return existingProgress;
  }

  // Upsert: creates the row if it doesn't exist yet (forward compat for new stages)
  const stageName = PIPELINE_STAGES.find(s => s.number === stageNumber)?.name ?? `Stage ${stageNumber}`;
  const progress = await prisma.jobProgress.upsert({
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
    await prisma.jobProgress.update({
      where: { id: progress.id },
      data: {
        durationSeconds: (progress.completedAt.getTime() - progress.startedAt.getTime()) / 1000,
      },
    });
  }

  // Update job's current stage and progress percent
  const [completedStages, jobRecord] = await Promise.all([
    prisma.jobProgress.count({
      where: {
        jobId,
        status: { in: [StageStatus.COMPLETED, StageStatus.SKIPPED] },
      },
    }),
    prisma.job.findUnique({
      where: { id: jobId },
      select: { totalStages: true },
    }),
  ]);

  const dynamicTotal = Math.max(jobRecord?.totalStages ?? TOTAL_STAGES, TOTAL_STAGES);

  await prisma.job.update({
    where: { id: jobId },
    data: {
      currentStage: stageNumber,
      currentStageName: stageName,
      stagesCompleted: completedStages,
      progressPercent: (completedStages / dynamicTotal) * 100,
    },
  });

  return progress;
}

/**
 * Add an asset to a job
 */
export async function addJobAsset(
  jobId: string,
  assetType: AssetType,
  filePath: string,
  fileSizeBytes?: number
) {
  return prisma.jobAsset.upsert({
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
      select: { id: true, kind: true, seedOrdinal: true, sourceMessageId: true },
    });
    if (dispatch?.kind === DispatchKind.SEED_IDEA) {
      return cancelSeedIdeaDispatch(jobId, dispatch, existing.status, 'CANCELLED_BY_USER');
    }
  }

  if (!CANCELLABLE_STATUSES.includes(existing.status)) {
    return { cancelled: false, reason: 'not_cancellable', status: existing.status };
  }

  // Exclusive claim on the terminal state. If a failure got here first, count is 0 and we do
  // nothing — including no refund.
  const claimed = await prisma.job.updateMany({
    where: { id: jobId, status: { in: CANCELLABLE_STATUSES } },
    data: {
      status: JobStatus.CANCELLED,
      errorMessage: 'Cancelled by user',
      completedAt: new Date(),
      // Disarm the dispatch CAS. A worker still running this job can no longer mutate it — which
      // is what stops a matching-but-late callback from dragging a cancelled job back to life.
      activeDispatchId: null,
    },
  });

  if (claimed.count === 0) {
    const current = await prisma.job.findUnique({ where: { id: jobId }, select: { status: true } });
    return { cancelled: false, reason: 'not_cancellable', status: current?.status };
  }

  // Only reachable by the winner of the CAS, so each of these happens exactly once.
  if (existing.status === JobStatus.QUEUED) {
    const { removeJobFromQueue } = await import('./queueService.js');
    await removeJobFromQueue(jobId).catch((err) =>
      console.error(`[JobService] Failed to remove cancelled job ${jobId} from the queue:`, err)
    );
  }

  await prisma.jobProgress.updateMany({
    where: { jobId, status: StageStatus.RUNNING },
    data: { status: StageStatus.FAILED, errorMessage: 'Cancelled by user' },
  });

  // What the user is owed, which depends on the contract the run was sold under.
  const billing = await prisma.job.findUnique({
    where: { id: jobId },
    select: { billingModel: true, selectedSolutions: true },
  });

  const open = await prisma.jobDispatch.findMany({
    where: { jobId, state: { in: [DispatchState.AUTHORIZED, DispatchState.CLAIMED] } },
    select: { id: true, state: true, segment: true, chargeId: true, kind: true, gateStage: true },
  });

  await prisma.jobDispatch.updateMany({
    where: { jobId, state: { in: [DispatchState.AUTHORIZED, DispatchState.CLAIMED] } },
    data: { state: DispatchState.FAILED, failureKind: 'CANCELLED_BY_USER', settledAt: new Date() },
  });

  let creditRefunded = 0;
  try {
    if (billing?.billingModel === BillingModel.GUIDED_SEGMENTS_V1) {
      // Segment billing: you keep what you bought and it ran; you get back what nobody started.
      //
      // AUTHORIZED means the charge was taken but no worker ever claimed the work — the user paid
      // for nothing, so it comes back. CLAIMED means a worker picked it up and the analysis ran;
      // that segment was authorized at a checkpoint that told them the price, and it is not owed
      // back. This is what makes "pay for work that ran" literally true rather than a slogan.
      //
      // Note what is NOT here: no proration, no consumed-stage arithmetic, no reading of live
      // prices. Those were all consequences of charging up front, and charging as work is
      // authorized removes them rather than fixing them.
      for (const d of open) {
        if (d.state !== DispatchState.AUTHORIZED) continue;

        let stage: StageName | null = null;
        if (d.segment && d.chargeId) {
          if (!isGuidedSegment(d.segment)) {
            console.warn(`[JobService] Dispatch ${d.id} has unrecognised segment '${d.segment}' — skipping refund`);
            continue;
          }
          stage = d.segment;
        } else if (d.kind === DispatchKind.CONTINUE && d.gateStage == null) {
          // No segment recorded — these are the two dispatches opened with no identity at all
          // (jobs.ts: the job-creation dispatch, and the post-select-solution phase-2 dispatch).
          // A segment-only lookup would silently lose them, so fall back to naming the stage the
          // same way the charge itself was named — 'guided_s1' before a solution is selected,
          // 'deep_research' after — mirroring how the DISCOVERY_PREPAID_V1 branch below refunds
          // by stage name rather than by dispatch linkage.
          stage = ((billing?.selectedSolutions as string[] | null)?.length ?? 0) > 0 ? 'deep_research' : 'guided_s1';
        }

        if (!stage) continue;

        const refund = await refundForStage(jobId, stage);
        if (refund) {
          creditRefunded += Math.abs(refund.amount);
          await prisma.jobDispatch.updateMany({
            where: { id: d.id },
            data: { state: DispatchState.REFUNDED },
          });
        }
      }
    } else {
      // Prepaid (every non-guided run, and every guided run created before segment billing): the
      // whole discovery phase was charged at creation, so cancelling refunds it in full — exactly
      // as it always did.
      const refund = await refundForStage(jobId, 'discovery');
      if (refund) creditRefunded = Math.abs(refund.amount);
    }
  } catch (refundError) {
    console.error(`[JobService] Failed to refund credit for cancelled job ${jobId}:`, refundError);
  }

  return { cancelled: true, creditRefunded };
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
  dispatch: { id: string; seedOrdinal: number | null; sourceMessageId?: string | null },
  currentStatus: JobStatus,
  failureKind: string,
): Promise<CancelOutcome> {
  const reverted = await prisma.$transaction(async (tx) => {
    const result = await tx.job.updateMany({
      where: {
        id: jobId,
        status: { in: [JobStatus.QUEUED, JobStatus.RUNNING] },
        activeDispatchId: dispatch.id,
      },
      data: { status: JobStatus.AWAITING_SELECTION, activeDispatchId: null },
    });
    if (result.count === 0) return 0;

    await tx.jobDispatch.updateMany({
      where: { id: dispatch.id },
      data: { state: DispatchState.FAILED, failureKind, settledAt: new Date() },
    });

    // Durable 'seed_settled' receipt with outcome='refunded' — without this the durable
    // 'seed_submitted' receipt (written by POST /:jobId/seed-idea) stays 'pending' forever,
    // which pins the frontend's hasPendingSeed lock open permanently (mirrors /seed-failed's
    // own receipt write in workers.ts). Guard: if this dispatch predates sourceMessageId
    // (shouldn't happen, but be safe), skip the receipt — never throw over a missing id.
    if (dispatch.sourceMessageId) {
      await tx.chatMessage.create({
        data: {
          jobId,
          gateStage: 5,
          role: 'receipt',
          content: buildSeedReceiptContent('seed_settled', 'refunded'),
          patchJson: buildSeedEnvelope(
            'seed_settled', dispatch.sourceMessageId, 'refunded',
          ) as unknown as object,
        },
      });
    } else {
      console.warn(`[JobService] Seed dispatch ${dispatch.id} has no sourceMessageId — skipping seed_settled receipt`);
    }

    return result.count;
  });

  if (reverted === 0) {
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

  let creditRefunded = 0;
  if (dispatch.seedOrdinal != null) {
    try {
      const refund = await refundForSeedIdeaStage(jobId, dispatch.seedOrdinal);
      if (refund) {
        creditRefunded = Math.abs(refund.amount);
        await prisma.jobDispatch.updateMany({
          where: { id: dispatch.id },
          data: { state: DispatchState.REFUNDED },
        });
      }
    } catch (refundError) {
      console.error(`[JobService] Failed to refund seed idea credit for job ${jobId}:`, refundError);
    }
  }

  return { cancelled: true, creditRefunded };
}

export async function failJob(
  jobId: string,
  errorMessage: string,
  errorStage?: number,
  stopReason?: string,
  stopReasonDetails?: Record<string, any>,
  errorCode?: string,
  errorDetails?: Record<string, any>
) {
  // Check if job is already FAILED (idempotency)
  const existingJob = await prisma.job.findUnique({
    where: { id: jobId },
    select: { status: true, regenerationCount: true, activeDispatchId: true },
  });

  if (!existingJob) {
    console.log(`[JobService] Job ${jobId} not found`);
    return null;
  }

  if (existingJob.status === JobStatus.FAILED) {
    console.log(`[JobService] Job ${jobId} is already FAILED, skipping duplicate failJob() call`);
    return prisma.job.findUnique({ where: { id: jobId } });
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
    return null;
  }

  // Terminal write as a CAS, not a bare update().
  //
  // The status was read above, and an unconditional update() by id would blindly overwrite
  // whatever happened in between — most importantly a CANCEL. Cancel and fail were racing for the
  // terminal status: whichever wrote LAST won the status, but BOTH refunded, so the same job could
  // be settled twice and the same user action could have two prices. Now exactly one of them can
  // win the transition, and only the winner pays out.
  const claimed = await prisma.job.updateMany({
    where: { id: jobId, status: { in: validPreFailStatuses } },
    data: {
      status: JobStatus.FAILED,
      errorMessage,
      errorStage,
      stopReason: stopReason ?? null,
      stopReasonDetails: stopReasonDetails ?? Prisma.JsonNull,
      errorCode: errorCode ?? null,
      errorDetails: errorDetails ?? Prisma.JsonNull,
      // Disarm the CAS: a worker still in flight for this job can no longer mutate it.
      activeDispatchId: null,
    },
  });

  if (claimed.count === 0) {
    // Somebody else reached a terminal state first (a cancel, almost always). They own the
    // settlement; we must not refund on top of it.
    const current = await prisma.job.findUnique({ where: { id: jobId } });
    console.log(
      `[JobService] Job ${jobId} was settled concurrently (now ${current?.status}) — not failing, not refunding`
    );
    return current;
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
          if (refund) {
            console.log(
              `[JobService] Refunded ${Math.abs(refund.amount)} credits for failed guided job ${jobId} ` +
              `(stage ${stage})`
            );
          }
          await prisma.jobDispatch.updateMany({
            where: { id: inFlight.id },
            data: { state: DispatchState.REFUNDED, settledAt: new Date() },
          });
        }
      }
    } catch (refundError) {
      console.error(`[JobService] Failed to refund segment for failed job ${jobId}:`, refundError);
    }
    return job;
  }

  // Auto-refund the failed stage's credits. `activeDispatchKind` (read BEFORE the CAS above
  // nulled it) lets determineFailedStage recognise a SEED_IDEA dispatch and return null rather
  // than guessing 'discovery'/'deep_research' — a seed never charges either. In practice a
  // SEED_IDEA dispatch is intercepted earlier (cancelJob / heartbeatService's stale-job
  // recovery both branch on it before ever calling failJob), so this is defense-in-depth for
  // any path that reaches failJob directly with one still active.
  try {
    const activeDispatchKind = existingJob.activeDispatchId
      ? (await prisma.jobDispatch.findUnique({
          where: { id: existingJob.activeDispatchId },
          select: { kind: true },
        }))?.kind
      : null;
    const failedStage = determineFailedStage(errorStage, existingJob.status, activeDispatchKind);
    if (failedStage) {
      const refund = await refundForStage(jobId, failedStage);
      if (refund) {
        console.log(`[JobService] Auto-refunded ${Math.abs(refund.amount)} credits for failed job ${jobId} stage ${failedStage}`);
      }
    } else if (existingJob.status === JobStatus.REGENERATING) {
      // Numbered regeneration stage — use count from initial SELECT
      if (existingJob.regenerationCount) {
        const refund = await refundForRegenerationStage(jobId, existingJob.regenerationCount);
        if (refund) {
          console.log(`[JobService] Auto-refunded ${Math.abs(refund.amount)} credits for crashed regen job ${jobId}`);
        }
      }
    }
  } catch (refundError) {
    // Log but don't fail the failJob operation
    console.error(`[JobService] Failed to auto-refund credit for job ${jobId}:`, refundError);
  }

  return job;
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

