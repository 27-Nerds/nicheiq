-- AlterTable
ALTER TABLE "CatalogIdea" ADD COLUMN     "researchCount" INTEGER NOT NULL DEFAULT 0;

-- CreateTable
CREATE TABLE "CatalogIdeaResearch" (
    "id" TEXT NOT NULL,
    "ideaId" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "jobId" VARCHAR(100) NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "CatalogIdeaResearch_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "CatalogIdeaResearch_userId_idx" ON "CatalogIdeaResearch"("userId");

-- CreateIndex
CREATE INDEX "CatalogIdeaResearch_jobId_idx" ON "CatalogIdeaResearch"("jobId");

-- CreateIndex
CREATE UNIQUE INDEX "CatalogIdeaResearch_ideaId_userId_key" ON "CatalogIdeaResearch"("ideaId", "userId");

-- AddForeignKey
ALTER TABLE "CatalogIdeaResearch" ADD CONSTRAINT "CatalogIdeaResearch_ideaId_fkey" FOREIGN KEY ("ideaId") REFERENCES "CatalogIdea"("id") ON DELETE CASCADE ON UPDATE CASCADE;
