-- AlterTable
ALTER TABLE "CatalogIdea" ADD COLUMN     "conventionalApproach" TEXT,
ADD COLUMN     "estimatedCacPaid" TEXT,
ADD COLUMN     "innovationAngle" TEXT,
ADD COLUMN     "organicDiscoveryQueries" TEXT[] DEFAULT ARRAY[]::TEXT[],
ADD COLUMN     "whyItWorks" TEXT;
