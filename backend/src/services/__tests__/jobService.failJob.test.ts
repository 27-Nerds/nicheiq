import { describe, it, expect, vi, beforeEach } from 'vitest';

// ============================================
// Mock dependencies
// ============================================
const mockJobFindUnique = vi.fn();
const mockJobUpdate = vi.fn();
const mockJobUpdateMany = vi.fn(async (_a?: any) => ({ count: 1 }) as any);

vi.mock('../db.js', () => ({
  prisma: {
    job: {
      findUnique: (...args: any[]) => mockJobFindUnique(...args),
      update: (...args: any[]) => mockJobUpdate(...args),
      // failJob's terminal write is now a CAS over the valid pre-fail statuses, not an
      // unconditional update() by id — otherwise a cancel landing between the status read and the
      // write got silently overwritten AND double-refunded.
      updateMany: (...args: any[]) => mockJobUpdateMany(...args),
    },
    jobProgress: { updateMany: async () => ({ count: 0 }) },
    jobDispatch: { updateMany: async () => ({ count: 0 }) },
  },
}));

vi.mock('../creditService.js', () => ({
  refundForStage: vi.fn().mockResolvedValue(null),
  refundForRegenerationStage: vi.fn().mockResolvedValue(null),
  determineFailedStage: vi.fn().mockReturnValue('discovery'),
}));

import { failJob } from '../jobService.js';

// Phase B (Codex 16-19 status-consumer sweep): AWAITING_GATE must be a valid pre-fail
// state — notify_job_failed is queue_consumer's LAST RESORT when even notify_gate_failed's
// compensating revert fails, and a job stuck AWAITING_GATE must still be failable.
describe('failJob — AWAITING_GATE is a valid pre-fail state', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('transitions AWAITING_GATE -> FAILED', async () => {
    mockJobFindUnique.mockResolvedValue({ status: 'AWAITING_GATE', regenerationCount: 0 });
    mockJobUpdate.mockResolvedValue({ id: 'job-1', status: 'FAILED' });

    const result = await failJob('job-1', 'worker crashed mid gate-continuation');

    expect(result).not.toBeNull();
    // The write is now a CAS: it may only fail a job that is still in a valid pre-fail state, so
    // a cancel that landed first wins and this matches nothing.
    expect(mockJobUpdateMany).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({
          id: 'job-1',
          status: { in: expect.arrayContaining(['AWAITING_GATE']) },
        }),
        data: expect.objectContaining({ status: 'FAILED' }),
      })
    );
  });

  it('rejects a job in a genuinely terminal state (COMPLETED)', async () => {
    mockJobFindUnique.mockResolvedValue({ status: 'COMPLETED', regenerationCount: 0 });

    const result = await failJob('job-1', 'should not apply');

    expect(result).toBeNull();
    expect(mockJobUpdate).not.toHaveBeenCalled();
  });
});
