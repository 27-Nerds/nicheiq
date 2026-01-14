import { prisma } from './db.js';
import { JobStatus, StageStatus, AssetType, Prisma } from '@prisma/client';
import { PIPELINE_STAGES, TOTAL_STAGES } from '../types/job.js';

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

  // Update the specific stage
  const progress = await prisma.jobProgress.update({
    where: {
      jobId_stageNumber: {
        jobId,
        stageNumber,
      },
    },
    data: {
      status,
      startedAt: status === StageStatus.RUNNING ? now : undefined,
      completedAt: status === StageStatus.COMPLETED || status === StageStatus.FAILED ? now : undefined,
      errorMessage,
    },
  });

  // Calculate duration if completed
  if (progress.startedAt && progress.completedAt) {
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
 */
export async function completeJob(
  jobId: string,
  reportPath: string,
  landingPath?: string
) {
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
 */
export async function failJob(jobId: string, errorMessage: string, errorStage?: number) {
  return prisma.job.update({
    where: { id: jobId },
    data: {
      status: JobStatus.FAILED,
      errorMessage,
      errorStage,
    },
  });
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
