/**
 * Dispatch identity for worker callbacks.
 *
 * A dispatch is one attempt to run work for a job. Its id rides the queue payload and comes back
 * on every callback the worker makes, so the backend can tell "this is the attempt I am currently
 * expecting" from "this is a message from an attempt that has been superseded".
 *
 * Without it, callbacks correlate on (job, status, gateStage) — which is why a delayed /gate-failed
 * could revert a NEWER attempt, a duplicate /gate-reached could rewind a job that had already moved
 * on, and two workers could both run the same job.
 */
import {
  AssetType,
  Prisma,
  DispatchKind,
  DispatchState,
  JobStatus,
  StageStatus,
} from '@prisma/client';
import { prisma } from './db.js';
import { refundChargeInTx } from './creditService.js';

/**
 * The CAS predicate, as a `where` fragment that `updateMany` can satisfy from the Job row alone
 * (Prisma cannot join inside updateMany, which is why `activeDispatchId` is denormalised onto Job).
 *
 * Both branches are guards — neither is a bypass:
 *
 *   worker sent an id  -> the job's active dispatch must be EXACTLY that one.
 *   worker sent none   -> the job must have NO active dispatch.
 *
 * That second branch is the narrow legacy path, and its narrowness is the whole point. A worker
 * predating this change (or a message already sitting in the queue when it shipped) carries no id,
 * and must still be able to finish its job. But it may only do so for a job that was never given a
 * dispatch. If the job HAS an active dispatch and the callback doesn't name it, the callback is
 * stale — an old worker reporting on an attempt that has since been replaced — and it is rejected.
 *
 * Treating a missing id as "skip the check" would have reinstated every race this exists to close,
 * for exactly as long as one old worker survived anywhere in the fleet.
 */
export function dispatchGuard(dispatchId?: string | null): Prisma.JobWhereInput {
  return dispatchId ? { activeDispatchId: dispatchId } : { activeDispatchId: null };
}

/** Why a guarded callback matched no rows. Callers use this to answer the worker correctly. */
export type GuardMiss = 'stale_dispatch' | 'status' | 'not_found';

/**
 * Diagnose a zero-row CAS. The callback already failed to match; this only decides what to TELL the
 * worker, so it is a plain read.
 *
 * A stale dispatch is not an error — it is the system working. The worker is told `stale: true` and
 * asked to stop, rather than being handed a 4xx it would retry.
 */
export async function diagnoseGuardMiss(
  jobId: string,
  dispatchId: string | null | undefined,
  runnableStatuses: JobStatus[],
): Promise<GuardMiss> {
  const job = await prisma.job.findUnique({
    where: { id: jobId },
    select: { status: true, activeDispatchId: true },
  });
  if (!job) return 'not_found';
  // Compare against what the worker actually claimed, including the legacy "claimed nothing" case.
  // Both sides ?? null-normalised — an absent column reads `undefined`, and `undefined !== null`
  // would condemn a legitimate legacy callback as stale.
  const claimed = dispatchId ?? null;
  if ((job.activeDispatchId ?? null) !== claimed) return 'stale_dispatch';
  if (!runnableStatuses.includes(job.status)) return 'status';
  return 'status';
}

/**
 * Open a dispatch. MUST be called inside the same transaction as the charge and the status flip —
 * that is what makes the intent to run durable before the queue is touched, so an ambiguous enqueue
 * error can be RETRIED against this row instead of compensated. (Compensating an ambiguous error is
 * how you end up doing free work: the LPUSH may have landed even though the client saw a failure.)
 *
 * Writes Job.activeDispatchId in the same breath, so the CAS predicate is armed the moment the
 * transaction commits and can never lag behind the queue message.
 */
