-- AlterTable
ALTER TABLE "CatalogCategory" ADD COLUMN     "faqJsonMeta" JSONB;

-- AlterTable
ALTER TABLE "CatalogIdea" ADD COLUMN     "faqJson" JSONB,
ADD COLUMN     "faqJsonMeta" JSONB;

-- AlterTable
ALTER TABLE "CatalogPainPoint" ADD COLUMN     "faqJson" JSONB,
ADD COLUMN     "faqJsonMeta" JSONB;
