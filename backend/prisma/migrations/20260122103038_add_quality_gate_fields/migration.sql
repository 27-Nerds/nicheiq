-- AlterTable
ALTER TABLE "Job" ADD COLUMN     "stopReason" VARCHAR(50),
ADD COLUMN     "stopReasonDetails" JSONB;