export async function openDispatch(
  tx: Prisma.TransactionClient,
  args: {
    jobId: string;
    kind: DispatchKind;
    gateStage?: number | null;
    /** CreditTransaction.stage this attempt paid for. Null when the attempt is free. */
    segment?: string | null;
    /** CreditTransaction.id — the exact row a failure must refund. Null when free. */
    chargeId?: string | null;
    /** SEED_IDEA only: the ordinal this attempt bought (Job.seedIdeaCount at open time) — the
     *  same number the seed_idea_N charge/refund uses. */
    seedOrdinal?: number | null;
    /** SEED_IDEA only: the durable chat message id that proposed this seed, for card identity. */
    sourceMessageId?: string | null;
    clientRequestId?: string | null;
    requestSnapshot?: Prisma.InputJsonValue | null;
    requestFingerprint?: string | null;
    workPayload?: Prisma.InputJsonValue | null;
    batchOrdinal?: number | null;
  },
): Promise<string> {
  const dispatch = await tx.jobDispatch.create({
    data: {
      jobId: args.jobId,
      kind: args.kind,
      gateStage: args.gateStage ?? null,
      segment: args.segment ?? null,
      chargeId: args.chargeId ?? null,
      seedOrdinal: args.seedOrdinal ?? null,
      sourceMessageId: args.sourceMessageId ?? null,
      clientRequestId: args.clientRequestId ?? null,
      requestSnapshot: args.requestSnapshot ?? undefined,
      requestFingerprint: args.requestFingerprint ?? null,
      workPayload: args.workPayload ?? undefined,
      batchOrdinal: args.batchOrdinal ?? null,
      state: DispatchState.AUTHORIZED,
    },
    select: { id: true },
  });

  await tx.job.update({
    where: { id: args.jobId },
    data: { activeDispatchId: dispatch.id },
  });

  return dispatch.id;
}

/**
 * Cancel one exact selection operation before any worker has crossed AUTHORIZED -> CLAIMED.
 * Job-first write ordering mirrors `startDispatchedJob`, so cancellation and worker claim cannot
 * both commit. The charge reversal is exact and part of the same transaction.
 */
export async function cancelAuthorizedSelectionDispatch(
  jobId: string,
  dispatchId: string,
): Promise<'cancelled' | 'started' | 'stale' | 'not_found'> {
  return prisma.$transaction(async (tx) => {
    const dispatch = await tx.jobDispatch.findFirst({
      where: { id: dispatchId, jobId },
      select: { id: true, kind: true, state: true, chargeId: true },
    });
    if (!dispatch) return 'not_found';
    if (dispatch.state !== DispatchState.AUTHORIZED) {
      return dispatch.state === DispatchState.CLAIMED ? 'started' : 'stale';
    }
    if (dispatch.kind !== DispatchKind.DEEP_RESEARCH && dispatch.kind !== DispatchKind.REGENERATE) {
      return 'stale';
    }

    const reverted = await tx.job.updateMany({
      where: {
        id: jobId,
        status: JobStatus.QUEUED,
        activeDispatchId: dispatchId,
      },
      data: {
        status: JobStatus.AWAITING_SELECTION,
        activeDispatchId: null,
        queuedAt: null,
        ...(dispatch.kind === DispatchKind.DEEP_RESEARCH
          ? {
              selectedSolutions: [],
              selectedSolutionIds: [],
              selectedSolutionRefs: Prisma.JsonNull,
              selectionRationale: null,
            }
          : {}),
      },
    });
    if (reverted.count !== 1) return 'stale';

    const terminal = await tx.jobDispatch.updateMany({
      where: { id: dispatchId, state: DispatchState.AUTHORIZED },
      data: { state: DispatchState.CANCELLED, settledAt: new Date(), failureKind: 'USER_CANCELLED' },
    });
    if (terminal.count !== 1) {
      throw new Error('DISPATCH_CANCEL_RACE');
    }

    if (dispatch.chargeId) {
      const refund = await refundChargeInTx(tx, dispatch.chargeId);
      if (refund) {
        await tx.jobDispatch.update({
          where: { id: dispatchId },
          data: {
            refundTransactionId: refund.id,
            refundedAt: new Date(),
            refundedAmount: refund.amount,
          },
        });
      }
    }
    return 'cancelled';
  });
}

/**
 * Atomically cross the worker-start billing boundary. Job first, Dispatch second: this matches
 * cancellation's lock order and makes CLAIMED mean the worker's start transition committed.
 * Returns `retry` only when this same worker already owns the committed Job + Dispatch pair;
 * returns false for cancellation, a stale dispatch, or a competing worker.
 */
