-- AlterTable
ALTER TABLE "ReportShare" ADD COLUMN     "allowIndexing" BOOLEAN NOT NULL DEFAULT false;

-- AlterTable
ALTER TABLE "DiscoveryShare" ADD COLUMN     "allowIndexing" BOOLEAN NOT NULL DEFAULT false;
