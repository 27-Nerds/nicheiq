import { DispatchKind, JobStatus } from '@prisma/client';

export type DiscoveryShareLifecycleContext = {
  status: JobStatus;
  activeDispatchKind?: DispatchKind | null;
};

export const DISCOVERY_SHARE_LIFECYCLE_JOB_SELECT = {
  status: true,
  activeDispatchId: true,
  dispatches: {
    select: { id: true, kind: true },
  },
} as const;

type DiscoveryShareLifecycleJob = {
  status: JobStatus;
  activeDispatchId: string | null;
  dispatches: ReadonlyArray<{ id: string; kind: DispatchKind }>;
};

/**
 * Discovery sharing follows the selection workspace, not the share row's active flag alone.
 * Append-only pool work keeps that workspace valid; Deep Research and every other job phase do not.
 */
export function isDiscoveryShareLifecycleOpen({
  status,
  activeDispatchKind = null,
}: DiscoveryShareLifecycleContext): boolean {
  if (activeDispatchKind === DispatchKind.DEEP_RESEARCH) return false;

  if (status === JobStatus.AWAITING_SELECTION || status === JobStatus.REGENERATING) {
    return true;
  }

  return (
    status === JobStatus.QUEUED || status === JobStatus.RUNNING
  ) && (
    activeDispatchKind === DispatchKind.REGENERATE
    || activeDispatchKind === DispatchKind.SEED_IDEA
  );
}

export function isDiscoveryShareLifecycleOpenForJob(
  job: DiscoveryShareLifecycleJob,
): boolean {
  const activeDispatchKind = job.activeDispatchId
    ? job.dispatches.find(dispatch => dispatch.id === job.activeDispatchId)?.kind ?? null
    : null;
  return isDiscoveryShareLifecycleOpen({ status: job.status, activeDispatchKind });
}
