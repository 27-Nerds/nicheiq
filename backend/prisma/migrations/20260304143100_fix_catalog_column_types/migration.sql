-- Fix column type drift: schema says TEXT but original migration created VARCHAR

-- CatalogIdea: widen VARCHAR columns to TEXT
ALTER TABLE "CatalogIdea" ALTER COLUMN "solutionName" SET DATA TYPE TEXT;
ALTER TABLE "CatalogIdea" ALTER COLUMN "projectType" SET DATA TYPE TEXT;
ALTER TABLE "CatalogIdea" ALTER COLUMN "estimatedDevTime" SET DATA TYPE TEXT;
ALTER TABLE "CatalogIdea" ALTER COLUMN "estimatedCacOrganic" SET DATA TYPE TEXT;

-- CatalogPainPoint: widen VARCHAR columns to TEXT
ALTER TABLE "CatalogPainPoint" ALTER COLUMN "title" SET DATA TYPE TEXT;
ALTER TABLE "CatalogPainPoint" ALTER COLUMN "opportunityLevel" SET DATA TYPE TEXT;

-- CreditTransaction: rename index to match Prisma's expected name
ALTER INDEX IF EXISTS "CreditTransaction_relatedJobId_type_stage_key" RENAME TO "unique_job_stage_transaction";

-- Job: drop default on selectedSolutions (schema no longer specifies one)
ALTER TABLE "Job" ALTER COLUMN "selectedSolutions" DROP DEFAULT;
