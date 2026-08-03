import path from 'node:path';
import { randomUUID } from 'node:crypto';
import {
  AssetType,
  DispatchKind,
  DispatchState,
  JobStatus,
  Prisma,
} from '@prisma/client';

import { prisma } from './db.js';
import { refundChargeInTx } from './creditService.js';
import {
  buildRegenerationEnvelope,
  buildRegenerationReceiptContent,
  buildSeedEnvelope,
  buildSeedReceiptContent,
} from '../utils/ledgerEvents.js';

export type PaidPoolRecoveryJournal = {
  schemaVersion: 1;
  lockPath: string;
  files: Array<{ canonicalPath: string; backupPath: string }>;
};

const POOL_KINDS = [DispatchKind.SEED_IDEA, DispatchKind.REGENERATE] as const;
const POOL_STATUSES = [JobStatus.RUNNING, JobStatus.REGENERATING] as const;

function backupPath(canonicalPath: string, dispatchId: string): string {
  return `${canonicalPath}.paid-op-${dispatchId}.before`;
}

export function buildPaidPoolRecoveryJournal(
  checkpointPath: string,
  previewPath: string,
  dispatchId: string,
): PaidPoolRecoveryJournal {
  const stagePath = path.join(checkpointPath, 'stage_5_3_refinement.json');
  const metadataPath = path.join(checkpointPath, 'metadata.json');
  return {
    schemaVersion: 1,
    lockPath: path.join(checkpointPath, '.paid-pool.lock'),
    files: [stagePath, metadataPath, previewPath].map((canonicalPath) => ({
      canonicalPath,
      backupPath: backupPath(canonicalPath, dispatchId),
    })),
  };
}

function sameJournal(a: unknown, b: PaidPoolRecoveryJournal): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}

/** Register the before-image after its files exist and before the worker may mutate them. */
export async function preparePaidPoolMutation(args: {
  jobId: string;
  dispatchId: string;
  workerId: string;
  checkpointPath: string;
  previewPath: string;
}): Promise<'prepared' | 'idempotent' | 'stale'> {
  const [job, previewAsset, dispatch] = await Promise.all([
    prisma.job.findUnique({
      where: { id: args.jobId },
      select: { status: true, activeDispatchId: true, phase1CheckpointPath: true, workerId: true },
    }),
    prisma.jobAsset.findUnique({
      where: { jobId_assetType: { jobId: args.jobId, assetType: AssetType.PREVIEW_REPORT } },
      select: { filePath: true },
    }),
    prisma.jobDispatch.findUnique({
      where: { id: args.dispatchId },
      select: {
        jobId: true,
        kind: true,
        state: true,
        workerId: true,
        recoveryPreparedAt: true,
        recoveryJournal: true,
      },
    }),
  ]);
  if (
    !job
    || job.activeDispatchId !== args.dispatchId
    || !POOL_STATUSES.includes(job.status as (typeof POOL_STATUSES)[number])
    || job.workerId !== args.workerId
    || job.phase1CheckpointPath !== args.checkpointPath
    || previewAsset?.filePath !== args.previewPath
    || dispatch?.jobId !== args.jobId
    || !POOL_KINDS.includes(dispatch.kind as (typeof POOL_KINDS)[number])
    || dispatch.state !== DispatchState.CLAIMED
    || dispatch.workerId !== args.workerId
  ) {
    return 'stale';
  }

  const journal = buildPaidPoolRecoveryJournal(
    args.checkpointPath,
    args.previewPath,
    args.dispatchId,
  );
  if (dispatch.recoveryPreparedAt) {
    return sameJournal(dispatch.recoveryJournal, journal) ? 'idempotent' : 'stale';
  }

  const prepared = await prisma.jobDispatch.updateMany({
    where: {
      id: args.dispatchId,
      jobId: args.jobId,
      kind: { in: [...POOL_KINDS] },
      state: DispatchState.CLAIMED,
      workerId: args.workerId,
      recoveryPreparedAt: null,
    },
    data: {
      recoveryJournal: journal as unknown as Prisma.InputJsonValue,
      recoveryPreparedAt: new Date(),
    },
  });
  return prepared.count === 1 ? 'prepared' : 'stale';
}

export type PaidPoolRecoveryFence = {
  status: JobStatus;
  workerId: string | null;
  lastHeartbeat: Date | null;
};

/** Settle a dead CLAIMED writer only if it never crossed the durable prepare boundary.
 * Job is locked first; if prepare wins the dispatch CAS, this transaction rolls the Job back. */
