-- AlterEnum
ALTER TYPE "JobStatus" ADD VALUE 'AWAITING_GATE';

-- AlterTable
ALTER TABLE "Job" ADD COLUMN     "gateArtifact" JSONB,
ADD COLUMN     "gateReachedAt" TIMESTAMP(3),
ADD COLUMN     "gateStage" INTEGER;
