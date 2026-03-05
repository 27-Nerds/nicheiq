-- CreateTable
CREATE TABLE "CatalogSuperGroup" (
    "id" TEXT NOT NULL,
    "name" VARCHAR(100) NOT NULL,
    "slug" VARCHAR(120) NOT NULL,
    "description" VARCHAR(500),
    "sortOrder" INTEGER NOT NULL DEFAULT 0,
    "isActive" BOOLEAN NOT NULL DEFAULT true,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "CatalogSuperGroup_pkey" PRIMARY KEY ("id")
);

-- AlterTable
ALTER TABLE "CatalogCategory" ADD COLUMN "superGroupId" TEXT;

-- CreateIndex
CREATE UNIQUE INDEX "CatalogSuperGroup_slug_key" ON "CatalogSuperGroup"("slug");

-- CreateIndex
CREATE INDEX "CatalogSuperGroup_isActive_sortOrder_idx" ON "CatalogSuperGroup"("isActive", "sortOrder");

-- CreateIndex
CREATE INDEX "CatalogCategory_superGroupId_idx" ON "CatalogCategory"("superGroupId");

-- AddForeignKey
ALTER TABLE "CatalogCategory" ADD CONSTRAINT "CatalogCategory_superGroupId_fkey" FOREIGN KEY ("superGroupId") REFERENCES "CatalogSuperGroup"("id") ON DELETE SET NULL ON UPDATE CASCADE;
