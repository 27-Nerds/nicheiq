-- Remove the dead VALIDATING_IDEAS status from JobStatus enum.
-- Safety: No jobs should be in this status (verified pre-migration).
-- If any exist, they must be updated to AWAITING_SELECTION first:
--   UPDATE "Job" SET status = 'AWAITING_SELECTION' WHERE status = 'VALIDATING_IDEAS';

-- PostgreSQL does not support DROP VALUE from enums directly.
-- We must recreate the enum type and swap the column.

-- 1. Drop indexes that reference the enum type (they block the ALTER)
DROP INDEX IF EXISTS "Job_status_idx";
DROP INDEX IF EXISTS "job_status_awaiting_selection_idx";

-- 2. Create the new enum without VALIDATING_IDEAS
CREATE TYPE "JobStatus_new" AS ENUM (
  'PENDING',
  'QUEUED',
  'RUNNING',
  'AWAITING_SELECTION',
  'REGENERATING',
  'RUNNING_PHASE2',
  'COMPLETED',
  'FAILED',
  'CANCELLED'
);

-- 3. Swap the column to use the new enum (cast via text to avoid operator errors)
ALTER TABLE "Job"
  ALTER COLUMN "status" DROP DEFAULT,
  ALTER COLUMN "status" TYPE "JobStatus_new" USING ("status"::text::"JobStatus_new"),
  ALTER COLUMN "status" SET DEFAULT 'PENDING';

-- 4. Drop the old enum and rename the new one
DROP TYPE "JobStatus";
ALTER TYPE "JobStatus_new" RENAME TO "JobStatus";

-- 5. Recreate indexes
CREATE INDEX "Job_status_idx" ON "Job" ("status");
CREATE INDEX "job_status_awaiting_selection_idx" ON "Job" ("status")
  WHERE ("status" = 'AWAITING_SELECTION'::"JobStatus");
