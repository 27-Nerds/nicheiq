import { prisma } from './db.js';
import { JobStatus, StageStatus, AssetType, Prisma } from '@prisma/client';
import { PIPELINE_STAGES, TOTAL_STAGES } from '../types/job.js';
import { refundCreditsForJob } from './creditService.js';

/**
 * Create a new research job
 */
export async function createJob(
  niche: string,
  allowedProjectTypes?: string[],
  userId?: string
) {
  // Create job with initial progress entries for all stages
  const job = await prisma.job.create({
    data: {
      niche,
      userId, // Associate with user if provided
      allowedProjectTypes: allowedProjectTypes as Prisma.InputJsonValue,
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
  errorMessage?: string
) {
  const now = new Date();

  // Get current stage status to avoid overwriting historical data on resume
  const currentStage = await prisma.jobProgress.findUnique({
    where: { jobId_stageNumber: { jobId, stageNumber } },
    select: { status: true, startedAt: true, completedAt: true, durationSeconds: true },
  });

  // Skip update if stage is already completed (preserve historical timestamps during resume)
  if (currentStage?.status === StageStatus.COMPLETED && status === StageStatus.COMPLETED) {
    // Stage already completed - don't overwrite timestamps
    const existingProgress = await prisma.jobProgress.findUnique({
      where: { jobId_stageNumber: { jobId, stageNumber } },
    });
    return existingProgress;
  }

  // Only set timestamps for new transitions (not already set)
  const progress = await prisma.jobProgress.update({
    where: {
      jobId_stageNumber: {
        jobId,
        stageNumber,
      },
    },
    data: {
      status,
      startedAt: status === StageStatus.RUNNING && !currentStage?.startedAt ? now : undefined,
      completedAt: (status === StageStatus.COMPLETED || status === StageStatus.FAILED) && !currentStage?.completedAt ? now : undefined,
      errorMessage,
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
  const completedStages = await prisma.jobProgress.count({
    where: {
      jobId,
      status: StageStatus.COMPLETED,
    },
  });

  const stageName = PIPELINE_STAGES.find(s => s.number === stageNumber)?.name;

  await prisma.job.update({
    where: { id: jobId },
    data: {
      currentStage: stageNumber,
      currentStageName: stageName,
      stagesCompleted: completedStages,
      progressPercent: (completedStages / TOTAL_STAGES) * 100,
      status: status === StageStatus.RUNNING ? JobStatus.RUNNING : undefined,
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
 */
export async function failJob(jobId: string, errorMessage: string, errorStage?: number) {
  // Check if job is already FAILED (idempotency)
  const existingJob = await prisma.job.findUnique({
    where: { id: jobId },
    select: { status: true },
  });

  if (!existingJob) {
    console.log(`[JobService] Job ${jobId} not found`);
    return null;
  }

  if (existingJob.status === JobStatus.FAILED) {
    console.log(`[JobService] Job ${jobId} is already FAILED, skipping duplicate failJob() call`);
    return prisma.job.findUnique({ where: { id: jobId } });
  }

  // Update job status to FAILED
  const job = await prisma.job.update({
    where: { id: jobId },
    data: {
      status: JobStatus.FAILED,
      errorMessage,
      errorStage,
    },
  });

  // Auto-refund the credit for failed jobs
  try {
    const refund = await refundCreditsForJob(jobId, 1);
    if (refund) {
      console.log(`[JobService] Auto-refunded 1 credit for failed job ${jobId}`);
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

