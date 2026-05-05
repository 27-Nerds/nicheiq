-- Phase 1 of detail-page IA rework: add denormalized array column +
-- GIN index on CatalogIdea so we can do `WHERE addressedPainTitles && ARRAY[...]`
-- lookups for the new pain → ideas cross-link.
--
-- Production-safety notes:
-- - `ADD COLUMN ... DEFAULT ARRAY[]::TEXT[]` is metadata-only on PG ≥ 11
--   (no row rewrite). The default keeps writes that don't set the column safe.
-- - `CREATE INDEX` (not CONCURRENTLY) is acceptable here because the column is
--   brand new — every row has the empty-array default, so the GIN build is
--   effectively instant with no contention. CONCURRENTLY would be required
--   only when indexing an already-populated column.

-- AlterTable
ALTER TABLE "CatalogIdea" ADD COLUMN     "addressedPainTitles" TEXT[] DEFAULT ARRAY[]::TEXT[];

-- CreateIndex
CREATE INDEX "CatalogIdea_addressedPainTitles_idx" ON "CatalogIdea" USING GIN ("addressedPainTitles");