export async function failUnpreparedPaidPoolMutation(
  jobId: string,
  dispatchId: string,
  fence: PaidPoolRecoveryFence,
): Promise<boolean> {
  class SettlementConflict extends Error {}
  try {
    await prisma.$transaction(async (tx) => {
      const job = await tx.job.updateMany({
        where: {
          id: jobId,
          status: fence.status,
          activeDispatchId: dispatchId,
          workerId: fence.workerId,
          lastHeartbeat: fence.lastHeartbeat,
        },
        data: {
          status: JobStatus.AWAITING_SELECTION,
          activeDispatchId: null,
          workerId: null,
          lastHeartbeat: null,
        },
      });
      if (job.count !== 1) throw new SettlementConflict();
      const dispatch = await tx.jobDispatch.findUnique({
        where: { id: dispatchId },
        select: {
          jobId: true,
          kind: true,
          state: true,
          workerId: true,
          recoveryPreparedAt: true,
          chargeId: true,
          sourceMessageId: true,
          segment: true,
          batchOrdinal: true,
        },
      });
      if (
        dispatch?.jobId !== jobId
        || !POOL_KINDS.includes(dispatch.kind as (typeof POOL_KINDS)[number])
        || dispatch.state !== DispatchState.CLAIMED
        || dispatch.workerId !== fence.workerId
        || dispatch.recoveryPreparedAt !== null
      ) {
        throw new SettlementConflict();
      }
      const terminal = await tx.jobDispatch.updateMany({
        where: {
          id: dispatchId,
          state: DispatchState.CLAIMED,
          workerId: fence.workerId,
          recoveryPreparedAt: null,
        },
        data: {
          state: DispatchState.FAILED,
          failureKind: 'WORKER_LEASE_EXPIRED',
          settledAt: new Date(),
        },
      });
      if (terminal.count !== 1) throw new SettlementConflict();

      const refund = dispatch.chargeId
        ? await refundChargeInTx(tx, dispatch.chargeId)
        : null;
      const actuallyRefunded = Boolean(refund && refund.amount > 0);
      if (actuallyRefunded) {
        await tx.jobDispatch.update({
          where: { id: dispatchId },
          data: {
            state: DispatchState.REFUNDED,
            refundTransactionId: refund!.id,
            refundedAt: new Date(),
            refundedAmount: refund!.amount,
          },
        });
      }

      if (dispatch.kind === DispatchKind.SEED_IDEA && dispatch.sourceMessageId) {
        const outcome = actuallyRefunded ? 'refunded' : 'failed';
        await tx.chatMessage.create({
          data: {
            jobId,
            gateStage: 5,
            role: 'receipt',
            content: buildSeedReceiptContent('seed_settled', outcome),
            patchJson: buildSeedEnvelope(
              'seed_settled', dispatch.sourceMessageId, outcome, undefined, dispatchId,
            ) as unknown as Prisma.InputJsonValue,
          },
        });
      }
      if (dispatch.kind === DispatchKind.REGENERATE) {
        const ordinal = dispatch.batchOrdinal ?? Number(dispatch.segment?.match(/(\d+)$/)?.[1] ?? 0);
        const outcome = actuallyRefunded ? 'refunded' : 'failed';
        await tx.chatMessage.upsert({
          where: { operationId: `regeneration:${dispatchId}:settled` },
          create: {
            jobId,
            gateStage: 5,
            role: 'receipt',
            content: buildRegenerationReceiptContent('regeneration_settled', outcome),
            operationId: `regeneration:${dispatchId}:settled`,
            patchJson: buildRegenerationEnvelope({
              event: 'regeneration_settled',
              operationId: dispatchId,
              ordinal,
              outcome,
              refunded: actuallyRefunded,
            }) as unknown as Prisma.InputJsonValue,
          },
          update: {},
        });
      }
    });
    return true;
  } catch (error) {
    if (error instanceof SettlementConflict) return false;
    throw error;
  }
}

