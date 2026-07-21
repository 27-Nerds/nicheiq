import { Prisma } from '@prisma/client';
import { prisma } from './db.js';

export const selectionWorkspaceJobSelect = {
  id: true,
  status: true,
  solutionIdeas: true,
  selectionDecisionProfile: true,
  selectionFounderFit: true,
  selectionFinalDecision: { select: { id: true } },
} satisfies Prisma.JobSelect;

export type SelectionWorkspaceJob = Prisma.JobGetPayload<{
  select: typeof selectionWorkspaceJobSelect;
}>;

export async function findOwnedSelectionWorkspaceJob(jobId: string, userId: string) {
  return prisma.job.findFirst({
    where: { id: jobId, userId },
    select: selectionWorkspaceJobSelect,
  });
}

export async function findOwnedJob<T extends Prisma.JobSelect>(
  jobId: string,
  userId: string,
  select: T,
): Promise<Prisma.JobGetPayload<{ select: T }> | null> {
  return prisma.job.findFirst({
    where: { id: jobId, userId },
    select,
  }) as Promise<Prisma.JobGetPayload<{ select: T }> | null>;
}
