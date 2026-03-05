-- AlterTable
ALTER TABLE "Job" ADD COLUMN "regenerationCount" INTEGER NOT NULL DEFAULT 0;

-- Backfill: existing jobs that already regenerated should start with count=1
UPDATE "Job" SET "regenerationCount" = 1 WHERE "ideasRegeneratedAt" IS NOT NULL;
