-- AlterTable
ALTER TABLE "CatalogIdea" ADD COLUMN     "isFreePreview" BOOLEAN NOT NULL DEFAULT false;

-- AlterTable
ALTER TABLE "CatalogPainPoint" ADD COLUMN     "isFreePreview" BOOLEAN NOT NULL DEFAULT false;


-- One free-preview item per sub-niche, enforced at the DB level (non-deferrable partial unique index;
-- updateCatalogIdea/PainPoint must demote-first-then-set to satisfy it).
CREATE UNIQUE INDEX "CatalogIdea_one_free_preview_per_category" ON "CatalogIdea" ("categoryId") WHERE "isFreePreview";
CREATE UNIQUE INDEX "CatalogPainPoint_one_free_preview_per_category" ON "CatalogPainPoint" ("categoryId") WHERE "isFreePreview";