export async function startDispatchedJob(
  dispatchId: string,
  workerId: string,
  start: { jobId: string; runningStatus: JobStatus },
): Promise<'started' | 'retry' | false> {
  class DispatchClaimConflictError extends Error {}

  try {
    return await prisma.$transaction(async (tx) => {
      // Job first, Dispatch second. Cancellation takes the same lock order, so whichever Job CAS
      // wins decides whether the segment started and CLAIMED can never commit on its own.
      const started = await tx.job.updateMany({
        where: {
          id: start.jobId,
          status: { in: [JobStatus.QUEUED, JobStatus.PENDING] },
          activeDispatchId: dispatchId,
        },
        data: {
          workerId,
          lastHeartbeat: new Date(),
          status: start.runningStatus,
          startedAt: new Date(),
          errorMessage: null,
        },
      });

      if (started.count === 0) {
        const [job, dispatch] = await Promise.all([
          tx.job.findUnique({
            where: { id: start.jobId },
            select: { status: true, activeDispatchId: true, workerId: true },
          }),
          tx.jobDispatch.findUnique({
            where: { id: dispatchId },
            select: { jobId: true, state: true, workerId: true },
          }),
        ]);
        const sameWorkerRetry =
          job?.status === start.runningStatus
          && job.activeDispatchId === dispatchId
          && job.workerId === workerId
          && dispatch?.jobId === start.jobId
          && dispatch.state === DispatchState.CLAIMED
          && dispatch.workerId === workerId;
        return sameWorkerRetry ? 'retry' : false;
      }

      const claimed = await tx.jobDispatch.updateMany({
        where: {
          id: dispatchId,
          jobId: start.jobId,
          OR: [{ state: DispatchState.AUTHORIZED }, { state: DispatchState.CLAIMED, workerId }],
        },
        data: { state: DispatchState.CLAIMED, workerId, claimedAt: new Date() },
      });
      if (claimed.count === 0) {
        throw new DispatchClaimConflictError();
      }
      return 'started';
    });
  } catch (error) {
    if (error instanceof DispatchClaimConflictError) return false;
    throw error;
  }
}

/**
 * Claim a landing-page auxiliary dispatch without changing the parent research Job out of
 * COMPLETED. The landing lifecycle is carried by landingPageStatus.
 */
export async function startLandingPageDispatch(
  dispatchId: string,
  workerId: string,
  jobId: string,
): Promise<'started' | 'retry' | false> {
  class LandingClaimConflictError extends Error {}

  try {
    return await prisma.$transaction(async (tx) => {
      const started = await tx.job.updateMany({
        where: {
          id: jobId,
          status: JobStatus.COMPLETED,
          landingPageStatus: 'QUEUED',
          activeDispatchId: dispatchId,
        },
        data: {
          landingPageStatus: 'RUNNING',
          workerId,
          lastHeartbeat: new Date(),
        },
      });

      if (started.count === 0) {
        const [job, dispatch] = await Promise.all([
          tx.job.findUnique({
            where: { id: jobId },
            select: {
              status: true,
              landingPageStatus: true,
              activeDispatchId: true,
              workerId: true,
            },
          }),
          tx.jobDispatch.findUnique({
            where: { id: dispatchId },
            select: {
              jobId: true,
              kind: true,
              segment: true,
              state: true,
              workerId: true,
            },
          }),
        ]);
        const sameWorkerRetry =
          job?.status === JobStatus.COMPLETED
          && job.landingPageStatus === 'RUNNING'
          && job.activeDispatchId === dispatchId
          && job.workerId === workerId
          && dispatch?.jobId === jobId
          && dispatch.kind === DispatchKind.CONTINUE
          && dispatch.segment === 'landing_page'
          && dispatch.state === DispatchState.CLAIMED
          && dispatch.workerId === workerId;
        return sameWorkerRetry ? 'retry' : false;
      }

      const claimed = await tx.jobDispatch.updateMany({
        where: {
          id: dispatchId,
          jobId,
          kind: DispatchKind.CONTINUE,
          segment: 'landing_page',
          OR: [
            { state: DispatchState.AUTHORIZED },
            { state: DispatchState.CLAIMED, workerId },
          ],
        },
        data: {
          state: DispatchState.CLAIMED,
          workerId,
          claimedAt: new Date(),
        },
      });
      if (claimed.count !== 1) throw new LandingClaimConflictError();
      return 'started';
    });
  } catch (error) {
    if (error instanceof LandingClaimConflictError) return false;
    throw error;
  }
}

