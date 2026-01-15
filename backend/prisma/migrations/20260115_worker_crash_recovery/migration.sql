-- Worker crash recovery migration
-- Adds heartbeat tracking and retry count fields

-- Add new columns to Job table for crash recovery
ALTER TABLE "Job" ADD COLUMN "workerId" VARCHAR(100);
ALTER TABLE "Job" ADD COLUMN "lastHeartbeat" TIMESTAMP(3);
ALTER TABLE "Job" ADD COLUMN "retryCount" INTEGER NOT NULL DEFAULT 0;

-- Create indexes for efficient queries
CREATE INDEX "Job_workerId_idx" ON "Job"("workerId");
CREATE INDEX "Job_lastHeartbeat_idx" ON "Job"("lastHeartbeat");

-- Create WorkerHeartbeat table to track worker status
CREATE TABLE "WorkerHeartbeat" (
    "id" TEXT NOT NULL,
    "workerId" VARCHAR(100) NOT NULL,
    "currentJobId" TEXT,
    "status" VARCHAR(20) NOT NULL DEFAULT 'active',
    "lastHeartbeat" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "startedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "hostname" VARCHAR(255),
    "processId" INTEGER,

    CONSTRAINT "WorkerHeartbeat_pkey" PRIMARY KEY ("id")
);

-- Create unique constraint on workerId
CREATE UNIQUE INDEX "WorkerHeartbeat_workerId_key" ON "WorkerHeartbeat"("workerId");

-- Create indexes for efficient queries
CREATE INDEX "WorkerHeartbeat_lastHeartbeat_idx" ON "WorkerHeartbeat"("lastHeartbeat");
CREATE INDEX "WorkerHeartbeat_currentJobId_idx" ON "WorkerHeartbeat"("currentJobId");
CREATE INDEX "WorkerHeartbeat_status_idx" ON "WorkerHeartbeat"("status");