/** Fence a dead writer. The parent stays closed until restoration reports completion. */
export async function fencePaidPoolMutationForRecovery(
  jobId: string,
  dispatchId: string,
  fence: PaidPoolRecoveryFence,
): Promise<{ recoveryToken: string; journal: PaidPoolRecoveryJournal } | null> {
  const recoveryToken = randomUUID();
  class FenceConflict extends Error {}
  try {
    return await prisma.$transaction(async (tx) => {
      const job = await tx.job.updateMany({
        where: {
          id: jobId,
          status: fence.status,
          activeDispatchId: dispatchId,
          workerId: fence.workerId,
          lastHeartbeat: fence.lastHeartbeat,
        },
        data: { workerId: null, lastHeartbeat: new Date() },
      });
      if (job.count !== 1) throw new FenceConflict();

      const dispatch = await tx.jobDispatch.findUnique({
        where: { id: dispatchId },
        select: {
          jobId: true,
          kind: true,
          state: true,
          workerId: true,
          recoveryPreparedAt: true,
          recoveryJournal: true,
        },
      });
      if (
        dispatch?.jobId !== jobId
        || !POOL_KINDS.includes(dispatch.kind as (typeof POOL_KINDS)[number])
        || dispatch.state !== DispatchState.CLAIMED
        || dispatch.workerId !== fence.workerId
        || !dispatch.recoveryPreparedAt
        || !dispatch.recoveryJournal
      ) {
        throw new FenceConflict();
      }
      const fenced = await tx.jobDispatch.updateMany({
        where: {
          id: dispatchId,
          state: DispatchState.CLAIMED,
          workerId: fence.workerId,
          recoveryPreparedAt: { not: null },
        },
        data: {
          state: DispatchState.RECOVERING,
          workerId: null,
          claimedAt: null,
          recoveryToken,
        },
      });
      if (fenced.count !== 1) throw new FenceConflict();
      return {
        recoveryToken,
        journal: dispatch.recoveryJournal as unknown as PaidPoolRecoveryJournal,
      };
    });
  } catch (error) {
    if (error instanceof FenceConflict) return null;
    throw error;
  }
}

/** Rotate a dead recovery worker's token. A late restore can no longer settle the attempt. */
export async function refencePaidPoolRecovery(
  jobId: string,
  dispatchId: string,
  priorToken: string,
  fence: PaidPoolRecoveryFence,
): Promise<{ recoveryToken: string; journal: PaidPoolRecoveryJournal } | null> {
  const recoveryToken = randomUUID();
  class FenceConflict extends Error {}
  try {
    return await prisma.$transaction(async (tx) => {
      const job = await tx.job.updateMany({
        where: {
          id: jobId,
          status: fence.status,
          activeDispatchId: dispatchId,
          workerId: fence.workerId,
          lastHeartbeat: fence.lastHeartbeat,
        },
        data: { workerId: null, lastHeartbeat: new Date() },
      });
      if (job.count !== 1) throw new FenceConflict();
      const dispatch = await tx.jobDispatch.findUnique({
        where: { id: dispatchId },
        select: { state: true, workerId: true, recoveryToken: true, recoveryJournal: true },
      });
      if (
        dispatch?.state !== DispatchState.RECOVERING
        || dispatch.workerId !== fence.workerId
        || dispatch.recoveryToken !== priorToken
        || !dispatch.recoveryJournal
      ) {
        throw new FenceConflict();
      }
      const updated = await tx.jobDispatch.updateMany({
        where: {
          id: dispatchId,
          state: DispatchState.RECOVERING,
          workerId: fence.workerId,
          recoveryToken: priorToken,
        },
        data: { workerId: null, claimedAt: null, recoveryToken },
      });
      if (updated.count !== 1) throw new FenceConflict();
      return {
        recoveryToken,
        journal: dispatch.recoveryJournal as unknown as PaidPoolRecoveryJournal,
      };
    });
  } catch (error) {
    if (error instanceof FenceConflict) return null;
    throw error;
  }
}

export async function startPaidPoolRecovery(args: {
  jobId: string;
  dispatchId: string;
  recoveryToken: string;
  workerId: string;
}): Promise<'started' | 'retry' | false> {
  class ClaimConflict extends Error {}
  try {
    return await prisma.$transaction(async (tx) => {
      const started = await tx.job.updateMany({
        where: {
          id: args.jobId,
          status: { in: [...POOL_STATUSES] },
          activeDispatchId: args.dispatchId,
          workerId: null,
        },
        data: { workerId: args.workerId, lastHeartbeat: new Date() },
      });
      if (started.count === 0) {
        const [job, dispatch] = await Promise.all([
          tx.job.findUnique({
            where: { id: args.jobId },
            select: { activeDispatchId: true, workerId: true },
          }),
          tx.jobDispatch.findUnique({
            where: { id: args.dispatchId },
            select: { state: true, workerId: true, recoveryToken: true },
          }),
        ]);
        return job?.activeDispatchId === args.dispatchId
          && job.workerId === args.workerId
          && dispatch?.state === DispatchState.RECOVERING
          && dispatch.workerId === args.workerId
          && dispatch.recoveryToken === args.recoveryToken
          ? 'retry'
          : false;
      }
      const claimed = await tx.jobDispatch.updateMany({
        where: {
          id: args.dispatchId,
          jobId: args.jobId,
          state: DispatchState.RECOVERING,
          workerId: null,
          recoveryToken: args.recoveryToken,
        },
        data: { workerId: args.workerId, claimedAt: new Date() },
      });
      if (claimed.count !== 1) throw new ClaimConflict();
      return 'started';
    });
  } catch (error) {
    if (error instanceof ClaimConflict) return false;
    throw error;
  }
}