/** Atomically publish the landing asset and settle its exact claimed dispatch. */
export async function completeLandingPageDispatch(
  jobId: string,
  dispatchId: string,
  landingPath: string,
): Promise<boolean> {
  class LandingCompletionConflictError extends Error {}

  try {
    return await prisma.$transaction(async (tx) => {
      const job = await tx.job.updateMany({
        where: {
          id: jobId,
          status: JobStatus.COMPLETED,
          landingPageStatus: { in: ['RUNNING', 'QUEUED'] },
          activeDispatchId: dispatchId,
        },
        data: {
          landingPageStatus: 'COMPLETED',
          activeDispatchId: null,
        },
      });
      if (job.count !== 1) throw new LandingCompletionConflictError();

      const dispatch = await tx.jobDispatch.updateMany({
        where: {
          id: dispatchId,
          jobId,
          kind: DispatchKind.CONTINUE,
          segment: 'landing_page',
          state: DispatchState.CLAIMED,
        },
        data: {
          state: DispatchState.COMPLETED,
          settledAt: new Date(),
        },
      });
      if (dispatch.count !== 1) throw new LandingCompletionConflictError();

      await tx.jobAsset.upsert({
        where: {
          jobId_assetType: { jobId, assetType: AssetType.LANDING_PAGE },
        },
        create: {
          jobId,
          assetType: AssetType.LANDING_PAGE,
          filePath: landingPath,
        },
        update: { filePath: landingPath },
      });
      const progress = await tx.jobProgress.updateMany({
        where: {
          jobId,
          stageNumber: 15,
          status: { in: [StageStatus.PENDING, StageStatus.RUNNING] },
        },
        data: {
          status: StageStatus.COMPLETED,
          errorMessage: null,
          completedAt: new Date(),
        },
      });
      if (progress.count !== 1) throw new LandingCompletionConflictError();
      return true;
    });
  } catch (error) {
    if (error instanceof LandingCompletionConflictError) return false;
    throw error;
  }
}

export type DeepResearchReportPublication = 'published' | 'idempotent' | 'stale';

/**
 * Publish the report artifact and settle its exact Deep Research attempt in one Job-first
 * transaction. Failure/refund uses the same first row, so publication and failure cannot both win.
 */
export async function publishDeepResearchReport(
  jobId: string,
  dispatchId: string,
  reportPath: string,
  resultSnapshot: Prisma.InputJsonValue,
  resultFingerprint: string,
  jobUpdate: Prisma.JobUpdateManyMutationInput,
): Promise<DeepResearchReportPublication> {
  class ReportPublicationConflictError extends Error {}

  try {
    return await prisma.$transaction(async (tx) => {
      const now = new Date();
      const job = await tx.job.updateMany({
        where: {
          id: jobId,
          status: JobStatus.RUNNING_PHASE2,
          activeDispatchId: dispatchId,
        },
        data: {
          ...jobUpdate,
          status: JobStatus.COMPLETED,
          completedAt: now,
          progressPercent: 100,
          activeDispatchId: null,
        },
      });
      if (job.count !== 1) throw new ReportPublicationConflictError();

      const dispatch = await tx.jobDispatch.updateMany({
        where: {
          id: dispatchId,
          jobId,
          kind: DispatchKind.DEEP_RESEARCH,
          state: DispatchState.CLAIMED,
          OR: [
            { resultFingerprint: null },
            { resultFingerprint },
          ],
        },
        data: {
          state: DispatchState.COMPLETED,
          settledAt: now,
          resultSnapshot,
          resultFingerprint,
        },
      });
      if (dispatch.count !== 1) throw new ReportPublicationConflictError();

      await tx.jobAsset.upsert({
        where: {
          jobId_assetType: { jobId, assetType: AssetType.REPORT_JSON },
        },
        create: {
          jobId,
          assetType: AssetType.REPORT_JSON,
          filePath: reportPath,
        },
        update: { filePath: reportPath },
      });
      await tx.jobProgress.updateMany({
        where: {
          jobId,
          stageNumber: 14,
          status: { in: [StageStatus.PENDING, StageStatus.RUNNING] },
        },
        data: {
          status: StageStatus.COMPLETED,
          errorMessage: null,
          completedAt: now,
        },
      });
      return 'published' as const;
    });
  } catch (error) {
    if (!(error instanceof ReportPublicationConflictError)) throw error;
  }

  const [job, dispatch, asset] = await Promise.all([
    prisma.job.findUnique({
      where: { id: jobId },
      select: { status: true, activeDispatchId: true },
    }),
    prisma.jobDispatch.findUnique({
      where: { id: dispatchId },
      select: {
        jobId: true,
        kind: true,
        state: true,
        resultFingerprint: true,
      },
    }),
    prisma.jobAsset.findUnique({
      where: {
        jobId_assetType: { jobId, assetType: AssetType.REPORT_JSON },
      },
      select: { filePath: true },
    }),
  ]);
  return (
    job?.status === JobStatus.COMPLETED
    && job.activeDispatchId === null
    && dispatch?.jobId === jobId
    && dispatch.kind === DispatchKind.DEEP_RESEARCH
    && dispatch.state === DispatchState.COMPLETED
    && dispatch.resultFingerprint === resultFingerprint
    && asset?.filePath === reportPath
  )
    ? 'idempotent'
    : 'stale';
}

