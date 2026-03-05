-- Clean slate: delete existing published records (they can be re-published)
DELETE FROM "CatalogIdea";
DELETE FROM "CatalogPainPoint";

-- Reset cache published status
UPDATE "CatalogItemCache" SET "isPublished" = false, "categoryId" = NULL;

-- AlterTable
ALTER TABLE "CatalogIdea" ADD COLUMN "sourceItemIndex" INTEGER NOT NULL;

-- AlterTable
ALTER TABLE "CatalogPainPoint" ADD COLUMN "sourceItemIndex" INTEGER NOT NULL;
