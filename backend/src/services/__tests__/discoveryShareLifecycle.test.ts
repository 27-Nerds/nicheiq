import { describe, expect, it } from 'vitest';
import { DispatchKind, JobStatus } from '@prisma/client';
import {
  isDiscoveryShareLifecycleOpen,
  isDiscoveryShareLifecycleOpenForJob,
} from '../discoveryShareLifecycle.js';

describe('Discovery share lifecycle', () => {
  const dispatchKinds = [
    null,
    DispatchKind.CONTINUE,
    DispatchKind.APPLY_STAY,
    DispatchKind.REGENERATE,
    DispatchKind.SEED_IDEA,
    DispatchKind.DEEP_RESEARCH,
  ] as const;

  for (const status of Object.values(JobStatus)) {
    for (const activeDispatchKind of dispatchKinds) {
      const appendOnlyDispatch = activeDispatchKind === DispatchKind.REGENERATE
        || activeDispatchKind === DispatchKind.SEED_IDEA;
      const expected = activeDispatchKind !== DispatchKind.DEEP_RESEARCH && (
        status === JobStatus.AWAITING_SELECTION
        || status === JobStatus.REGENERATING
        || (
          (status === JobStatus.QUEUED || status === JobStatus.RUNNING)
          && appendOnlyDispatch
        )
      );

      it(`${expected ? 'allows' : 'rejects'} ${status} with ${activeDispatchKind ?? 'no dispatch'}`, () => {
        expect(isDiscoveryShareLifecycleOpen({ status, activeDispatchKind })).toBe(expected);
      });
    }
  }

  it('uses the dispatch named by activeDispatchId, not another dispatch in the job history', () => {
    expect(isDiscoveryShareLifecycleOpenForJob({
      status: JobStatus.RUNNING,
      activeDispatchId: 'seed-active',
      dispatches: [
        { id: 'newer-deep-row', kind: DispatchKind.DEEP_RESEARCH },
        { id: 'seed-active', kind: DispatchKind.SEED_IDEA },
      ],
    })).toBe(true);
  });

  it('fails closed when the active dispatch identity cannot be resolved', () => {
    expect(isDiscoveryShareLifecycleOpenForJob({
      status: JobStatus.RUNNING,
      activeDispatchId: 'missing',
      dispatches: [{ id: 'other', kind: DispatchKind.SEED_IDEA }],
    })).toBe(false);
  });
});
