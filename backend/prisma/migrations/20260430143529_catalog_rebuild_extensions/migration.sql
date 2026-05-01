-- Catalog rebuild extensions (Phase 5.4).
--
-- 1. Adds two nullable JSONB columns to CatalogResearchContext for the new
--    public catalog UI: keyword clusters (sourced from
--    FinalReport.keyword_clusters) and theme severity scores (0-100 ints,
--    sourced from ContentCategorizationReport.theme_categories).
--
-- 2. Creates the CatalogCollection + CatalogCollectionItem tables for the
--    featured-collections feature, manually curated via admin UI and rendered
--    on the public /ideas index page.
--
-- 3. Enforces XOR(ideaId, painPointId) on CatalogCollectionItem at the DB
--    level via CHECK constraint — exactly one target per join row, mirrored
--    by service-level validation in catalogCollectionService.ts.
--
-- Production-safety notes:
--   * ALTER TABLE ... ADD COLUMN with no default and nullable is a metadata-
--     only operation in PostgreSQL (no table rewrite, no full-table lock).
--   * New tables are additive — no impact on existing reads/writes.
--   * Cascade deletes on CatalogCollectionItem only fire on the NEW relations.
--     Existing CatalogIdea/CatalogPainPoint deletion paths still go through
--     `Restrict` on category and the (intentional) absence of cascade on
--     researchContext per existing schema convention.

-- AlterTable
ALTER TABLE "CatalogResearchContext" ADD COLUMN     "keywordClusters" JSONB,
ADD COLUMN     "themeSeverityScores" JSONB;

-- CreateTable
CREATE TABLE "CatalogCollection" (
    "id" TEXT NOT NULL,
    "slug" VARCHAR(120) NOT NULL,
    "name" VARCHAR(120) NOT NULL,
    "description" TEXT,
    "tagline" VARCHAR(160),
    "colorAccent" VARCHAR(20),
    "sortOrder" INTEGER NOT NULL DEFAULT 0,
    "isActive" BOOLEAN NOT NULL DEFAULT true,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "CatalogCollection_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "CatalogCollectionItem" (
    "id" TEXT NOT NULL,
    "collectionId" TEXT NOT NULL,
    "ideaId" TEXT,
    "painPointId" TEXT,
    "position" INTEGER NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "CatalogCollectionItem_pkey" PRIMARY KEY ("id"),
    -- Exactly-one-of XOR: ideaId and painPointId cannot both be NULL or both
    -- be set. This is the authoritative enforcement; service-level validation
    -- exists for clearer error messages but the DB is the safety net.
    CONSTRAINT "CatalogCollectionItem_target_xor"
      CHECK (("ideaId" IS NOT NULL AND "painPointId" IS NULL)
          OR ("ideaId" IS NULL AND "painPointId" IS NOT NULL))
);

-- CreateIndex
CREATE UNIQUE INDEX "CatalogCollection_slug_key" ON "CatalogCollection"("slug");

-- CreateIndex
CREATE INDEX "CatalogCollection_isActive_sortOrder_idx" ON "CatalogCollection"("isActive", "sortOrder");

-- CreateIndex
CREATE INDEX "CatalogCollectionItem_collectionId_idx" ON "CatalogCollectionItem"("collectionId");

-- CreateIndex
CREATE INDEX "CatalogCollectionItem_ideaId_idx" ON "CatalogCollectionItem"("ideaId");

-- CreateIndex
CREATE INDEX "CatalogCollectionItem_painPointId_idx" ON "CatalogCollectionItem"("painPointId");

-- CreateIndex
-- Postgres treats NULLs as distinct in unique indexes, so this only fires
-- when ideaId is non-null (which by the XOR check means painPointId is null).
CREATE UNIQUE INDEX "CatalogCollectionItem_collectionId_ideaId_key" ON "CatalogCollectionItem"("collectionId", "ideaId");

-- CreateIndex
CREATE UNIQUE INDEX "CatalogCollectionItem_collectionId_painPointId_key" ON "CatalogCollectionItem"("collectionId", "painPointId");

-- CreateIndex
CREATE UNIQUE INDEX "CatalogCollectionItem_collectionId_position_key" ON "CatalogCollectionItem"("collectionId", "position");

-- AddForeignKey
ALTER TABLE "CatalogCollectionItem" ADD CONSTRAINT "CatalogCollectionItem_collectionId_fkey" FOREIGN KEY ("collectionId") REFERENCES "CatalogCollection"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "CatalogCollectionItem" ADD CONSTRAINT "CatalogCollectionItem_ideaId_fkey" FOREIGN KEY ("ideaId") REFERENCES "CatalogIdea"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "CatalogCollectionItem" ADD CONSTRAINT "CatalogCollectionItem_painPointId_fkey" FOREIGN KEY ("painPointId") REFERENCES "CatalogPainPoint"("id") ON DELETE CASCADE ON UPDATE CASCADE;
