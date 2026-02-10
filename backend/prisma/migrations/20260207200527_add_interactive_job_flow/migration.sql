-- AlterEnum
-- This migration adds more than one value to an enum.
-- With PostgreSQL versions 11 and earlier, this is not possible
-- in a single migration. This can be worked around by creating
-- multiple migrations, each migration adding only one value to
-- the enum.


ALTER TYPE "JobStatus" ADD VALUE 'VALIDATING_IDEAS';
ALTER TYPE "JobStatus" ADD VALUE 'AWAITING_SELECTION';
ALTER TYPE "JobStatus" ADD VALUE 'REGENERATING';
ALTER TYPE "JobStatus" ADD VALUE 'RUNNING_PHASE2';

-- AlterTable
ALTER TABLE "Job" ADD COLUMN     "awaitingSelectionAt" TIMESTAMP(3),
ADD COLUMN     "ideasRegeneratedAt" TIMESTAMP(3),
ADD COLUMN     "ideasShownAt" TIMESTAMP(3),
ADD COLUMN     "jobMode" VARCHAR(20),
ADD COLUMN     "lastReminderSentAt" TIMESTAMP(3),
ADD COLUMN     "phase1CheckpointPath" VARCHAR(500),
ADD COLUMN     "selectedSolution" VARCHAR(255),
ADD COLUMN     "selectionRationale" TEXT,
ADD COLUMN     "selectionReminderCount" INTEGER NOT NULL DEFAULT 0,
ADD COLUMN     "solutionIdeas" JSONB,
ADD COLUMN     "totalToValidate" INTEGER NOT NULL DEFAULT 0,
ADD COLUMN     "validatedCount" INTEGER NOT NULL DEFAULT 0;

-- AlterTable
ALTER TABLE "NotificationPreferences" ADD COLUMN     "emailOnSolutionsReady" BOOLEAN NOT NULL DEFAULT true;