/** Exact, idempotent failure settlement for the landing-page auxiliary attempt. */
export type LandingHeartbeatRecoveryFence = {
  landingPageStatus: string | null;
  lastHeartbeat: Date | null;
  updatedAt: Date;
};

export async function failLandingPageDispatch(
  jobId: string,
  dispatchId: string,
  errorMessage = 'Landing page generation failed',
  recoveryFence?: LandingHeartbeatRecoveryFence,
): Promise<boolean> {
  class LandingFailureConflictError extends Error {}

  try {
    return await prisma.$transaction(async (tx) => {
      const dispatch = await tx.jobDispatch.findFirst({
        where: {
          id: dispatchId,
          jobId,
          kind: DispatchKind.CONTINUE,
          segment: 'landing_page',
          state: { in: [DispatchState.AUTHORIZED, DispatchState.CLAIMED] },
        },
        select: { chargeId: true },
      });
      if (!dispatch) throw new LandingFailureConflictError();

      const job = await tx.job.updateMany({
        where: {
          id: jobId,
          status: JobStatus.COMPLETED,
          landingPageStatus: recoveryFence
            ? recoveryFence.landingPageStatus
            : { in: ['RUNNING', 'QUEUED'] },
          activeDispatchId: dispatchId,
          ...(recoveryFence
            ? {
                lastHeartbeat: recoveryFence.lastHeartbeat,
                updatedAt: recoveryFence.updatedAt,
              }
            : {}),
        },
        data: {
          landingPageStatus: 'FAILED',
          activeDispatchId: null,
        },
      });
      if (job.count !== 1) throw new LandingFailureConflictError();

      const refund = dispatch.chargeId
        ? await refundChargeInTx(tx, dispatch.chargeId)
        : null;
      const settled = await tx.jobDispatch.updateMany({
        where: {
          id: dispatchId,
          jobId,
          state: { in: [DispatchState.AUTHORIZED, DispatchState.CLAIMED] },
        },
        data: {
          state: refund ? DispatchState.REFUNDED : DispatchState.FAILED,
          failureKind: 'SYSTEM_FAULT',
          settledAt: new Date(),
          refundTransactionId: refund?.id,
          refundedAt: refund ? new Date() : undefined,
          refundedAmount: refund?.amount,
        },
      });
      if (settled.count !== 1) throw new LandingFailureConflictError();
      const progress = await tx.jobProgress.updateMany({
        where: {
          jobId,
          stageNumber: 15,
          status: { in: [StageStatus.PENDING, StageStatus.RUNNING] },
        },
        data: {
          status: StageStatus.FAILED,
          errorMessage,
          completedAt: new Date(),
        },
      });
      if (progress.count !== 1) throw new LandingFailureConflictError();
      return true;
    });
  } catch (error) {
    if (error instanceof LandingFailureConflictError) return false;
    throw error;
  }
}

/**
 * Low-level AUTHORIZED -> CLAIMED transition for callers that do not also start a Job.
 * Idempotent for the same worker and exclusive against a different worker.
 */
export async function claimDispatch(
  dispatchId: string,
  workerId: string,
): Promise<boolean> {
  const claimed = await prisma.jobDispatch.updateMany({
    where: {
      id: dispatchId,
      OR: [{ state: DispatchState.AUTHORIZED }, { state: DispatchState.CLAIMED, workerId }],
    },
    data: { state: DispatchState.CLAIMED, workerId, claimedAt: new Date() },
  });
  return claimed.count > 0;
}

/** Terminal settlement. `refunded` is set by the refund path once the credit is actually returned. */
export async function settleDispatch(
  tx: Prisma.TransactionClient,
  dispatchId: string,
  state: Extract<DispatchState, 'COMPLETED' | 'FAILED' | 'REFUNDED'> | DispatchState,
  failureKind?: string | null,
): Promise<void> {
  await tx.jobDispatch.updateMany({
    where: { id: dispatchId },
    data: { state, failureKind: failureKind ?? undefined, settledAt: new Date() },
  });
  // Disarm the CAS. Any callback still in flight for this dispatch now matches nothing, which is
  // precisely what we want once the attempt is over.
  await tx.job.updateMany({
    where: { activeDispatchId: dispatchId },
    data: { activeDispatchId: null },
  });
}

/** The dispatch a job is currently expecting a callback for, with the charge it must settle. */
export async function getActiveDispatch(jobId: string) {
  const job = await prisma.job.findUnique({
    where: { id: jobId },
    select: { activeDispatchId: true },
  });
  if (!job?.activeDispatchId) return null;
  return prisma.jobDispatch.findUnique({ where: { id: job.activeDispatchId } });
}