export async function completePaidPoolRecovery(args: {
  jobId: string;
  dispatchId: string;
  recoveryToken: string;
  workerId: string;
}): Promise<'completed' | 'idempotent' | 'stale'> {
  const snapshot = await prisma.jobDispatch.findUnique({
    where: { id: args.dispatchId },
    select: {
      jobId: true,
      kind: true,
      state: true,
      workerId: true,
      recoveryToken: true,
      chargeId: true,
      seedOrdinal: true,
      sourceMessageId: true,
      segment: true,
      batchOrdinal: true,
    },
  });
  if (
    snapshot?.jobId === args.jobId
    && snapshot.recoveryToken === args.recoveryToken
    && (snapshot.state === DispatchState.REFUNDED || snapshot.state === DispatchState.FAILED)
  ) {
    return 'idempotent';
  }
  if (
    snapshot?.jobId !== args.jobId
    || !POOL_KINDS.includes(snapshot.kind as (typeof POOL_KINDS)[number])
    || snapshot.state !== DispatchState.RECOVERING
    || snapshot.workerId !== args.workerId
    || snapshot.recoveryToken !== args.recoveryToken
  ) {
    return 'stale';
  }

  class CompletionConflict extends Error {}
  try {
    await prisma.$transaction(async (tx) => {
      const job = await tx.job.updateMany({
        where: {
          id: args.jobId,
          status: { in: [...POOL_STATUSES] },
          activeDispatchId: args.dispatchId,
          workerId: args.workerId,
        },
        data: {
          status: JobStatus.AWAITING_SELECTION,
          activeDispatchId: null,
          workerId: null,
          lastHeartbeat: null,
        },
      });
      if (job.count !== 1) throw new CompletionConflict();

      const refund = snapshot.chargeId
        ? await refundChargeInTx(tx, snapshot.chargeId)
        : null;
      const actuallyRefunded = Boolean(refund && refund.amount > 0);
      const settled = await tx.jobDispatch.updateMany({
        where: {
          id: args.dispatchId,
          state: DispatchState.RECOVERING,
          workerId: args.workerId,
          recoveryToken: args.recoveryToken,
        },
        data: {
          state: actuallyRefunded ? DispatchState.REFUNDED : DispatchState.FAILED,
          failureKind: 'WORKER_LEASE_EXPIRED',
          settledAt: new Date(),
          refundTransactionId: actuallyRefunded ? refund!.id : undefined,
          refundedAt: actuallyRefunded ? new Date() : undefined,
          refundedAmount: actuallyRefunded ? refund!.amount : undefined,
        },
      });
      if (settled.count !== 1) throw new CompletionConflict();

      if (snapshot.kind === DispatchKind.SEED_IDEA && snapshot.sourceMessageId) {
        await tx.chatMessage.create({
          data: {
            jobId: args.jobId,
            gateStage: 5,
            role: 'receipt',
            content: buildSeedReceiptContent(
              'seed_settled',
              actuallyRefunded ? 'refunded' : 'failed',
            ),
            patchJson: buildSeedEnvelope(
              'seed_settled',
              snapshot.sourceMessageId,
              actuallyRefunded ? 'refunded' : 'failed',
              undefined,
              args.dispatchId,
            ) as unknown as Prisma.InputJsonValue,
          },
        });
      }
      if (snapshot.kind === DispatchKind.REGENERATE) {
        const ordinal = snapshot.batchOrdinal ?? Number(snapshot.segment?.match(/(\d+)$/)?.[1] ?? 0);
        await tx.chatMessage.upsert({
          where: { operationId: `regeneration:${args.dispatchId}:settled` },
          create: {
            jobId: args.jobId,
            gateStage: 5,
            role: 'receipt',
            content: buildRegenerationReceiptContent(
              'regeneration_settled',
              actuallyRefunded ? 'refunded' : 'failed',
            ),
            operationId: `regeneration:${args.dispatchId}:settled`,
            patchJson: buildRegenerationEnvelope({
              event: 'regeneration_settled',
              operationId: args.dispatchId,
              ordinal,
              outcome: actuallyRefunded ? 'refunded' : 'failed',
              refunded: actuallyRefunded,
            }) as unknown as Prisma.InputJsonValue,
          },
          update: {},
        });
      }
    });
    return 'completed';
  } catch (error) {
    if (error instanceof CompletionConflict) return 'stale';
    throw error;
  }
}
