-- AlterTable
ALTER TABLE "CatalogPainPoint" ADD COLUMN     "themeId" VARCHAR(160);

-- CreateIndex
CREATE INDEX "CatalogPainPoint_themeId_idx" ON "CatalogPainPoint"("themeId");
