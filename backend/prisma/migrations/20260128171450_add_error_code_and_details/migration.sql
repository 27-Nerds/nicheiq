-- AlterTable
ALTER TABLE "Job" ADD COLUMN     "errorCode" VARCHAR(50),
ADD COLUMN     "errorDetails" JSONB;
