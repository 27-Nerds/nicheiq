-- AlterTable: Remove enrichment tracking fields, add multi-select support
ALTER TABLE "Job" DROP COLUMN "totalToValidate",
DROP COLUMN "validatedCount",
ADD COLUMN "selectedSolutions" TEXT[] NOT NULL DEFAULT '{}';
