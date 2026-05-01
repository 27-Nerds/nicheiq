-- AlterTable
ALTER TABLE "CatalogResearchContext" ADD COLUMN     "categorizationSummary" TEXT,
ADD COLUMN     "nicheContext" JSONB,
ADD COLUMN     "painAnalysisSummary" TEXT,
ADD COLUMN     "qualitySignals" JSONB,
ADD COLUMN     "topPainCategories" JSONB;
