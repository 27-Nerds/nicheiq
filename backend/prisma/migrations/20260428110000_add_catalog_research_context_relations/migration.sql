-- Phase 5 Migration B: REQUIRED FK relations on CatalogIdea / CatalogPainPoint.
--
-- Prerequisites:
-- 1. Migration A (20260428100000_add_catalog_research_context_table) applied.
-- 2. backend/scripts/backfillResearchContexts.ts ran successfully — every
--    distinct sourceJobId across CatalogIdea ∪ CatalogPainPoint has a row
--    in CatalogResearchContext (placeholder row when the report.json is
--    missing on disk).
--
-- This migration adds the FK constraints. It will FAIL on any environment
-- where the backfill hasn't completed.

ALTER TABLE "CatalogIdea"
    ADD CONSTRAINT "CatalogIdea_sourceJobId_fkey"
    FOREIGN KEY ("sourceJobId") REFERENCES "CatalogResearchContext"("sourceJobId")
    ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE "CatalogPainPoint"
    ADD CONSTRAINT "CatalogPainPoint_sourceJobId_fkey"
    FOREIGN KEY ("sourceJobId") REFERENCES "CatalogResearchContext"("sourceJobId")
    ON DELETE RESTRICT ON UPDATE CASCADE;
