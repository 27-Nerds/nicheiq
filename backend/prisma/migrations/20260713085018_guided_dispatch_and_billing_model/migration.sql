-- CreateEnum
CREATE TYPE "BillingModel" AS ENUM ('DISCOVERY_PREPAID_V1', 'GUIDED_SEGMENTS_V1');

-- CreateEnum
CREATE TYPE "DispatchKind" AS ENUM ('CONTINUE', 'APPLY_STAY', 'REGENERATE');

-- CreateEnum
CREATE TYPE "DispatchState" AS ENUM ('AUTHORIZED', 'CLAIMED', 'COMPLETED', 'FAILED', 'REFUNDED');

-- AlterTable
ALTER TABLE "Job" ADD COLUMN     "activeDispatchId" VARCHAR(36),
ADD COLUMN     "billingModel" "BillingModel" NOT NULL DEFAULT 'DISCOVERY_PREPAID_V1';

-- CreateTable
CREATE TABLE "JobDispatch" (
    "id" TEXT NOT NULL,
    "jobId" TEXT NOT NULL,
    "kind" "DispatchKind" NOT NULL,
    "gateStage" INTEGER,
    "segment" VARCHAR(50),
    "chargeId" TEXT,
    "state" "DispatchState" NOT NULL DEFAULT 'AUTHORIZED',
    "workerId" VARCHAR(100),
    "failureKind" VARCHAR(30),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "claimedAt" TIMESTAMP(3),
    "settledAt" TIMESTAMP(3),

    CONSTRAINT "JobDispatch_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "JobDispatch_jobId_state_idx" ON "JobDispatch"("jobId", "state");

-- CreateIndex
CREATE INDEX "JobDispatch_state_createdAt_idx" ON "JobDispatch"("state", "createdAt");

-- AddForeignKey
ALTER TABLE "JobDispatch" ADD CONSTRAINT "JobDispatch_jobId_fkey" FOREIGN KEY ("jobId") REFERENCES "Job"("id") ON DELETE CASCADE ON UPDATE CASCADE;
