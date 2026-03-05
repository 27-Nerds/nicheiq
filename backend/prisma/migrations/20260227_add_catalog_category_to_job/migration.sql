-- AlterTable
ALTER TABLE "Job" ADD COLUMN "catalogCategoryId" TEXT;

-- CreateIndex
CREATE INDEX "Job_catalogCategoryId_idx" ON "Job"("catalogCategoryId");

-- Partial unique index: prevents duplicate active catalog jobs per category+mode
-- NOTE: Managed manually — Prisma does not support partial unique indexes.
-- Do not remove via prisma migrate; it won't conflict with schema.prisma.
CREATE UNIQUE INDEX "Job_catalog_active_unique"
  ON "Job" ("catalogCategoryId", "jobMode")
  WHERE "status" IN ('PENDING', 'QUEUED', 'RUNNING', 'AWAITING_SELECTION', 'REGENERATING', 'RUNNING_PHASE2');

-- AddForeignKey
ALTER TABLE "Job" ADD CONSTRAINT "Job_catalogCategoryId_fkey"
  FOREIGN KEY ("catalogCategoryId") REFERENCES "CatalogCategory"("id")
  ON DELETE SET NULL ON UPDATE CASCADE;
