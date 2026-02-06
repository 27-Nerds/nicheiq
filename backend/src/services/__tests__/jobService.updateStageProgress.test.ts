import { describe, it, expect, vi, beforeEach } from 'vitest';

// ============================================
// Mock dependencies
// ============================================
const mockJobProgressFindUnique = vi.fn();
const mockJobProgressUpdate = vi.fn();
const mockJobProgressCount = vi.fn();
const mockJobUpdate = vi.fn();
const mockJobFindUnique = vi.fn();

vi.mock('../db.js', () => ({
  prisma: {
    jobProgress: {
      findUnique: (...args: any[]) => mockJobProgressFindUnique(...args),
      update: (...args: any[]) => mockJobProgressUpdate(...args),
      count: (...args: any[]) => mockJobProgressCount(...args),
    },
    job: {
      update: (...args: any[]) => mockJobUpdate(...args),
      findUnique: (...args: any[]) => mockJobFindUnique(...args),
    },
  },
}));

vi.mock('./creditService.js', () => ({
  refundCreditsForJob: vi.fn(),
}));

import { updateStageProgress } from '../jobService.js';

// ============================================
// Setup
// ============================================
const JOB_ID = 'job-123';
const STAGE_NUMBER = 5; // 'Search & Discovery' — must match a PIPELINE_STAGES entry

beforeEach(() => {
  vi.clearAllMocks();

  // Default: stage not yet started
  mockJobProgressFindUnique.mockResolvedValue(null);

  // Default: stage progress update returns a progress record
  mockJobProgressUpdate.mockResolvedValue({
    id: 'progress-1',
    jobId: JOB_ID,
    stageNumber: STAGE_NUMBER,
    status: 'RUNNING',
    startedAt: new Date(),
    completedAt: null,
    durationSeconds: null,
  });

  // Default: 2 stages completed
  mockJobProgressCount.mockResolvedValue(2);

  // Default: job has 16 total stages
  mockJobFindUnique.mockResolvedValue({ totalStages: 16 });

  // Default: job update succeeds
  mockJobUpdate.mockResolvedValue({});
});

// ============================================
// Tests
// ============================================
describe('updateStageProgress', () => {
  it('should NOT set job status when stage transitions to RUNNING', async () => {
    await updateStageProgress(JOB_ID, STAGE_NUMBER, 'RUNNING' as any);

    expect(mockJobUpdate).toHaveBeenCalledOnce();
    const updateData = mockJobUpdate.mock.calls[0][0].data;
    expect(updateData).not.toHaveProperty('status');
  });

  it('should NOT set job status when stage transitions to COMPLETED', async () => {
    mockJobProgressFindUnique.mockResolvedValue({
      status: 'RUNNING',
      startedAt: new Date(),
      completedAt: null,
      durationSeconds: null,
    });
    mockJobProgressUpdate.mockResolvedValue({
      id: 'progress-1',
      jobId: JOB_ID,
      stageNumber: STAGE_NUMBER,
      status: 'COMPLETED',
      startedAt: new Date(Date.now() - 5000),
      completedAt: new Date(),
      durationSeconds: null,
    });

    await updateStageProgress(JOB_ID, STAGE_NUMBER, 'COMPLETED' as any);

    expect(mockJobUpdate).toHaveBeenCalledOnce();
    const updateData = mockJobUpdate.mock.calls[0][0].data;
    expect(updateData).not.toHaveProperty('status');
  });

  it('should NOT set job status when stage transitions to FAILED', async () => {
    mockJobProgressFindUnique.mockResolvedValue({
      status: 'RUNNING',
      startedAt: new Date(),
      completedAt: null,
      durationSeconds: null,
    });
    mockJobProgressUpdate.mockResolvedValue({
      id: 'progress-1',
      jobId: JOB_ID,
      stageNumber: STAGE_NUMBER,
      status: 'FAILED',
      startedAt: new Date(Date.now() - 5000),
      completedAt: new Date(),
      durationSeconds: null,
    });

    await updateStageProgress(JOB_ID, STAGE_NUMBER, 'FAILED' as any, 'Something went wrong');

    expect(mockJobUpdate).toHaveBeenCalledOnce();
    const updateData = mockJobUpdate.mock.calls[0][0].data;
    expect(updateData).not.toHaveProperty('status');
  });

  it('should update currentStage, currentStageName, stagesCompleted, and progressPercent', async () => {
    await updateStageProgress(JOB_ID, STAGE_NUMBER, 'RUNNING' as any);

    expect(mockJobUpdate).toHaveBeenCalledOnce();
    const call = mockJobUpdate.mock.calls[0][0];
    expect(call.where).toEqual({ id: JOB_ID });
    expect(call.data).toEqual({
      currentStage: STAGE_NUMBER,
      currentStageName: expect.any(String),
      stagesCompleted: 2,
      progressPercent: (2 / 16) * 100,
    });
  });
});
