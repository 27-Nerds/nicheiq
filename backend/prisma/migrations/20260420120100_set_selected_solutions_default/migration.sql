-- AlterTable: set an empty-array default on Job.selectedSolutions so new rows
-- don't require explicit initialisation. Matches current schema.prisma.
ALTER TABLE "Job" ALTER COLUMN "selectedSolutions" SET DEFAULT ARRAY[]::TEXT[];
