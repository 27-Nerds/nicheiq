-- CreateEnum
CREATE TYPE "JobStatus" AS ENUM ('PENDING', 'QUEUED', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED');

-- CreateEnum
CREATE TYPE "StageStatus" AS ENUM ('PENDING', 'RUNNING', 'COMPLETED', 'SKIPPED', 'FAILED');

-- CreateEnum
CREATE TYPE "AssetType" AS ENUM ('REPORT_JSON', 'REPORT_RAW', 'LANDING_PAGE');

-- CreateTable
CREATE TABLE "Job" (
    "id" TEXT NOT NULL,
    "email" VARCHAR(255) NOT NULL,
    "niche" TEXT NOT NULL,
    "allowedProjectTypes" JSONB,
    "status" "JobStatus" NOT NULL DEFAULT 'PENDING',
    "currentStage" DOUBLE PRECISION NOT NULL DEFAULT 1,
    "currentStageName" VARCHAR(100),
    "stagesCompleted" INTEGER NOT NULL DEFAULT 0,
    "totalStages" INTEGER NOT NULL DEFAULT 14,
    "progressPercent" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "errorMessage" TEXT,
    "errorStage" DOUBLE PRECISION,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    "startedAt" TIMESTAMP(3),
    "completedAt" TIMESTAMP(3),

    CONSTRAINT "Job_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "JobProgress" (
    "id" SERIAL NOT NULL,
    "jobId" TEXT NOT NULL,
    "stageNumber" DOUBLE PRECISION NOT NULL,
    "stageName" VARCHAR(100) NOT NULL,
    "status" "StageStatus" NOT NULL DEFAULT 'PENDING',
    "startedAt" TIMESTAMP(3),
    "completedAt" TIMESTAMP(3),
    "durationSeconds" DOUBLE PRECISION,
    "details" JSONB,
    "errorMessage" TEXT,

    CONSTRAINT "JobProgress_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "JobAsset" (
    "id" SERIAL NOT NULL,
    "jobId" TEXT NOT NULL,
    "assetType" "AssetType" NOT NULL,
    "filePath" VARCHAR(500) NOT NULL,
    "fileSizeBytes" INTEGER,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "JobAsset_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "Job_email_idx" ON "Job"("email");

-- CreateIndex
CREATE INDEX "Job_status_idx" ON "Job"("status");

-- CreateIndex
CREATE INDEX "Job_createdAt_idx" ON "Job"("createdAt");

-- CreateIndex
CREATE INDEX "JobProgress_jobId_idx" ON "JobProgress"("jobId");

-- CreateIndex
CREATE UNIQUE INDEX "JobProgress_jobId_stageNumber_key" ON "JobProgress"("jobId", "stageNumber");

-- CreateIndex
CREATE INDEX "JobAsset_jobId_idx" ON "JobAsset"("jobId");

-- CreateIndex
CREATE UNIQUE INDEX "JobAsset_jobId_assetType_key" ON "JobAsset"("jobId", "assetType");

-- AddForeignKey
ALTER TABLE "JobProgress" ADD CONSTRAINT "JobProgress_jobId_fkey" FOREIGN KEY ("jobId") REFERENCES "Job"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "JobAsset" ADD CONSTRAINT "JobAsset_jobId_fkey" FOREIGN KEY ("jobId") REFERENCES "Job"("id") ON DELETE CASCADE ON UPDATE CASCADE;
